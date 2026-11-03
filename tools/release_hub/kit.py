#!/usr/bin/env python3
"""Read-only gates, deterministic bundles and isolated immutable publisher."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import time

MAX_ASSET = 64 * 1024 * 1024
SHA = r"[0-9a-f]{40}"
DIGEST = r"[0-9a-f]{64}"
SLUG = r"lafiabrew/3ds_(?!hub$)[a-z0-9]+"
TAG = r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
KIT_WORKFLOW = "lafiabrew/3ds_hub/.github/workflows/homebrew-release.yml@"
POLICY_KEYS = {'schema', 'repo', 'publish_enabled', 'channel', 'reason', 'native_target',
               'artifact_dir', 'cia_asset', 'host_commands', 'native_commands', 'extra_engine_check'}
EVIDENCE = {'tests', 'rugged', 'spec', 'quality', 'license_history_assets', 'drop_integration'}


class GateError(Exception):
    pass


def require(ok, message):
    if not ok:
        raise GateError(message)


def match(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def load(data):
    try:
        return json.loads(data, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError) as exc:
        raise GateError('invalid JSON') from exc


def regular(path, maximum=MAX_ASSET):
    """Reject symlinks in every component and bound reads before allocation."""
    path = Path(os.path.abspath(path))
    for parent in [*reversed(path.parents), path]:
        require(not parent.is_symlink(), 'symlink path forbidden')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'not a single regular file')
    require(0 < info.st_size <= maximum, 'file size out of bounds')
    # O_NOFOLLOW also protects the final component against replacement.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_ino, opened.st_dev, opened.st_size) ==
                (info.st_ino, info.st_dev, info.st_size), 'file changed during open')
        data = stream.read(maximum + 1)
    require(len(data) == info.st_size, 'file changed during read')
    return data


def policy(data, repo):
    require(match(SLUG, repo), 'unexpected repository slug')
    p = load(data)
    require(isinstance(p, dict) and set(p) == POLICY_KEYS, 'policy schema keys')
    require(type(p['schema']) is int and p['schema'] == 1, 'policy schema version')
    # Context is strictly fully qualified above; schema-1 policy stores ONLY
    # the exact bare slug. Do not normalize foreign contexts or fullslug policy.
    require(p['repo'] == repo.split('/')[1], 'policy repository mismatch (expected bare slug)')
    require(type(p['publish_enabled']) is bool and type(p['extra_engine_check']) is bool,
            'policy booleans must be booleans')
    require(p['channel'] in ('stable', 'wip'), 'policy channel')
    require(isinstance(p['reason'], str) and len(p['reason']) <= 2000, 'policy reason')
    require(p['publish_enabled'] or p['reason'].strip(), 'disabled policy needs reason')
    require(p['artifact_dir'] == 'build/3ds', 'artifact directory must be build/3ds')
    require(p['cia_asset'] == repo.split('/')[1] + '.cia', 'CIA asset name mismatch')
    require(p['native_target'] in ('3ds-native', '3ds'), 'unsupported native target')
    # Current 28 audited profiles use these argv exactly. Extra app gates belong
    # in make test/verify-3ds; no free-form shell, environment or make assignments.
    require(p['host_commands'] == [['make', 'test']], 'host gate must be make test')
    require(p['native_commands'] == [['make', p['native_target']], ['make', 'verify-3ds']],
            'native gates must build then verify-3ds')
    if p['publish_enabled']:
        require(p['channel'] == 'stable', 'WIP publication forbidden')
    return p


def context(repo, tag, source):
    require(match(SLUG, repo), 'repository format')
    require(match(TAG, tag), 'stable SemVer tag required')
    require(match(SHA, source), 'full source SHA required')


def workflow_pin(workflow_ref, kit_ref, workflow_sha=None):
    require(match(SHA, kit_ref), 'kit_ref must be a full lowercase SHA')
    require(workflow_ref == KIT_WORKFLOW + kit_ref, 'workflow_ref and kit_ref must share full SHA')
    if workflow_sha is not None:
        require(workflow_sha == kit_ref, 'executed workflow SHA mismatch')


def cia_identity(data):
    """Single unencrypted NCCH CIA. Check ticket/TMD/NCCH IDs and TMD digest.

    This is archive/identity validation, not Nintendo signature certification or
    an app behavior/provenance test. Multi-content/encrypted CIAs are unsupported.
    """
    require(len(data) >= 0x2020, 'short/HTML CIA')
    header, kind, version, cert, ticket, tmd, meta, content_size = struct.unpack_from('<IHHIIIIQ', data)
    require((header, kind, version) == (0x2020, 0, 0), 'CIA header/type/version')
    require(cert >= 0x100 and ticket >= 0x2a4 and tmd >= 0xb34, 'CIA section sizes')
    align = lambda n: (n + 63) & ~63
    ticket_at = align(header) + align(cert)
    tmd_at = ticket_at + align(ticket)
    content_at = tmd_at + align(tmd)
    meta_at = content_at + align(content_size)
    expected_end = meta_at + meta if meta else content_at + content_size
    require(expected_end == len(data), 'CIA section bounds/trailing data')
    require(content_size >= 0x200 and tmd_at + tmd <= content_at, 'CIA content bounds')
    # Only the standard RSA-2048/SHA-256 signed sections emitted by makerom.
    require(data[ticket_at:ticket_at+4] == b'\x00\x01\x00\x04' and
            data[tmd_at:tmd_at+4] == b'\x00\x01\x00\x04', 'unsupported signature section')
    ticket_body, tmd_body = ticket_at + 0x140, tmd_at + 0x140
    title = data[tmd_body+0x4c:tmd_body+0x54]
    require(len(title) == 8 and title[:4] == bytes.fromhex('00040000'), 'homebrew title ID category')
    require(data[ticket_body+0x9c:ticket_body+0xa4] == title, 'ticket/TMD identity mismatch')
    require(int.from_bytes(data[tmd_body+0x9e:tmd_body+0xa0], 'big') == 1, 'multiple/zero CIA contents')
    record = tmd_body + 0x9c4
    require(record + 48 == tmd_at + tmd, 'TMD record layout')
    index, flags = struct.unpack_from('>HH', data, record + 4)
    require(index == 0 and not flags & 1, 'encrypted/indexed CIA content')
    require(data[0x20] == 0x80 and not any(data[0x21:0x2020]), 'CIA content index bitmap')
    require(int.from_bytes(data[record+8:record+16], 'big') == content_size, 'TMD content size')
    ncch = data[content_at:content_at+content_size]
    require(hashlib.sha256(ncch).digest() == data[record+16:record+48], 'TMD content hash')
    require(ncch[0x100:0x104] == b'NCCH', 'NCCH magic')
    require(int.from_bytes(ncch[0x104:0x108], 'little') * 0x200 == content_size, 'NCCH size')
    require(ncch[0x108:0x110][::-1] == title and ncch[0x118:0x120][::-1] == title,
            'NCCH/TMD title ID mismatch')
    require(ncch[0x18f] & 4, 'NCCH must be unencrypted')
    raw_product = ncch[0x150:0x160].rstrip(b'\0')
    try:
        product = raw_product.decode('ascii')
    except UnicodeError as exc:
        raise GateError('NCCH product code') from exc
    require(match(r'CTR-P-[A-Z0-9]{4}', product), 'NCCH product code')
    # ExeFS and exheader must fit; logo/RomFS are optional.
    exheader = int.from_bytes(ncch[0x180:0x184], 'little')
    require(exheader == 0x400 and len(ncch) >= 0xa00, 'NCCH exheader')
    require(ncch[0x200+0x200:0x200+0x208][::-1] == title, 'exheader program ID')
    for offset in (0x190, 0x198, 0x1a0, 0x1b0):
        start, length = struct.unpack_from('<II', ncch, offset)
        require((start == length == 0) or (start > 0 and length > 0 and
                (start + length) * 0x200 <= len(ncch)), 'NCCH section bounds')
    require(int.from_bytes(ncch[0x1a4:0x1a8], 'little') > 0, 'missing ExeFS')
    return {'title_id': title.hex(), 'product_code': product}


def asset_info(name, data):
    require(0 < len(data) <= MAX_ASSET, 'asset size')
    result = {'name': name, 'size': len(data), 'sha256': digest(data)}
    if name.endswith('.cia'):
        result['native_identity'] = cia_identity(data)
    elif name.endswith('.smdh'):
        require(len(data) == 0x36c0 and data[:4] == b'SMDH', 'invalid SMDH')
    elif name.endswith('.3dsx'):
        require(len(data) >= 32 and data[:4] == b'3DSX', 'invalid 3DSX')
        hdr, reloc = struct.unpack_from('<HH', data, 4)
        code, ro, rw, bss = struct.unpack_from('<IIII', data, 16)
        require(hdr in (32, 44) and reloc == 8 and code > 0 and rw >= bss and
                hdr + code + ro + rw - bss <= len(data), 'invalid 3DSX layout')
    else:
        raise GateError('unknown asset type')
    return result


def bundle(config, repo, tag, source, artifacts, output, started_ns, kit_ref, approval_ref='', approval_id=''):
    context(repo, tag, source)
    require(match(SHA, kit_ref), 'immutable executable kit SHA required')
    require((not approval_ref and not approval_id) or
            (match(SHA, approval_ref) and match(DIGEST, approval_id)), 'approval ref/id pair')
    raw = regular(config, 65536)
    p = policy(raw, repo)
    root = Path(artifacts)
    require(root.name == '3ds' and root.parent.name == 'build', 'artifact root layout')
    require(root.is_dir() and not root.is_symlink(), 'artifact root')
    require(started_ns > 0 and started_ns <= time.time_ns(), 'invalid build start')
    stem = repo.split('/')[1]
    candidates = sorted(x for x in root.iterdir() if x.suffix in ('.cia', '.3dsx', '.smdh'))
    require(any(x.name == p['cia_asset'] for x in candidates), 'missing CIA')
    records, payload = [], {}
    for path in candidates:
        require(path.name in {stem + s for s in ('.cia', '.3dsx', '.smdh')}, 'multiple/mismatched asset')
        data = regular(path)
        require(path.stat().st_mtime_ns >= started_ns, 'stale artifact')
        records.append(asset_info(path.name, data))
        payload[path.name] = data
    manifest = {'schema': 1, 'repo': repo, 'tag': tag, 'source_sha': source,
                'policy_sha256': digest(raw), 'kit_sha': kit_ref,
                'approval_ref': approval_ref, 'approval_id': approval_id, 'assets': records}
    target = Path(output)
    require(not target.exists() and not target.is_symlink(), 'bundle output already exists')
    target.mkdir(parents=True)
    for name, data in payload.items():
        (target / name).write_bytes(data)
    (target / 'release.json').write_bytes(encode(manifest))
    (target / 'SHA256SUMS').write_bytes(sums(records))
    return manifest


def sums(records):
    return ''.join(f"{a['sha256']}  {a['name']}\n" for a in records).encode()


def validate_bundle(directory, raw_policy, repo, tag, source):
    context(repo, tag, source)
    p = policy(raw_policy, repo)
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), 'bundle directory')
    raw_manifest = regular(root / 'release.json', 65536)
    manifest = load(raw_manifest)
    require(isinstance(manifest, dict) and set(manifest) ==
            {'schema', 'repo', 'tag', 'source_sha', 'policy_sha256', 'kit_sha',
             'approval_ref', 'approval_id', 'assets'}, 'manifest schema')
    require(match(SHA, manifest['kit_sha']), 'manifest executable kit SHA')
    require((not manifest['approval_ref'] and not manifest['approval_id']) or
            (match(SHA, manifest['approval_ref']) and match(DIGEST, manifest['approval_id'])),
            'manifest approval refs')
    require(type(manifest['schema']) is int and manifest['schema'] == 1, 'manifest schema version')
    require((manifest['repo'], manifest['tag'], manifest['source_sha'], manifest['policy_sha256']) ==
            (repo, tag, source, digest(raw_policy)), 'manifest source/tag/repository/policy mismatch')
    entries = manifest['assets']
    require(isinstance(entries, list) and 1 <= len(entries) <= 3, 'manifest asset count')
    stem = repo.split('/')[1]
    allowed = {stem + s for s in ('.cia', '.3dsx', '.smdh')}
    records = []
    for item in entries:
        require(isinstance(item, dict) and item.get('name') in allowed, 'manifest asset name')
        data = regular(root / item['name'])
        actual = asset_info(item['name'], data)
        require(item == actual, 'manifest digest/size/native identity mismatch')
        records.append(actual)
    names = [a['name'] for a in records]
    require(names == sorted(set(names)) and p['cia_asset'] in names, 'duplicate/unsorted/missing assets')
    require(set(x.name for x in root.iterdir()) == set(names) | {'release.json', 'SHA256SUMS'},
            'unexpected bundle files')
    require(regular(root / 'SHA256SUMS', 65536) == sums(records), 'checksum manifest mismatch')
    require(raw_manifest == encode(manifest), 'manifest must be canonical deterministic JSON')
    return manifest


def approval(gh, approval_ref, approval_id, kit_ref, raw_policy, repo, tag, source):
    context(repo, tag, source)
    p = policy(raw_policy, repo)
    require(p['publish_enabled'] and p['channel'] == 'stable', 'publication disabled by policy')
    require(match(SHA, kit_ref), 'immutable executable kit SHA required')
    require(match(SHA, approval_ref), 'immutable independent approval_ref required')
    require(match(DIGEST, approval_id), 'independent approval ID required')
    comparison = gh.api(f'repos/lafiabrew/3ds_hub/compare/{approval_ref}...main')
    require(comparison.get('status') in ('ahead', 'identical') and
            comparison.get('base_commit', {}).get('sha') == approval_ref and
            comparison.get('merge_base_commit', {}).get('sha') == approval_ref,
            'approval commit is not reachable on public hub main')
    data = remote_file(gh, 'lafiabrew/3ds_hub',
                       f'tools/release_hub/approvals/{approval_id}.json', approval_ref)
    require(digest(data) == approval_id, 'approval record hash')
    a = load(data)
    require(isinstance(a, dict) and set(a) == {'schema', 'repo', 'tag', 'source_sha',
            'policy_sha256', 'kit_sha', 'decision', 'approver_role', 'evidence', 'assets'}, 'approval schema')
    require(type(a['schema']) is int and a['schema'] == 1 and a['decision'] == 'approved' and
            a['approver_role'] == 'app-coordinator', 'independent approval decision/role')
    require((a['repo'], a['tag'], a['source_sha'], a['policy_sha256'], a['kit_sha']) ==
            (repo, tag, source, digest(raw_policy), kit_ref), 'approval exact-source/policy/kit binding')
    require(isinstance(a['evidence'], dict) and set(a['evidence']) == EVIDENCE and
            all(match(DIGEST, v) for v in a['evidence'].values()), 'approval evidence hashes')
    require(isinstance(a['assets'], list) and 1 <= len(a['assets']) <= 3, 'approval assets')
    return a


class GitHub:
    """Only transport seam. Tests replace gh in PATH; no alternate API in CLI."""
    def run(self, *args):
        proc = subprocess.run(['gh', *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.stdout

    def api(self, endpoint):
        return load(self.run('api', '--method', 'GET', endpoint))

    def absent_release(self, repo, tag):
        # A nonzero gh exit is NOT evidence of absence (auth/rate/network fail closed).
        page = 1
        while page <= 10:
            entries = self.api(f'repos/{repo}/releases?per_page=100&page={page}')
            require(isinstance(entries, list), 'release inventory response')
            require(not any(x.get('tag_name') == tag for x in entries), 'release already exists (including draft)')
            if len(entries) < 100:
                return
            page += 1
        raise GateError('release inventory pagination bound')


def remote_source(gh, repo, tag, source):
    context(repo, tag, source)
    ref = gh.api(f'repos/{repo}/git/ref/tags/{tag}')
    obj = ref.get('object', {})
    require(obj.get('type') == 'tag' and match(SHA, obj.get('sha')), 'new release requires existing annotated tag')
    annotation = gh.api(f"repos/{repo}/git/tags/{obj['sha']}")
    require(annotation.get('tag') == tag and annotation.get('object') == {'type': 'commit', 'sha': source,
            'url': f'https://api.github.com/repos/{repo}/git/commits/{source}'}, 'tag does not bind exact source')
    head = gh.api(f'repos/{repo}/git/ref/heads/main')
    require(head.get('object', {}).get('sha') == source and head.get('object', {}).get('type') == 'commit',
            'main changed since approval; requalification required')
    raw = remote_file(gh, repo, '.github/homebrew-release.json', source)
    policy(raw, repo)
    return raw, obj['sha']


def remote_file(gh, repo, path, source):
    item = gh.api(f'repos/{repo}/contents/{path}?ref={source}')
    require(item.get('type') == 'file' and item.get('encoding') == 'base64' and
            type(item.get('size')) is int and 0 < item['size'] <= 65536, 'remote data file')
    content = item.get('content')
    require(isinstance(content, str) and len(content) <= 90000, 'remote encoding size')
    raw = base64.b64decode(content.replace('\n', ''), validate=True)
    require(len(raw) == item['size'], 'remote data length')
    return raw


def admit(gh, approval_ref, approval_id, kit_ref, repo, tag, source):
    raw, tag_object = remote_source(gh, repo, tag, source)
    a = approval(gh, approval_ref, approval_id, kit_ref, raw, repo, tag, source)
    gh.absent_release(repo, tag)
    return raw, a, tag_object


def publish(gh, approval_ref, approval_id, kit_ref, directory, repo, tag, source):
    # No app code/config commands are executed here. Remote policy, trusted record,
    # full archive parser and exact APPROVED BINARY hashes are all authoritative.
    raw, a, tag_object = admit(gh, approval_ref, approval_id, kit_ref, repo, tag, source)
    manifest = validate_bundle(directory, raw, repo, tag, source)
    require((manifest['kit_sha'], manifest['approval_ref'], manifest['approval_id']) ==
            (kit_ref, approval_ref, approval_id), 'bundle approval/kit identity mismatch')
    require(manifest['assets'] == a['assets'], 'built assets differ from independently approved hashes')
    # Snapshot validated bytes to a private, fresh directory. Never upload source
    # paths after validation (no symlink/TOCTOU substitutions in transport).
    import tempfile
    with tempfile.TemporaryDirectory(prefix='release-hub-') as tmp:
        names = [x['name'] for x in manifest['assets']] + ['SHA256SUMS', 'release.json']
        for name in names:
            Path(tmp, name).write_bytes(regular(Path(directory, name)))
        validate_bundle(tmp, raw, repo, tag, source)
        latest_raw, _, latest_tag = admit(gh, approval_ref, approval_id, kit_ref, repo, tag, source)
        require(latest_raw == raw and latest_tag == tag_object, 'remote source/policy changed')
        # --verify-tag is real gh syntax. Never --target, --clobber, force/delete.
        gh.run('release', 'create', tag, '--repo', repo, '--verify-tag', '--draft',
               '--title', tag, '--notes', f'Exact source {source}; integrity: SHA256SUMS and release.json.')
        gh.run('release', 'upload', tag, '--repo', repo, *[str(Path(tmp, x)) for x in names])
        actual = gh.api(f'repos/{repo}/releases/tags/{tag}')
        require(actual.get('draft') is True and actual.get('tag_name') == tag, 'draft verification')
        assets = actual.get('assets', [])
        require({x.get('name') for x in assets} == set(names) and len(assets) == len(names), 'remote asset names')
        for name in names:
            expected = regular(Path(tmp, name))
            entry = next(x for x in assets if x['name'] == name)
            require(entry.get('size') == len(expected) and entry.get('digest') == 'sha256:' + digest(expected),
                    'uploaded asset digest/size not confirmed by GitHub')
        # A final current source/policy check; unlike admit, draft now exists.
        final_raw, final_tag = remote_source(gh, repo, tag, source)
        require(final_raw == raw and final_tag == tag_object, 'source changed before visibility')
        gh.run('release', 'edit', tag, '--repo', repo, '--draft=false', '--latest', '--verify-tag')
    return manifest


def run_commands(config, repo, phase, cwd):
    # Called inside a tokenless, networkless container. Never accepts shell text.
    p = policy(regular(config, 65536), repo)
    commands = p['host_commands'] if phase == 'host' else p['native_commands']
    for command in commands:
        print(json.dumps({'argv': command, 'cwd': str(cwd)}), flush=True)
        subprocess.run(command, cwd=cwd, check=True)
    if phase == 'host' and p['extra_engine_check']:
        # Legacy field name: actual public FoldQuest contract, not imaginary
        # private-candidate engine coverage. unittest discovery alone allows 0.
        regular(Path(cwd) / 'tests/test_contract.py', 1024 * 1024)
        code = ('import sys,unittest; '
                'suite=unittest.defaultTestLoader.discover("tests",pattern="test_contract.py"); '
                'count=suite.countTestCases(); print("contract tests collected:",count,flush=True); '
                'sys.exit(1) if count == 0 else None; '
                'result=unittest.TextTestRunner(verbosity=2).run(suite); '
                'sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)')
        command = ['python3', '-c', code]
        print(json.dumps({'argv': command, 'cwd': str(cwd)}), flush=True)
        subprocess.run(command, cwd=cwd, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('bundle', 'validate', 'admit', 'publish', 'run'):
        p = sub.add_parser(name)
        p.add_argument('--repo', required=True)
        if name != 'run':
            p.add_argument('--tag', required=True)
            p.add_argument('--source-sha', required=True)
        if name in ('bundle', 'validate', 'run'):
            p.add_argument('--config', required=True)
        if name == 'bundle':
            p.add_argument('--artifacts', required=True)
            p.add_argument('--output', required=True)
            p.add_argument('--started-ns', required=True, type=int)
        if name in ('validate', 'publish'):
            p.add_argument('--bundle', required=True)
        if name in ('admit', 'publish', 'bundle'):
            p.add_argument('--kit-ref', required=True)
            p.add_argument('--approval-id', default='')
            p.add_argument('--approval-ref', default='')
        if name == 'run':
            p.add_argument('--phase', choices=('host', 'native'), required=True)
            p.add_argument('--cwd', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'bundle':
            result = bundle(args.config, args.repo, args.tag, args.source_sha,
                            args.artifacts, args.output, args.started_ns, args.kit_ref,
                            args.approval_ref, args.approval_id)
        elif args.command == 'validate':
            result = validate_bundle(args.bundle, regular(args.config, 65536), args.repo, args.tag, args.source_sha)
        elif args.command == 'admit':
            _, result, _ = admit(GitHub(), args.approval_ref, args.approval_id, args.kit_ref,
                                  args.repo, args.tag, args.source_sha)
        elif args.command == 'publish':
            result = publish(GitHub(), args.approval_ref, args.approval_id, args.kit_ref,
                             args.bundle, args.repo, args.tag, args.source_sha)
        else:
            run_commands(args.config, args.repo, args.phase, args.cwd)
            result = {'phase': args.phase, 'exit': 0}
        print(encode(result).decode(), end='')
    except (GateError, OSError, ValueError, KeyError, TypeError, struct.error, subprocess.CalledProcessError) as exc:
        print(f'BLOCKED: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
