#!/usr/bin/env python3
"""Prepare a Git-free build copy; verify tracked bytes without consulting Git.

Only prepare may invoke Git, BEFORE any app code. The original checkout, kit
and snapshot must remain outside the container's writable mounts. Generated
untracked outputs are not source-reviewed by this check (bundle checks apply).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

MAX_FILE = 64 * 1024 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def inspect(path):
    path = Path(os.path.abspath(path))
    for component in [*reversed(path.parents), path]:
        need(not component.is_symlink(), 'symlink in tracked path')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'tracked file must be single regular file')
    need(0 <= info.st_size <= MAX_FILE, 'tracked file size bound')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as f:
        opened = os.fstat(f.fileno())
        need((opened.st_ino, opened.st_dev, opened.st_mode, opened.st_size, opened.st_nlink) ==
             (info.st_ino, info.st_dev, info.st_mode, info.st_size, 1), 'tracked file replaced')
        data = f.read(MAX_FILE + 1)
    need(len(data) == info.st_size, 'tracked file changed')
    return {'size': len(data), 'mode': stat.S_IMODE(info.st_mode),
            'sha256': hashlib.sha256(data).hexdigest()}, data


def safe_name(name):
    p = Path(name)
    need(not p.is_absolute() and p.parts and all(x not in ('.', '..', '.git') for x in p.parts),
         'unsafe tracked name')
    return name


def prepare(source, app, snapshot):
    need(not app.exists() and not app.is_symlink(), 'build copy already exists')
    need(not snapshot.exists() and not snapshot.is_symlink(), 'snapshot already exists')
    # This is the ONLY Git command here, and is never called after app execution.
    raw = subprocess.run(['git', '-C', str(source), 'ls-files', '--stage', '-z'],
                         check=True, stdout=subprocess.PIPE).stdout
    records = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, _, stage = header.split()
        need(mode in (b'100644', b'100755') and stage == b'0', 'unsupported tracked mode/stage')
        name = safe_name(os.fsdecode(name))
        need(name not in records, 'duplicate tracked file')
        info, data = inspect(source / name)
        need(bool(info['mode'] & 0o111) == (mode == b'100755'), 'tracked executable mode mismatch')
        records[name] = info
        target = app / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as f:
            f.write(data)
        target.chmod(info['mode'])
    need(records, 'empty tracked source')
    with snapshot.open('x') as f:
        json.dump(records, f, sort_keys=True, indent=2)
        f.write('\n')
    verify(app, snapshot)


def verify(app, snapshot):
    # No subprocess/Git/config/hooks/fsmonitor/textconv/diff-driver evaluation.
    # Reject recreated .git too; checkout action cleanup uses only the separate
    # original checkout, never this app-writable directory.
    need(app.is_dir() and not app.is_symlink(), 'build copy directory')
    need(not (app / '.git').exists() and not (app / '.git').is_symlink(), 'app created .git')
    records = json.loads(snapshot.read_text())
    need(isinstance(records, dict) and records, 'invalid trusted snapshot')
    for name, expected in records.items():
        actual, _ = inspect(app / safe_name(name))
        need(actual == expected, 'tracked content/metadata changed: ' + name)
    print('tracked snapshot verified:', len(records), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'verify'))
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            need(args.source is not None, 'source required')
            prepare(args.source, args.app, args.snapshot)
        else:
            verify(args.app, args.snapshot)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('BLOCKED:', exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
