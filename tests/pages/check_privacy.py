#!/usr/bin/env python3
"""Check every public-source Markdown file and its explicit publication scope.

This does not erase Git history/caches, inspect holdouts, or certify every kind
of personal identifier. Only reviewed manifest routes may be called published.
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from pages_docs import findings, inventory, load_manifest


def main():
    bad = "http://" + ".".join(["10", "23", "42", "99"]) + ":8766"
    assert findings(bad), "identifying-host mutant survived"
    assert not findings("http://127.0.0.1:8765 http://0.0.0.0:0 http://192.0.2.1:8766")
    try:
        manifest = load_manifest(ROOT)
    except (ValueError, KeyError, TypeError) as error:
        print(json.dumps({"pass": False, "manifest_error": str(error)}))
        return 1
    records = []
    for source in inventory(ROOT):
        text = (ROOT / source).read_text()
        records.append({"source": source, "route": manifest["pages"].get(source),
                        "publication": "page" if source in manifest["pages"] else "source-only",
                        "mermaid_blocks": len(re.findall(r"^```mermaid\s*$", text, re.M)),
                        "findings": findings(text)})
    result = {"pass": all(not item["findings"] for item in records), "inventory": records,
              "base_path": manifest["base_path"], "identifying_host_mutant_rejected": True,
              "standards_controls_passed": True,
              "scope": "tracked/new non-hidden Markdown, explicit source-only classification; no history/cache claim"}
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
