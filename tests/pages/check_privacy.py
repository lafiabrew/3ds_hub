#!/usr/bin/env python3
"""Inventory public Markdown and reject identifying IPv4 literals without echoing them.

This checks current source, not old Git history, caches, credentials or every
possible identifier. Loopback/listener and RFC 5737 documentation ranges pass.
"""
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
EXAMPLES = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def findings(text):
    found = []
    for match in PATTERN.finditer(text):
        try:
            address = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if address.is_loopback or address.is_unspecified or any(address in net for net in EXAMPLES):
            continue
        found.append({"line": text.count("\n", 0, match.start()) + 1,
                      "fingerprint": hashlib.sha256(match.group().encode()).hexdigest()[:12]})
    return found


def inventory():
    tracked = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    return sorted(p for p in tracked if p.endswith(".md") and
                  not any(part.startswith(".") or part == "scenarios" for part in Path(p).parts))


def route(path):
    p = Path(path)
    if p.name.lower() == "readme.md":
        return "/" if p.parent == Path(".") else str(p.parent) + "/"
    return str(p.with_suffix(".html"))


def main():
    # Reject an identifying-host mutant; positive standards examples prevent blanket rejection.
    bad = "http://" + ".".join(["10", "23", "42", "99"]) + ":8766"
    assert findings(bad), "identifying-host mutant survived"
    assert not findings("http://127.0.0.1:8765 http://0.0.0.0:0 http://192.0.2.1:8766")
    records = [{"source": path, "route": route(path), "mermaid_blocks": len(re.findall(r"^```mermaid\s*$", (ROOT / path).read_text(), re.M)), "findings": findings((ROOT / path).read_text())}
               for path in inventory()]
    result = {"pass": all(not item["findings"] for item in records), "inventory": records,
              "identifying_host_mutant_rejected": True, "standards_controls_passed": True,
              "scope": "current tracked/new non-hidden Markdown, no holdout content, no history/cache claim"}
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
