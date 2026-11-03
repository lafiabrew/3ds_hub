"""Exercise production CLI/real subprocess gates, synthetic archives and gh seam."""
import base64
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / 'releasefixtures'))
from cia import cia, smdh, threedsx
from tools.release_hub import kit

REPO = 'lafiabrew/3ds_padtest'
SOURCE = 'a' * 40
TAG = 'v0.1.0'
KIT = 'd' * 40  # Executable kit K0 exists BEFORE app source A0.
APPROVAL_REF = 'e' * 40  # Data commit R1 AFTER A0; no caller repin.


def policy(enabled=False):
    return {'schema': 1, 'repo': '3ds_padtest', 'publish_enabled': enabled, 'channel': 'stable',
            'reason': '' if enabled else 'Independent QA/provenance approval absent',
            'native_target': '3ds-native', 'artifact_dir': 'build/3ds', 'cia_asset': '3ds_padtest.cia',
            'host_commands': [['make', 'test']], 'native_commands': [['make', '3ds-native'], ['make', 'verify-3ds']],
            'extra_engine_check': False}


class ReleaseProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script = self.root / 'trusted-kit' / 'kit.py'
        self.script.parent.mkdir()
        shutil.copyfile(ROOT / 'tools/release_hub/kit.py', self.script)
        self.approvals = self.script.parent / 'approvals'
        self.approvals.mkdir()
        self.config = self.root / 'policy.json'
        self.config.write_bytes(kit.encode(policy()))
        self.artifacts = self.root / 'app/build/3ds'
        self.artifacts.mkdir(parents=True)
        self.started = time.time_ns() - 1_000_000_000
        (self.artifacts / '3ds_padtest.cia').write_bytes(cia())
        self.bundle = self.root / 'bundle'
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        shim = self.bin / 'gh'
        shim.write_text('#!' + sys.executable + '\n' + (ROOT / 'tests/releasefixtures/gh_transport.py').read_text())
        shim.chmod(0o755)
        self.state = {'repo': REPO, 'tag': TAG, 'source': SOURCE, 'approval_ref': APPROVAL_REF}
        self.save_state()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'], MOCK_GH_ROOT=str(self.root))

    def save_state(self):
        (self.root / 'state.json').write_text(json.dumps(self.state))

    def invoke(self, command, *args, success=True):
        p = subprocess.run([sys.executable, str(self.script), command, '--repo', REPO,
                            *([] if command == 'run' else ['--tag', TAG, '--source-sha', SOURCE]), *map(str, args)],
                           env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(p.returncode == 0, success, p.stdout + p.stderr)
        return p

    def make_bundle(self, success=True):
        return self.invoke('bundle', '--config', self.config, '--artifacts', self.artifacts,
                           '--output', self.bundle, '--started-ns', self.started, '--kit-ref', KIT,
                           *(['--approval-ref', APPROVAL_REF, '--approval-id', self.approval]
                             if hasattr(self, 'approval') else []), success=success)

    def validate(self, success=True):
        return self.invoke('validate', '--config', self.config, '--bundle', self.bundle, success=success)

    def approved(self):
        self.config.write_bytes(kit.encode(policy(True)))
        self.make_bundle()
        m = json.loads((self.bundle / 'release.json').read_text())
        a = {'schema': 1, 'repo': REPO, 'tag': TAG, 'source_sha': SOURCE,
             'policy_sha256': kit.digest(self.config.read_bytes()), 'kit_sha': KIT, 'decision': 'approved',
             'approver_role': 'app-coordinator', 'evidence': {x: kit.digest(x.encode()) for x in kit.EVIDENCE},
             'assets': m['assets']}
        self.approval = kit.digest(kit.encode(a))
        (self.approvals / (self.approval + '.json')).write_bytes(kit.encode(a))
        m.update(kit_sha=KIT, approval_ref=APPROVAL_REF, approval_id=self.approval)
        (self.bundle / 'release.json').write_bytes(kit.encode(m))
        return a

    def publish(self, success=True, approval=None):
        return self.invoke('publish', '--bundle', self.bundle, '--approval-id', approval or self.approval,
                           '--kit-ref', KIT, '--approval-ref', APPROVAL_REF, success=success)

    def calls(self):
        p = self.root / 'calls.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def assert_no_writes(self):
        self.assertFalse(any(c[:1] == ['release'] for c in self.calls()), self.calls())
        self.assertFalse(list(self.root.glob('uploaded-*')))

    def test_cli_help_real(self):
        for command in ('bundle', 'validate', 'run', 'admit', 'publish'):
            p = subprocess.run([sys.executable, str(self.script), command, '--help'], capture_output=True)
            self.assertEqual(p.returncode, 0)

    def test_dryrun_disabled_policy_local_bundle_no_transport(self):
        self.make_bundle()
        self.validate()
        self.assertEqual(self.calls(), [])
        self.assertEqual(json.loads((self.bundle / 'release.json').read_text())['source_sha'], SOURCE)

    def test_deterministic_manifest_and_hashes(self):
        self.make_bundle()
        m = json.loads(self.validate().stdout)
        expected = kit.digest(cia())
        self.assertEqual(m['assets'][0]['sha256'], expected)
        self.assertEqual((self.bundle / 'SHA256SUMS').read_text(), expected + '  3ds_padtest.cia\n')
        self.assertEqual(m['assets'][0]['native_identity'], {'title_id': '0004000000d3e703', 'product_code': 'CTR-P-PADT'})

    def test_optional_matching_formats(self):
        (self.artifacts / '3ds_padtest.smdh').write_bytes(smdh())
        (self.artifacts / '3ds_padtest.3dsx').write_bytes(threedsx())
        self.make_bundle()
        self.assertEqual(len(json.loads(self.validate().stdout)['assets']), 3)

    def test_bundle_rejects_bad_artifacts_process(self):
        cases = {'short': b'\x20\x20', 'html': b'<!DOCTYPE html>' * 1000,
                 'wrong_type': b'\x20\x20\x00\x00\x01\x00' + cia()[6:],
                 'truncated': cia()[:-1], 'trailing': cia()+b'x',
                 'content_hash': cia()[:-1]+b'x'}
        for label, data in cases.items():
            with self.subTest(label=label):
                (self.artifacts / '3ds_padtest.cia').write_bytes(data)
                self.make_bundle(success=False)
                self.assertFalse(self.bundle.exists())
                self.assert_no_writes()

    def test_optional_short_html_formats_and_missing_cia_rejected(self):
        for suffix, payload in (('.smdh', b'SMDH'), ('.3dsx', b'3DSX'),
                                ('.smdh', b'<html>' * 2000), ('.3dsx', b'3DSX' + bytes(60))):
            with self.subTest(suffix=suffix, size=len(payload)):
                path = self.artifacts / ('3ds_padtest' + suffix)
                path.write_bytes(payload)
                self.make_bundle(success=False)
                path.unlink()
        (self.artifacts / '3ds_padtest.cia').unlink()
        self.make_bundle(success=False)
        self.assert_no_writes()

    def test_structure_negative_controls(self):
        valid = cia()
        # Mutations beyond a bare magic check: ticket identity, TMD count,
        # bitmap, TMD length/hash and NCCH internal identity/section ranges.
        ticket_at, tmd_at = 0x2a40, 0x2dc0
        for offset, value in [(0x20, 0), (ticket_at+0x140+0x9c, 1),
                              (tmd_at+0x140+0x9f, 2), (tmd_at+0x140+0x9c4+15, 1)]:
            with self.subTest(offset=offset):
                bad = bytearray(valid)
                bad[offset] = value
                with self.assertRaises(kit.GateError):
                    kit.cia_identity(bad)
        # Update TMD digest after corruption to exercise NCCH rather than just hash rejection.
        content_at = 0x3900
        for offset in (0x100, 0x108, 0x118, 0x150, 0x180, 0x18f, 0x1a4, 0x400):
            with self.subTest(ncch_offset=offset):
                bad = bytearray(valid)
                bad[content_at+offset] ^= 0xff
                h = __import__('hashlib').sha256(bad[content_at:]).digest()
                r = tmd_at + 0x140 + 0x9c4
                bad[r+16:r+48] = h
                with self.assertRaises(kit.GateError):
                    kit.cia_identity(bad)

    def test_stale_multiple_symlink_and_oversize(self):
        path = self.artifacts / '3ds_padtest.cia'
        os.utime(path, ns=(self.started-1, self.started-1))
        self.make_bundle(success=False)
        path.write_bytes(cia())
        extra = self.artifacts / 'other.cia'
        extra.write_bytes(cia())
        self.make_bundle(success=False)
        extra.unlink()
        path.unlink()
        path.symlink_to(self.config)
        self.make_bundle(success=False)
        path.unlink()
        path.write_bytes(cia())
        with path.open('r+b') as f:
            f.truncate(kit.MAX_ASSET + 1)
        self.make_bundle(success=False)
        self.assert_no_writes()

    def test_root_symlink_and_hardlink_rejected(self):
        real = self.artifacts.parent / 'real'
        self.artifacts.rename(real)
        self.artifacts.symlink_to(real, target_is_directory=True)
        self.make_bundle(success=False)
        self.artifacts.unlink()
        real.rename(self.artifacts)
        os.link(self.artifacts / '3ds_padtest.cia', self.root / 'hardlink')
        self.make_bundle(success=False)

    def test_actual28_bare_policy_full_context_cli_bundle_and_validate(self):
        fixture = json.loads((ROOT / 'tests/releasefixtures/public_profiles.json').read_text())
        for name in fixture['native_3ds_native'] + fixture['native_3ds_intentionally_failing_stubs']:
            with self.subTest(repo=name):
                target = '3ds-native' if name in fixture['native_3ds_native'] else '3ds'
                # Independent fixture contract, not the policy() test helper.
                p = dict(fixture['policy_example'], repo=name, cia_asset=name+'.cia',
                         native_target=target,
                         native_commands=[['make', target], ['make', 'verify-3ds']],
                         extra_engine_check=name in fixture['extra_engine_check'],
                         channel='stable' if target == '3ds-native' and name != '3ds_foldquest' else 'wip')
                self.config.write_bytes(kit.encode(p))
                artifact = self.artifacts / (name + '.cia')
                # Synthetic structure test, NOT 28 native builds/identity approvals.
                for old in self.artifacts.iterdir():
                    old.unlink()
                artifact.write_bytes(cia())
                output = self.root / ('bundle-' + name)
                repo = 'lafiabrew/' + name
                for command, args in [('bundle', ['--artifacts', str(self.artifacts), '--output', str(output),
                            '--started-ns', str(self.started), '--kit-ref', KIT]),
                            ('validate', ['--bundle', str(output)])]:
                    result = subprocess.run([sys.executable, str(self.script), command, '--repo', repo,
                        '--tag', TAG, '--source-sha', SOURCE, '--config', str(self.config), *args],
                        env=self.env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    manifest = json.loads(result.stdout)
                    self.assertEqual(manifest['repo'], repo)
                    self.assertEqual(manifest['policy_sha256'], kit.digest(self.config.read_bytes()))
                self.assertFalse(p['publish_enabled'])
        self.assert_no_writes()

    def test_policy_identity_rejections_stop_before_actual_host_command(self):
        app = self.artifacts.parent.parent
        (app / 'Makefile').write_text('test:\n\t@touch host-command-executed\n')
        for policy_repo, context_repo in [('lafiabrew/3ds_padtest', REPO),
                ('3ds_drop', REPO), ('3ds_padtest', 'foreign/3ds_padtest'),
                ('3ds_padtest', '3ds_padtest'), ('3ds_padtest', 'lafiabrew/3ds_padtest/extra'),
                ('3ds_hub', 'lafiabrew/3ds_hub')]:
            with self.subTest(policy_repo=policy_repo, context_repo=context_repo):
                self.config.write_bytes(kit.encode(dict(policy(), repo=policy_repo)))
                result = subprocess.run([sys.executable, str(self.script), 'run', '--repo', context_repo,
                    '--config', str(self.config), '--cwd', str(app), '--phase', 'host'],
                    env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('BLOCKED:', result.stderr)
                self.assertFalse((app / 'host-command-executed').exists())
        self.assert_no_writes()

    def test_strict_policy_process_controls(self):
        base = policy()
        changes = {'schema': True, 'repo': 'evil/3ds_padtest', 'publish_enabled': 'false',
                   'extra_engine_check': 1, 'channel': 'preview', 'reason': '',
                   'native_target': '3ds; touch /tmp/escaped', 'artifact_dir': '../build/3ds',
                   'cia_asset': '../bad.cia', 'host_commands': [['echo', 'passed']],
                   'native_commands': [['make', '3ds-native']]}
        for key, value in changes.items():
            with self.subTest(key=key):
                p = dict(base, **{key: value})
                self.config.write_bytes(kit.encode(p))
                self.make_bundle(success=False)
        self.config.write_text('{"schema":1,"schema":1}')
        self.make_bundle(success=False)
        self.assert_no_writes()

    def test_unknown_policy_field_and_wip_enable(self):
        for p in (dict(policy(), surprise=True), dict(policy(True), channel='wip')):
            self.config.write_bytes(kit.encode(p))
            self.make_bundle(success=False)

    def test_version_and_source_contract(self):
        for tag in ('v01.0.0', '1.0.0', 'v1.0.0-rc.1', '--help', 'v1.0.0;echo bad'):
            with self.assertRaises(kit.GateError):
                kit.context(REPO, tag, SOURCE)
        for repo, source in [('evil/3ds_padtest', SOURCE), (REPO, 'main'), ('lafiabrew/3ds_hub', SOURCE)]:
            with self.assertRaises(kit.GateError):
                kit.context(repo, TAG, source)

    def test_publisher_positive_real_process_transport(self):
        self.approved()
        self.publish()
        state = json.loads((self.root / 'state.json').read_text())
        self.assertFalse(state['release']['draft'])
        self.assertEqual((self.root / 'uploaded-3ds_padtest.cia').read_bytes(), cia())
        mutations = [c[:2] for c in self.calls() if c[0] == 'release']
        self.assertEqual(mutations, [['release', 'create'], ['release', 'upload'], ['release', 'edit']])
        self.assertTrue(all('--clobber' not in c and '--target' not in c and '--force' not in c for c in self.calls()))
        endpoints = [c[3] for c in self.calls() if c[:3] == ['api', '--method', 'GET']]
        self.assertNotIn(f'repos/{REPO}/releases/tags/{TAG}', endpoints)
        self.assertIn(f'repos/{REPO}/releases/101', endpoints)
        upload = next(i for i, c in enumerate(self.calls()) if c[:2] == ['release', 'upload'])
        self.assertTrue(any('/releases?' in c[-1] for c in self.calls()[upload+1:]))

    def test_draft_published_only_endpoint_is_404_numeric_endpoint_works(self):
        self.approved()
        self.state['release'] = {'id': 101, 'tag_name': TAG, 'draft': True, 'assets': []}
        self.save_state()
        p = subprocess.run(['gh', 'api', '--method', 'GET', f'repos/{REPO}/releases/tags/{TAG}'],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 44)
        self.assertIn('404', p.stderr)
        p = subprocess.run(['gh', 'api', '--method', 'GET', f'repos/{REPO}/releases/101'],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['id'], 101)
        self.assert_no_writes()

    def test_draft_discovery_failures_and_collisions_never_change_visibility(self):
        self.approved()
        baseline = dict(self.state)
        for field, value in [('fail_draft_lookup', True), ('omit_draft_lookup', True),
                ('missing_draft_id', True), ('wrong_draft_id', 0), ('wrong_draft_id', True),
                ('wrong_draft_id', '101'), ('wrong_draft_id', 999), ('draft_collision', True),
                ('draft_id_collision', True),
                ('inventory_not_draft', True), ('inventory_wrong_tag', True),
                ('fail_numeric_lookup', True), ('missing_numeric_id', True),
                ('numeric_id', 999), ('numeric_id', True), ('numeric_tag_name', 'v9.9.9'),
                ('numeric_draft', False), ('bad_remote_size', True),
                ('bad_remote_digest_name', '3ds_padtest.cia'),
                ('bad_remote_digest_name', 'SHA256SUMS'), ('bad_remote_digest_name', 'release.json'),
                ('change_source_after_upload', True), ('collision_after_upload', True)]:
            with self.subTest(field=field, value=value):
                self.state = dict(baseline, **{field: value})
                self.save_state()
                self.publish(success=False)
                state = json.loads((self.root / 'state.json').read_text())
                self.assertTrue(state['release']['draft'])
                self.assertFalse(any(c[:2] == ['release', 'edit'] for c in self.calls()))
                self.assertFalse(any(c[:2] == ['release', 'delete'] for c in self.calls()))

    def test_draft_inventory_cross_page_collision_and_bound_fail_closed(self):
        self.approved()
        baseline = dict(self.state)
        release = {'id': 101, 'tag_name': TAG, 'draft': True, 'assets': []}
        filler = [{'id': n + 1000, 'tag_name': 'other-' + str(n), 'draft': False} for n in range(99)]
        for pages in ({'1': [release, *filler], '2': [dict(release, id=102)]},
                      {str(n): filler + [{'id': n + 2000, 'tag_name': 'unrelated'}] for n in range(1, 11)}):
            with self.subTest(pages=len(pages)):
                self.state = dict(baseline, inventory_pages=pages)
                self.save_state()
                self.publish(success=False)
                self.assertTrue(json.loads((self.root / 'state.json').read_text())['release']['draft'])
                self.assertFalse(any(c[:2] == ['release', 'upload'] for c in self.calls()))
                self.assertFalse(any(c[:2] == ['release', 'edit'] for c in self.calls()))

    def test_leftover_draft_blocks_retry_without_delete_resume_or_upload(self):
        self.approved()
        self.state['bad_remote_digest'] = True
        self.save_state()
        self.publish(success=False)
        before = len(self.calls())
        self.publish(success=False)
        self.assertFalse(any(c[0] == 'release' for c in self.calls()[before:]))
        self.assertTrue(json.loads((self.root / 'state.json').read_text())['release']['draft'])

    def test_disabled_policy_never_dispatches_even_with_approval(self):
        self.approved()
        self.config.write_bytes(kit.encode(policy(False)))
        self.publish(success=False)
        self.assert_no_writes()

    def test_disabled_admission_prevents_actual_upload_dispatch(self):
        import shlex
        self.approved()
        self.config.write_bytes(kit.encode(policy(False)))
        command = shlex.join([sys.executable, str(self.script), 'admit', '--repo', REPO,
            '--tag', TAG, '--source-sha', SOURCE, '--kit-ref', KIT,
            '--approval-ref', APPROVAL_REF, '--approval-id', self.approval])
        command += ' && gh release upload ' + TAG + ' --repo ' + REPO + ' ' + str(self.bundle / '3ds_padtest.cia')
        result = subprocess.run(['bash', '-euc', command], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('publication disabled by policy', result.stderr)
        self.assert_no_writes()

    def test_boolean_alone_missing_or_forged_approval_blocks(self):
        self.config.write_bytes(kit.encode(policy(True)))
        self.make_bundle()
        self.approval = '0'*64
        self.publish(success=False)
        self.assert_no_writes()

    def test_approval_source_policy_and_evidence_binding(self):
        original = self.approved()
        for key, value in [('source_sha', 'c'*40), ('tag', 'v1.2.3'), ('repo', 'lafiabrew/3ds_drop'),
                           ('policy_sha256', '0'*64), ('kit_sha', 'c'*40),
                           ('evidence', {}), ('decision', 'blocked')]:
            with self.subTest(key=key):
                data = kit.encode(dict(original, **{key: value}))
                identifier = kit.digest(data)
                (self.approvals / (identifier + '.json')).write_bytes(data)
                self.publish(success=False, approval=identifier)
                self.assert_no_writes()

    def test_approval_ref_mutable_foreign_unreachable_and_kit_mismatch(self):
        self.approved()
        for ref in ('main', 'evil/branch', 'f'*40):
            self.invoke('publish', '--bundle', self.bundle, '--approval-id', self.approval,
                        '--kit-ref', KIT, '--approval-ref', ref, success=False)
            self.assert_no_writes()
        for field, value in [('approval_status', 'diverged'), ('approval_merge_base', 'f'*40)]:
            self.state[field] = value
            self.save_state()
            self.publish(success=False)
            self.assert_no_writes()
            del self.state[field]
        self.save_state()
        self.invoke('publish', '--bundle', self.bundle, '--approval-id', self.approval,
                    '--kit-ref', 'f'*40, '--approval-ref', APPROVAL_REF, success=False)
        self.assert_no_writes()

    def test_approval_record_bytes_hash_not_trusted(self):
        self.approved()
        record = self.approvals / (self.approval + '.json')
        record.write_bytes(record.read_bytes() + b' ')
        self.publish(success=False)
        self.assert_no_writes()

    def test_contract_extra_gate_rejects_missing_zero_skipped_and_failure(self):
        p = policy()
        p['extra_engine_check'] = True
        self.config.write_bytes(kit.encode(p))
        app = self.artifacts.parent.parent
        (app / 'Makefile').write_text('test:\n\t@true\n')
        tests = app / 'tests'
        tests.mkdir()
        self.invoke('run', '--config', self.config, '--cwd', app, '--phase', 'host', success=False)
        path = tests / 'test_contract.py'
        for source in ('# only a comment\n',
                       'import unittest\nclass Test(unittest.TestCase):\n def test_no(self): self.fail("real failure")\n',
                       'import unittest\nclass Test(unittest.TestCase):\n @unittest.skip("not executed")\n def test_no(self): pass\n'):
            path.write_text(source)
            shutil.rmtree(tests / '__pycache__', ignore_errors=True)
            self.invoke('run', '--config', self.config, '--cwd', app, '--phase', 'host', success=False)
        path.write_text('import unittest\nclass Test(unittest.TestCase):\n def test_real(self): self.assertEqual(2+2,4)\n')
        shutil.rmtree(tests / '__pycache__', ignore_errors=True)
        result = self.invoke('run', '--config', self.config, '--cwd', app, '--phase', 'host')
        self.assertIn('contract tests collected: 1', result.stdout)
        self.assert_no_writes()

    def test_existing_release_no_clobber_or_visibility_change(self):
        self.approved()
        self.state['release'] = {'tag_name': TAG, 'draft': False, 'assets': [{'name': 'old.cia'}]}
        self.save_state()
        self.publish(success=False)
        self.assert_no_writes()

    def test_tag_missing_lightweight_wrongsource_or_stale_main_blocks(self):
        self.approved()
        for field, value in [('tag_type', 'commit'), ('tag_source', 'c'*40), ('head', 'c'*40),
                             ('fail_transport', True)]:
            with self.subTest(field=field):
                self.state[field] = value
                self.save_state()
                self.publish(success=False)
                self.assert_no_writes()
                del self.state[field]

    def test_asset_hash_size_source_tag_nativeidentity_mutations(self):
        self.approved()
        path = self.bundle / 'release.json'
        original = path.read_bytes()
        for key, value in [('source_sha', 'c'*40), ('tag', 'v9.0.0'), ('repo', 'lafiabrew/3ds_drop')]:
            with self.subTest(key=key):
                m = json.loads(original)
                m[key] = value
                path.write_bytes(kit.encode(m))
                self.publish(success=False)
                self.assert_no_writes()
        for key, value in [('size', 1), ('sha256', '0'*64), ('native_identity', {'title_id': '0'*16})]:
            with self.subTest(asset_key=key):
                m = json.loads(original)
                m['assets'][0][key] = value
                path.write_bytes(kit.encode(m))
                self.publish(success=False)
                self.assert_no_writes()

    def test_valid_structural_wrong_app_and_unapproved_binary_rejected(self):
        self.approved()
        for data in (cia(title='0004000000d3e003', product='CTR-P-PD3D'), cia(product='CTR-P-AAAA')):
            shutil.rmtree(self.bundle)
            (self.artifacts / '3ds_padtest.cia').write_bytes(data)
            self.make_bundle()
            self.validate()  # A valid archive/config does not make this binary trusted.
            self.publish(success=False)
            self.assert_no_writes()

    def test_bundle_escape_extra_duplicate_symlink_and_checksum(self):
        self.make_bundle()
        path = self.bundle / 'release.json'
        original = path.read_bytes()
        for name in ('../outside.cia', '/tmp/3ds_padtest.cia'):
            m = json.loads(original)
            m['assets'][0]['name'] = name
            path.write_bytes(kit.encode(m))
            self.validate(success=False)
        m = json.loads(original)
        m['assets'].append(m['assets'][0])
        path.write_bytes(kit.encode(m))
        self.validate(success=False)
        path.write_bytes(original)
        extra = self.bundle / 'extra'
        extra.mkdir()
        self.validate(success=False)
        extra.rmdir()
        asset = self.bundle / '3ds_padtest.cia'
        asset.unlink()
        asset.symlink_to(self.artifacts / '3ds_padtest.cia')
        self.validate(success=False)
        asset.unlink()
        asset.write_bytes(cia())
        (self.bundle / 'SHA256SUMS').write_text('wrong\n')
        self.validate(success=False)

    def test_publisher_independently_rejects_symlink_html_and_oversize(self):
        self.approved()
        path = self.bundle / '3ds_padtest.cia'
        path.unlink()
        path.symlink_to(self.artifacts / '3ds_padtest.cia')
        self.publish(success=False)
        self.assert_no_writes()
        path.unlink()
        path.write_bytes(b'<!DOCTYPE html>' * 1000)
        self.publish(success=False)
        self.assert_no_writes()
        with path.open('wb') as stream:
            stream.truncate(kit.MAX_ASSET + 1)
        self.publish(success=False)
        self.assert_no_writes()

    def test_upload_digest_failure_never_makes_release_visible(self):
        self.approved()
        self.state['bad_remote_digest'] = True
        self.save_state()
        self.publish(success=False)
        state = json.loads((self.root / 'state.json').read_text())
        self.assertTrue(state['release']['draft'])
        self.assertFalse(any(c[:2] == ['release', 'edit'] for c in self.calls()))

    def test_actual_failing_make_stops_downstream_bundle_and_publish(self):
        (self.artifacts.parent.parent / 'Makefile').write_text(
            'test:\n\t@echo INTENTIONAL_FAILED_HOST >&2\n\t@exit 23\n'
            '3ds-native:\n\t@touch downstream-native\nverify-3ds:\n\t@touch downstream-verify\n')
        app = self.artifacts.parent.parent
        import shlex
        args = [sys.executable, str(self.script), 'run', '--repo', REPO, '--config', str(self.config),
                '--cwd', str(app), '--phase', 'host']
        gate = shlex.join(args)
        native = shlex.join(args[:-1] + ['native'])
        # Actual shell failure propagation, not a fake success marker or a
        # counter generated by the artifact generator under test.
        command = gate + ' && ' + native + ' && ' + shlex.join([sys.executable, str(self.script), 'publish',
                  '--repo', REPO, '--tag', TAG, '--source-sha', SOURCE, '--approval-id', '0'*64,
                  '--bundle', str(self.bundle), '--kit-ref', KIT, '--approval-ref', APPROVAL_REF])
        p = subprocess.run(['bash', '-euc', command], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('INTENTIONAL_FAILED_HOST', p.stderr)
        self.assertFalse((app / 'downstream-native').exists())
        self.assertFalse((app / 'downstream-verify').exists())
        self.assertEqual(self.calls(), [])

    def test_actual_native_verify_failure_stops(self):
        app = self.artifacts.parent.parent
        (app / 'Makefile').write_text('3ds-native:\n\t@echo genuine-native-command\nverify-3ds:\n\t@exit 19\n')
        p = self.invoke('run', '--config', self.config, '--cwd', app, '--phase', 'native', success=False)
        self.assertIn('genuine-native-command', p.stdout)
        self.assert_no_writes()


class PostBuildHostCanaryTests(unittest.TestCase):
    """Run shipped shell commands, not a reimplementation of the boundary."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'app-source'
        self.source.mkdir()
        self.app = self.root / 'app'
        shutil.copytree(ROOT / 'tools/release_hub', self.root / 'kit/tools/release_hub',
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.sentinel = self.root / 'HOST-EXECUTED'
        self.network = self.root / 'NETWORK-DISPATCHED'
        self.payload = self.root / 'fsmonitor-payload'
        self.payload.write_text('#!/bin/sh\ntouch "' + str(self.sentinel) + '"\ncurl blocked.invalid\n')
        self.payload.chmod(0o755)
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        curl = bin_dir / 'curl'
        curl.write_text('#!/bin/sh\ntouch "' + str(self.network) + '"\n')
        curl.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                        REPO=REPO, TAG=TAG, SOURCE=SOURCE, KIT_REF=KIT, APPROVAL='', APPROVAL_REF='')
        (self.source / 'tracked.txt').write_text('trusted source\n')
        (self.source / 'empty').touch()
        (self.source / '.gitattributes').write_text('tracked.txt diff=attack\n')
        # Actual application command installs attacker-controlled Git config.
        (self.source / 'Makefile').write_text('test:\n\t@git init -q .\n'
            '\t@git config core.fsmonitor "' + str(self.payload) + '"\n'
            '\t@git config diff.attack.command "' + str(self.payload) + '"\n'
            '\t@git config diff.attack.textconv "' + str(self.payload) + '"\n'
            '\t@git config core.hooksPath "' + str(self.root) + '"\n')
        for args in (['init', '-q'], ['add', '.'], ['-c', 'user.name=Test', '-c',
                'user.email=test@example.invalid', 'commit', '-qm', 'trusted source']):
            subprocess.run(['git', '-C', str(self.source), *args], check=True, capture_output=True)
        self.workflow = (ROOT / '.github/workflows/homebrew-release.yml').read_text()
        self.prepare = next(x.strip() for x in self.workflow.splitlines() if 'tracked.py prepare ' in x)
        self.verify = next(x.strip() for x in self.workflow.splitlines() if 'tracked.py verify ' in x)
        block = self.workflow.split('      - name: Make deterministic local bundle and validate it', 1)[1]
        block = block.split('        run: |\n', 1)[1].split('      - name:', 1)[0]
        self.bundle_commands = '\n'.join(x[10:] for x in block.splitlines() if x.strip())
        self.shell(self.prepare, True)
        (self.root / 'frozen-policy.json').write_bytes(kit.encode(policy()))
        (self.root / 'started-ns').write_text(str(time.time_ns() - 1_000_000_000))
        (self.app / 'build/3ds').mkdir(parents=True)
        (self.app / 'build/3ds/3ds_padtest.cia').write_bytes(cia())

    def shell(self, command, success):
        result = subprocess.run(['bash', '-euc', command], cwd=self.root, env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def assert_no_host_dispatch(self):
        self.assertFalse(self.sentinel.exists(), 'host fsmonitor/diff/textconv executed')
        self.assertFalse(self.network.exists(), 'host network tool dispatched')
        self.assertFalse((self.source / '.git/config').read_text().find('fsmonitor') >= 0)

    def test_exact_postbuild_positive_commands_do_not_invoke_git(self):
        self.shell(self.verify + '\n' + self.bundle_commands, True)
        self.assertTrue((self.root / 'bundle/release.json').is_file())
        self.assert_no_host_dispatch()
        # No host Git after app code, including no checkout-action cleanup of
        # the writable copy: only app-source is registered with checkout.
        post = self.workflow.split('      - name: Tokenless isolated actual host/native gates', 1)[1]
        self.assertNotIn('git -C', post)
        self.assertIn('path: app-source', self.workflow)
        for line in post.splitlines():
            if 'docker run' in line:
                self.assertNotIn('app-source', line)

    def test_real_app_config_injection_cannot_execute_host_canary(self):
        self.shell('make -C app test', True)
        config = (self.app / '.git/config').read_text()
        for value in ('fsmonitor', 'textconv', 'command', 'hooksPath'):
            self.assertIn(value, config)
        self.shell(self.verify + '\n' + self.bundle_commands, False)
        self.assertFalse((self.root / 'bundle').exists())
        self.assert_no_host_dispatch()
        # Prove this is an executable attack, not a harmless config fixture.
        # Deliberately run the OLD vulnerable command only as a negative control.
        self.shell('git -C app diff --exit-code', True)
        self.assertTrue(self.sentinel.exists())
        self.assertTrue(self.network.exists())  # local stub, never actual network

    def test_tracked_content_metadata_symlink_and_fifo_replacements_block(self):
        path = self.app / 'tracked.txt'
        original = path.read_bytes()
        original_mode = path.stat().st_mode & 0o777
        for mutation in ('content', 'mode', 'symlink', 'fifo', 'parent-symlink'):
            with self.subTest(mutation=mutation):
                if mutation == 'content':
                    path.write_bytes(b'changed\n')
                elif mutation == 'mode':
                    path.chmod(original_mode ^ 0o100)
                elif mutation == 'symlink':
                    path.unlink()
                    path.symlink_to(self.source / 'tracked.txt')
                elif mutation == 'fifo':
                    path.unlink()
                    os.mkfifo(path)
                else:
                    moved = self.root / 'app-moved'
                    self.app.rename(moved)
                    self.app.symlink_to(moved, target_is_directory=True)
                self.shell(self.verify + '\n' + self.bundle_commands, False)
                self.assertFalse((self.root / 'bundle').exists())
                self.assert_no_host_dispatch()
                if mutation == 'parent-symlink':
                    self.app.unlink()
                    moved.rename(self.app)
                else:
                    path.unlink()
                    path.write_bytes(original)
                    path.chmod(original_mode)


class WorkflowBoundaryTests(unittest.TestCase):
    def test_all_28_actual_public_profiles_admitted_without_faking_builds(self):
        fixture = json.loads((ROOT / 'tests/releasefixtures/public_profiles.json').read_text())
        native = fixture['native_3ds_native']
        stubs = fixture['native_3ds_intentionally_failing_stubs']
        self.assertEqual(len(native), 17)
        self.assertEqual(len(stubs), 11)
        self.assertEqual(len(set(native + stubs)), 28)
        for name in native + stubs:
            repo = 'lafiabrew/' + name
            p = dict(fixture['policy_example'])
            p.update(repo=name, cia_asset=name+'.cia', native_target='3ds-native' if name in native else '3ds',
                     native_commands=[['make', '3ds-native' if name in native else '3ds'], ['make', 'verify-3ds']],
                     extra_engine_check=name in fixture['extra_engine_check'],
                     channel='stable' if name in native and name != '3ds_foldquest' else 'wip')
            with self.subTest(repo=repo):
                actual = kit.policy(kit.encode(p), repo)
                self.assertFalse(actual['publish_enabled'])
                self.assertEqual(actual['host_commands'], [['make', 'test']])
                self.assertEqual(actual['repo'], name)
                for bad_policy, bad_context in [(dict(p, repo=repo), repo),
                        (dict(p, repo='3ds_drop' if name != '3ds_drop' else '3ds_padtest'), repo),
                        (p, 'foreign/' + name)]:
                    with self.assertRaises(kit.GateError):
                        kit.policy(kit.encode(bad_policy), bad_context)

    def test_both_immutable_refs_production_validator(self):
        pin = 'a'*40
        kit.workflow_pin(kit.KIT_WORKFLOW + pin, pin, pin)
        for workflow_ref, kit_ref, executed in [(kit.KIT_WORKFLOW+'main', pin, pin),
                 (kit.KIT_WORKFLOW+pin, 'main', pin), (kit.KIT_WORKFLOW+'b'*40, pin, pin),
                 (kit.KIT_WORKFLOW+pin, pin, 'b'*40)]:
            with self.assertRaises(kit.GateError):
                kit.workflow_pin(workflow_ref, kit_ref, executed)

    def test_executed_inline_oidc_bootstrap_rejects_bad_claims_process(self):
        text = (ROOT / '.github/workflows/homebrew-release.yml').read_text()
        body = text.split('        run: |\n', 1)[1].split('\n  build:', 1)[0]
        code = '\n'.join(line[10:] for line in body.splitlines())
        pin = 'a'*40
        claims = {'iss': 'https://token.actions.githubusercontent.com', 'aud': 'homebrew-release-kit',
                  'exp': time.time()+3600, 'job_workflow_ref': kit.KIT_WORKFLOW+pin, 'job_workflow_sha': pin,
                  'repository': REPO, 'sha': SOURCE}
        with tempfile.TemporaryDirectory() as d:
            for label, change, input_pin, success in [('good', {}, pin, True),
                    ('workflow-main', {'job_workflow_ref': kit.KIT_WORKFLOW+'main'}, pin, False),
                    ('workflow-other-sha', {'job_workflow_ref': kit.KIT_WORKFLOW+'b'*40}, pin, False),
                    ('executed-other-sha', {'job_workflow_sha': 'b'*40}, pin, False),
                    ('kit-main', {}, 'main', False), ('repo', {'repository': 'evil/repo'}, pin, False),
                    ('issuer', {'iss': 'https://evil.example'}, pin, False),
                    ('audience', {'aud': 'other-kit'}, pin, False),
                    ('expired', {'exp': 1}, pin, False),
                    ('source', {'sha': 'b'*40}, pin, False)]:
                with self.subTest(label=label):
                    c = dict(claims, **change)
                    jwt = 'header.' + base64.urlsafe_b64encode(json.dumps(c).encode()).decode().rstrip('=') + '.signature'
                    # Only replace HTTPS transport; execute the exact production
                    # workflow bootstrap in a child Python interpreter.
                    seam = 'import urllib.request, io, json\n' + \
                           'urllib.request.urlopen = lambda *a, **k: io.StringIO(' + repr(json.dumps({'value': jwt})) + ')\n'
                    env = dict(os.environ, KIT_REF=input_pin, CANDIDATE_TAG=TAG,
                        ACTIONS_ID_TOKEN_REQUEST_URL='https://test.actions.githubusercontent.com/id?x=y',
                        ACTIONS_ID_TOKEN_REQUEST_TOKEN='read-only-oidc-fixture', GITHUB_REPOSITORY=REPO,
                        GITHUB_SHA=SOURCE, GITHUB_REF='refs/heads/main', GITHUB_OUTPUT=str(Path(d, label)))
                    p = subprocess.run([sys.executable, '-c', seam+code], env=env, capture_output=True, text=True)
                    self.assertEqual(p.returncode == 0, success, p.stderr)

    def test_token_ownership_upload_and_failed_job_boundaries(self):
        text = (ROOT / '.github/workflows/homebrew-release.yml').read_text()
        default, jobs = text.split('jobs:', 1)
        self.assertNotIn('contents: write', default)
        build, publisher = jobs.split('  publisher:', 1)
        self.assertNotIn('contents: write', build)
        self.assertIn('contents: write', publisher)
        self.assertIn("if: ${{ !inputs.dry_run && needs.build.result == 'success' }}", publisher)
        self.assertNotIn('path: app', publisher)
        self.assertNotIn('docker run', publisher)
        self.assertNotIn('make ', publisher)
        app_step = build.split('      - name: Tokenless isolated actual host/native gates', 1)[1].split('      - name:', 1)[0]
        self.assertNotIn('GH_TOKEN', app_step)
        self.assertNotIn('github.token', app_step)
        for line in app_step.splitlines():
            if 'docker run' in line:
                self.assertIn('--network none', line)
                self.assertNotIn('/var/run/docker.sock', line)
                self.assertNotIn('GITHUB_', line)
                self.assertIn('--cap-drop ALL', line)
                self.assertIn(':/kit:ro', line)
        upload = build.split('      - name: Transfer only a publication-admitted bundle', 1)[1]
        self.assertIn('if: ${{ !inputs.dry_run }}', upload)
        self.assertIn('persist-credentials: false', build)
        self.assertNotIn('${{', '\n'.join(x for x in text.splitlines() if 'run: python' in x))
        self.assertFalse(list((ROOT / 'tools/release_hub/approvals').glob('*.json')))


if __name__ == '__main__':
    unittest.main()
