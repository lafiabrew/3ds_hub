from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "rollout_release.py"
FIX = ROOT / "tests" / "rolloutfixtures"
WORK_BASE = FIX / "_work"


def run_cmd(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd or ROOT, text=True, capture_output=True)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def mk_repo(path: Path, branch: str = "main") -> str:
    path.mkdir(parents=True, exist_ok=True)
    run_cmd(["git", "init", "-b", branch, str(path)])
    run_cmd(["git", "-C", str(path), "config", "user.email", "test@example.com"])
    run_cmd(["git", "-C", str(path), "config", "user.name", "Test User"])
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    run_cmd(["git", "-C", str(path), "add", "README.md"])
    run_cmd(["git", "-C", str(path), "commit", "-m", "init"], cwd=path)
    head = run_cmd(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout.strip()
    return head


class RolloutPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        WORK_BASE.mkdir(parents=True, exist_ok=True)

    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="rr-", dir=WORK_BASE))

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_help_and_bogus_flag(self) -> None:
        ok = run_cmd(["python3", str(TOOL), "--help"])
        self.assertEqual(ok.returncode, 0)
        self.assertIn("plan", ok.stdout)

        bad = run_cmd(["python3", str(TOOL), "plan", "--bogus"])
        self.assertNotEqual(bad.returncode, 0)

    def test_plan_requires_matching_repo_sets(self) -> None:
        kit = "a" * 40
        audit = {"rows": [{"repo": "3ds_a", "head_sha": "1" * 40, "branch": "main"}]}
        profiles = {"rows": []}
        readiness = {"rows": [{"repo": "3ds_a", "source_sha": "1" * 40}]}
        a = self.workdir / "audit.json"
        p = self.workdir / "profiles.json"
        r = self.workdir / "readiness.json"
        o = self.workdir / "plan.json"
        write_json(a, audit)
        write_json(p, profiles)
        write_json(r, readiness)

        cp = run_cmd([
            "python3",
            str(TOOL),
            "plan",
            "--audit",
            str(a),
            "--profiles",
            str(p),
            "--readiness",
            str(r),
            "--kit-ref",
            kit,
            "--output",
            str(o),
        ])
        self.assertEqual(cp.returncode, 2)
        self.assertFalse(o.exists())

    def test_plan_rejects_stale_profile_sha(self) -> None:
        kit = "b" * 40
        audit = {"rows": [{"repo": "3ds_a", "head_sha": "1" * 40, "branch": "main"}]}
        profiles = {
            "rows": [
                {
                    "repo": "3ds_a",
                    "source_sha": "2" * 40,
                    "native_target": "3ds",
                    "targets": ["3ds", "verify-3ds", "test"],
                }
            ]
        }
        readiness = {"rows": [{"repo": "3ds_a", "source_sha": "1" * 40}]}
        a = self.workdir / "audit.json"
        p = self.workdir / "profiles.json"
        r = self.workdir / "readiness.json"
        o = self.workdir / "plan.json"
        write_json(a, audit)
        write_json(p, profiles)
        write_json(r, readiness)

        cp = run_cmd([
            "python3",
            str(TOOL),
            "plan",
            "--audit",
            str(a),
            "--profiles",
            str(p),
            "--readiness",
            str(r),
            "--kit-ref",
            kit,
            "--output",
            str(o),
        ])
        self.assertEqual(cp.returncode, 2)
        self.assertIn("profile source_sha", cp.stderr)
        self.assertFalse(o.exists())

    def test_plan_rejects_missing_verify_target(self) -> None:
        kit = "c" * 40
        audit = {"rows": [{"repo": "3ds_a", "head_sha": "1" * 40, "branch": "main"}]}
        profiles = {
            "rows": [
                {
                    "repo": "3ds_a",
                    "source_sha": "1" * 40,
                    "native_target": "3ds",
                    "targets": ["3ds", "test"],
                }
            ]
        }
        readiness = {"rows": [{"repo": "3ds_a", "source_sha": "1" * 40}]}
        a = self.workdir / "audit.json"
        p = self.workdir / "profiles.json"
        r = self.workdir / "readiness.json"
        o = self.workdir / "plan.json"
        write_json(a, audit)
        write_json(p, profiles)
        write_json(r, readiness)

        cp = run_cmd([
            "python3",
            str(TOOL),
            "plan",
            "--audit",
            str(a),
            "--profiles",
            str(p),
            "--readiness",
            str(r),
            "--kit-ref",
            kit,
            "--output",
            str(o),
        ])
        self.assertEqual(cp.returncode, 2)
        self.assertIn("verify-3ds", cp.stderr)

    def test_plan_works_on_real_28_repo_inputs(self) -> None:
        pages_run = os.environ.get("PAGES_RUN")
        self.assertTrue(pages_run, "PAGES_RUN env var must exist")
        kit = "d" * 40
        out = self.workdir / "plan-real.json"
        cp = run_cmd([
            "python3",
            str(TOOL),
            "plan",
            "--audit",
            str(Path(pages_run) / "reports" / "REPO_AUDIT.json"),
            "--profiles",
            str(Path(pages_run) / "reports" / "BUILD_PROFILES.json"),
            "--readiness",
            str(Path(pages_run) / "reports" / "RELEASE_READINESS.json"),
            "--kit-ref",
            kit,
            "--output",
            str(out),
        ])
        self.assertEqual(cp.returncode, 0, cp.stderr)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(data["repos"]), 28)
        repo_names = {r["repo"] for r in data["repos"]}
        self.assertIn("3ds_drop", repo_names)
        self.assertIn("3ds_supaplex", repo_names)

    def test_apply_dry_run_and_idempotent_paths(self) -> None:
        # Build a single-repo plan using minimal fixtures
        repo = "3ds_fixture"
        sha = "1" * 40
        kit = "e" * 40
        audit = {"rows": [{"repo": repo, "head_sha": sha, "branch": "main"}]}
        profiles = {"rows": [{"repo": repo, "source_sha": sha, "native_target": "3ds", "targets": ["test", "3ds", "verify-3ds"]}]}
        readiness = {
            "rows": [
                {
                    "repo": repo,
                    "source_sha": sha,
                    "tags": [],
                    "stable_releases": [],
                    "eligibility": "blocked",
                    "publish_enabled": False,
                    "blockers": ["blocked"],
                }
            ]
        }
        a = self.workdir / "audit.json"
        p = self.workdir / "profiles.json"
        r = self.workdir / "readiness.json"
        plan = self.workdir / "plan.json"
        write_json(a, audit)
        write_json(p, profiles)
        write_json(r, readiness)

        cp1 = run_cmd([
            "python3", str(TOOL), "plan", "--audit", str(a), "--profiles", str(p), "--readiness", str(r), "--kit-ref", kit, "--output", str(plan)
        ])
        self.assertEqual(cp1.returncode, 0, cp1.stderr)

        repos_root = self.workdir / "repos"
        repo_dir = repos_root / repo
        head = mk_repo(repo_dir)
        heads = self.workdir / "heads.json"
        write_json(heads, {repo: head})
        open_prs = self.workdir / "open-prs.json"
        open_prs.write_text("[]\n", encoding="utf-8")
        receipt = self.workdir / "apply.json"

        cp2 = run_cmd([
            "python3", str(TOOL), "apply", "--plan", str(plan), "--kit-ref", kit, "--repos-root", str(repos_root),
            "--expected-heads", str(heads), "--open-prs-json", str(open_prs), "--dry-run", "--output", str(receipt)
        ])
        self.assertEqual(cp2.returncode, 0, cp2.stderr)

        data = json.loads(receipt.read_text(encoding="utf-8"))
        changed = {c["path"] for c in data["receipts"][0]["changes"]}
        self.assertEqual(changed, {".github/workflows/homebrew-release.yml", ".github/homebrew-release.json", "docs/RELEASING.md"})

    def test_apply_rejects_dirty_repo(self) -> None:
        repo = "3ds_fixture"
        kit = "f" * 40
        plan = {
            "mode": "plan",
            "kit_ref": kit,
            "repos": [{"repo": repo, "rendered_contents": {
                ".github/workflows/homebrew-release.yml": "a\n",
                ".github/homebrew-release.json": "{}\n",
                "docs/RELEASING.md": "b\n",
            }}],
        }
        plan_path = self.workdir / "plan.json"
        write_json(plan_path, plan)
        repos_root = self.workdir / "repos"
        repo_dir = repos_root / repo
        mk_repo(repo_dir)
        (repo_dir / "DIRTY.txt").write_text("dirty\n", encoding="utf-8")

        cp = run_cmd([
            "python3", str(TOOL), "apply", "--plan", str(plan_path), "--kit-ref", kit, "--repos-root", str(repos_root),
            "--dry-run", "--output", str(self.workdir / "out.json")
        ])
        self.assertEqual(cp.returncode, 2)
        self.assertIn("dirty", cp.stderr.lower())

    def test_apply_rejects_conflicting_existing_file(self) -> None:
        repo = "3ds_fixture"
        kit = "1" * 40
        plan = {
            "mode": "plan",
            "kit_ref": kit,
            "repos": [{"repo": repo, "rendered_contents": {
                ".github/workflows/homebrew-release.yml": "expected\n",
                ".github/homebrew-release.json": "{}\n",
                "docs/RELEASING.md": "doc\n",
            }}],
        }
        plan_path = self.workdir / "plan.json"
        write_json(plan_path, plan)
        repos_root = self.workdir / "repos"
        repo_dir = repos_root / repo
        mk_repo(repo_dir)
        wf = repo_dir / ".github" / "workflows"
        wf.mkdir(parents=True, exist_ok=True)
        (wf / "homebrew-release.yml").write_text("different\n", encoding="utf-8")
        run_cmd(["git", "-C", str(repo_dir), "add", ".github/workflows/homebrew-release.yml"])
        run_cmd(["git", "-C", str(repo_dir), "commit", "-m", "add conflicting workflow"], cwd=repo_dir)

        cp = run_cmd([
            "python3", str(TOOL), "apply", "--plan", str(plan_path), "--kit-ref", kit, "--repos-root", str(repos_root),
            "--dry-run", "--output", str(self.workdir / "out.json")
        ])
        self.assertEqual(cp.returncode, 2)
        self.assertIn("conflict", cp.stderr.lower())

    def test_apply_rejects_open_pr_cap(self) -> None:
        repo = "3ds_fixture"
        kit = "2" * 40
        plan = {
            "mode": "plan",
            "kit_ref": kit,
            "repos": [{"repo": repo, "rendered_contents": {
                ".github/workflows/homebrew-release.yml": "x\n",
                ".github/homebrew-release.json": "{}\n",
                "docs/RELEASING.md": "y\n",
            }}],
        }
        plan_path = self.workdir / "plan.json"
        write_json(plan_path, plan)
        repos_root = self.workdir / "repos"
        mk_repo(repos_root / repo)

        open_prs = self.workdir / "open-prs.json"
        open_prs.write_text(json.dumps([1, 2, 3, 4, 5, 6]) + "\n", encoding="utf-8")

        cp = run_cmd([
            "python3", str(TOOL), "apply", "--plan", str(plan_path), "--kit-ref", kit, "--repos-root", str(repos_root),
            "--open-prs-json", str(open_prs), "--dry-run", "--output", str(self.workdir / "out.json")
        ])
        self.assertEqual(cp.returncode, 2)
        self.assertIn("cap", cp.stderr.lower())

    def test_apply_detects_head_race(self) -> None:
        repo = "3ds_fixture"
        kit = "3" * 40
        plan = {
            "mode": "plan",
            "kit_ref": kit,
            "repos": [{"repo": repo, "rendered_contents": {
                ".github/workflows/homebrew-release.yml": "x\n",
                ".github/homebrew-release.json": "{}\n",
                "docs/RELEASING.md": "y\n",
            }}],
        }
        plan_path = self.workdir / "plan.json"
        write_json(plan_path, plan)
        repos_root = self.workdir / "repos"
        repo_dir = repos_root / repo
        head = mk_repo(repo_dir)

        heads = self.workdir / "heads.json"
        # Intentionally stale expected head
        write_json(heads, {repo: "4" * 40})

        cp = run_cmd([
            "python3", str(TOOL), "apply", "--plan", str(plan_path), "--kit-ref", kit, "--repos-root", str(repos_root),
            "--expected-heads", str(heads), "--dry-run", "--output", str(self.workdir / "out.json")
        ])
        self.assertEqual(cp.returncode, 2)
        self.assertIn("HEAD changed", cp.stderr)


if __name__ == "__main__":
    unittest.main()
