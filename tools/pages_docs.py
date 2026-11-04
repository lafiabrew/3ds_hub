"""Shared, fail-closed publication policy for 3DS documentation (stdlib only)."""
from __future__ import annotations
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "site/docs-manifest.json"
ASSETS = {"assets/css/style.css", "assets/js/mermaid-loader.js",
          "assets/vendor/mermaid-11.12.2.min.js", "assets/vendor/MERMAID-LICENSE"}
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
EXAMPLES = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def findings(text: str) -> list[dict]:
    found = []
    for match in IPV4.finditer(text):
        try:
            address = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if address.is_loopback or address.is_unspecified or any(address in net for net in EXAMPLES):
            continue
        found.append({"line": text.count("\n", 0, match.start()) + 1,
                      "fingerprint": hashlib.sha256(match.group().encode()).hexdigest()[:12]})
    return found


def inventory(root: Path = ROOT) -> list[str]:
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
    return sorted(set(p for p in names if p.endswith(".md") and
                      not any(part.startswith(".") or part == "scenarios" for part in Path(p).parts)))


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise ValueError("unsafe publication path")
    if any(part in ("", ".", "..") for part in value.rstrip("/").split("/")):
        raise ValueError("unsafe publication path")
    return value


def output_path(route: str) -> str:
    safe_relative(route)
    return route + "index.html" if route.endswith("/") else route


def load_manifest(root: Path = ROOT, *, check_inventory: bool = True) -> dict:
    manifest = json.loads((root / "site/docs-manifest.json").read_text())
    if set(manifest) != {"schema", "base_path", "pages", "assets", "source_only"} or manifest["schema"] != "3ds-docs-manifest-v1":
        raise ValueError("unsupported docs manifest")
    if manifest["base_path"] != "/3ds_hub/" or not isinstance(manifest["pages"], dict):
        raise ValueError("unexpected docs base path/pages")
    pages = manifest["pages"]
    outputs = []
    for source, route in pages.items():
        safe_relative(source)
        output = output_path(route)
        if not source.startswith(("docs/", "specs/")) or not source.endswith(".md"):
            raise ValueError("only docs/specs Markdown can be published")
        if not output.startswith(("docs/", "specs/")) or not output.endswith(".html"):
            raise ValueError("docs output must be namespaced HTML")
        outputs.append(output)
    if pages.get("docs/STATUS.md") != "docs/STATUS.html" or pages.get("docs/README.md") != "docs/":
        raise ValueError("required safety/index route missing")
    assets = manifest["assets"]
    only = manifest["source_only"]
    if not isinstance(assets, list) or set(assets) != ASSETS or len(assets) != len(ASSETS):
        raise ValueError("unexpected docs asset allowlist")
    if not isinstance(only, list) or len(only) != len(set(only)):
        raise ValueError("invalid source-only classification")
    for source in only:
        safe_relative(source)
        if source in pages or source.startswith(("docs/", "specs/")):
            raise ValueError("published guides cannot be hidden as source-only")
    if len(outputs) != len(set(outputs)):
        raise ValueError("duplicate docs output route")
    if check_inventory:
        sources = set(inventory(root))
        if sources != set(pages) | set(only):
            raise ValueError("Markdown inventory differs from reviewed publication classification")
    manifest["outputs"] = sorted(outputs + assets)
    return manifest
