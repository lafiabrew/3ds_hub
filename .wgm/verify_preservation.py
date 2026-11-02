#!/usr/bin/env python3
"""Validate this run against its private, hashes-only local baseline snapshot."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BASE = json.loads((ROOT / ".wgm/privacy-baseline.json").read_text())
ALLOWED = {"AGENTS.md", "README.md", "Makefile", "serve_3ds.py", "IMPLEMENTATION_PLAN.md", "specs/CONSTITUTION.md", "docs/audit/2026-11-02_3ds-homebrew-suite-audit.md", ".gitignore"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for name, digest in BASE["diagnostics"].items():
        assert sha(ROOT / name) == digest, f"Diagnostic altered: {name}"
    for repo, record in BASE["repos"].items():
        for name, digest in record["files"].items():
            if repo == "." and name in ALLOWED:
                continue
            assert sha(ROOT / repo / name) == digest, f"Unrelated file changed: {repo}/{name}"
        changed = subprocess.check_output(["git", "-C", str(ROOT / repo), "diff", record["head"], "--name-only"]).decode().splitlines()
        allowed = ALLOWED if repo == "." else {".github/wgm-hive.yml"}
        assert all(name in allowed or (repo == "." and name.startswith(".wgm/")) for name in changed), f"Out-of-scope change in {repo}"
        subprocess.run(["git", "-C", str(ROOT / repo), "merge-base", "--is-ancestor", record["head"], "HEAD"], check=True)
    tree = ast.parse((ROOT / "serve_3ds.py").read_text())
    if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        tree.body.pop(0)
    digest = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    assert digest == BASE["server_ast"], "Executable server code changed"
    readme = (ROOT / "README.md").read_text()
    assert "https://github.com/orgs/lafiabrew/repositories" in readme, "Project link removed"
    listed = subprocess.check_output(["python3", str(ROOT / "serve_3ds.py"), "--list"], text=True, cwd=ROOT)
    for repo in BASE["repos"]:
        if repo != ".":
            assert repo in listed, f"App missing from discovery: {repo}"
    print("PASS: diagnostic hashes, executable AST, all eight discovered apps, attribution/tests, nested product files, and ancestor history preserved")


if __name__ == "__main__":
    main()
