#!/usr/bin/env python3
"""Disposable Git negative controls; never use real private prose as fixtures."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from validate_public_hygiene import EXPECTED_APPS, check, git, main
from verify_preservation import AUTHORIZED_LINES, check_authorized, digest, server_parts, verify


class HygieneGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        consent = b"consent: true\nauto_report: true\n"
        for repo in (self.root, *(self.root / name for name in EXPECTED_APPS)):
            repo.mkdir(exist_ok=True)
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "Fixture")
            git(repo, "config", "user.email", "fixture@example.invalid")
            (repo / ".github").mkdir()
            (repo / ".github/wgm-hive.yml").write_bytes(consent)
            (repo / ".gitignore").write_text("sd_logs*/\n3ds_*/\n")
            (repo / "public.txt").write_text("Portable workspace\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "Fixture baseline")
        for name in AUTHORIZED_LINES:
            path = self.root / name
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text("".join(f"Public line {n}\n" for n in range(1, 21)))
        (self.root / "Makefile").write_text(
            "# Portable workspace\n\nPROJECTS := " + " ".join(EXPECTED_APPS) + "\n"
        )
        (self.root / "serve_3ds.py").write_text(
            '"""Public description."""\nprint(' + repr(" ".join(EXPECTED_APPS)) + ")\n"
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "Fixture prose")
        self.base_ref = git(self.root, "rev-parse", "HEAD").decode().strip()
        names = git(self.root, "ls-files", "-z").decode().strip("\0").split("\0")
        self.baseline = {
            "diagnostics": {},
            "server_ast": server_parts((self.root / "serve_3ds.py").read_bytes())[0],
            "repos": {
                ".": {
                    "head": self.base_ref,
                    "files": {name: digest((self.root / name).read_bytes()) for name in names},
                },
                **{
                    name: {"head": git(self.root / name, "rev-parse", "HEAD").decode().strip()}
                    for name in EXPECTED_APPS
                },
            },
        }

    def assert_rejected(self, reason):
        errors, _ = check(self.root)
        self.assertTrue(any(reason in error for error in errors), errors)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.root), 1)

    def test_clean_inventory_and_prose(self):
        # A complete portable checkout must pass both real guard implementations.
        self.assertEqual(check(self.root)[0], [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.root), 0)
            verify(self.root, self.baseline, self.base_ref)

    def test_missing_repository(self):
        # A missing child cannot silently reduce privacy coverage.
        repo = self.root / EXPECTED_APPS[0]
        repo.rename(self.root / "absent-child")
        self.assert_rejected("missing repository")

    def test_staged_private_path_with_clean_working_tree(self):
        # Cleaning disk alone must not hide a private staged blob, in any repo.
        examples = (
            "/" + "home" + "/" + "fixture-user" + "/workspace",
            "/" + "Users" + "/" + "fixture-user",
            "(" + "/" + "home" + "/" + "fixture-user" + ")",
            "C:" + "\\" + "Users" + "\\" + "fixture-user",
            "`" + "@" + "fixture-user" + "`",
        )
        for name in (".", *EXPECTED_APPS):
            repo = self.root / name
            path = repo / "public.txt"
            for example in examples:
                with self.subTest(repo=name, kind=examples.index(example)):
                    path.write_text(example + "\n")
                    git(repo, "add", "public.txt")
                    path.write_text("Portable workspace\n")
                    self.assert_rejected("index:")
                    git(repo, "add", "public.txt")

    def test_working_tree_private_path(self):
        # A clean index must not hide private text left on disk.
        (self.root / "public.txt").write_text("/" + "home" + "/fixture-user/workspace\n")
        self.assert_rejected("working tree: user-home path")

    def test_forced_diagnostic_staging(self):
        # Even ignored exports forced into root or child indexes must be rejected.
        for name in (".", *EXPECTED_APPS):
            repo = self.root / name
            path = repo / "sd_logs_fixture" / "report.txt"
            path.parent.mkdir()
            path.write_text("Synthetic export\n")
            git(repo, "add", "-f", "sd_logs_fixture/report.txt")
            self.assert_rejected("diagnostic export in index")
            git(repo, "rm", "--cached", "-q", "sd_logs_fixture/report.txt")

    def test_staged_consent_not_enabled(self):
        # Disk-only consent does not sanitize a disabled staged config.
        path = self.root / ".github/wgm-hive.yml"
        original = path.read_bytes()
        path.write_text("consent: false\nauto_report: true\n")
        git(self.root, "add", ".github/wgm-hive.yml")
        path.write_bytes(original)
        self.assert_rejected("index: consent missing or not enabled")

    def test_authorized_lines_only(self):
        # Every named prose boundary allows its lines, but rejects all others and insertions.
        for name, allowed in AUTHORIZED_LINES.items():
            original = (self.root / name).read_bytes()
            for number in range(1, len(original.splitlines()) + 1):
                lines = original.splitlines(keepends=True)
                lines[number - 1] = b"Changed public prose\n"
                with self.subTest(file=name, line=number):
                    if number in allowed:
                        check_authorized(name, original, b"".join(lines))
                    else:
                        with self.assertRaisesRegex(AssertionError, "outside authorized"):
                            check_authorized(name, original, b"".join(lines))
            with self.assertRaisesRegex(AssertionError, "Line count"):
                check_authorized(name, original, original + b"Extra line\n")

    def test_preservation_rejects_working_and_index_edits(self):
        # Exercise the Git-backed checker, not just its line-comparison helper.
        path = self.root / "AGENTS.md"
        original = path.read_bytes()
        path.write_bytes(original.replace(b"Public line 2\n", b"Unauthorized change\n"))
        with self.assertRaisesRegex(AssertionError, "outside authorized"):
            verify(self.root, self.baseline, self.base_ref)
        git(self.root, "add", "AGENTS.md")
        path.write_bytes(original)
        with self.assertRaisesRegex(AssertionError, "outside authorized"):
            verify(self.root, self.baseline, self.base_ref)

    def test_server_docstring_only(self):
        # AST parity alone misses comments; protect source outside the module docstring too.
        original = (self.root / "serve_3ds.py").read_bytes()
        check_authorized("serve_3ds.py", original, original.replace(b"Public description", b"Portable description"))
        for suffix in (b"# Extra comment\n", b"print('changed')\n"):
            with self.assertRaisesRegex(AssertionError, "outside module docstring"):
                check_authorized("serve_3ds.py", original, original + suffix)

    def test_concurrent_child_work_is_not_root_preservation_failure(self):
        # Legitimate child development is reported, not reset or compared to old hashes.
        (self.root / EXPECTED_APPS[0] / "public.txt").write_text("Concurrent public work\n")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            verify(self.root, self.baseline, self.base_ref)
        self.assertIn("1 changed tracked paths", output.getvalue())


if __name__ == "__main__":
    unittest.main()
