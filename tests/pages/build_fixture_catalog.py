#!/usr/bin/env python3
"""Drive the production catalogue builder through the existing captured API transport.

Offline protocol evidence only; not a current public-release or binary check.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--output", type=Path, required=True)
args = p.parse_args()
spec = importlib.util.spec_from_file_location("pages_catalog_fixture", ROOT / "tests/test_catalog.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
api = module.FakeGitHub()
try:
    env = dict(os.environ, GITHUB_TOKEN="", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, str(ROOT / "tools/build_catalog.py"), "--organization", "lafiabrew",
                             "--output", str(args.output), "--base-path", "/3ds_hub/", "--api-url", api.url],
                            cwd=ROOT, env=env, timeout=90)
    raise SystemExit(result.returncode)
finally:
    api.close()
