#!/usr/bin/env python3
"""Offline process transport only. Runs real Git for ALL repository operations.

Installed as gh/git in per-test PATH. Production CLI receives no fixture flag;
identity checks still use actual Git config, remote freshness uses real bare Git.
No external API writes or network Git commands are supported by this seam.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

cfg_path = Path(os.environ['ROLLOUT_TEST_TRANSPORT'])
cfg = json.loads(cfg_path.read_text())
args = sys.argv[1:]
if Path(sys.argv[0]).name == 'git':
    if 'ls-remote' in args:
        idx = args.index('ls-remote')
        repo = Path(args[args.index('-C') + 1]).name
        cfg['remote_probes'] = cfg.get('remote_probes', 0) + 1
        cfg_path.write_text(json.dumps(cfg))
        if cfg.get('output_race_at') == cfg['remote_probes']:
            output = Path(cfg['output_race_path'])
            if cfg.get('output_race_kind') == 'ancestor':
                output.parent.symlink_to(cfg['output_race_target'], target_is_directory=True)
            elif cfg.get('output_race_kind') == 'symlink':
                output.symlink_to(cfg['output_race_target'])
            else:
                output.write_bytes(b'late competing output')
        if cfg.get('local_race_at') == cfg['remote_probes']:
            subprocess.run(['/usr/bin/git', '-C', args[args.index('-C') + 1],
                            'update-ref', 'refs/heads/main', cfg['race_sha']], check=True)
        if cfg.get('race_at') == cfg['remote_probes']:
            subprocess.run(['/usr/bin/git', '--git-dir', cfg['remotes'][repo],
                            'update-ref', 'refs/heads/main', cfg['race_sha']], check=True)
        args[idx + 2] = cfg['remotes'][repo]  # --symref ORIGIN
    os.execv('/usr/bin/git', ['/usr/bin/git', *args])
if args[:1] != ['api'] or any(a in args for a in ('-X', '--method', '-f', '-F')):
    sys.exit(71)
if cfg.get('gh_fail'):
    sys.exit(72)
endpoint = args[-1]
if endpoint.startswith('repos/lafiabrew/3ds_hub/compare/'):
    kit = endpoint.split('/')[-1].split('...')[0]
    data = {'base_commit': {'sha': kit}, 'merge_base_commit': {'sha': '0' * 40 if cfg.get('kit_unreachable') else kit}, 'status': 'ahead'}
elif endpoint.startswith('repos/lafiabrew/3ds_hub/contents/'):
    data = {'type': 'symlink' if cfg.get('kit_missing') else 'file',
            'path': '.github/workflows/homebrew-release.yml', 'size': 100}
elif endpoint == 'orgs/lafiabrew':
    data = {} if cfg.get('private_total_unavailable') else {'total_private_repos': cfg.get('private_total', len(cfg.get('private_repos', [])))}
elif endpoint.startswith('orgs/lafiabrew/repos?'):
    if endpoint != 'orgs/lafiabrew/repos?type=all&per_page=100':
        sys.exit(74)
    cfg['org_probes'] = cfg.get('org_probes', 0) + 1
    if cfg.get('cap_race_at') == cfg['org_probes']:
        cfg['open_count'] = 5
    cfg_path.write_text(json.dumps(cfg))
    data = [{'name': repo, 'full_name': 'lafiabrew/' + repo, 'private': False} for repo in cfg['remotes']]
    data += [{'name': repo, 'full_name': 'lafiabrew/' + repo, 'private': True, 'archived': True} for repo in cfg.get('private_repos', [])]
elif '/pulls?' in endpoint:
    repo = endpoint.split('/')[2]
    count = cfg.get('private_open_count', 0) if repo in cfg.get('private_repos', []) else (cfg.get('open_count', 0) if repo == sorted(cfg['remotes'])[0] else 0)
    data = [{'head': {'ref': 'rollout/homebrew-release-' + str(i)}} for i in range(count)]
else:
    repo = endpoint.split('/')[-1]
    data = {'full_name': 'lafiabrew/' + repo, 'private': False,
            'archived': False, 'default_branch': 'main'}
    if repo != '3ds_hub':
        data.update(cfg.get('identity', {}))
if '--paginate' in args:
    if '--slurp' not in args:
        sys.exit(73)
    data = [data]
print(json.dumps(data))
