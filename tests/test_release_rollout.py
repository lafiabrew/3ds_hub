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
WORK_BASE = FIX / '_work'
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
    @classmethod
    def setUpClass(cls) -> None:
        WORK_BASE.mkdir(parents=True, exist_ok=True)

    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix='rr-', dir=WORK_BASE))
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
        shutil.rmtree(self.workdir)

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
        pages = Path(os.environ['PAGES_RUN'])
        cp = run_cmd(['python3', str(TOOL), 'plan', '--audit', str(pages / 'reports/REPO_AUDIT.json'),
                      '--profiles', str(pages / 'reports/BUILD_PROFILES.json'), '--readiness', str(pages / 'reports/RELEASE_READINESS.json'),
                      '--kit-ref', KIT, '--output', str(self.plan_path)])
        self.assertEqual(cp.returncode, 0, cp.stderr)
        data = json.loads(self.plan_path.read_text())
        self.assertEqual(len(data['repos']), 28)
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
        cp = self.apply()
        self.assertEqual(cp.returncode, 0, cp.stderr)
        applied = self.snapshot()
        cp = self.apply()
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

    def test_prepared_branch_publish_boundary_positive_and_negative(self):
        self.add_repo()
        self.good_plan()
        cp = self.apply()
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.git('3ds_fixture', 'switch', '-c', 'rollout/homebrew-release')
        self.git('3ds_fixture', 'add', *sorted(OWNED))
        self.git('3ds_fixture', 'commit', '-m', 'Configure release metadata')
        before = self.snapshot()
        cp = self.apply('--repo', '3ds_fixture', verify=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(before, self.snapshot())
        (self.root / '3ds_fixture/README.md').write_text('extra source edit')
        self.git('3ds_fixture', 'add', 'README.md')
        self.git('3ds_fixture', 'commit', '--amend', '--no-edit')
        cp = self.apply('--repo', '3ds_fixture', verify=True)
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('exactly the three', cp.stderr)


if __name__ == '__main__':
    unittest.main()
