#!/usr/bin/env python3
"""Check tracked workspace/app files without printing private matching content."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_APPS = (
    "3ds_drop", "3ds_netpass", "3ds_padtest", "3ds_pieceduel",
    "3ds_pokedash", "3ds_rngtool", "3ds_sysdash", "3ds_wigle",
)
PATTERNS = {
    "user-home path": re.compile(rb"/(?:home|Users)/[A-Za-z0-9_.-]+"),
    "Windows user path": re.compile(rb"[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9_.-]+"),
    "inline personal handle": re.compile(rb"`@[A-Za-z0-9_-]+`"),
}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def check(root):
    repos = [root, *(root / name for name in EXPECTED_APPS)]
    errors = []
    files = 0
    projects = re.search(rb"^PROJECTS := (.+)$", (root / "Makefile").read_bytes(), re.M)
    if projects is None or sorted(projects[1].decode().split()) != sorted(EXPECTED_APPS):
        errors.append("root: unexpected Makefile app inventory")
    discovered = {p.parent.name for p in root.glob("*/.git")}
    if discovered != set(EXPECTED_APPS):
        errors.append("root: expected eight child repositories")
    for repo in repos:
        label = "root" if repo == root else repo.name
        if not (repo / ".git").exists():
            errors.append(f"{label}: missing repository")
            continue
        if Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo.resolve():
            errors.append(f"{label}: not an independent repository")
            continue
        for entry in git(repo, "ls-files", "--stage", "-z").split(b"\0"):
            if not entry:
                continue
            metadata, name = entry.split(b"\t", 1)
            mode, _, stage = metadata.split()
            name = name.decode("utf-8")
            path = repo / name
            if any(part.startswith("sd_logs") for part in Path(name).parts[:-1]):
                errors.append(f"{label}: diagnostic export in index")
                continue
            if stage != b"0":
                errors.append(f"{label}: unresolved index entry")
                continue
            if mode == b"160000":
                continue
            if not path.is_file() or path.is_symlink():
                errors.append(f"{label}: missing or unsupported tracked working-tree file")
                continue
            files += 1
            for surface, data in (
                ("working tree", path.read_bytes()),
                ("index", git(repo, "show", f":{name}")),
            ):
                if b"\0" not in data:
                    for kind, pattern in PATTERNS.items():
                        if pattern.search(data):
                            errors.append(f"{label}: {surface}: {kind}")
        consent = repo / ".github" / "wgm-hive.yml"
        for surface, config in (
            ("working tree", consent.read_bytes() if consent.is_file() else b""),
            ("index", git(repo, "show", ":.github/wgm-hive.yml")
             if b".github/wgm-hive.yml\0" in git(repo, "ls-files", "-z") else b""),
        ):
            if not {b"consent: true", b"auto_report: true"} <= set(config.splitlines()):
                errors.append(f"{label}: {surface}: consent missing or not enabled")
        for args in (("diff", "--check"), ("diff", "--cached", "--check")):
            if subprocess.run(["git", "-C", str(repo), *args], capture_output=True).returncode:
                errors.append(f"{label}: whitespace errors")
        for path in repo.glob("sd_logs*/"):
            if subprocess.run(
                ["git", "-C", str(repo), "check-ignore", "-q", "--", path.name],
                capture_output=True,
            ).returncode:
                errors.append(f"{label}: diagnostic export is not ignored")
    return errors, files


def main(root=ROOT):
    try:
        errors, files = check(root)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("FAIL: public hygiene checks could not inspect repository data")
        return 1
    if errors:
        print("FAIL: public hygiene checks")
        print("\n".join(errors))
        return 1
    print(f"PASS: {files} tracked files across nine repositories; working trees and indexes clean; consent enabled; diagnostics excluded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
