#!/usr/bin/env python3
"""Build the static lafiabrew 3DS FBI QR catalogue for GitHub Pages.

Usage (runbook contract):

    python3 tools/build_catalog.py --organization lafiabrew --output _site --base-path /3ds_hub/

What it does, at build time only (visitors never call the GitHub API):

* Lists public, non-archived ``<org>/3ds_*`` repositories (excluding ``3ds_hub``).
* For each, reads its releases and picks the highest strict ``vMAJOR.MINOR.PATCH``
  release that is published, not a draft and not a prerelease.
* Only when that release carries exactly one asset named ``<repo>.cia`` whose
  download URL is the direct, versioned
  ``https://github.com/<org>/<repo>/releases/download/<tag>/<repo>.cia`` does the
  card get an install button and a QR code. The QR (made with the hub's existing
  ``serve_3ds.encode_qr_matrix``/``render_qr_svg``) encodes that exact string, and
  the button's ``href`` is that exact string. Everything else becomes a
  source-only card with a stated reason.
* Legacy releases without ``SHA256SUMS``/``release.json`` are labelled Published,
  with the missing manifest disclosed. New-contract releases have both manifests
  downloaded (size-bounded) and cross-checked; contradictions demote the card.

API access is bounded (10 s timeout, at most two retries, at most ten pages and
1000 repositories per listing, a total request budget). Any timeout, rate limit,
HTTP error, truncated/malformed JSON or pagination overflow aborts the build with a
nonzero exit and leaves an existing output directory byte-for-byte unchanged.
The optional ``GITHUB_TOKEN`` is only ever sent to the API origin and is never
written to the output.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import http.client
import importlib.util
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SITE_SOURCE = ROOT / "site"
STATIC_FILES = ("style.css", "favicon.svg")
SCHEMA = 1

PRODUCTION_API = "https://api.github.com"
MAX_TIMEOUT_SECONDS = 10.0
MAX_RETRIES = 2
MAX_PAGES = 10
MAX_ITEMS = 1000
MAX_REQUESTS = 400
MAX_RATE_WAIT_SECONDS = 30.0
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_REDIRECTS = 3
MAX_CIA_BYTES = 4 * 1024 * 1024 * 1024
QR_SCALE = 8
QR_BORDER = 4
USER_AGENT = "lafiabrew-3ds-hub-catalogue-builder"
MARKER = ".catalog-build.json"

ORG_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_RE = re.compile(r"^3ds_[A-Za-z0-9_-]{1,90}$")
TAG_RE = re.compile(r"^v(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})$")
BASE_PATH_RE = re.compile(r"^/(?:[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*/)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
REDIRECT_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class BuildError(RuntimeError):
    """Fatal: incomplete or untrustworthy upstream data. The build must not deploy."""


# ---------------------------------------------------------------------------
# Small validation helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: Any, limit: int) -> str:
    """Untrusted API text -> single safe plain-text string (HTML escaping happens at render)."""
    if not isinstance(value, str):
        return ""
    text = CONTROL_RE.sub("", value).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(" ".join(line.split()) for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "\u2026"
    return text


def validate_base_path(value: str) -> str:
    if not BASE_PATH_RE.match(value) or "//" in value:
        raise BuildError(f"invalid --base-path {value!r}: need an absolute path such as /3ds_hub/ (or /)")
    return value


def validate_api_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if value.rstrip("/") == PRODUCTION_API:
        return PRODUCTION_API
    # Loopback http is accepted only so tests can run the real code path against a fake API.
    if parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS and parsed.port and parsed.path in ("", "/") \
            and not parsed.query and not parsed.fragment and not parsed.username:
        return f"http://{parsed.netloc}"
    raise BuildError(f"refusing API origin {value!r}: only {PRODUCTION_API} (or loopback http for tests)")


def semver_key(tag: str) -> Tuple[int, int, int]:
    m = TAG_RE.match(tag)
    assert m
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def expected_cia_url(org: str, repo: str, tag: str) -> str:
    return f"https://github.com/{org}/{repo}/releases/download/{tag}/{repo}.cia"


def expected_asset_url(org: str, repo: str, tag: str, name: str) -> str:
    return f"https://github.com/{org}/{repo}/releases/download/{tag}/{name}"


def display_name(repo: str) -> str:
    stem = repo[4:]
    return " ".join(part[:1].upper() + part[1:] for part in re.split(r"[_-]+", stem) if part) or repo


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MiB"
    return f"{(size + 1023) // 1024} KiB"


# ---------------------------------------------------------------------------
# Bounded GitHub API client
# ---------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None  # handled explicitly so every hop is validated


class GitHubClient:
    def __init__(self, api_url: str, token: Optional[str], timeout: float, log=None) -> None:
        self.api = api_url
        self.api_parts = urllib.parse.urlsplit(api_url)
        self.loopback = self.api_parts.hostname in LOOPBACK_HOSTS
        self.token = token or None
        self.timeout = timeout
        self.requests = 0
        self.log = log or (lambda msg: print(msg, file=sys.stderr))
        self.opener = urllib.request.build_opener(_NoRedirect())

    # -- low level --------------------------------------------------------
    def _open(self, url: str, accept: str, send_token: bool, limit: int):
        """One GET with retries. Returns (status, headers, body, final_url)."""
        last_error = "no attempt"
        for attempt in range(MAX_RETRIES + 1):
            self.requests += 1
            if self.requests > MAX_REQUESTS:
                raise BuildError(f"request budget {MAX_REQUESTS} exceeded; refusing partial catalogue")
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", accept)
            req.add_header("User-Agent", USER_AGENT)
            req.add_header("X-GitHub-Api-Version", "2022-11-28")
            if send_token and self.token:
                # Unredirected: never forwarded if a redirect is followed.
                req.add_unredirected_header("Authorization", f"Bearer {self.token}")
            wait = None
            try:
                with self.opener.open(req, timeout=self.timeout) as resp:
                    body = resp.read(limit + 1)
                    if len(body) > limit:
                        raise BuildError(f"response from {self._redact(url)} exceeds {limit} bytes")
                    return resp.status, resp.headers, body, url
            except urllib.error.HTTPError as err:
                status = err.code
                headers = err.headers
                try:
                    err.read(1024)
                except Exception:  # pragma: no cover - body irrelevant
                    pass
                err.close()
                if status in (301, 302, 303, 307, 308):
                    return status, headers, b"", url
                remaining = headers.get("X-RateLimit-Remaining") if headers else None
                retry_after = headers.get("Retry-After") if headers else None
                if status == 429 or (status == 403 and (remaining == "0" or retry_after)):
                    wait = self._rate_wait(headers)
                    last_error = f"HTTP {status} rate limited (remaining={remaining}, retry-after={retry_after})"
                    if wait is None:
                        raise BuildError(f"{last_error} at {self._redact(url)}; reset too far away, failing instead of waiting")
                elif 500 <= status < 600:
                    last_error = f"HTTP {status}"
                    wait = float(2 ** attempt)
                else:
                    raise BuildError(f"HTTP {status} from {self._redact(url)}")
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, http.client.HTTPException) as err:
                last_error = f"network error: {getattr(err, 'reason', err)}"
                wait = float(2 ** attempt)
            if attempt < MAX_RETRIES:
                self.log(f"retry {attempt + 1}/{MAX_RETRIES} for {self._redact(url)} after {last_error}")
                time.sleep(min(wait or 0.0, MAX_RATE_WAIT_SECONDS))
        raise BuildError(f"{last_error} from {self._redact(url)} after {MAX_RETRIES + 1} attempts")

    @staticmethod
    def _rate_wait(headers) -> Optional[float]:
        retry_after = headers.get("Retry-After") if headers else None
        if retry_after is not None:
            try:
                value = float(retry_after)
            except ValueError:
                return None
            return value if 0 <= value <= MAX_RATE_WAIT_SECONDS else None
        reset = headers.get("X-RateLimit-Reset") if headers else None
        try:
            delta = float(reset) - time.time() if reset is not None else None
        except ValueError:
            return None
        if delta is not None and delta <= MAX_RATE_WAIT_SECONDS:
            return max(delta, 0.0)
        return None

    def _redact(self, url: str) -> str:
        return urllib.parse.urlsplit(url)._replace(query="").geturl()

    # -- JSON API ----------------------------------------------------------
    def get_json(self, path_and_query: str) -> Tuple[Any, Any]:
        url = self.api + path_and_query
        status, headers, body, _ = self._open(url, "application/vnd.github+json", True, MAX_JSON_BYTES)
        if status != 200:
            raise BuildError(f"unexpected HTTP {status} from {self._redact(url)}")
        ctype = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise BuildError(f"non-JSON content type {ctype!r} from {self._redact(url)}")
        try:
            return json.loads(body.decode("utf-8")), headers
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise BuildError(f"malformed/truncated JSON from {self._redact(url)}: {err}") from None

    def paginate(self, path: str, query: Dict[str, str]) -> List[Any]:
        items: List[Any] = []
        query = dict(query, per_page="100", page="1")
        next_path = f"{path}?{urllib.parse.urlencode(query)}"
        for page in range(1, MAX_PAGES + 1):
            data, headers = self.get_json(next_path)
            if not isinstance(data, list):
                raise BuildError(f"expected a JSON list from {path} page {page}, got {type(data).__name__}")
            items.extend(data)
            if len(items) > MAX_ITEMS:
                raise BuildError(f"{path} exceeded {MAX_ITEMS} items; refusing truncated catalogue")
            nxt = self._next_link(headers.get("Link") or "", path)
            if nxt is None:
                return items
            next_path = nxt
        raise BuildError(f"{path} exceeded {MAX_PAGES} pages; refusing truncated catalogue")

    def _next_link(self, link_header: str, path: str) -> Optional[str]:
        for part in link_header.split(","):
            m = re.match(r'\s*<([^>]+)>\s*;\s*rel="([^"]+)"', part)
            if not m or "next" not in m.group(2).split():
                continue
            target = urllib.parse.urlsplit(m.group(1))
            if (target.scheme, target.netloc) != (self.api_parts.scheme, self.api_parts.netloc) or target.path != path:
                raise BuildError(f"refusing pagination link to foreign location {m.group(1)!r}")
            return f"{target.path}?{target.query}"
        return None

    # -- small manifest download -------------------------------------------
    def download_asset(self, org: str, repo: str, asset_id: int) -> bytes:
        url = f"{self.api}/repos/{org}/{repo}/releases/assets/{asset_id}"
        send_token = True
        for _ in range(MAX_REDIRECTS + 1):
            status, headers, body, _ = self._open(url, "application/octet-stream", send_token, MAX_MANIFEST_BYTES)
            if status == 200:
                return body
            if status in (301, 302, 303, 307, 308):
                location = headers.get("Location") or ""
                target = urllib.parse.urljoin(url, location)
                parts = urllib.parse.urlsplit(target)
                allowed = (parts.scheme == "https" and parts.hostname in REDIRECT_HOSTS) or (
                    self.loopback and parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS)
                if not allowed:
                    raise BuildError(f"refusing manifest redirect to {parts.scheme}://{parts.hostname}")
                send_token = False  # credentials never leave the API origin
                url = target
                continue
            raise BuildError(f"unexpected HTTP {status} downloading manifest asset {asset_id}")
        raise BuildError(f"too many redirects downloading manifest asset {asset_id}")


# ---------------------------------------------------------------------------
# Release evaluation
# ---------------------------------------------------------------------------

def _require(obj: Any, key: str, kind, where: str):
    if not isinstance(obj, dict) or key not in obj or not isinstance(obj[key], kind) or isinstance(obj[key], bool) and kind is not bool:
        raise BuildError(f"malformed API data: {where} missing/invalid {key!r}")
    return obj[key]


def parse_sums(text: str) -> Dict[str, str]:
    sums: Dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([0-9a-f]{64}) [ *]([^\s/\\]+)$", line)
        if not m or m.group(2) in sums:
            raise ValueError(f"malformed SHA256SUMS line {line[:80]!r}")
        sums[m.group(2)] = m.group(1)
    return sums


def evaluate_repo(org: str, repo: str, releases: List[Any], client: GitHubClient) -> Dict[str, Any]:
    """Return one catalogue entry. Raise BuildError only for incomplete/malformed data."""
    entry: Dict[str, Any] = {"status": "source-only", "reason": None, "release": None, "install": None,
                             "integrity": None}
    stable = []
    bad_tags = []
    for i, rel in enumerate(releases):
        where = f"{repo} release[{i}]"
        tag = _require(rel, "tag_name", str, where)
        draft = _require(rel, "draft", bool, where)
        pre = _require(rel, "prerelease", bool, where)
        _require(rel, "assets", list, where)
        if draft or pre or not isinstance(rel.get("published_at"), str):
            continue
        if not TAG_RE.match(tag):
            bad_tags.append(tag)
            continue
        stable.append(rel)
    if bad_tags:
        entry["reason"] = ("Published stable release tag(s) are not strict vMAJOR.MINOR.PATCH "
                           f"({', '.join(clean_text(t, 40) for t in bad_tags[:3])}); latest version is ambiguous.")
        return entry
    if not stable:
        entry["reason"] = ("No published stable release (drafts and prereleases are never offered)."
                           if releases else "No published release yet (source / work in progress).")
        return entry
    rel = max(stable, key=lambda r: semver_key(r["tag_name"]))
    tag = rel["tag_name"]
    release_url = f"https://github.com/{org}/{repo}/releases/tag/{tag}"
    entry["release"] = {
        "tag": tag,
        "name": clean_text(rel.get("name"), 120) or tag,
        "published_at": clean_text(rel.get("published_at"), 40),
        "html_url": release_url,
        "notes_excerpt": clean_text(rel.get("body"), 600),
        "github_immutable_release": rel.get("immutable") if isinstance(rel.get("immutable"), bool) else None,
    }
    if rel.get("html_url") != release_url:
        entry["release"]["html_url"] = None
        entry["reason"] = "Release page URL in API data is not the expected GitHub URL; links suppressed."
        return entry

    expected = f"{repo}.cia"
    assets = rel["assets"]
    for j, asset in enumerate(assets):
        _require(asset, "name", str, f"{repo} {tag} asset[{j}]")
    cia_like = [a for a in assets if a["name"].lower().endswith(".cia")]
    exact = [a for a in assets if a["name"] == expected]
    if not exact:
        entry["reason"] = f"Latest stable release {tag} has no {expected} asset."
        return entry
    if len(exact) != 1 or len(cia_like) != 1:
        names = ", ".join(clean_text(a["name"], 60) for a in cia_like[:4])
        entry["reason"] = f"Latest stable release {tag} has ambiguous CIA assets ({names}); refusing to guess."
        return entry
    asset = exact[0]
    url = asset.get("browser_download_url")
    size = asset.get("size")
    want = expected_cia_url(org, repo, tag)
    if url != want:
        entry["reason"] = (f"{expected} download URL is not the direct versioned GitHub release URL; "
                           "refusing foreign, redirecting or page links.")
        return entry
    if asset.get("state") != "uploaded" or not isinstance(size, int) or isinstance(size, bool) \
            or not 0 < size < MAX_CIA_BYTES:
        entry["reason"] = f"{expected} is not a completely uploaded, plausibly sized file."
        return entry
    ctype = str(asset.get("content_type") or "").lower()
    if ctype.startswith("text/") or "html" in ctype:
        entry["reason"] = f"{expected} is labelled {clean_text(ctype, 40)!r}, not a binary CIA."
        return entry
    digest = asset.get("digest")
    api_sha = None
    if isinstance(digest, str) and digest.startswith("sha256:") and SHA256_RE.match(digest[7:]):
        api_sha = digest[7:]
    elif digest is not None:
        entry["reason"] = f"{expected} has a malformed GitHub digest; refusing."
        return entry

    integrity, problem = evaluate_integrity(org, repo, tag, assets, size, api_sha, client)
    if problem:
        entry["reason"] = problem
        return entry
    entry["status"] = "published"
    entry["install"] = {"cia_name": expected, "cia_url": want, "size": size, "github_sha256": api_sha}
    entry["integrity"] = integrity
    return entry


def evaluate_integrity(org, repo, tag, assets, cia_size, api_sha, client) -> Tuple[Dict[str, Any], Optional[str]]:
    by_name = {a["name"]: a for a in assets}
    sums_asset = by_name.get("SHA256SUMS")
    manifest_asset = by_name.get("release.json")
    if sums_asset is None and manifest_asset is None:
        summary = ("Legacy release: no SHA256SUMS or release.json manifest was published. "
                   + ("GitHub reports the file's SHA-256 shown here." if api_sha else
                      "No checksum is available from GitHub either."))
        return {"level": "legacy-no-manifest", "summary": summary, "sha256": api_sha,
                "source_sha": None, "manifest_urls": None}, None
    if sums_asset is None or manifest_asset is None:
        missing = "SHA256SUMS" if sums_asset is None else "release.json"
        return {}, f"Release {tag} has an incomplete integrity manifest (missing {missing}); refusing install link."
    for asset in (sums_asset, manifest_asset):
        if asset.get("browser_download_url") != expected_asset_url(org, repo, tag, asset["name"]) \
                or not isinstance(asset.get("id"), int) or isinstance(asset.get("id"), bool):
            return {}, f"{asset['name']} metadata is not a direct versioned GitHub asset; refusing."
    try:
        sums = parse_sums(client.download_asset(org, repo, sums_asset["id"]).decode("utf-8"))
        manifest = json.loads(client.download_asset(org, repo, manifest_asset["id"]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as err:
        return {}, f"Release {tag} integrity manifest is malformed ({clean_text(str(err), 80)})."
    cia_name = f"{repo}.cia"
    problems = []
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        problems.append("release.json schema is not 1")
        manifest = manifest if isinstance(manifest, dict) else {}
    if manifest.get("repo") != repo:
        problems.append("release.json repo mismatch")
    if manifest.get("tag") != tag:
        problems.append("release.json tag mismatch")
    source_sha = manifest.get("source_sha")
    if not (isinstance(source_sha, str) and GIT_SHA_RE.match(source_sha)):
        problems.append("release.json source_sha is not a full commit SHA")
    entries = [a for a in manifest.get("assets", []) if isinstance(a, dict) and a.get("name") == cia_name] \
        if isinstance(manifest.get("assets"), list) else []
    if len(entries) != 1:
        problems.append(f"release.json lists {len(entries)} {cia_name} entries")
    else:
        m_sha = entries[0].get("sha256")
        if entries[0].get("size") != cia_size:
            problems.append("release.json size differs from uploaded asset")
        if not (isinstance(m_sha, str) and SHA256_RE.match(m_sha)):
            problems.append("release.json sha256 malformed")
        elif sums.get(cia_name) != m_sha:
            problems.append("SHA256SUMS and release.json disagree")
        elif api_sha and api_sha != m_sha:
            problems.append("GitHub asset digest differs from manifests")
    if problems:
        return {}, f"Release {tag} integrity manifests contradict the asset: {'; '.join(problems)}."
    return {"level": "manifest", "summary": "SHA256SUMS and release.json published and consistent with the uploaded CIA.",
            "sha256": sums[cia_name], "source_sha": source_sha,
            "manifest_urls": {"SHA256SUMS": expected_asset_url(org, repo, tag, "SHA256SUMS"),
                              "release.json": expected_asset_url(org, repo, tag, "release.json")}}, None


def discover(org: str, client: GitHubClient, minimum_repositories: int) -> List[Dict[str, Any]]:
    raw = client.paginate(f"/orgs/{org}/repos", {"type": "public"})
    selected = []
    seen = set()
    for i, repo in enumerate(raw):
        where = f"repository[{i}]"
        name = _require(repo, "name", str, where)
        private = _require(repo, "private", bool, where)
        archived = _require(repo, "archived", bool, where)
        owner = _require(_require(repo, "owner", dict, where), "login", str, where + ".owner")
        if not name.startswith("3ds_") or name.lower() == "3ds_hub" or private or archived:
            continue
        if repo.get("visibility") not in (None, "public"):
            continue
        if owner.lower() != org.lower():
            raise BuildError(f"API listed {name!r} owned by {owner!r} under org {org!r}")
        if not REPO_RE.match(name):
            raise BuildError(f"repository name {name!r} is outside the safe 3ds_* pattern")
        if name.lower() in seen:
            raise BuildError(f"duplicate repository {name!r} in listing")
        seen.add(name.lower())
        selected.append(repo)
    if len(selected) < max(1, minimum_repositories):
        raise BuildError(f"discovered {len(selected)} homebrew repositories (< {max(1, minimum_repositories)}); "
                         "refusing a false empty/partial catalogue")
    apps = []
    for repo in sorted(selected, key=lambda r: r["name"].lower()):
        name = repo["name"]
        releases = client.paginate(f"/repos/{org}/{name}/releases", {})
        entry = evaluate_repo(org, name, releases, client)
        source_url = f"https://github.com/{org}/{name}"
        if repo.get("html_url") != source_url:
            raise BuildError(f"API html_url for {name} is not {source_url}")
        entry.update({
            "repo": name,
            "title": display_name(name),
            "description": clean_text(repo.get("description"), 280),
            "source_url": source_url,
            "tiers": {
                "published": entry["status"] == "published",
                "reviewed": "not certified by this catalogue",
                "ci_executed": "not certified by this catalogue",
                "physically_tested": "not observed by this catalogue",
            },
        })
        apps.append(entry)
    return apps


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def load_encoder():
    spec = importlib.util.spec_from_file_location("serve_3ds_readonly", ROOT / "serve_3ds.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def h(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def initials_icon(repo: str) -> str:
    """Original procedural badge: two letters on a colour derived from the repo name."""
    stem = re.sub(r"[^A-Za-z0-9]", "", repo[4:]) or "app"
    letters = (stem[0] + (stem[1] if len(stem) > 1 else "")).upper()
    digest = hashlib.sha256(repo.encode()).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    return (f'<svg class="icon" aria-hidden="true" focusable="false" viewBox="0 0 48 48" width="48" height="48">'
            f'<rect width="48" height="48" rx="10" fill="hsl({hue},55%,30%)"/>'
            f'<text x="24" y="31" text-anchor="middle" font-family="system-ui,sans-serif" font-size="20" '
            f'font-weight="700" fill="#ffffff">{h(letters)}</text></svg>')


def render_card(app: Dict[str, Any], base: str) -> str:
    repo = app["repo"]
    parts = [f'<article class="card {"published" if app["install"] else "source-only"}" id="app-{h(repo)}" '
             f'aria-labelledby="t-{h(repo)}">',
             f'<header class="card-head">{initials_icon(repo)}<div><h3 id="t-{h(repo)}">{h(app["title"])}</h3>'
             f'<p class="repo"><code>{h(repo)}</code></p></div></header>']
    if app["description"]:
        parts.append(f'<p class="desc">{h(app["description"])}</p>')
    rel = app["release"]
    if app["install"]:
        inst = app["install"]
        integ = app["integrity"]
        parts.append('<p class="badge ok">Published stable release — installable via FBI</p>')
        parts.append(
            f'<figure class="qr"><img src="{h(base + inst["qr_svg"])}" width="{inst["qr_pixels"]}" '
            f'height="{inst["qr_pixels"]}" alt="QR code for FBI Remote Install of {h(repo)} {h(rel["tag"])}. '
            f'It encodes {h(inst["cia_url"])}">'
            f'<figcaption>Scan with FBI → Remote Install → Scan QR Code. Encodes:<br>'
            f'<code class="url">{h(inst["cia_url"])}</code></figcaption></figure>')
        parts.append(f'<p><a class="install" href="{h(inst["cia_url"])}" rel="noopener">Download '
                     f'{h(inst["cia_name"])} ({h(human_size(inst["size"]))})</a></p>')
        facts = [("Version", f'<code>{h(rel["tag"])}</code> — {h(rel["name"])}'),
                 ("Published", f'<time datetime="{h(rel["published_at"])}">{h(rel["published_at"])}</time>'),
                 ("Size", f'{inst["size"]:,} bytes'),
                 ("Integrity", h(integ["summary"]) + (f'<br>SHA-256 <code class="hash">{h(integ["sha256"])}</code>'
                                                      if integ.get("sha256") else "")
                  + (f'<br>Built from <code class="hash">{h(integ["source_sha"])}</code> · '
                     f'<a href="{h(integ["manifest_urls"]["SHA256SUMS"])}">SHA256SUMS</a> · '
                     f'<a href="{h(integ["manifest_urls"]["release.json"])}">release.json</a>'
                     if integ.get("manifest_urls") else "")),
                 ("GitHub immutable release", {True: "yes", False: "no", None: "unknown"}[rel["github_immutable_release"]]),
                 ("Status", "Published. Not certified here as reviewed, CI-executed or physically tested on a console."),
                 ("Release notes", f'<a href="{h(rel["html_url"])}">{h(rel["tag"])} release notes</a>'),
                 ("Source", f'<a href="{h(app["source_url"])}">{h(app["source_url"])}</a>')]
        parts.append('<dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl>")
        if rel["notes_excerpt"]:
            parts.append(f'<details><summary>Release notes excerpt</summary><p class="notes">'
                         f'{h(rel["notes_excerpt"])}</p></details>')
    else:
        parts.append('<p class="badge wip">Source only — no install offered</p>')
        parts.append(f'<p class="reason"><strong>Why:</strong> {h(app["reason"])}</p>')
        facts = []
        if rel and rel.get("html_url"):
            facts.append(("Latest stable", f'<a href="{h(rel["html_url"])}">{h(rel["tag"])}</a>'))
        facts.append(("Source", f'<a href="{h(app["source_url"])}">{h(app["source_url"])}</a>'))
        parts.append('<dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl>")
    parts.append("</article>")
    return "".join(parts)


def render_index(catalog: Dict[str, Any]) -> str:
    base = catalog["base_path"]
    apps = catalog["apps"]
    installs = [a for a in apps if a["install"]]
    sources = [a for a in apps if not a["install"]]
    nav = "".join(f'<li><a href="#app-{h(a["repo"])}">{h(a["title"])}</a>'
                  f'{" (install)" if a["install"] else " (source)"}</li>' for a in apps)
    org = catalog["organization"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>{h(org)} 3DS homebrew — FBI QR install hub</title>
<link rel="stylesheet" href="{h(base)}style.css">
<link rel="icon" href="{h(base)}favicon.svg" type="image/svg+xml">
</head>
<body>
<a class="skip" href="#apps">Skip to apps</a>
<header class="top">
<h1>{h(org)} 3DS homebrew — FBI install hub</h1>
<p>Each installable card shows a QR code and a download button that point to the <strong>same</strong> direct, versioned
<code>.cia</code> file on GitHub Releases. Nothing here needs JavaScript, an account or a PC.</p>
<p class="meta">Catalogue generated <time datetime="{h(catalog["generated_utc"])}">{h(catalog["generated_utc"])}</time>
from the public GitHub API: {len(apps)} repositories, {len(installs)} installable, {len(sources)} source-only.
New releases appear at the next scheduled rebuild (hourly), not instantly.
<a href="{h(base)}catalog.json">Machine-readable catalogue</a>.</p>
</header>
<main>
<section class="howto" aria-labelledby="howto">
<h2 id="howto">Install, update, back up, roll back</h2>
<ol>
<li><strong>Install:</strong> on a 3DS running custom firmware, open <strong>FBI</strong> → <strong>Remote Install</strong> →
<strong>Scan QR Code</strong>, point the camera at the app's QR code and confirm. Or download the <code>.cia</code> on a computer,
copy it to the SD card and install it with FBI.</li>
<li><strong>Back up first:</strong> before updating or removing an app, back up its save data with a save manager
(for example Checkpoint) and keep a copy of the <code>.cia</code> you have installed.</li>
<li><strong>Update:</strong> when a newer version appears here, scan its QR code; it installs over the same title.</li>
<li><strong>Roll back:</strong> every version keeps its own versioned download URL on the app's Releases page. Install the older
<code>.cia</code> the same way; if FBI refuses, delete the title in FBI first, reinstall, then restore your save backup.</li>
</ol>
<p class="tiers"><strong>What “Published” means:</strong> the file is a public, stable, non-draft GitHub release asset with the
expected name. It does <em>not</em> mean the release was independently reviewed, built by CI, or tested on real hardware;
this page does not certify those. Use at your own risk and keep backups.</p>
</section>
<nav aria-labelledby="jump"><h2 id="jump">Apps</h2><p class="hint">Use your browser's find-in-page to search.</p><ul class="jump">{nav}</ul></nav>
<section id="apps" aria-label="Applications">
<h2>Installable releases</h2>
<div class="grid">{"".join(render_card(a, base) for a in installs) or '<p>No installable release found.</p>'}</div>
<h2>Source-only and work-in-progress</h2>
<div class="grid">{"".join(render_card(a, base) for a in sources) or '<p>None.</p>'}</div>
</section>
</main>
<footer><p>Static page built by <code>tools/build_catalog.py</code> in
<a href="https://github.com/{h(org)}/3ds_hub">{h(org)}/3ds_hub</a>{(" at <code>" + h(catalog["hub_source_sha"]) + "</code>") if catalog["hub_source_sha"] else ""}.
Icons are generated initials. QR codes are generated locally; no third-party QR service or tracking is used.</p></footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Output (atomic, preserves previous bytes on failure)
# ---------------------------------------------------------------------------

def check_output_target(output: Path) -> Path:
    out = output.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), ROOT, SITE_SOURCE.resolve(),
                 (ROOT / "tools").resolve(), (ROOT / "tests").resolve(), (ROOT / ".github").resolve()}
    if out in forbidden or out in ROOT.parents or out.name in ("", ".", ".."):
        raise BuildError(f"refusing to use {output} as output directory")
    if out.exists() or out.is_symlink():
        if out.is_symlink() or not out.is_dir():
            raise BuildError(f"output {output} exists and is not a plain directory")
        if any(out.iterdir()) and not (out / MARKER).is_file():
            raise BuildError(f"output {output} is a non-empty directory not created by this builder; refusing to replace it")
    return out


def write_site(catalog: Dict[str, Any], qr_files: Dict[str, str], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{out.name}.tmp-", dir=out.parent))
    try:
        (tmp / "qr").mkdir()
        for rel_path, svg in qr_files.items():
            (tmp / rel_path).write_text(svg, encoding="utf-8")
        for name in STATIC_FILES:
            shutil.copyfile(SITE_SOURCE / name, tmp / name)
        (tmp / "catalog.json").write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (tmp / "index.html").write_text(render_index(catalog), encoding="utf-8")
        (tmp / MARKER).write_text(json.dumps({"generated_utc": catalog["generated_utc"]}) + "\n", encoding="utf-8")
        old = None
        if out.exists():
            old = out.parent / f".{out.name}.old-{os.getpid()}"
            os.rename(out, old)
        try:
            os.rename(tmp, out)
        except OSError:
            if old is not None:
                os.rename(old, out)
            raise
        if old is not None:
            shutil.rmtree(old)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def build(args) -> Dict[str, Any]:
    if not ORG_RE.match(args.organization):
        raise BuildError(f"invalid organization {args.organization!r}")
    base = validate_base_path(args.base_path)
    api = validate_api_url(args.api_url)
    if not 0 < args.timeout <= MAX_TIMEOUT_SECONDS:
        raise BuildError(f"--timeout must be in (0, {MAX_TIMEOUT_SECONDS:g}] seconds")
    out = check_output_target(Path(args.output))
    token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    client = GitHubClient(api, token, args.timeout)
    apps = discover(args.organization, client, args.minimum_repositories)

    encoder = load_encoder()
    qr_files: Dict[str, str] = {}
    for app in apps:
        if not app["install"]:
            continue
        url = app["install"]["cia_url"]
        try:
            matrix = encoder.encode_qr_matrix(url)
        except ValueError as err:
            app.update(status="source-only", install=None, integrity=None,
                       reason=f"Download URL too long for the hub QR encoder ({err}).")
            app["tiers"]["published"] = False
            continue
        svg = encoder.render_qr_svg(matrix, border=QR_BORDER, scale=QR_SCALE)
        rel_path = f"qr/{app['repo']}-{app['release']['tag']}.svg"
        qr_files[rel_path] = svg
        app["install"].update(qr_svg=rel_path, qr_modules=len(matrix), qr_quiet_zone_modules=QR_BORDER,
                              qr_pixels=(len(matrix) + 2 * QR_BORDER) * QR_SCALE)

    hub_sha = os.environ.get("GITHUB_SHA", "").strip()
    catalog = {
        "schema": SCHEMA,
        "generated_utc": utc_now(),
        "organization": args.organization,
        "base_path": base,
        "hub_source_sha": hub_sha if GIT_SHA_RE.match(hub_sha) else None,
        "source": {"api": "GitHub REST API (build time only)", "requests": client.requests,
                   "repositories": len(apps), "authenticated": bool(token)},
        "qr_encoder": {"module": "serve_3ds.py", "functions": ["encode_qr_matrix", "render_qr_svg"],
                       "sha256": hashlib.sha256((ROOT / "serve_3ds.py").read_bytes()).hexdigest()},
        "policy": ("Install controls only for the highest published, non-draft, non-prerelease vX.Y.Z release with exactly "
                   "one <repo>.cia at its direct versioned GitHub download URL. QR payload == href == install.cia_url."),
        "apps": apps,
    }
    blob = json.dumps(catalog)
    if token and token in blob:  # defence in depth: never ship the credential
        raise BuildError("credential material found in catalogue output")
    write_site(catalog, qr_files, out)
    if token:
        for path in out.rglob("*"):
            if path.is_file() and token.encode() in path.read_bytes():
                raise BuildError("credential material found in written output")
    return catalog


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--organization", required=True, help="GitHub organization, e.g. lafiabrew")
    parser.add_argument("--output", required=True, help="output directory (replaced atomically on success only)")
    parser.add_argument("--base-path", required=True, help="site path prefix, e.g. /3ds_hub/")
    parser.add_argument("--api-url", default=PRODUCTION_API,
                        help=f"API origin (default {PRODUCTION_API}; loopback http allowed for tests only)")
    parser.add_argument("--timeout", type=float, default=MAX_TIMEOUT_SECONDS,
                        help=f"per-request timeout seconds, at most {MAX_TIMEOUT_SECONDS:g}")
    parser.add_argument("--minimum-repositories", type=int, default=1,
                        help="fail if fewer homebrew repositories are discovered (default 1; never 0)")
    args = parser.parse_args(argv)
    try:
        catalog = build(args)
    except BuildError as err:
        print(f"catalogue build FAILED: {err}. Previous output (if any) left unchanged.", file=sys.stderr)
        return 1
    installs = sum(1 for a in catalog["apps"] if a["install"])
    print(f"catalogue built: {len(catalog['apps'])} repositories, {installs} installable, "
          f"{len(catalog['apps']) - installs} source-only, {catalog['source']['requests']} API requests -> {args.output}")
    for app in catalog["apps"]:
        detail = app["install"]["cia_url"] if app["install"] else f"source-only: {app['reason']}"
        print(f"  {app['repo']}: {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
