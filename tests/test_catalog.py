#!/usr/bin/env python3
"""Tests for the static FBI QR catalogue (tools/build_catalog.py) and its probe (tools/probe_pages.py).

Run: python3 -m unittest discover -s tests -p test_catalog.py -v

Design notes (why these tests look the way they do):

* The builder is always exercised through its real CLI and real HTTP client against a
  loopback fake GitHub API that serves *actual captured* public API bodies
  (tests/fixtures/catalog/api). Negative controls are small, visible mutations of those
  real objects made right here in the test.
* QR codes are never checked with the hub's own encoder. The probe rasterizes the served
  SVG and decodes the pixels with the vendored, hash-pinned Apache-2.0 jsQR decoder in
  Node. Counterfactuals (mutated href, swapped/blank/corrupt QR, wrong base path) prove
  the probe actually fails when the binding is broken.
* Every failing build must leave a previous output directory byte-for-byte unchanged.
Requires only Python stdlib and an existing `node` binary; nothing is installed.
"""

from __future__ import annotations

import copy
import hashlib
import http.server
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "build_catalog.py"
PROBE = ROOT / "tools" / "probe_pages.py"
FIXTURES = ROOT / "tests" / "fixtures" / "catalog" / "api"
VENDOR = ROOT / "tests" / "vendor" / "jsqr"
WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"
ORG = "lafiabrew"
ORG_PATH = "/orgs/lafiabrew/repos?type=public&per_page=100&page=1"
EXPECTED_INSTALLS = sorted([
    "3ds_chip8", "3ds_drop", "3ds_mahjong", "3ds_netpass", "3ds_padtest", "3ds_picross", "3ds_pieceduel",
    "3ds_pokedash", "3ds_pokedex", "3ds_rngtool", "3ds_roulette", "3ds_sandlab", "3ds_sokoban",
    "3ds_solitaire", "3ds_sysdash", "3ds_wigle"])
# Full commit SHAs resolved from the GitHub API (tag -> commit) and recorded with their
# action.yml metadata in the catalogue author evidence; the workflow must use exactly these.
VERIFIED_ACTION_PINS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",  # v7.0.1
    "actions/upload-pages-artifact": "fc324d3547104276b827a68afc52ff2a11cc49c9",  # v5.0.0
    "actions/deploy-pages": "368f82528645a54fb793d4d04e342629a3f51346",  # v5.0.1
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe_mod = load_module("probe_pages_under_test", PROBE)
encoder = load_module("serve_3ds_readonly_test", ROOT / "serve_3ds.py")


def fixture_json(name: str):
    return json.loads((FIXTURES / name).read_text())


def tree_digest(path: Path) -> dict:
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# Loopback fake GitHub API
# ---------------------------------------------------------------------------

class FakeGitHub:
    """Serves real fixture bodies; `overrides[path]` may replace any response.

    An override is either a tuple (status, headers, body) or a callable(count) -> tuple,
    where count is how many times that path has been requested (1-based)."""

    def __init__(self) -> None:
        self.overrides = {}
        self.requests = []
        self.counts = {}
        self.org = json.loads((FIXTURES / "org-repos-page1.json").read_bytes())
        self.releases = {}
        for p in FIXTURES.glob("releases-*.json"):
            self.releases[p.stem[len("releases-"):]] = json.loads(p.read_bytes())
        self.pristine_chip8 = copy.deepcopy(self.releases["3ds_chip8"][0])
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):  # noqa: N802
                fake.requests.append({"path": self.path, "auth": self.headers.get("Authorization")})
                fake.counts[self.path] = fake.counts.get(self.path, 0) + 1
                status, headers, body, delay = fake.respond(self.path, fake.counts[self.path])
                if delay:
                    time.sleep(delay)
                try:
                    self.send_response(status)
                    headers = dict(headers)
                    headers.setdefault("Content-Type", "application/json; charset=utf-8")
                    headers.setdefault("Content-Length", str(len(body)))
                    for k, v in headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    @staticmethod
    def js(data, status=200, headers=None):
        return status, headers or {}, json.dumps(data).encode(), 0

    def respond(self, path, count):
        if path in self.overrides:
            o = self.overrides[path]
            res = o(count) if callable(o) else o
            return res if len(res) == 4 else (*res, 0)
        if path == ORG_PATH:
            return self.js(self.org)
        m = re.fullmatch(r"/repos/lafiabrew/([^/]+)/releases\?per_page=100&page=1", path)
        if m and m.group(1) in self.releases:
            return self.js(self.releases[m.group(1)])
        return 404, {}, b'{"message":"Not Found"}', 0

    def set_releases(self, repo, releases):
        self.releases[repo] = releases

    def chip8(self):
        return copy.deepcopy(self.pristine_chip8)


class Base(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHub()
        self.tmp = Path(tempfile.mkdtemp(prefix="catalog-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(self.api.close)

    def build(self, out=None, env=None, extra=(), base="/3ds_hub/", api=None):
        out = out or (self.tmp / "site")
        e = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GITHUB_SHA")}
        e.update(env or {})
        cmd = [sys.executable, str(BUILD), "--organization", ORG, "--output", str(out), "--base-path", base,
               "--api-url", api or self.api.url, "--timeout", "1", *extra]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=e, timeout=180)
        return proc, out

    def build_ok(self, **kw):
        proc, out = self.build(**kw)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return out, json.loads((out / "catalog.json").read_text())

    def app(self, catalog, repo):
        return next(a for a in catalog["apps"] if a["repo"] == repo)

    def assert_fails_preserving(self, expect_in_stderr, **kw):
        """A failed build must exit nonzero and leave the previous site untouched."""
        out = self.tmp / "preserved"
        good, _ = self.build(out=out)
        self.assertEqual(good.returncode, 0, good.stderr)
        before = tree_digest(out)
        self.mutate()
        proc, _ = self.build(out=out, **kw)
        self.assertNotEqual(proc.returncode, 0, "build should have failed")
        self.assertIn(expect_in_stderr, proc.stderr)
        self.assertEqual(tree_digest(out), before, "previous output bytes changed after failed build")
        self.assertEqual([p.name for p in out.parent.iterdir() if ".tmp-" in p.name or ".old-" in p.name], [])
        return proc

    def mutate(self):  # overridden per test via assignment
        pass


# ---------------------------------------------------------------------------
# Fixture provenance and real-data build
# ---------------------------------------------------------------------------

class RealFixtureTests(Base):
    def test_fixtures_are_unmodified_captured_api_bodies(self):
        """Fixtures must be the real captured bytes, so the 'real metadata' claim is checkable."""
        receipt = json.loads((FIXTURES / "capture-receipt.json").read_text())
        self.assertEqual(len(receipt["requests"]), 29)
        for req in receipt["requests"]:
            self.assertEqual(req["status"], 200)
            self.assertEqual(hashlib.sha256((FIXTURES / req["file"]).read_bytes()).hexdigest(), req["sha256"])
        self.assertTrue(self.api.org, "org listing fixture must be nonempty")

    def test_real_metadata_yields_16_installs_and_12_source_cards(self):
        """28 public non-archived 3ds_* repos (3ds_hub and .github excluded); 16 stable CIAs."""
        out, cat = self.build_ok()
        self.assertEqual(len(cat["apps"]), 28)
        self.assertNotIn("3ds_hub", [a["repo"] for a in cat["apps"]])
        installs = sorted(a["repo"] for a in cat["apps"] if a["install"])
        self.assertEqual(installs, EXPECTED_INSTALLS)
        for a in cat["apps"]:
            if a["install"]:
                self.assertEqual(a["install"]["cia_url"],
                                 f"https://github.com/lafiabrew/{a['repo']}/releases/download/v1.0.0/{a['repo']}.cia")
                self.assertEqual(a["integrity"]["level"], "legacy-no-manifest")
                self.assertRegex(a["integrity"]["sha256"], r"^[0-9a-f]{64}$")
                self.assertIs(a["tiers"]["published"], True)
                self.assertIn("not", a["tiers"]["reviewed"])
                self.assertIn("not observed", a["tiers"]["physically_tested"])
            else:
                self.assertTrue(a["reason"])
                self.assertIsNone(a["install"])
        self.assertRegex(cat["generated_utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(cat["base_path"], "/3ds_hub/")
        # No application binaries are produced or mirrored into the site.
        self.assertEqual([p for p in out.rglob("*") if p.suffix in (".cia", ".3dsx", ".smdh")], [])

    def test_qr_svgs_are_the_existing_hub_encoder_output(self):
        """The site must reuse serve_3ds.encode_qr_matrix/render_qr_svg (quiet zone 4, black/white, crisp)."""
        out, cat = self.build_ok()
        a = self.app(cat, "3ds_drop")
        svg = (out / a["install"]["qr_svg"]).read_text()
        self.assertEqual(svg, encoder.render_qr_svg(encoder.encode_qr_matrix(a["install"]["cia_url"]), border=4, scale=8))
        self.assertIn('shape-rendering="crispEdges"', svg)
        self.assertEqual(set(re.findall(r'fill="([^"]+)"', svg)), {"#ffffff", "#000000"})
        self.assertGreaterEqual(a["install"]["qr_quiet_zone_modules"], 4)
        self.assertGreaterEqual(a["install"]["qr_pixels"], 280)

    def test_html_is_static_accessible_and_wip_cards_have_no_install(self):
        out, cat = self.build_ok()
        page = (out / "index.html").read_text()
        self.assertNotIn("<script", page.lower())
        self.assertNotIn("refresh", page.lower())
        self.assertIn('<html lang="en">', page)
        self.assertIn('name="viewport"', page)
        self.assertIn("default-src 'none'", page)
        self.assertIn('href="/3ds_hub/style.css"', page)
        parser = probe_mod.PageParser()
        parser.feed(page)
        self.assertEqual(parser.problems, [])
        for a in cat["apps"]:
            card = parser.cards[a["repo"]]
            if a["install"]:
                self.assertEqual(card["install"], [a["install"]["cia_url"]])
                self.assertEqual(len(card["imgs"]), 1)
            else:
                self.assertEqual((card["install"], card["cia_links"], card["imgs"]), ([], [], []))
        self.assertIn("does <em>not</em> mean the release was independently reviewed", page)
        self.assertIn("Roll back", page)
        self.assertIn("Back up first", page)


# ---------------------------------------------------------------------------
# Release selection and URL/text hardening
# ---------------------------------------------------------------------------

class SelectionTests(Base):
    def chip8_result(self, releases):
        self.api.set_releases("3ds_chip8", releases)
        out, cat = self.build_ok()
        return out, self.app(cat, "3ds_chip8")

    def test_draft_is_never_offered(self):
        r = self.api.chip8(); r["draft"] = True
        _, a = self.chip8_result([r])
        self.assertIsNone(a["install"]); self.assertIn("No published stable release", a["reason"])

    def test_prerelease_newer_than_stable_is_ignored(self):
        stable = self.api.chip8()
        pre = self.api.chip8(); pre.update(tag_name="v1.1.0", prerelease=True)
        _, a = self.chip8_result([pre, stable])
        self.assertEqual(a["release"]["tag"], "v1.0.0")
        self.assertTrue(a["install"]["cia_url"].endswith("/v1.0.0/3ds_chip8.cia"))

    def test_highest_semver_wins_and_no_fallback_to_older_cia(self):
        """Latest stable without CIA must not silently fall back to an older binary."""
        old = self.api.chip8()
        new = self.api.chip8(); new.update(tag_name="v1.10.0", html_url="https://github.com/lafiabrew/3ds_chip8/releases/tag/v1.10.0")
        new["assets"] = [x for x in new["assets"] if not x["name"].endswith(".cia")]
        _, a = self.chip8_result([old, new])
        self.assertIsNone(a["install"]); self.assertIn("v1.10.0 has no 3ds_chip8.cia", a["reason"])

    def test_missing_cia_is_source_only(self):
        r = self.api.chip8(); r["assets"] = [x for x in r["assets"] if x["name"] != "3ds_chip8.cia"]
        _, a = self.chip8_result([r])
        self.assertIsNone(a["install"]); self.assertIn("no 3ds_chip8.cia", a["reason"])

    def test_multiple_or_case_variant_cia_is_ambiguous(self):
        for extra in ("3ds_chip8-debug.cia", "3DS_CHIP8.CIA"):
            r = self.api.chip8()
            dup = copy.deepcopy(next(x for x in r["assets"] if x["name"] == "3ds_chip8.cia"))
            dup["name"] = extra
            dup["browser_download_url"] = f"https://github.com/lafiabrew/3ds_chip8/releases/download/v1.0.0/{extra}"
            r["assets"].append(dup)
            _, a = self.chip8_result([r])
            self.assertIsNone(a["install"], extra); self.assertIn("ambiguous", a["reason"])

    def test_foreign_scheme_latest_and_page_urls_are_rejected(self):
        bad_urls = [
            "https://evil.example/lafiabrew/3ds_chip8/releases/download/v1.0.0/3ds_chip8.cia",
            "javascript:alert(1)//3ds_chip8.cia",
            "http://github.com/lafiabrew/3ds_chip8/releases/download/v1.0.0/3ds_chip8.cia",
            "https://github.com/lafiabrew/3ds_chip8/releases/latest/download/3ds_chip8.cia",
            "https://github.com/lafiabrew/3ds_chip8/releases/tag/v1.0.0",
            "https://github.com/lafiabrew/3ds_chip8/releases/download/v1.0.0/../../evil/3ds_chip8.cia",
            "https://github.com/other/3ds_chip8/releases/download/v1.0.0/3ds_chip8.cia",
        ]
        for url in bad_urls:
            r = self.api.chip8()
            next(x for x in r["assets"] if x["name"] == "3ds_chip8.cia")["browser_download_url"] = url
            out, a = self.chip8_result([r])
            self.assertIsNone(a["install"], url)
            self.assertIn("not the direct versioned", a["reason"])
            parser = probe_mod.PageParser()
            parser.feed((out / "index.html").read_text())
            card = parser.cards["3ds_chip8"]
            self.assertEqual((card["install"], card["cia_links"], card["imgs"]), ([], [], []), url)
            if "/releases/tag/" not in url:
                # The genuine release-notes page may still be linked as notes; nothing else may appear.
                self.assertNotIn(url, (out / "index.html").read_text())

    def test_incomplete_or_html_asset_is_rejected(self):
        for field, value in (("state", "starter"), ("size", 0), ("content_type", "text/html")):
            r = self.api.chip8()
            next(x for x in r["assets"] if x["name"] == "3ds_chip8.cia")[field] = value
            _, a = self.chip8_result([r])
            self.assertIsNone(a["install"], field)

    def test_non_semver_stable_tag_makes_latest_ambiguous_and_is_escaped(self):
        r = self.api.chip8(); r["tag_name"] = "<b>latest</b>"
        out, a = self.chip8_result([r, self.api.chip8()])
        self.assertIsNone(a["install"]); self.assertIn("not strict", a["reason"])
        page = (out / "index.html").read_text()
        self.assertNotIn("<b>latest</b>", page); self.assertIn("&lt;b&gt;latest&lt;/b&gt;", page)

    def test_release_page_url_mismatch_suppresses_links(self):
        r = self.api.chip8(); r["html_url"] = "https://evil.example/notes"
        out, a = self.chip8_result([r])
        self.assertIsNone(a["install"]); self.assertNotIn("evil.example", (out / "index.html").read_text())

    def test_malicious_description_and_notes_are_escaped(self):
        """Untrusted repo/release text can never inject markup, scripts or URL schemes."""
        payload = '<script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:alert(1)">x</a>\u202e'
        for repo in self.api.org:
            if repo["name"] == "3ds_chip8":
                repo["description"] = payload
        r = self.api.chip8(); r["name"] = payload; r["body"] = payload
        out, a = self.chip8_result([r])
        self.assertIsNotNone(a["install"])
        page = (out / "index.html").read_text()
        self.assertNotIn("<script", page); self.assertNotIn("<img src=x", page)
        self.assertNotIn('href="javascript:', page); self.assertNotIn("\u202e", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        rc = subprocess.run([sys.executable, str(PROBE), "--directory", str(out), "--base-path", "/3ds_hub/",
                             "--minimum-installs", "16", "--skip-binary-range"], capture_output=True, text=True, timeout=300)
        self.assertEqual(rc.returncode, 0, rc.stderr)

    def test_archived_private_hub_and_non_3ds_repos_are_excluded(self):
        for repo in self.api.org:
            if repo["name"] == "3ds_wigle":
                repo["archived"] = True
            if repo["name"] == "3ds_drop":
                repo["private"] = True
        _, cat = self.build_ok()
        names = [a["repo"] for a in cat["apps"]]
        self.assertEqual(len(names), 26)
        for excluded in ("3ds_wigle", "3ds_drop", "3ds_hub", ".github"):
            self.assertNotIn(excluded, names)

    def test_foreign_repo_identity_fails_build(self):
        for field, value in (("html_url", "https://evil.example/3ds_chip8"), ("owner", {"login": "someone"})):
            api_org = copy.deepcopy(self.api.org)
            for repo in self.api.org:
                if repo["name"] == "3ds_chip8":
                    repo[field] = value
            proc, _ = self.build(out=self.tmp / f"x-{field}")
            self.assertEqual(proc.returncode, 1, field)
            self.api.org = api_org


# ---------------------------------------------------------------------------
# New-contract manifests and token handling
# ---------------------------------------------------------------------------

class ManifestTests(Base):
    CIA_SHA = "a11388f4c41dfd5fa26aca10692db5fcddf29a7f884ddce55c43dd1a032555fc"
    SOURCE = "92940977acd92c8c6210990c323fd61872cad17c"

    def setUp(self):
        super().setUp()
        self.blobs = {}
        self.blob_auth = []
        outer = self

        class Blob(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):  # noqa: N802
                outer.blob_auth.append(self.headers.get("Authorization"))
                body = outer.blobs.get(self.path, b"")
                self.send_response(200 if self.path in outer.blobs else 404)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.blob_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Blob)
        threading.Thread(target=self.blob_server.serve_forever, daemon=True).start()
        self.addCleanup(self.blob_server.server_close)
        self.addCleanup(self.blob_server.shutdown)
        self.blob_url = f"http://127.0.0.1:{self.blob_server.server_address[1]}"

    def with_manifests(self, sums: bytes, manifest: bytes):
        r = self.api.chip8()
        base = "https://github.com/lafiabrew/3ds_chip8/releases/download/v1.0.0/"
        for aid, name, body in ((9001, "SHA256SUMS", sums), (9002, "release.json", manifest)):
            r["assets"].append({"id": aid, "name": name, "state": "uploaded", "size": len(body),
                                "content_type": "application/octet-stream", "browser_download_url": base + name})
            self.blobs[f"/blob/{name}"] = body
            # GitHub's asset endpoint redirects to a different storage host; so does the fake.
            self.api.overrides[f"/repos/lafiabrew/3ds_chip8/releases/assets/{aid}"] = (
                302, {"Location": f"{self.blob_url}/blob/{name}"}, b"")
        self.api.set_releases("3ds_chip8", [r])

    def manifest(self, **over):
        m = {"schema": 1, "repo": "3ds_chip8", "tag": "v1.0.0", "source_sha": self.SOURCE,
             "assets": [{"name": "3ds_chip8.cia", "size": 222144, "sha256": self.CIA_SHA}]}
        m.update(over)
        return json.dumps(m).encode()

    def test_consistent_manifests_are_shown_and_token_stays_on_api_origin(self):
        """release.json/SHA256SUMS compatibility, and GITHUB_TOKEN never leaves the API origin or reaches output."""
        canary = "ghs_CANARYtoken0123456789"
        self.with_manifests(f"{self.CIA_SHA}  3ds_chip8.cia\n".encode(), self.manifest())
        out, cat = self.build_ok(env={"GITHUB_TOKEN": canary})
        a = self.app(cat, "3ds_chip8")
        self.assertEqual(a["integrity"]["level"], "manifest")
        self.assertEqual(a["integrity"]["source_sha"], self.SOURCE)
        api_auth = {r["auth"] for r in self.api.requests if r["path"].startswith(("/orgs/", "/repos/"))}
        self.assertEqual(api_auth, {f"Bearer {canary}"})
        self.assertEqual(self.blob_auth, [None, None], "credential forwarded to redirected storage host")
        for p in out.rglob("*"):
            if p.is_file():
                self.assertNotIn(canary.encode(), p.read_bytes(), p)
        self.assertIn(self.SOURCE, (out / "index.html").read_text())

    def test_contradicting_manifests_demote_to_source_only(self):
        cases = [
            (f"{'0' * 64}  3ds_chip8.cia\n".encode(), self.manifest()),
            (f"{self.CIA_SHA}  3ds_chip8.cia\n".encode(), self.manifest(repo="3ds_other")),
            (f"{self.CIA_SHA}  3ds_chip8.cia\n".encode(), self.manifest(source_sha="main")),
            (f"{self.CIA_SHA}  3ds_chip8.cia\n".encode(),
             self.manifest(assets=[{"name": "3ds_chip8.cia", "size": 1, "sha256": self.CIA_SHA}])),
            (b"not a sums file", self.manifest()),
            (f"{self.CIA_SHA}  3ds_chip8.cia\n".encode(), b"{truncated"),
        ]
        for i, (sums, man) in enumerate(cases):
            self.with_manifests(sums, man)
            _, cat = self.build_ok(out=self.tmp / f"s{i}")
            a = self.app(cat, "3ds_chip8")
            self.assertIsNone(a["install"], (sums, man)); self.assertIn("manifest", a["reason"])

    def test_partial_manifest_is_refused(self):
        self.with_manifests(f"{self.CIA_SHA}  3ds_chip8.cia\n".encode(), self.manifest())
        rel = self.api.releases["3ds_chip8"][0]
        rel["assets"] = [x for x in rel["assets"] if x["name"] != "release.json"]
        _, cat = self.build_ok()
        self.assertIn("incomplete integrity manifest", self.app(cat, "3ds_chip8")["reason"])

    def test_manifest_redirect_to_foreign_host_fails_build(self):
        self.with_manifests(f"{self.CIA_SHA}  3ds_chip8.cia\n".encode(), self.manifest())
        self.api.overrides["/repos/lafiabrew/3ds_chip8/releases/assets/9001"] = (
            302, {"Location": "https://evil.example/x"}, b"")
        proc, _ = self.build()
        self.assertEqual(proc.returncode, 1); self.assertIn("refusing manifest redirect", proc.stderr)


# ---------------------------------------------------------------------------
# Bounded API failure oracles (fail closed, preserve previous output)
# ---------------------------------------------------------------------------

class FailureTests(Base):
    def test_rate_limit_with_distant_reset_fails_immediately(self):
        def mutate():
            self.api.overrides[ORG_PATH] = (403, {"X-RateLimit-Remaining": "0",
                                                  "X-RateLimit-Reset": str(int(time.time()) + 3600)}, b"{}")
            self.api.counts.clear()
        self.mutate = mutate
        self.assert_fails_preserving("rate limited")
        self.assertEqual(self.api.counts[ORG_PATH], 1, "must not spin on a distant rate-limit reset")

    def test_short_retry_after_is_honoured_then_succeeds(self):
        self.api.overrides[ORG_PATH] = lambda n: (429, {"Retry-After": "1"}, b"{}") if n == 1 else \
            (200, {}, json.dumps(self.api.org).encode())
        _, cat = self.build_ok()
        self.assertEqual(self.api.counts[ORG_PATH], 2)
        self.assertEqual(len(cat["apps"]), 28)

    def test_server_errors_retry_at_most_twice(self):
        def mutate():
            self.api.overrides["/repos/lafiabrew/3ds_wigle/releases?per_page=100&page=1"] = (502, {}, b"bad gateway")
            self.api.counts.clear()
        self.mutate = mutate
        self.assert_fails_preserving("after 3 attempts")
        self.assertEqual(self.api.counts["/repos/lafiabrew/3ds_wigle/releases?per_page=100&page=1"], 3)

    def test_timeout_is_bounded(self):
        def mutate():
            self.api.overrides[ORG_PATH] = (200, {}, json.dumps(self.api.org).encode(), 2.5)
            self.api.counts.clear()
        self.mutate = mutate
        start = time.monotonic()
        self.assert_fails_preserving("after 3 attempts")
        self.assertEqual(self.api.counts[ORG_PATH], 3)
        self.assertLess(time.monotonic() - start, 60)

    def test_truncated_or_wrong_json_fails(self):
        bodies = [(200, {}, json.dumps(self.api.org).encode()[:-40]),
                  (200, {}, b'{"message":"not a list"}'),
                  (200, {"Content-Type": "text/html"}, b"<html>login</html>")]
        for body in bodies:
            self.api.overrides[ORG_PATH] = body
            proc, _ = self.build(out=self.tmp / "t")
            self.assertEqual(proc.returncode, 1, body)

    def test_empty_listing_never_produces_empty_catalogue(self):
        def mutate():
            self.api.overrides[ORG_PATH] = (200, {}, b"[]")
        self.mutate = mutate
        self.assert_fails_preserving("false empty")

    def test_missing_release_listing_fails_build(self):
        def mutate():
            self.api.releases.pop("3ds_pinball")
        self.mutate = mutate
        self.assert_fails_preserving("HTTP 404")

    def test_pagination_followed_and_bounded(self):
        org = self.api.org
        base = self.api.url
        pages = [org[0:10], org[10:20], org[20:]]
        for i, chunk in enumerate(pages, start=1):
            link = {"Link": f'<{base}/orgs/lafiabrew/repos?type=public&per_page=100&page={i + 1}>; rel="next"'} \
                if i < len(pages) else {}
            self.api.overrides[f"/orgs/lafiabrew/repos?type=public&per_page=100&page={i}"] = (200, link, json.dumps(chunk).encode())
        _, cat = self.build_ok()
        self.assertEqual(len(cat["apps"]), 28)
        # 11 pages -> refuse truncated data
        for i in range(1, 12):
            self.api.overrides[f"/orgs/lafiabrew/repos?type=public&per_page=100&page={i}"] = (
                200, {"Link": f'<{base}/orgs/lafiabrew/repos?type=public&per_page=100&page={i + 1}>; rel="next"'},
                json.dumps(org[:3] if i == 1 else []).encode())
        proc, _ = self.build(out=self.tmp / "p")
        self.assertEqual(proc.returncode, 1); self.assertIn("exceeded 10 pages", proc.stderr)
        # foreign pagination link
        self.api.overrides[ORG_PATH] = (200, {"Link": '<https://evil.example/orgs/lafiabrew/repos?page=2>; rel="next"'},
                                        json.dumps(org).encode())
        proc, _ = self.build(out=self.tmp / "q")
        self.assertEqual(proc.returncode, 1); self.assertIn("foreign", proc.stderr)

    def test_unsafe_arguments_and_outputs_are_refused(self):
        for base in ("3ds_hub", "/3ds_hub", "//evil/", "/a/../b/", "/x y/"):
            proc, _ = self.build(base=base, out=self.tmp / "b")
            self.assertEqual(proc.returncode, 1, base)
        for api in ("https://evil.example", "http://10.0.0.1:80"):
            proc, _ = self.build(api=api, out=self.tmp / "c")
            self.assertEqual(proc.returncode, 1, api)
        precious = self.tmp / "precious"
        precious.mkdir(); (precious / "keep.txt").write_text("keep")
        proc, _ = self.build(out=precious)
        self.assertEqual(proc.returncode, 1); self.assertEqual((precious / "keep.txt").read_text(), "keep")
        proc, _ = self.build(out=ROOT)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.api.requests, [], "argument validation must happen before any API call")


# ---------------------------------------------------------------------------
# Probe: real loopback HTTP + independent decoder, with counterfactual controls
# ---------------------------------------------------------------------------

class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = FakeGitHub()
        cls.tmp = Path(tempfile.mkdtemp(prefix="probe-test-"))
        cls.site = cls.tmp / "site"
        e = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
        proc = subprocess.run([sys.executable, str(BUILD), "--organization", ORG, "--output", str(cls.site),
                               "--base-path", "/3ds_hub/", "--api-url", cls.api.url, "--timeout", "1"],
                              capture_output=True, text=True, env=e, timeout=180)
        assert proc.returncode == 0, proc.stderr
        cls.catalog = json.loads((cls.site / "catalog.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.api.close()
        shutil.rmtree(cls.tmp, True)

    def probe(self, site=None, base="/3ds_hub/", minimum=16, report=None):
        cmd = [sys.executable, str(PROBE), "--directory", str(site or self.site), "--base-path", base,
               "--minimum-installs", str(minimum), "--skip-binary-range"]
        if report:
            cmd += ["--report", str(report)]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    def copy_site(self):
        dst = Path(tempfile.mkdtemp(prefix="mut-", dir=self.tmp)) / "site"
        shutil.copytree(self.site, dst)
        return dst

    def test_all_16_qr_codes_decode_independently_to_exact_href(self):
        report = self.tmp / "report-pass.json"
        proc = self.probe(report=report)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(report.read_text())
        self.assertEqual(len(rep["installs"]), 16)
        self.assertEqual(rep["source_only"], 12)
        for row in rep["installs"]:
            self.assertEqual(row["decoded"], row["href"])
            self.assertEqual(row["decoded"], row["cia_url"])
            self.assertGreaterEqual(row["quiet_zone_modules"], 4.0)
        self.assertTrue(rep["server_closed"])
        self.assertFalse(rep["binary_range_checked"], "offline test must say Range checks were skipped")
        port = urllib.parse.urlsplit(rep["site_url"]).port
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
        self.assertEqual(rep["decoder"]["license"], "Apache-2.0")

    def test_live_url_mode_uses_same_checks(self):
        """The post-deploy interface (--url) runs the identical checks over real HTTP."""
        site = probe_mod.LoopbackSite(self.site, "/3ds_hub/")
        with site:
            url = f"http://127.0.0.1:{site.port}/3ds_hub/"
            ok = subprocess.run([sys.executable, str(PROBE), "--url", url, "--minimum-installs", "16",
                                 "--skip-binary-range"], capture_output=True, text=True, timeout=300)
            wrong = subprocess.run([sys.executable, str(PROBE), "--url", url, "--base-path", "/other/",
                                    "--minimum-installs", "16", "--skip-binary-range"],
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("PASS: 16 installable cards", ok.stdout)
        self.assertEqual(wrong.returncode, 1)
        for bad in ("https://evil.example/3ds_hub/", "http://lafiabrew.github.io/3ds_hub/"):
            proc = subprocess.run([sys.executable, str(PROBE), "--url", bad, "--minimum-installs", "16"],
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 1, bad)

    def test_report_is_never_overwritten(self):
        existing = self.tmp / "existing-report.json"
        existing.write_text("keep")
        proc = self.probe(report=existing)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(existing.read_text(), "keep")

    def test_threshold_is_not_silently_lowered(self):
        proc = self.probe(minimum=17)
        self.assertEqual(proc.returncode, 1); self.assertIn("minimum 17", proc.stderr)

    def test_mutated_html_href_is_caught(self):
        """Counterfactual: QR still valid, but the button points elsewhere -> must fail."""
        site = self.copy_site()
        page = (site / "index.html").read_text()
        good = "https://github.com/lafiabrew/3ds_chip8/releases/download/v1.0.0/3ds_chip8.cia"
        bad = "https://github.com/lafiabrew/3ds_chip8/releases/download/v1.0.0/3ds_chip8x.cia"
        self.assertEqual(page.count(f'class="install" href="{good}"'), 1)
        (site / "index.html").write_text(page.replace(f'class="install" href="{good}"', f'class="install" href="{bad}"'))
        proc = self.probe(site)
        self.assertEqual(proc.returncode, 1); self.assertIn("install href", proc.stderr)

    def test_catalog_pointing_to_html_release_page_is_caught(self):
        site = self.copy_site()
        cat = json.loads((site / "catalog.json").read_text())
        cat["apps"][2]["install"]["cia_url"] = "https://github.com/lafiabrew/3ds_chip8/releases/tag/v1.0.0"
        (site / "catalog.json").write_text(json.dumps(cat))
        proc = self.probe(site)
        self.assertEqual(proc.returncode, 1); self.assertIn("not the direct versioned", proc.stderr)

    def test_swapped_qr_is_caught_by_independent_decode(self):
        """Wrong binding: a valid QR for another app must not pass for chip8."""
        site = self.copy_site()
        shutil.copyfile(site / "qr/3ds_drop-v1.0.0.svg", site / "qr/3ds_chip8-v1.0.0.svg")
        proc = self.probe(site)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("3ds_drop.cia", proc.stderr)
        self.assertIn("QR decodes to", proc.stderr)

    def test_blank_and_corrupt_qr_are_caught(self):
        svg = (self.site / "qr/3ds_chip8-v1.0.0.svg").read_text()
        size = re.search(r'width="(\d+)"', svg).group(1)
        blank = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" '
                 f'height="{size}" shape-rendering="crispEdges"><rect width="{size}" height="{size}" fill="#ffffff"/>'
                 f'<rect x="32" y="32" width="8" height="8" fill="#000000"/></svg>')
        modules = (int(size) // 8) - 8
        def in_finder(r, c):
            return (r < 8 and c < 8) or (r < 8 and c >= modules - 8) or (r >= modules - 8 and c < 8)
        # Keep the three finder patterns and quiet zone intact but drop every other dark data
        # module: still a crisp black/white SVG that passes geometry checks, yet undecodable.
        kept, dropped = [], 0
        for m in re.finditer(r'<rect x="(\d+)" y="(\d+)" width="8" height="8" fill="#000000"/>', svg):
            c, r = int(m.group(1)) // 8 - 4, int(m.group(2)) // 8 - 4
            if not in_finder(r, c) and dropped % 2 == 0:
                dropped += 1
                continue
            if not in_finder(r, c):
                dropped += 1
            kept.append(m.group(0))
        head = svg[:svg.index('<rect x=')]
        corrupt = head + "".join(kept) + "</svg>"
        self.assertGreater(dropped, 100)
        for label, body in (("blank", blank), ("corrupt", corrupt)):
            site = self.copy_site()
            (site / "qr/3ds_chip8-v1.0.0.svg").write_text(body)
            proc = self.probe(site)
            self.assertEqual(proc.returncode, 1, label)
            self.assertIn("QR decodes to None", proc.stderr, label)

    def test_insufficient_quiet_zone_and_non_crisp_svg_are_caught(self):
        url = "https://github.com/lafiabrew/3ds_chip8/releases/download/v1.0.0/3ds_chip8.cia"
        thin = encoder.render_qr_svg(encoder.encode_qr_matrix(url), border=2, scale=8)
        script = (self.site / "qr/3ds_chip8-v1.0.0.svg").read_text().replace("</svg>", "<script>alert(1)</script></svg>")
        soft = (self.site / "qr/3ds_chip8-v1.0.0.svg").read_text().replace(' shape-rendering="crispEdges"', "")
        for label, body, needle in (("thin", thin, "quiet zone"), ("script", script, "unexpected SVG element"),
                                    ("soft", soft, "crispEdges")):
            site = self.copy_site()
            (site / "qr/3ds_chip8-v1.0.0.svg").write_text(body)
            proc = self.probe(site)
            self.assertEqual(proc.returncode, 1, label)
            self.assertIn(needle, proc.stderr, label)

    def test_wrong_base_path_fails_and_server_is_reaped(self):
        report = self.tmp / "report-wrong-base.json"
        proc = self.probe(base="/other/", report=report)
        self.assertEqual(proc.returncode, 1)
        rep = json.loads(report.read_text())
        self.assertTrue(rep["server_closed"])
        port = urllib.parse.urlsplit(rep["site_url"]).port
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=1).close()

    def test_redirects_scripts_and_source_card_install_are_caught(self):
        install_card = '<article class="card source-only" id="app-3ds_pinball"'
        cases = [
            ("<head>", '<head><meta http-equiv="refresh" content="0;url=https://github.com/">', "meta refresh"),
            ("<body>", "<body><script>location='x'</script>", "forbidden <script>"),
            ("<body>", '<body><a href="javascript:alert(1)">x</a>', "unsafe URL scheme"),
            (install_card, install_card +
             '><a class="install" href="https://github.com/lafiabrew/3ds_pinball/releases/download/v1.0.0/3ds_pinball.cia">x</a',
             "source-only card"),
        ]
        for needle, repl, expect in cases:
            site = self.copy_site()
            page = (site / "index.html").read_text()
            self.assertIn(needle, page)
            (site / "index.html").write_text(page.replace(needle, repl, 1))
            proc = self.probe(site)
            self.assertEqual(proc.returncode, 1, expect)
            self.assertIn(expect, proc.stderr)


class DecoderTests(unittest.TestCase):
    def test_vendored_decoder_is_pinned_apache_2_and_independent(self):
        prov = json.loads((VENDOR / "PROVENANCE.json").read_text())
        self.assertEqual(prov["license"], "Apache-2.0")
        self.assertEqual(prov["commit"], "8e6a036beafa7053dd44b1b76ac578d22b1b3311")
        self.assertIs(prov["modified"], False)
        lic = (VENDOR / "LICENSE").read_text()
        self.assertIn("Apache License", lic); self.assertIn("Version 2.0", lic)
        for name in ("PROVENANCE.json", "README.md"):
            self.assertNotIn("MIT", (VENDOR / name).read_text(), f"{name} must not mislabel the license")
        for name, meta in prov["files"].items():
            self.assertEqual(hashlib.sha256((VENDOR / name).read_bytes()).hexdigest(), meta["sha256"])
        # The decoder contains no reference to the hub encoder.
        self.assertNotIn("encode_qr_matrix", (VENDOR / "jsQR.js").read_text())

    def test_blank_raster_decodes_to_nothing(self):
        dec = probe_mod.Decoder(VENDOR)
        self.assertIsNone(dec.decode(b"\xff" * (300 * 300 * 4), 300, 300))

    def test_tampered_decoder_is_refused(self):
        tmp = Path(tempfile.mkdtemp(prefix="dec-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(VENDOR, tmp / "jsqr")
        with open(tmp / "jsqr" / "jsQR.js", "a") as fh:
            fh.write("\n// tampered\n")
        with self.assertRaises(probe_mod.ProbeError):
            probe_mod.Decoder(tmp / "jsqr")


class WorkflowTests(unittest.TestCase):
    """Static guard-rails for .github/workflows/pages.yml (actionlint runs separately)."""

    def setUp(self):
        self.text = WORKFLOW.read_text()

    def test_triggers_are_push_manual_and_hourly_minute_17_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertRegex(self.text, r"cron: '17 \* \* \* \*'")
        self.assertNotRegex(self.text, r"pull_request|repository_dispatch|workflow_run")
        self.assertRegex(self.text, r"branches:\s*\[main\]")

    def test_actions_pinned_to_verified_full_shas(self):
        uses = re.findall(r"uses:\s*([^@\s]+)@(\S+)", self.text)
        self.assertTrue(uses)
        for action, ref in uses:
            self.assertEqual(VERIFIED_ACTION_PINS.get(action), ref, action)

    def test_least_privilege_and_no_expressions_in_shell(self):
        self.assertRegex(self.text, r"(?m)^permissions: \{\}$")
        self.assertRegex(self.text, r"contents: read")
        self.assertRegex(self.text, r"pages: write")
        self.assertRegex(self.text, r"id-token: write")
        self.assertIn("persist-credentials: false", self.text)
        lines = self.text.splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", line)
            if not m:
                continue
            block = [m.group(2)]
            indent = len(m.group(1))
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                block.append(nxt)
            self.assertNotIn("${{", "\n".join(block), f"GitHub expression inside run: at line {i + 1}")

    def test_build_and_probe_commands_match_runbook(self):
        self.assertIn("python3 tools/build_catalog.py --organization lafiabrew --output _site --base-path /3ds_hub/", self.text)
        self.assertIn("python3 tools/probe_pages.py --directory _site --base-path /3ds_hub/ --minimum-installs 16", self.text)
        self.assertIn("python3 -m unittest discover -s tests -p test_catalog.py -v", self.text)


if __name__ == "__main__":
    unittest.main()
