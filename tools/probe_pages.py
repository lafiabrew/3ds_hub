#!/usr/bin/env python3
"""Probe a built or deployed 3DS hub catalogue end to end.

Usage (runbook contract):

    python3 tools/probe_pages.py --directory _site --base-path /3ds_hub/ --minimum-installs 16
    python3 tools/probe_pages.py --url https://lafiabrew.github.io/3ds_hub/ --minimum-installs 16

``--directory`` serves the directory from a real stdlib HTTP server on an ephemeral
127.0.0.1 port, *only* under ``--base-path`` (everything else is 404), then fetches
it exactly as a browser would. ``--url`` fetches a live deployment instead.

For every installable card the probe:

1. reads ``catalog.json`` and the card's real ``<a class="install" href>`` in
   ``index.html``;
2. downloads the card's QR SVG over HTTP, rasterizes it strictly (only white
   background and black square modules are accepted), measures the quiet zone, and
   decodes the pixels with the vendored, SHA-256-pinned Apache-2.0 jsQR decoder in
   Node -- not with the hub's own encoder;
3. requires decoded text == href == catalog ``cia_url`` == the direct versioned
   ``https://github.com/<org>/<repo>/releases/download/<tag>/<repo>.cia``;
4. unless ``--skip-binary-range`` is given, performs an HTTPS ``Range: bytes=0-63``
   GET of that URL and requires a non-HTML response whose total length equals the
   catalogue size and whose first bytes are a CIA header (header size 0x2020).

It also rejects scripts, meta refresh, inline event handlers, non-https links and
install controls on source-only cards. The loopback server is always shut down,
its thread joined and the port verified closed, even on failure.
Exit 0 = pass, 1 = probe failure, 2 = usage error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html.parser
import http.client
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECODER = ROOT / "tests" / "vendor" / "jsqr"
TIMEOUT = 10.0
MAX_BYTES = 4 * 1024 * 1024
SVG_NS = "{http://www.w3.org/2000/svg}"
BASE_PATH_RE = re.compile(r"^/(?:[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*/)*$")
CIA_URL_RE = re.compile(
    r"^https://github\.com/(?P<org>[A-Za-z0-9-]+)/(?P<repo>3ds_[A-Za-z0-9_-]+)/releases/download/"
    r"(?P<tag>v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))/(?P<file>[A-Za-z0-9_-]+\.cia)$")
RANGE_REDIRECT_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
DECODE_JS = ("const fs=require('fs');const jsQR=require(process.argv[1]);"
             "const w=Number(process.argv[2]),h=Number(process.argv[3]);"
             "const r=jsQR(new Uint8ClampedArray(fs.readFileSync(0)),w,h);"
             "process.stdout.write(JSON.stringify(r?{data:r.data,version:r.version}:null));")


class ProbeError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Independent decoder (pinned jsQR in Node)
# ---------------------------------------------------------------------------

class Decoder:
    def __init__(self, directory: Path) -> None:
        prov = json.loads((directory / "PROVENANCE.json").read_text())
        if prov.get("license") != "Apache-2.0":
            raise ProbeError("decoder provenance does not declare Apache-2.0")
        for name, meta in prov["files"].items():
            digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            if digest != meta["sha256"]:
                raise ProbeError(f"vendored decoder file {name} sha256 {digest} != pinned {meta['sha256']}")
        self.script = directory / "jsQR.js"
        self.node = shutil.which("node")
        if not self.node:
            raise ProbeError("node is required for the independent jsQR decoder")
        self.provenance = {"source": prov["source"], "commit": prov["commit"], "license": prov["license"],
                           "jsQR.js_sha256": prov["files"]["jsQR.js"]["sha256"]}

    def decode(self, rgba: bytes, width: int, height: int) -> Optional[Dict[str, Any]]:
        if len(rgba) != width * height * 4:
            raise ProbeError("raster size mismatch")
        proc = subprocess.run([self.node, "-e", DECODE_JS, str(self.script), str(width), str(height)],
                              input=rgba, capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise ProbeError(f"jsQR decoder failed: {proc.stderr.decode(errors='replace')[:300]}")
        return json.loads(proc.stdout.decode())


# ---------------------------------------------------------------------------
# Strict SVG rasterizer (pixels only; knows nothing about QR semantics)
# ---------------------------------------------------------------------------

def _int_attr(el, name: str, default: Optional[int] = None) -> int:
    value = el.attrib.get(name)
    if value is None:
        if default is None:
            raise ProbeError(f"SVG rect missing {name}")
        return default
    if not re.fullmatch(r"[0-9]{1,5}", value):
        raise ProbeError(f"SVG attribute {name}={value!r} is not a small integer")
    return int(value)


def rasterize_svg(data: bytes) -> Tuple[bytes, int, int]:
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data or len(data) > MAX_BYTES:
        raise ProbeError("SVG contains a DOCTYPE/entity or is too large")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as err:
        raise ProbeError(f"SVG does not parse: {err}") from None
    if root.tag != SVG_NS + "svg":
        raise ProbeError("QR resource is not an SVG document")
    width, height = _int_attr(root, "width"), _int_attr(root, "height")
    if width != height or not 21 <= width <= 4096:
        raise ProbeError(f"QR SVG must be square and reasonably sized, got {width}x{height}")
    if root.attrib.get("viewBox") != f"0 0 {width} {height}":
        raise ProbeError("QR SVG viewBox does not match pixel size (would be resampled, not crisp)")
    if root.attrib.get("shape-rendering") != "crispEdges":
        raise ProbeError("QR SVG lacks shape-rendering=crispEdges")
    children = list(root)
    if not children:
        raise ProbeError("QR SVG is empty")
    pixels = bytearray(b"\xff" * (width * height * 4))
    first = children[0]
    if first.tag != SVG_NS + "rect" or first.attrib.get("fill") != "#ffffff" or \
            _int_attr(first, "x", 0) or _int_attr(first, "y", 0) or \
            _int_attr(first, "width") != width or _int_attr(first, "height") != height:
        raise ProbeError("QR SVG must start with a full white background rect")
    for el in children[1:]:
        if el.tag != SVG_NS + "rect" or list(el) or (el.text or "").strip():
            raise ProbeError(f"unexpected SVG element {el.tag}")
        fill = el.attrib.get("fill")
        if fill not in ("#000000", "#ffffff") or set(el.attrib) - {"x", "y", "width", "height", "fill"}:
            raise ProbeError("QR SVG rect has non black/white fill or unexpected attributes")
        x, y, w, h = (_int_attr(el, "x"), _int_attr(el, "y"), _int_attr(el, "width"), _int_attr(el, "height"))
        if x + w > width or y + h > height or w == 0 or h == 0:
            raise ProbeError("QR SVG rect outside canvas")
        value = 0 if fill == "#000000" else 255
        for row in range(y, y + h):
            start = (row * width + x) * 4
            for col in range(w):
                i = start + col * 4
                pixels[i] = pixels[i + 1] = pixels[i + 2] = value
    return bytes(pixels), width, height


def quiet_zone_modules(rgba: bytes, width: int, height: int) -> float:
    """Measure white margin in modules, using the top-left finder's 7-module run."""
    def dark(x: int, y: int) -> bool:
        return rgba[(y * width + x) * 4] < 128
    rows = [y for y in range(height) if any(dark(x, y) for x in range(width))]
    cols = [x for x in range(width) if any(dark(x, y) for y in range(height))]
    if not rows:
        raise ProbeError("QR raster has no dark modules")
    top, left = rows[0], cols[0]
    run = 0
    while left + run < width and dark(left + run, top):
        run += 1
    module = run / 7.0
    margin = min(top, left, width - 1 - cols[-1], height - 1 - rows[-1])
    return margin / module if module else 0.0


# ---------------------------------------------------------------------------
# HTML inspection
# ---------------------------------------------------------------------------

class PageParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.problems: List[str] = []
        self.cards: Dict[str, Dict[str, Any]] = {}
        self.current: Optional[str] = None
        self.depth = 0
        self.csp = False
        self.links: List[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k, v in attrs:
            if k.startswith("on"):
                self.problems.append(f"inline event handler {k} on <{tag}>")
            if k in ("href", "src", "action", "formaction") and v is not None:
                low = v.strip().lower()
                if low.startswith(("javascript:", "data:", "vbscript:", "http:")):
                    self.problems.append(f"unsafe URL scheme in {k}={v[:60]!r}")
                self.links.append(v)
        if tag in ("script", "iframe", "object", "embed", "form", "base"):
            self.problems.append(f"forbidden <{tag}> element")
        if tag == "meta":
            equiv = (a.get("http-equiv") or "").lower()
            if equiv == "refresh":
                self.problems.append("meta refresh present")
            if equiv == "content-security-policy":
                self.csp = "default-src 'none'" in (a.get("content") or "")
        if tag == "article":
            ident = a.get("id") or ""
            if self.current is not None:
                self.problems.append("nested article")
            if ident.startswith("app-"):
                self.current = ident[4:]
                self.depth = 1
                self.cards[self.current] = {"install": [], "imgs": [], "cia_links": [],
                                            "classes": (a.get("class") or "").split()}
            return
        if self.current is not None:
            if tag not in ("img", "br", "meta", "link", "input"):
                self.depth += 1
            card = self.cards[self.current]
            href = a.get("href")
            if tag == "a" and href:
                if "install" in (a.get("class") or "").split():
                    card["install"].append(href)
                if href.lower().split("?")[0].endswith(".cia"):
                    card["cia_links"].append(href)
            if tag == "img":
                card["imgs"].append(a.get("src") or "")

    def handle_endtag(self, tag):
        if self.current is not None:
            if tag == "article" and self.depth == 1:
                self.current = None
                self.depth = 0
            elif tag not in ("img", "br", "meta", "link", "input"):
                self.depth -= 1


# ---------------------------------------------------------------------------
# Serving and fetching
# ---------------------------------------------------------------------------

def make_handler(directory: Path, base_path: str):
    root = directory.resolve()

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "hub-probe"

        def log_message(self, fmt, *args):  # keep probe output readable
            pass

        def do_GET(self):  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if not path.startswith(base_path):
                return self.send_error(404)
            rel = urllib.parse.unquote(path[len(base_path):]) or "index.html"
            if rel.endswith("/"):
                rel += "index.html"
            target = (root / rel).resolve()
            if root not in target.parents and target != root or not target.is_file() \
                    or any(p.startswith(".") for p in Path(rel).parts):
                return self.send_error(404)
            ctype = {".html": "text/html; charset=utf-8", ".json": "application/json",
                     ".svg": "image/svg+xml", ".css": "text/css"}.get(target.suffix, "application/octet-stream")
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


class LoopbackSite:
    def __init__(self, directory: Path, base_path: str) -> None:
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(directory, base_path))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.closed = False

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                self.closed = False
        except OSError:
            self.closed = not self.thread.is_alive()
        return False


def fetch(url: str, expect_types: Tuple[str, ...]) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "lafiabrew-3ds-hub-probe"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(MAX_BYTES + 1)
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if resp.status != 200:
                raise ProbeError(f"HTTP {resp.status} for {url}")
    except urllib.error.HTTPError as err:
        raise ProbeError(f"HTTP {err.code} for {url}") from None
    except (urllib.error.URLError, OSError, http.client.HTTPException) as err:
        raise ProbeError(f"fetch failed for {url}: {err}") from None
    if len(body) > MAX_BYTES:
        raise ProbeError(f"{url} is larger than {MAX_BYTES} bytes")
    if ctype not in expect_types:
        raise ProbeError(f"{url} served {ctype!r}, expected one of {expect_types}")
    return body


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def range_check(url: str, size: int) -> Dict[str, Any]:
    opener = urllib.request.build_opener(_NoRedirect())
    current = url
    hops = []
    for _ in range(5):
        parts = urllib.parse.urlsplit(current)
        if parts.scheme != "https" or parts.hostname not in RANGE_REDIRECT_HOSTS:
            raise ProbeError(f"binary request left GitHub hosts: {parts.scheme}://{parts.hostname}")
        req = urllib.request.Request(current, headers={"Range": "bytes=0-63", "User-Agent": "lafiabrew-3ds-hub-probe"})
        try:
            resp = opener.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as err:
            if err.code in (301, 302, 303, 307, 308) and err.headers.get("Location"):
                hops.append(parts.hostname)
                current = urllib.parse.urljoin(current, err.headers["Location"])
                err.close()
                continue
            raise ProbeError(f"HTTP {err.code} for binary {url}") from None
        except (urllib.error.URLError, OSError, http.client.HTTPException) as err:
            raise ProbeError(f"binary fetch failed for {url}: {err}") from None
        with resp:
            status = resp.status
            ctype = (resp.headers.get("Content-Type") or "").lower()
            crange = resp.headers.get("Content-Range") or ""
            length = resp.headers.get("Content-Length")
            prefix = resp.read(64)
        if "html" in ctype or ctype.startswith("text/"):
            raise ProbeError(f"{url} returned {ctype}, not a binary CIA")
        if status == 206:
            m = re.fullmatch(r"bytes 0-63/([0-9]+)", crange.strip())
            if not m or int(m.group(1)) != size:
                raise ProbeError(f"{url} Content-Range {crange!r} does not match catalogue size {size}")
        elif status == 200:
            if length is None or int(length) != size:
                raise ProbeError(f"{url} Content-Length {length} does not match catalogue size {size}")
        else:
            raise ProbeError(f"{url} unexpected HTTP {status}")
        if len(prefix) < 64 or prefix[:1] == b"<" or int.from_bytes(prefix[0:4], "little") != 0x2020:
            raise ProbeError(f"{url} does not start with a CIA header (header size 0x2020)")
        return {"status": status, "content_type": ctype, "content_range": crange, "redirect_hosts": hops,
                "prefix_hex": prefix.hex()}
    raise ProbeError(f"too many redirects for {url}")


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

def probe_origin(site_url: str, base_path: str, minimum: int, decoder: Decoder, check_binaries: bool) -> Dict[str, Any]:
    origin = urllib.parse.urlsplit(site_url)
    index_html = fetch(site_url, ("text/html",)).decode("utf-8")
    catalog = json.loads(fetch(urllib.parse.urljoin(site_url, "catalog.json"), ("application/json",)))
    if catalog.get("schema") != 1 or catalog.get("base_path") != base_path:
        raise ProbeError(f"catalog base_path {catalog.get('base_path')!r} != probe base path {base_path!r}")
    org = catalog.get("organization")
    parser = PageParser()
    parser.feed(index_html)
    parser.close()
    if parser.problems:
        raise ProbeError("unsafe HTML: " + "; ".join(parser.problems[:5]))
    if not parser.csp:
        raise ProbeError("Content-Security-Policy meta with default-src 'none' missing")
    for link in parser.links:
        parts = urllib.parse.urlsplit(link)
        if parts.scheme == "" and not parts.netloc:
            if not (link.startswith(base_path) or link.startswith("#")):
                raise ProbeError(f"internal link {link!r} is outside base path {base_path!r}")
        elif parts.scheme != "https" or parts.hostname != "github.com":
            raise ProbeError(f"external link {link!r} is not https://github.com")
    apps = catalog.get("apps")
    if not isinstance(apps, list) or not apps:
        raise ProbeError("catalog has no apps")
    rows = []
    for app in apps:
        repo = app["repo"]
        card = parser.cards.get(repo)
        if card is None:
            raise ProbeError(f"index.html has no card for {repo}")
        inst = app.get("install")
        if not inst:
            if card["install"] or card["cia_links"] or card["imgs"] or not app.get("reason"):
                raise ProbeError(f"source-only card {repo} exposes install controls or lacks a reason")
            continue
        url = inst["cia_url"]
        m = CIA_URL_RE.match(url)
        if not m or m.group("org") != org or m.group("repo") != repo or m.group("file") != f"{repo}.cia" \
                or m.group("tag") != app["release"]["tag"]:
            raise ProbeError(f"{repo} catalogue URL {url!r} is not the direct versioned release CIA URL")
        if card["install"] != [url]:
            raise ProbeError(f"{repo} install href {card['install']!r} != catalogue URL {url!r}")
        if card["cia_links"] != [url]:
            raise ProbeError(f"{repo} card has unexpected .cia links {card['cia_links']!r}")
        qr_srcs = [s for s in card["imgs"] if s.endswith(".svg")]
        if len(qr_srcs) != 1:
            raise ProbeError(f"{repo} card must have exactly one QR image, found {len(qr_srcs)}")
        qr_url = urllib.parse.urljoin(site_url, qr_srcs[0])
        qr_parts = urllib.parse.urlsplit(qr_url)
        if (qr_parts.scheme, qr_parts.netloc) != (origin.scheme, origin.netloc) or not qr_parts.path.startswith(base_path):
            raise ProbeError(f"{repo} QR image {qr_url} is not same-origin under {base_path}")
        svg = fetch(qr_url, ("image/svg+xml",))
        rgba, w, h = rasterize_svg(svg)
        quiet = quiet_zone_modules(rgba, w, h)
        if quiet < 4.0:
            raise ProbeError(f"{repo} QR quiet zone {quiet:.2f} modules < 4")
        decoded = decoder.decode(rgba, w, h)
        if not decoded or decoded.get("data") != url:
            raise ProbeError(f"{repo} QR decodes to {decoded and decoded.get('data')!r}, expected {url!r}")
        row = {"repo": repo, "tag": app["release"]["tag"], "cia_url": url, "href": card["install"][0],
               "decoded": decoded["data"], "qr_version": decoded.get("version"), "qr_pixels": w,
               "quiet_zone_modules": round(quiet, 2), "qr_sha256": hashlib.sha256(svg).hexdigest()}
        if check_binaries:
            row["range"] = range_check(url, inst["size"])
        rows.append(row)
    if len(rows) < minimum:
        raise ProbeError(f"only {len(rows)} installable cards, minimum {minimum} (upstream removal is a blocker, "
                         "not a reason to lower the threshold)")
    return {"catalog_generated_utc": catalog.get("generated_utc"), "hub_source_sha": catalog.get("hub_source_sha"),
            "apps": len(apps), "installs": rows, "source_only": len(apps) - len(rows)}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Probe a built or live 3DS hub catalogue (HTTP + independent QR decode).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--directory", type=Path, help="built site directory to serve on loopback")
    src.add_argument("--url", help="live site URL, e.g. https://lafiabrew.github.io/3ds_hub/")
    ap.add_argument("--base-path", help="site path prefix (required with --directory; must match --url path)")
    ap.add_argument("--minimum-installs", type=int, required=True, help="required number of installable cards")
    ap.add_argument("--skip-binary-range", action="store_true",
                    help="offline mode: do not Range-request the GitHub CIA files (recorded in the report)")
    ap.add_argument("--decoder", type=Path, default=DEFAULT_DECODER, help="vendored jsQR directory")
    ap.add_argument("--report", type=Path, help="write a JSON report to this NEW file (never overwritten)")
    args = ap.parse_args(argv)
    if args.minimum_installs < 0:
        ap.error("--minimum-installs must be >= 0")
    report: Dict[str, Any] = {"started_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                              "binary_range_checked": not args.skip_binary_range}
    rc = 1
    try:
        decoder = Decoder(args.decoder)
        report["decoder"] = decoder.provenance
        if args.directory is not None:
            if not args.base_path or not BASE_PATH_RE.match(args.base_path):
                raise ProbeError("--directory requires a valid --base-path such as /3ds_hub/")
            if not (args.directory / "index.html").is_file():
                raise ProbeError(f"{args.directory} has no index.html")
            site = LoopbackSite(args.directory, args.base_path)
            report["mode"] = "loopback"
            try:
                with site:
                    url = f"http://127.0.0.1:{site.port}{args.base_path}"
                    report["site_url"] = url
                    report.update(probe_origin(url, args.base_path, args.minimum_installs, decoder,
                                               not args.skip_binary_range))
            finally:
                report["server_closed"] = site.closed
            if not site.closed:
                raise ProbeError("loopback server did not shut down cleanly")
        else:
            parts = urllib.parse.urlsplit(args.url)
            ok_host = (parts.scheme == "https" and parts.hostname and parts.hostname.endswith(".github.io")) or \
                      (parts.scheme == "http" and parts.hostname in LOOPBACK)
            if not ok_host or not parts.path.endswith("/") or parts.query or parts.fragment:
                raise ProbeError("--url must be an https://<owner>.github.io/<path>/ site URL")
            if args.base_path and args.base_path != parts.path:
                raise ProbeError(f"--base-path {args.base_path} != URL path {parts.path}")
            report["mode"] = "live"
            report["site_url"] = args.url
            report.update(probe_origin(args.url, parts.path, args.minimum_installs, decoder,
                                       not args.skip_binary_range))
        rc = 0
        n = len(report["installs"])
        print(f"PASS: {n} installable cards; every QR independently decoded (jsQR) to its exact href/catalogue "
              f"URL; {report['source_only']} source-only cards without install controls; "
              f"binary Range checks: {'yes' if report['binary_range_checked'] else 'SKIPPED (offline)'}; "
              f"server_closed={report.get('server_closed', 'n/a')}")
        for row in report["installs"]:
            extra = f" range={row['range']['status']}" if "range" in row else ""
            print(f"  {row['repo']} {row['tag']}: decoded == href == {row['decoded']} "
                  f"(QR v{row['qr_version']}, quiet zone {row['quiet_zone_modules']} modules){extra}")
    except ProbeError as err:
        report["error"] = str(err)
        print(f"PROBE FAILED: {err}", file=sys.stderr)
    report["exit"] = rc
    if args.report:
        with args.report.open("x") as out:
            out.write(json.dumps(report, indent=2) + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
