from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'rollout_release.py'
FIX = ROOT / 'tests' / 'rolloutfixtures'
KIT = 'e' * 40
OWNED = {'.github/workflows/homebrew-release.yml', '.github/homebrew-release.json', 'docs/RELEASING.md'}


def run_cmd(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(argv, cwd=cwd or ROOT, text=True, capture_output=True)
    if os.environ.get('ROLLOUT_PROCESS_LOG'):
        with open(os.environ['ROLLOUT_PROCESS_LOG'], 'a') as log:
            log.write(json.dumps({'argv': argv, 'cwd': str(cwd or ROOT), 'exit': cp.returncode,
                                  'stdout': cp.stdout, 'stderr': cp.stderr}) + '\n')
    return cp


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + '\n')


def mk_repo(path: Path, branch: str = 'main') -> str:
    path.mkdir(parents=True, exist_ok=True)
    commands = [['init', '-b', branch, str(path)]]
    for args in commands:
        cp = run_cmd(['/usr/bin/git', *args])
        if cp.returncode:
            raise AssertionError(cp.stderr)
    for key, value in [('user.email', 'test@example.com'), ('user.name', 'Test User')]:
        run_cmd(['/usr/bin/git', '-C', str(path), 'config', key, value])
    (path / 'README.md').write_text('fixture\n')
    run_cmd(['/usr/bin/git', '-C', str(path), 'add', 'README.md'])
    cp = run_cmd(['/usr/bin/git', '-C', str(path), 'commit', '-m', 'init'])
    if cp.returncode:
        raise AssertionError(cp.stderr)
    return run_cmd(['/usr/bin/git', '-C', str(path), 'rev-parse', 'HEAD']).stdout.strip()


class RolloutPlannerTests(unittest.TestCase):
    @staticmethod
    def source_snapshot():
        status = run_cmd(['/usr/bin/git', 'status', '--porcelain=v1', '--untracked-files=all']).stdout
        paths = run_cmd(['/usr/bin/git', 'ls-files', '-co', '--exclude-standard', '-z']).stdout.split('\0')
        content = {}
        for rel in set(paths) - {''}:
            path = ROOT / rel
            if path.is_symlink():
                content[rel] = ('symlink', os.readlink(path))
            elif path.is_file():
                content[rel] = (path.stat().st_mode, hashlib.sha256(path.read_bytes()).hexdigest())
        return status, content

    @classmethod
    def setUpClass(cls):
        cls.source_before = cls.source_snapshot()

    @classmethod
    def tearDownClass(cls):
        if cls.source_before != cls.source_snapshot():
            raise AssertionError('suite modified guarded source status/content')

    def setUp(self) -> None:
        # TMPDIR is coordinator-provided on the project volume; public CI uses
        # the standard system temporary directory. Never create source scratch.
        self.workdir = Path(tempfile.mkdtemp(prefix='rr-')).absolute()
        self.assertNotIn(ROOT, self.workdir.parents)
        self.work_identity = (self.workdir.stat().st_dev, self.workdir.stat().st_ino)
        self.root = self.workdir / 'repos'
        self.cfg_path = self.workdir / 'transport.json'
        self.cfg = {'remotes': {}}
        write_json(self.cfg_path, self.cfg)
        bin_dir = self.workdir / 'bin'
        bin_dir.mkdir()
        for name in ('git', 'gh'):
            target = bin_dir / name
            shutil.copyfile(FIX / 'transport.py', target)
            target.chmod(0o755)
        self.env = patch.dict(os.environ, {'PATH': str(bin_dir) + ':' + os.environ['PATH'],
                                          'ROLLOUT_TEST_TRANSPORT': str(self.cfg_path)})
        self.env.start()
        self.audit = {'rows': []}
        self.profiles = {'rows': []}
        self.readiness = {'rows': []}
        self.plan_path = self.workdir / 'plan.json'
        self.output = self.workdir / 'receipt.json'

    def tearDown(self) -> None:
        self.env.stop()
        self.assertFalse(self.workdir.is_symlink())
        self.assertEqual((self.workdir.stat().st_dev, self.workdir.stat().st_ino), self.work_identity)
        shutil.rmtree(self.workdir)
        self.assertFalse(self.workdir.exists(), 'owned temporary directory cleanup failed')

    def new_receipt(self):
        self.output = self.workdir / ('receipt-' + str(len(list(self.workdir.glob('receipt*.json')))) + '.json')

    def git(self, repo, *args):
        cp = run_cmd(['/usr/bin/git', '-C', str(self.root / repo), *args])
        self.assertEqual(cp.returncode, 0, cp.stderr)
        return cp.stdout.strip()

    def add_repo(self, repo='3ds_fixture'):
        path = self.root / repo
        sha = mk_repo(path)
        self.git(repo, 'remote', 'add', 'origin', f'https://github.com/lafiabrew/{repo}.git')
        bare = self.workdir / (repo + '.git')
        cp = run_cmd(['/usr/bin/git', 'clone', '--bare', str(path), str(bare)])
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.cfg['remotes'][repo] = str(bare)
        write_json(self.cfg_path, self.cfg)
        self.audit['rows'].append({'repo': repo, 'head_sha': sha, 'branch': 'main'})
        self.profiles['rows'].append({'repo': repo, 'source_sha': sha, 'native_target': '3ds',
                                      'targets': ['test', '3ds', 'verify-3ds']})
        self.readiness['rows'].append({'repo': repo, 'source_sha': sha, 'tags': [], 'stable_releases': [],
                                      'eligibility': 'blocked', 'blockers': ['Exact-source approval absent']})
        return sha

    def plan(self, kit=KIT):
        for name, data in [('audit', self.audit), ('profiles', self.profiles), ('readiness', self.readiness)]:
            write_json(self.workdir / (name + '.json'), data)
        return run_cmd(['python3', str(TOOL), 'plan', '--audit', str(self.workdir / 'audit.json'),
                        '--profiles', str(self.workdir / 'profiles.json'), '--readiness', str(self.workdir / 'readiness.json'),
                        '--kit-ref', kit, '--output', str(self.plan_path)])

    def good_plan(self):
        cp = self.plan()
        self.assertEqual(cp.returncode, 0, cp.stderr)
        return json.loads(self.plan_path.read_text())

    def apply(self, *extra, verify=False):
        return run_cmd(['python3', str(TOOL), 'verify-publish' if verify else 'apply', '--plan', str(self.plan_path),
                        '--kit-ref', KIT, '--repos-root', str(self.root), '--output', str(self.output), *extra])

    def snapshot(self):
        # Includes index bytes, tracked/untracked output bytes, refs and remote refs.
        values = {}
        for base in [self.root, *(Path(p) for p in self.cfg['remotes'].values())]:
            if not base.exists():
                continue
            for p in base.rglob('*'):
                if p.is_symlink():
                    values[str(p)] = ('link', os.readlink(p))
                elif p.is_file():
                    values[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return values

    def rejected_unchanged(self, *args, contains=None):
        before = self.snapshot()
        receipt_before = self.output.read_bytes() if self.output.exists() else None
        cp = self.apply(*args)
        self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
        if contains:
            self.assertIn(contains, cp.stderr)
        self.assertEqual(self.snapshot(), before, cp.stderr)
        self.assertEqual(self.output.read_bytes() if self.output.exists() else None, receipt_before)
        return cp

    def test_help_and_bogus_flag(self):
        for command in [[], ['plan'], ['apply'], ['verify-publish']]:
            self.assertEqual(run_cmd(['python3', str(TOOL), *command, '--help']).returncode, 0)
        self.assertNotEqual(run_cmd(['python3', str(TOOL), 'plan', '--bogus']).returncode, 0)
        self.assertNotEqual(run_cmd(['python3', str(TOOL), 'apply', '--open-prs-json', 'x']).returncode, 0)

    def test_plan_requires_matching_repo_sets(self):
        self.add_repo()
        self.profiles['rows'] = []
        self.assertEqual(self.plan().returncode, 2)
        self.assertFalse(self.plan_path.exists())

    def test_plan_rejects_stale_profile_sha(self):
        self.add_repo()
        self.profiles['rows'][0]['source_sha'] = '2' * 40
        cp = self.plan()
        self.assertEqual(cp.returncode, 2)
        self.assertIn('profile source_sha', cp.stderr)
        self.assertFalse(self.plan_path.exists())

    def test_plan_rejects_missing_verify_target(self):
        self.add_repo()
        self.profiles['rows'][0]['targets'].remove('verify-3ds')
        cp = self.plan()
        self.assertEqual(cp.returncode, 2)
        self.assertIn('verify-3ds', cp.stderr)

    def test_plan_works_on_real_28_repo_inputs(self):
        public = FIX / 'public28'
        provenance = json.loads((public / 'provenance.json').read_text())
        for name, digest in provenance['fixture_sha256'].items():
            self.assertEqual(hashlib.sha256((public / name).read_bytes()).hexdigest(), digest)
        cp = run_cmd(['python3', str(TOOL), 'plan', '--audit', str(public / 'audit.json'),
                      '--profiles', str(public / 'profiles.json'), '--readiness', str(public / 'readiness.json'),
                      '--kit-ref', KIT, '--output', str(self.plan_path)])
        self.assertEqual(cp.returncode, 0, cp.stderr)
        data = json.loads(self.plan_path.read_text())
        self.assertEqual(len(data['repos']), 28)
        self.assertEqual(len(provenance['sources']), 28)
        self.assertEqual({r['repo']: r['source_sha'] for r in data['repos']},
                         {r['repo']: r['source_sha'] for r in provenance['sources']})
        self.assertEqual(sum(r['published_existing'] for r in data['repos']), 16)
        self.assertEqual(sum(r['current_version'] == 'untagged' for r in data['repos']), 12)
        self.assertEqual(sum(r['expected_commands']['native_commands'][0] == ['make', '3ds-native'] for r in data['repos']), 17)
        self.assertEqual(sum(r['expected_commands']['native_commands'][0] == ['make', '3ds'] for r in data['repos']), 11)
        for source in provenance['sources']:
            self.assertEqual(source['public_owner'], 'lafiabrew')
            self.assertIn('/' + source['source_sha'] + '/Makefile', source['makefile_url'])
            self.assertRegex(source['makefile_git_blob'], r'^[a-f0-9]{40}$')
            self.assertRegex(source['makefile_sha256'], r'^[a-f0-9]{64}$')
        self.assertIn('3ds_drop', {r['repo'] for r in data['repos']})
        self.assertIn('3ds_supaplex', {r['repo'] for r in data['repos']})
        engine_repos = {row['repo'] for row in data['repos'] if json.loads(row['rendered_contents']['.github/homebrew-release.json'])['extra_engine_check']}
        self.assertEqual(engine_repos, {'3ds_foldquest'})
        foldquest = next(row for row in data['repos'] if row['repo'] == '3ds_foldquest')
        self.assertEqual(foldquest['expected_commands']['extra_engine_command'], ['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_contract.py', '-v'])
        self.assertIn('make test &&\npython3 -m unittest discover', foldquest['rendered_contents']['docs/RELEASING.md'])
        self.assertIn('zero tests is not acceptance', foldquest['rendered_contents']['docs/RELEASING.md'])
        for row in data['repos']:
            self.assertIs(row['publish_enabled'], False)
            self.assertEqual(set(row['rendered_contents']), OWNED)
            self.assertIn('After this commit is installed on public main: CI configured = true', row['rendered_contents']['docs/RELEASING.md'])

    def test_apply_dry_run_and_idempotent_paths(self):
        self.add_repo()
        self.good_plan()
        before = self.snapshot()
        cp = self.apply('--dry-run')
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(before, self.snapshot())
        data = json.loads(self.output.read_text())
        self.assertEqual({c['path'] for c in data['receipts'][0]['changes']}, OWNED)
        first_receipt = self.output.read_bytes()
        first_output = self.output
        self.new_receipt()
        cp = self.apply()
        self.assertEqual(cp.returncode, 0, cp.stderr)
        applied = self.snapshot()
        self.new_receipt()
        cp = self.apply()
        self.assertEqual(first_output.read_bytes(), first_receipt)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(applied, self.snapshot())
        status = self.git('3ds_fixture', 'ls-files', '--others', '--exclude-standard').splitlines()
        self.assertEqual(set(status), OWNED)

    def test_apply_rejects_dirty_repo(self):
        self.add_repo()
        self.good_plan()
        (self.root / '3ds_fixture/DIRTY.txt').write_text('dirty')
        self.rejected_unchanged(contains='dirty')

    def test_apply_rejects_conflicting_existing_file(self):
        self.add_repo()
        self.good_plan()
        path = self.root / '3ds_fixture/.github/homebrew-release.json'
        path.parent.mkdir()
        path.write_text('conflict')
        self.rejected_unchanged(contains='conflict')
        self.assertFalse((path.parent / 'workflows').exists())

    def test_apply_rejects_open_pr_cap(self):
        self.add_repo()
        self.good_plan()
        self.cfg['open_count'] = 5
        write_json(self.cfg_path, self.cfg)
        self.rejected_unchanged(contains='cap')

    def test_apply_detects_head_race(self):
        self.add_repo()
        self.good_plan()
        heads = self.workdir / 'heads.json'
        write_json(heads, {'3ds_fixture': '4' * 40})
        self.rejected_unchanged('--expected-heads', str(heads), contains='HEAD changed')

    def test_default_source_pin_cannot_be_overridden(self):
        self.add_repo()
        self.good_plan()
        self.git('3ds_fixture', 'commit', '--allow-empty', '-m', 'new actual local source')
        heads = self.workdir / 'heads.json'
        write_json(heads, {'3ds_fixture': self.git('3ds_fixture', 'rev-parse', 'HEAD')})
        self.rejected_unchanged(contains='HEAD changed')
        self.rejected_unchanged('--expected-heads', str(heads), contains='cannot override')

    def test_staged_and_unstaged_changes_preserved(self):
        self.add_repo()
        self.good_plan()
        path = self.root / '3ds_fixture/README.md'
        path.write_text('staged')
        self.git('3ds_fixture', 'add', 'README.md')
        path.write_text('unstaged too')
        self.rejected_unchanged(contains='dirty')

    def test_wrong_origin_push_origin_and_git_root(self):
        self.add_repo()
        self.good_plan()
        self.git('3ds_fixture', 'remote', 'set-url', 'origin', 'https://github.com/foreign/3ds_fixture.git')
        self.rejected_unchanged(contains='origin')
        self.git('3ds_fixture', 'remote', 'set-url', 'origin', 'https://github.com/lafiabrew/3ds_fixture.git')
        self.git('3ds_fixture', 'config', 'remote.origin.pushurl', 'https://github.com/foreign/3ds_fixture.git')
        self.rejected_unchanged(contains='push origin')

    def test_wrong_branch_and_detached_head(self):
        self.add_repo()
        self.good_plan()
        self.git('3ds_fixture', 'switch', '-c', 'other')
        self.rejected_unchanged(contains='branch')
        self.git('3ds_fixture', 'checkout', '--detach')
        self.rejected_unchanged()

    def test_archived_foreign_private_or_wrong_default_api_identity(self):
        self.add_repo()
        self.good_plan()
        for identity in [{'archived': True}, {'private': True}, {'full_name': 'foreign/3ds_fixture'}, {'default_branch': 'develop'}]:
            with self.subTest(identity=identity):
                self.cfg['identity'] = identity
                write_json(self.cfg_path, self.cfg)
                self.rejected_unchanged(contains='admission')

    def test_actual_remote_main_not_local_tracking_ref(self):
        self.add_repo()
        self.good_plan()
        self.git('3ds_fixture', 'commit', '--allow-empty', '-m', 'other remote source')
        other = self.git('3ds_fixture', 'rev-parse', 'HEAD')
        # Return local HEAD without reset; actual bare main moves independently.
        self.git('3ds_fixture', 'update-ref', 'refs/heads/main', self.audit['rows'][0]['head_sha'])
        bare = self.cfg['remotes']['3ds_fixture']
        run_cmd(['/usr/bin/git', '-C', str(self.root / '3ds_fixture'), 'push', bare, other + ':refs/heads/main'])
        self.rejected_unchanged(contains='actual remote main')

    def test_second_probe_remote_race_no_outputs(self):
        original = self.add_repo()
        self.git('3ds_fixture', 'commit', '--allow-empty', '-m', 'race object')
        race = self.git('3ds_fixture', 'rev-parse', 'HEAD')
        bare = self.cfg['remotes']['3ds_fixture']
        cp = run_cmd(['/usr/bin/git', '-C', str(self.root / '3ds_fixture'), 'push', bare, race + ':refs/heads/race-object'])
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.git('3ds_fixture', 'update-ref', 'refs/heads/main', original)
        self.good_plan()
        self.cfg.update({'race_at': 2, 'race_sha': race})
        write_json(self.cfg_path, self.cfg)
        before = {k: v for k, v in self.snapshot().items() if str(self.root) in k}
        cp = self.apply()
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('actual remote main', cp.stderr)
        after = {k: v for k, v in self.snapshot().items() if str(self.root) in k}
        self.assertEqual(before, after)
        self.assertFalse(self.output.exists())
        actual = run_cmd(['/usr/bin/git', '--git-dir', bare, 'rev-parse', 'main']).stdout.strip()
        self.assertEqual(actual, race, 'concurrent remote must be preserved, not repaired')

    def test_local_head_race_inside_final_remote_probe_preserves_concurrent_head(self):
        original = self.add_repo()
        self.git('3ds_fixture', 'commit', '--allow-empty', '-m', 'concurrent local source')
        race = self.git('3ds_fixture', 'rev-parse', 'HEAD')
        self.git('3ds_fixture', 'update-ref', 'refs/heads/main', original)
        self.good_plan()
        self.cfg.update({'local_race_at': 2, 'race_sha': race})
        write_json(self.cfg_path, self.cfg)
        index = (self.root / '3ds_fixture/.git/index').read_bytes()
        cp = self.apply()
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('HEAD changed during remote probe', cp.stderr)
        self.assertEqual(self.git('3ds_fixture', 'rev-parse', 'HEAD'), race)
        self.assertEqual((self.root / '3ds_fixture/.git/index').read_bytes(), index)
        self.assertFalse((self.root / '3ds_fixture/.github').exists())
        self.assertFalse((self.root / '3ds_fixture/docs').exists())
        self.assertFalse(self.output.exists())

    def test_all_repositories_preflight_before_first_write(self):
        self.add_repo('3ds_a')
        self.add_repo('3ds_b')
        self.good_plan()
        p = self.root / '3ds_b/docs/RELEASING.md'
        p.parent.mkdir()
        p.write_text('conflict last repo last path')
        self.rejected_unchanged(contains='conflict')
        self.assertFalse((self.root / '3ds_a/.github').exists())

    def test_symlink_ancestors_and_dangling_symlinks_even_dry_run(self):
        self.add_repo()
        self.good_plan()
        outside = self.workdir / 'outside'
        outside.mkdir()
        p = self.root / '3ds_fixture/.github'
        for target in [outside, self.workdir / 'dangling']:
            p.symlink_to(target, target_is_directory=True)
            self.rejected_unchanged('--dry-run', contains='symlink')
            self.rejected_unchanged(contains='symlink')
            p.unlink()
        docs = self.root / '3ds_fixture/docs'
        docs.mkdir()
        (docs / 'RELEASING.md').symlink_to(self.workdir / 'missing')
        self.rejected_unchanged('--dry-run', contains='symlink')

    def test_repos_root_symlink_rejected(self):
        self.add_repo()
        self.good_plan()
        link = self.workdir / 'root-link'
        link.symlink_to(self.root, target_is_directory=True)
        self.rejected_unchanged('--repos-root', str(link), contains='symlink')

    def test_directory_output_and_receipt_inside_repo_rejected(self):
        self.add_repo()
        self.good_plan()
        docs = self.root / '3ds_fixture/docs/RELEASING.md'
        docs.mkdir(parents=True)
        self.rejected_unchanged(contains='regular file')
        self.rejected_unchanged('--output', str(self.root / 'unexpected.json'), contains='outside')

    def test_plan_mutations_rejected_production_cli(self):
        self.add_repo()
        original = self.good_plan()
        mutations = []
        for repo in ['../escape', '/absolute', 'foreign/3ds_a', '3ds_hub', '3ds_a\n']:
            data = copy.deepcopy(original)
            data['repos'][0]['repo'] = repo
            mutations.append(data)
        for key, value in [('source_sha', 'x' * 40), ('publish_enabled', True), ('unexpected', 1)]:
            data = copy.deepcopy(original)
            data['repos'][0][key] = value
            mutations.append(data)
        for path, content in [('docs/RELEASING.md', '<script>bad</script>'), ('.github/homebrew-release.json', '{"publish_enabled":true}'),
                              ('.github/workflows/homebrew-release.yml', 'uses: foreign/workflow@main'), ('extra.txt', 'arbitrary')]:
            data = copy.deepcopy(original)
            data['repos'][0]['rendered_contents'][path] = content
            # Recomputed hashes must not authorize malicious text.
            data['repos'][0]['rendered_files'][path] = {'path': path, 'bytes': len(content.encode()), 'sha256': hashlib.sha256(content.encode()).hexdigest()}
            mutations.append(data)
        data = copy.deepcopy(original)
        data['repos'][0]['rendered_files']['docs/RELEASING.md']['sha256'] = '0' * 64
        mutations.append(data)
        for i, data in enumerate(mutations):
            with self.subTest(mutation=i):
                write_json(self.plan_path, data)
                self.rejected_unchanged()

    def test_invalid_audit_admission_missing_targets_stale_readiness(self):
        self.add_repo()
        original = copy.deepcopy(self.audit)
        for key, value in [('repo', '../escape'), ('repo', '3ds_hub'), ('head_sha', 'a' * 39), ('head_sha', 'G' * 40),
                           ('archived', True), ('private', True), ('full_name', 'foreign/3ds_fixture'), ('branch', 'dev')]:
            self.audit = copy.deepcopy(original)
            self.audit['rows'][0][key] = value
            cp = self.plan()
            self.assertEqual(cp.returncode, 2, cp.stderr)
            self.assertFalse(self.plan_path.exists())
        self.audit = original
        self.profiles['rows'][0]['targets'].remove('3ds')
        self.assertEqual(self.plan().returncode, 2)
        self.profiles['rows'][0]['targets'].append('3ds')
        self.readiness['rows'][0]['source_sha'] = '1' * 40
        self.assertEqual(self.plan().returncode, 2)

    def test_global_probe_failure_and_pending_batch_cap(self):
        self.add_repo('3ds_a')
        self.add_repo('3ds_b')
        self.good_plan()
        self.cfg['open_count'] = 4
        write_json(self.cfg_path, self.cfg)
        self.rejected_unchanged(contains='cap')
        cp = self.apply('--repo', '3ds_a', '--dry-run')
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.new_receipt()
        self.cfg['gh_fail'] = True
        write_json(self.cfg_path, self.cfg)
        self.rejected_unchanged(contains='probe failed')

    def test_kit_must_be_public_main_reachable_with_regular_workflow(self):
        self.add_repo()
        self.good_plan()
        for field in ['kit_unreachable', 'kit_missing']:
            with self.subTest(field=field):
                self.cfg[field] = True
                write_json(self.cfg_path, self.cfg)
                self.rejected_unchanged(contains='kit pin')
                self.cfg[field] = False

    def test_matching_pin_required_and_invalid_caps(self):
        self.add_repo()
        self.good_plan()
        self.rejected_unchanged('--kit-ref', 'a' * 40, contains='mismatch')
        self.rejected_unchanged('--kit-ref', 'main')
        for cap in ['0', '-1', '6']:
            self.rejected_unchanged('--max-open-prs', cap)

    def test_rendered_caller_contract_and_metadata_escaping(self):
        self.add_repo()
        self.readiness['rows'][0].update({'eligibility': '<script>alert(1)</script>',
                                          'blockers': ['<img src=x onerror=alert(1)> [link](https://evil) `code` {{KIT_SHA}}', '/home/person/raw-session']})
        data = self.good_plan()
        files = data['repos'][0]['rendered_contents']
        workflow = files['.github/workflows/homebrew-release.yml']
        for key in ['approval_id', 'approval_ref', 'dry_run', 'release_tag', 'kit_ref']:
            self.assertIn(key + ':', workflow)
        self.assertIn('default: true', workflow)
        self.assertIn('contents: read', workflow)
        self.assertIn('@' + KIT, workflow)
        self.assertNotIn('<script>', files['docs/RELEASING.md'])
        self.assertNotIn('<img', files['docs/RELEASING.md'])
        self.assertNotIn('/home/person', files['docs/RELEASING.md'])
        self.assertIn('v0.1.0', files['docs/RELEASING.md'])
        self.assertIn('&#123;&#123;KIT', files['docs/RELEASING.md'])
        self.assertIs(json.loads(files['.github/homebrew-release.json'])['publish_enabled'], False)

    def test_current_cap_race_before_first_write_is_nonmutating(self):
        self.add_repo()
        self.good_plan()
        self.cfg['cap_race_at'] = 2
        write_json(self.cfg_path, self.cfg)
        self.rejected_unchanged(contains='cap')
        self.assertFalse((self.root / '3ds_fixture/.github').exists())

    def test_actual_remote_default_branch_not_just_github_metadata(self):
        sha = self.add_repo()
        self.good_plan()
        bare = self.cfg['remotes']['3ds_fixture']
        for args in [['update-ref', 'refs/heads/develop', sha], ['symbolic-ref', 'HEAD', 'refs/heads/develop']]:
            cp = run_cmd(['/usr/bin/git', '--git-dir', bare, *args])
            self.assertEqual(cp.returncode, 0, cp.stderr)
        self.rejected_unchanged(contains='actual remote main')

    def test_nested_git_root_rejected(self):
        sha = mk_repo(self.root)
        nested = self.root / '3ds_fixture'
        nested.mkdir()
        self.audit['rows'] = [{'repo': '3ds_fixture', 'head_sha': sha, 'branch': 'main'}]
        self.profiles['rows'] = [{'repo': '3ds_fixture', 'source_sha': sha, 'native_target': '3ds', 'targets': ['test', '3ds', 'verify-3ds']}]
        self.readiness['rows'] = [{'repo': '3ds_fixture', 'source_sha': sha}]
        # GH probe still enumerates a real organization repository via its seam.
        self.cfg['remotes'] = {'3ds_fixture': str(self.workdir / 'unused.git')}
        write_json(self.cfg_path, self.cfg)
        self.good_plan()
        self.rejected_unchanged(contains='exact Git root')

    def test_strict_json_and_boolean_schema(self):
        self.add_repo()
        original = self.good_plan()
        for mutate in [lambda d: d.update(schema=True),
                       lambda d: d['repos'][0].update(publish_enabled=0),
                       lambda d: d.update(unexpected='output'),
                       lambda d: d['repos'].append(copy.deepcopy(d['repos'][0])),
                       lambda d: d['repos'][0]['rendered_contents'].pop('docs/RELEASING.md')]:
            data = copy.deepcopy(original)
            mutate(data)
            write_json(self.plan_path, data)
            self.rejected_unchanged()
        self.plan_path.write_text('{"mode":"plan","mode":"plan"}')
        self.rejected_unchanged(contains='duplicate JSON key')

    def test_public_generated_policy_omits_private_reason(self):
        self.add_repo()
        self.readiness['rows'][0]['blockers'] = ['/home/person/raw-session.log']
        row = self.good_plan()['repos'][0]
        for text in row['rendered_contents'].values():
            self.assertNotIn('/home/person', text)
            self.assertNotIn('raw-session.log', text)

    def test_immutable_plan_and_receipt_outputs_before_api(self):
        self.add_repo()
        self.good_plan()
        original_plan = self.plan_path.read_bytes()
        self.assertEqual(self.plan().returncode, 2)
        self.assertEqual(self.plan_path.read_bytes(), original_plan)
        self.cfg['gh_fail'] = True  # refusal must precede all API preflights
        write_json(self.cfg_path, self.cfg)
        for kind in ['regular', 'dangling', 'ancestor', 'source']:
            with self.subTest(kind=kind):
                self.output = self.workdir / ('old-' + kind + '.json')
                if kind == 'regular':
                    self.output.write_bytes(b'prior immutable receipt')
                elif kind == 'dangling':
                    self.output.symlink_to(self.workdir / 'missing')
                elif kind == 'ancestor':
                    link = self.workdir / 'output-link'
                    link.symlink_to(self.workdir, target_is_directory=True)
                    self.output = link / 'new.json'
                else:
                    self.output = TOOL
                before = self.snapshot()
                cp = self.apply()
                self.assertEqual(cp.returncode, 2, cp.stderr)
                self.assertNotIn('probe failed', cp.stderr)
                self.assertEqual(before, self.snapshot())
                if kind == 'regular':
                    self.assertEqual(self.output.read_bytes(), b'prior immutable receipt')
                elif kind == 'dangling':
                    self.assertTrue(self.output.is_symlink())
                # Same actual CLI parser/plan command rejects these output paths.
                old_plan_path = self.plan_path
                self.plan_path = self.output
                cp = self.plan()
                self.plan_path = old_plan_path
                self.assertEqual(cp.returncode, 2, cp.stderr)
                self.assertEqual(original_plan, self.plan_path.read_bytes())

    def test_new_output_in_guarded_source_refused(self):
        self.add_repo()
        self.good_plan()
        self.output = ROOT / 'never-create-rollout-output.json'
        self.assertFalse(os.path.lexists(self.output))
        self.rejected_unchanged(contains='guarded tool source')
        self.plan_path = self.output
        cp = self.plan()
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('guarded tool source', cp.stderr)
        self.assertFalse(os.path.lexists(self.output))

    def test_late_receipt_existence_and_symlink_races_before_repo_writes(self):
        self.add_repo()
        self.good_plan()
        outside = self.workdir / 'outside'
        outside.mkdir()
        for kind in ['regular', 'symlink', 'ancestor']:
            with self.subTest(kind=kind):
                self.output = self.workdir / ('late-' + kind + '.json')
                if kind == 'ancestor':
                    self.output = self.workdir / 'late-parent' / 'receipt.json'
                self.cfg.update(output_race_at=2, output_race_kind=kind,
                                output_race_path=str(self.output), output_race_target=str(outside), remote_probes=0)
                write_json(self.cfg_path, self.cfg)
                before = self.snapshot()
                cp = self.apply()
                self.assertEqual(cp.returncode, 2, cp.stderr)
                self.assertIn('partial local I/O', cp.stderr)
                self.assertEqual(before, self.snapshot())
                self.assertEqual(list(outside.iterdir()), [])
                if kind == 'regular':
                    self.assertEqual(self.output.read_bytes(), b'late competing output')
                elif kind == 'symlink':
                    self.assertTrue(self.output.is_symlink())
                else:
                    self.assertTrue(self.output.parent.is_symlink())

    def test_plan_late_creation_controls_actual_main(self):
        self.add_repo()
        self.good_plan()
        # Invoke production main/parser with only a local filesystem boundary
        # fault seam, never a production test flag or replacement planner.
        for kind in ['regular', 'symlink', 'ancestor']:
            target = self.workdir / ('late-plan-' + kind + '.json')
            outside = self.workdir / ('outside-' + kind)
            outside.mkdir()
            if kind == 'ancestor':
                target = self.workdir / 'late-plan-parent' / 'plan.json'
            script = '''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import rollout_release as tool
real = tool._open_exclusive
kind, target, outside = sys.argv[2:5]
def race(path):
    p = Path(target)
    if kind == 'regular': p.write_bytes(b'late plan bytes')
    elif kind == 'symlink': p.symlink_to(outside)
    else: p.parent.symlink_to(outside, target_is_directory=True)
    return real(path)
tool._open_exclusive = race
sys.exit(tool.main(sys.argv[5:]))
'''
            cp = run_cmd(['python3', '-B', '-c', script, str(TOOL.parent), kind, str(target), str(outside),
                          'plan', '--audit', str(self.workdir / 'audit.json'), '--profiles', str(self.workdir / 'profiles.json'),
                          '--readiness', str(self.workdir / 'readiness.json'), '--kit-ref', KIT, '--output', str(target)])
            self.assertEqual(cp.returncode, 2, cp.stderr)
            self.assertIn('partial local I/O', cp.stderr)
            self.assertEqual(list(outside.iterdir()), [])
            if kind == 'regular':
                self.assertEqual(target.read_bytes(), b'late plan bytes')

    def test_private_archived_rollout_prs_count_and_visibility_fail_closed(self):
        self.add_repo()
        self.good_plan()
        # Synthetic transport identity only; no private production name/payload.
        self.cfg.update(private_repos=['3ds_hidden_fixture'], private_open_count=1, open_count=4)
        write_json(self.cfg_path, self.cfg)
        self.rejected_unchanged(contains='cap')  # 4 public + 1 private + pending 1 > 5
        self.cfg['open_count'] = 3
        write_json(self.cfg_path, self.cfg)
        cp = self.apply('--dry-run')
        self.assertEqual(cp.returncode, 0, cp.stderr)
        receipt = json.loads(self.output.read_text())
        self.assertEqual(receipt['open_prs_seen'] + receipt['pending_batch'], 5)
        for settings in [{'private_total_unavailable': True}, {'private_total_unavailable': False, 'private_total': 2}]:
            self.new_receipt()
            self.cfg.update(settings)
            write_json(self.cfg_path, self.cfg)
            self.rejected_unchanged(contains='global PR cap unproven')

    def test_global_cap_includes_noncaller_repository_namespace(self):
        self.add_repo()
        self.good_plan()
        self.cfg.update(private_repos=['noncaller-hidden-fixture'], private_open_count=5)
        write_json(self.cfg_path, self.cfg)
        self.rejected_unchanged(contains='cap')
        self.assertFalse((self.root / '3ds_fixture/.github').exists())

    def test_prepared_branch_publish_boundary_positive_and_negative(self):
        self.add_repo()
        self.good_plan()
        cp = self.apply()
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.git('3ds_fixture', 'switch', '-c', 'rollout/homebrew-release')
        self.git('3ds_fixture', 'add', *sorted(OWNED))
        self.git('3ds_fixture', 'commit', '-m', 'Configure release metadata')
        before = self.snapshot()
        self.new_receipt()
        cp = self.apply('--repo', '3ds_fixture', verify=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(before, self.snapshot())
        (self.root / '3ds_fixture/README.md').write_text('extra source edit')
        self.git('3ds_fixture', 'add', 'README.md')
        self.git('3ds_fixture', 'commit', '--amend', '--no-edit')
        self.new_receipt()
        cp = self.apply('--repo', '3ds_fixture', verify=True)
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('exactly the three', cp.stderr)


if __name__ == '__main__':
    unittest.main()
