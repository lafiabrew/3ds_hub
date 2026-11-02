#!/usr/bin/env python3
"""Verify narrow root edits from Git, and local diagnostics from hashes only."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

from validate_public_hygiene import ROOT, git

BASE_REF = "ed47dbf"
AUTHORIZED_LINES = {
    "AGENTS.md": {1},
    "README.md": {1, 3},
    "Makefile": {1},
    "IMPLEMENTATION_PLAN.md": {4, 15},
    "specs/CONSTITUTION.md": {1},
    "docs/audit/2026-11-02_3ds-homebrew-suite-audit.md": {4},
}
PROSE_FILES = (*AUTHORIZED_LINES, "serve_3ds.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def server_parts(data):
    tree = ast.parse(data)
    doc = tree.body[0]
    assert (
        isinstance(doc, ast.Expr)
        and isinstance(doc.value, ast.Constant)
        and isinstance(doc.value.value, str)
    ), "Server module docstring missing"
    tree.body.pop(0)
    lines = data.splitlines(keepends=True)
    return (
        digest(ast.dump(tree, include_attributes=False).encode()),
        b"".join(lines[:doc.lineno - 1]),
        b"".join(lines[doc.end_lineno:]),
    )


def check_authorized(name, before, after):
    if name == "serve_3ds.py":
        assert server_parts(before) == server_parts(after), "Server changed outside module docstring"
        return
    original = before.splitlines(keepends=True)
    current = after.splitlines(keepends=True)
    assert len(original) == len(current), f"Line count changed: {name}"
    assert all(
        old == new or number in AUTHORIZED_LINES[name]
        for number, (old, new) in enumerate(zip(original, current), 1)
    ), f"Edit outside authorized lines: {name}"


def verify(root, baseline, base_ref=BASE_REF):
    for name, expected in baseline["diagnostics"].items():
        assert digest((root / name).read_bytes()) == expected, "Diagnostic hash changed"
    record = baseline["repos"]["."]
    for name, expected in record["files"].items():
        working = (root / name).read_bytes()
        indexed = git(root, "show", f":{name}")
        if name in PROSE_FILES:
            original = git(root, "show", f"{base_ref}:{name}")
            for data in (working, indexed):
                check_authorized(name, original, data)
        elif name == ".gitignore":
            # Planning already added the diagnostic ignore rule; preserve that state.
            assert working == indexed == git(root, "show", "HEAD:.gitignore"), "Ignore rules changed"
        else:
            assert digest(working) == digest(indexed) == expected, f"Unrelated root file changed: {name}"
    for args in (("diff", base_ref, "--name-only", "-z"), ("diff", "--cached", base_ref, "--name-only", "-z")):
        changed = git(root, *args).decode().split("\0")
        assert all(
            not name or name in PROSE_FILES or name == ".gitignore" or name.startswith(".wgm/")
            for name in changed
        ), "Out-of-scope root change"
    assert server_parts((root / "serve_3ds.py").read_bytes())[0] == baseline["server_ast"], "Executable server AST changed"
    listed = subprocess.check_output(
        ["python3", str(root / "serve_3ds.py"), "--list"], cwd=root, stderr=subprocess.PIPE,
    )
    for repo, item in baseline["repos"].items():
        location = root / repo
        subprocess.run(
            ["git", "-C", str(location), "merge-base", "--is-ancestor", item["head"], "HEAD"],
            check=True, capture_output=True,
        )
        if repo != ".":
            assert repo.encode() in listed, f"App missing from discovery: {repo}"
            changed = git(location, "diff", item["head"], "--name-only", "-z")
            count = len([name for name in changed.split(b"\0") if name])
            print(f"INFO: {repo}: {count} changed tracked paths since snapshot (concurrent/preparation work; not a preservation failure)")


def main():
    try:
        baseline = json.loads((ROOT / ".wgm/privacy-baseline.json").read_text())
        verify(ROOT, baseline)
    except (AssertionError, OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as error:
        if isinstance(error, AssertionError):
            print(f"FAIL: {error}")
        else:
            print("FAIL: preservation check could not inspect required data")
        return 1
    print("PASS: root authorized lines, index, executable AST, diagnostic hashes, app discovery, and ancestor history preserved; child changes reported separately")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
