#!/usr/bin/env python3
"""Local process transport seam: no network; persist real requested draft/assets."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(os.environ['MOCK_GH_ROOT'])
args = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as log:
    log.write(json.dumps(args) + '\n')
s = json.loads((root / 'state.json').read_text())
repo, tag, source = s['repo'], s['tag'], s['source']

def done(value):
    print(json.dumps(value))
    sys.exit(0)

if s.get('fail_transport'):
    sys.exit(37)
if args[:3] == ['api', '--method', 'GET']:
    endpoint = args[3]
    if endpoint == f"repos/lafiabrew/3ds_hub/compare/{s['approval_ref']}...main":
        ref = s['approval_ref']
        done({'status': s.get('approval_status', 'ahead'), 'base_commit': {'sha': ref},
              'merge_base_commit': {'sha': s.get('approval_merge_base', ref)}})
    prefix = 'repos/lafiabrew/3ds_hub/contents/tools/release_hub/approvals/'
    if endpoint.startswith(prefix):
        name, ref = endpoint[len(prefix):].split('?ref=')
        if ref != s['approval_ref']:
            sys.exit(40)
        path = root / 'trusted-kit' / 'approvals' / name
        if not path.exists():
            sys.exit(41)
        raw = path.read_bytes()
        done({'type': 'file', 'encoding': 'base64', 'size': len(raw), 'content': base64.b64encode(raw).decode()})
    if endpoint == f'repos/{repo}/git/ref/tags/{tag}':
        done({'object': {'type': s.get('tag_type', 'tag'), 'sha': s.get('tag_object', 'b'*40)}})
    if endpoint.startswith(f'repos/{repo}/git/tags/'):
        sha = s.get('tag_source', source)
        done({'tag': tag, 'object': {'type': 'commit', 'sha': sha,
            'url': f'https://api.github.com/repos/{repo}/git/commits/{sha}'}})
    if endpoint == f'repos/{repo}/git/ref/heads/main':
        done({'object': {'type': 'commit', 'sha': s.get('head', source)}})
    if endpoint == f'repos/{repo}/contents/.github/homebrew-release.json?ref={source}':
        raw = (root / 'policy.json').read_bytes()
        done({'type': 'file', 'encoding': 'base64', 'size': len(raw), 'content': base64.b64encode(raw).decode()})
    if endpoint.startswith(f'repos/{repo}/releases?'):
        done([s['release']] if 'release' in s else [])
    if endpoint == f'repos/{repo}/releases/tags/{tag}' and 'release' in s:
        r = s['release']
        if s.get('bad_remote_digest'):
            r['assets'][0]['digest'] = 'sha256:' + '0'*64
        done(r)
    sys.exit(38)
if args[:2] == ['release', 'create']:
    assert '--verify-tag' in args and '--draft' in args and '--target' not in args
    assert 'release' not in s
    s['release'] = {'tag_name': tag, 'draft': True, 'assets': []}
elif args[:2] == ['release', 'upload']:
    assert s['release']['draft'] and '--clobber' not in args
    for path in args[args.index('--repo')+2:]:
        p = Path(path)
        data = p.read_bytes()
        s['release']['assets'].append({'name': p.name, 'size': len(data), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest()})
        (root / ('uploaded-' + p.name)).write_bytes(data)
elif args[:2] == ['release', 'edit']:
    assert '--draft=false' in args and '--latest' in args
    assert s['release']['assets']
    s['release']['draft'] = False
else:
    sys.exit(39)
(root / 'state.json').write_text(json.dumps(s))
