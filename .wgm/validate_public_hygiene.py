#!/usr/bin/env python3
"""Check tracked workspace/app files without printing private matching content."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "user-home path": re.compile(rb"/(?:home|Users)/[A-Za-z0-9_.-]+/"),
    "Windows user path": re.compile(rb"[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9_.-]+"),
    "inline personal handle": re.compile(rb"`@[A-Za-z0-9_-]+`"),
}


def main():
    repos = [ROOT, *sorted(p.parent for p in ROOT.glob("*/.git"))]
    errors = []
    files = 0
    for repo in repos:
        names = subprocess.check_output(["git", "-C", str(repo), "ls-files", "-z"])
        for name in names.split(b"\0"):
            if not name:
                continue
            path = repo / name.decode("utf-8")
            if not path.is_file():
                continue
            files += 1
            data = path.read_bytes()
            if b"\0" in data:
                continue
            for label, pattern in PATTERNS.items():
                if pattern.search(data):
                    errors.append(f"{path.relative_to(ROOT)}: {label}")
        consent = repo / ".github" / "wgm-hive.yml"
        if not consent.is_file():
            errors.append(f"{repo.relative_to(ROOT)}: missing consent")
        else:
            config = consent.read_text().splitlines()
            if "consent: true" not in config or "auto_report: true" not in config:
                errors.append(f"{repo.relative_to(ROOT)}: consent not enabled")
        if subprocess.run(["git", "-C", str(repo), "diff", "--check"], capture_output=True).returncode:
            errors.append(f"{repo.relative_to(ROOT)}: whitespace errors")
    for path in ROOT.glob("sd_logs*/"):
        if subprocess.run(["git", "check-ignore", "-q", "--", str(path)], cwd=ROOT).returncode:
            errors.append(f"{path.name}: diagnostic export is not ignored")
    if errors:
        print("FAIL: public hygiene checks")
        print("\n".join(errors))
        return 1
    print(f"PASS: {files} tracked files across {len(repos)} repositories; consent enabled; local diagnostics ignored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
