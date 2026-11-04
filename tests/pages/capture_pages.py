#!/usr/bin/env python3
"""Capture real Pages HTML/theme bytes for browser integration, outside the repo.

Captured old HTML may contain identifying examples. Never commit or publish it.
No capture substitutes for --live-url deployment verification.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--out", type=Path, required=True)
args = p.parse_args()
out = args.out.resolve()
if out == ROOT or ROOT in out.parents:
    p.error("capture directory must be outside the public source checkout")
base = "https://lafiabrew.github.io/3ds_hub/"
files = {"index.html": base, "docs/ARCHITECTURE.html": base + "docs/ARCHITECTURE.html",
         "docs/AGENT_PLAYBOOK.html": base + "docs/AGENT_PLAYBOOK.html",
         "docs/SOP.html": base + "docs/SOP.html", "style.css": base + "assets/css/style.css",
         "anchor.min.js": "https://cdnjs.cloudflare.com/ajax/libs/anchor-js/4.1.0/anchor.min.js"}
if any((out / name).exists() for name in [*files, "capture-manifest.json"]):
    p.error("use a new capture directory; existing captures may be evidence")
manifest = {"observed_utc": datetime.now(timezone.utc).isoformat(), "resources": []}
for name, url in files.items():
    with urllib.request.urlopen(url, timeout=25) as response:
        data = response.read()
        if response.status != 200:
            raise RuntimeError("Unexpected capture response")
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    manifest["resources"].append({"file": name, "url": url, "sha256": hashlib.sha256(data).hexdigest()})
(out / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Captured six production/theme resources outside the checkout; no publication performed.")
