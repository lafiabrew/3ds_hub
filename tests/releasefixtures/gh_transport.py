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
        if 'release' not in s:
            done([])
        if s.get('fail_draft_lookup'):
            sys.exit(37)
        if s.get('omit_draft_lookup'):
            done([])
        r = dict(s['release'])
        if s.get('missing_draft_id'):
            r.pop('id', None)
        if 'wrong_draft_id' in s:
            r['id'] = s['wrong_draft_id']
        if s.get('inventory_not_draft'):
            r['draft'] = False
        if s.get('inventory_wrong_tag'):
            r['tag_name'] = 'v9.9.9'
        if s.get('draft_id_collision'):
            done([r, dict(r, tag_name='v9.9.9')])
        if s.get('inventory_pages'):
            page = int(endpoint.split('page=')[-1])
            done(s['inventory_pages'].get(str(page), []))
        done([r, dict(r, id=102)] if s.get('draft_collision') else [r])
    if endpoint == f'repos/{repo}/releases/tags/{tag}' and 'release' in s:
        # GitHub's REST tag endpoint only serves PUBLISHED releases.
        if s['release']['draft']:
            print('HTTP 404: Not Found (draft at published-only endpoint)', file=sys.stderr)
            sys.exit(44)
        done(s['release'])
    if endpoint.startswith(f'repos/{repo}/releases/') and 'release' in s:
        if s.get('fail_numeric_lookup'):
            sys.exit(37)
        if endpoint != f"repos/{repo}/releases/{s['release']['id']}":
            sys.exit(44)
        r = dict(s['release'])
        for field in ('id', 'tag_name', 'draft'):
            if 'numeric_' + field in s:
                r[field] = s['numeric_' + field]
        if s.get('missing_numeric_id'):
            r.pop('id', None)
        if s.get('bad_remote_digest'):
            r['assets'][0]['digest'] = 'sha256:' + '0'*64
        if s.get('bad_remote_size'):
            r['assets'][0]['size'] = 1
        if s.get('bad_remote_digest_name'):
            for asset in r['assets']:
                if asset['name'] == s['bad_remote_digest_name']:
                    asset['digest'] = 'sha256:' + '0'*64
        done(r)
    sys.exit(38)
if args[:2] == ['release', 'create']:
    assert '--verify-tag' in args and '--draft' in args and '--target' not in args
    assert 'release' not in s
    s['release'] = {'id': 101, 'tag_name': tag, 'draft': True, 'assets': []}
elif args[:2] == ['release', 'upload']:
    assert s['release']['draft'] and '--clobber' not in args
    for path in args[args.index('--repo')+2:]:
        p = Path(path)
        data = p.read_bytes()
        s['release']['assets'].append({'name': p.name, 'size': len(data), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest()})
        (root / ('uploaded-' + p.name)).write_bytes(data)
    if s.get('change_source_after_upload'):
        s['head'] = 'c'*40
    if s.get('collision_after_upload'):
        s['draft_collision'] = True
elif args[:2] == ['release', 'edit']:
    assert '--draft=false' in args and '--latest' in args
    assert s['release']['assets']
    s['release']['draft'] = False
else:
    sys.exit(39)
(root / 'state.json').write_text(json.dumps(s))
