#!/usr/bin/env python3
"""Publication composition regressions; real catalogue builder, bounded docs fixtures.

These host tests prove file/transaction policy, not rendering or deployment.
Real Jekyll/browser and original catalogue probes are separate gates.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import compose_pages as composition
from pages_docs import load_manifest, output_path


def digest_tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory(prefix="pages-catalog-base-")
        cls.catalog = Path(cls.base.name) / "catalog"
        env = dict(os.environ, GITHUB_SHA="", GITHUB_TOKEN="", PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, str(ROOT / "tests/pages/build_fixture_catalog.py"),
                            "--output", str(cls.catalog)], env=env, text=True, capture_output=True, timeout=100)
        assert p.returncode == 0, p.stdout + p.stderr
        cls.policy = load_manifest(ROOT)

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pages-compose-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.catalog = self.folder / "catalog"
        shutil.copytree(type(self).catalog, self.catalog)
        self.docs = self.folder / "docs-build"
        self.docs.mkdir()
        for name in self.policy["outputs"]:
            p = self.docs / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("<!doctype html><p>Reviewed fixture</p>" if name.endswith(".html") else "asset bytes")
        self.output = self.folder / "published"
        self.env = mock.patch.dict(os.environ, {"GITHUB_SHA": "", "GITHUB_TOKEN": "", "JEKYLL_GITHUB_TOKEN": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_compose(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return composition.compose(self.catalog, self.docs, self.output)

    def assert_rejected_unchanged(self):
        before = (digest_tree(self.catalog), digest_tree(self.docs))
        with self.assertRaises((ValueError, OSError)):
            self.run_compose()
        self.assertEqual(before, (digest_tree(self.catalog), digest_tree(self.docs)))
        self.assertFalse(self.output.exists())

    def test_complete_composition_preserves_every_public_catalogue_byte(self):
        """The homepage/JSON/QR/style are copied exactly, not replaced by Jekyll."""
        before = digest_tree(self.catalog)
        result = self.run_compose()
        for name, digest in before.items():
            if name == ".catalog-build.json":
                self.assertFalse((self.output / name).exists())  # Local ownership metadata is not published.
            else:
                self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(before, digest_tree(self.catalog))
        self.assertEqual(set(result["pages"]), set(self.policy["pages"]))
        expected = set(before) - {".catalog-build.json"} | set(self.policy["outputs"]) | {composition.READY}
        self.assertEqual(set(digest_tree(self.output)), expected)

    def test_unapproved_jekyll_files_never_enter_output(self):
        """Generic SDK output may contain source; explicit publication paths must not."""
        for name in ["index.html", "AGENTS.html", "serve_3ds.py", "tests/private-capture.html"]:
            p = self.docs / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("not approved")
        self.run_compose()
        self.assertNotEqual((self.output / "index.html").read_text(), "not approved")
        for name in ["AGENTS.html", "serve_3ds.py", "tests/private-capture.html"]:
            self.assertFalse((self.output / name).exists())

    def test_missing_status_is_fatal(self):
        """The authoritative safety page cannot disappear behind source-only exceptions."""
        (self.docs / "docs/STATUS.html").unlink()
        self.assert_rejected_unchanged()

    def test_existing_output_is_never_replaced(self):
        self.output.mkdir(); (self.output / "valuable").write_bytes(b"keep")
        before = digest_tree(self.output)
        with self.assertRaises(ValueError): self.run_compose()
        self.assertEqual(before, digest_tree(self.output))

    def test_identifying_host_is_rejected_without_echoing_value(self):
        private = ".".join(["10", "34", "45", "56"])
        (self.docs / "docs/STATUS.html").write_text("<code>http://" + private + ":8766</code>")
        with self.assertRaises(ValueError) as caught: self.run_compose()
        self.assertNotIn(private, str(caught.exception))
        self.assertFalse(self.output.exists())

    def test_runtime_credential_material_blocks_publication(self):
        """A CI token must not enter any copied HTML/asset, even through templates."""
        token = "ghs_UNIQUE_PUBLICATION_TEST_SENTINEL_23456789"
        (self.docs / "assets/js/mermaid-loader.js").write_text(token)
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": token}):
            self.assert_rejected_unchanged()

    def test_unexpected_catalogue_artifact_is_fatal(self):
        (self.catalog / "AGENTS.html").write_text("unexpected source")
        self.assert_rejected_unchanged()

    def test_symlinked_approved_input_is_fatal(self):
        status = self.docs / "docs/STATUS.html"; status.unlink()
        outside = self.folder / "outside"; outside.write_text("private")
        status.symlink_to(outside)
        self.assert_rejected_unchanged()

    def test_mixed_source_sha_is_fatal(self):
        with mock.patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}):
            self.assert_rejected_unchanged()

    def test_copy_failure_removes_only_new_owned_output(self):
        """No ready artifact or modified input may survive a partial-copy failure."""
        before = (digest_tree(self.catalog), digest_tree(self.docs))
        original = shutil.copyfile
        calls = []
        def fail(source, dest):
            calls.append(str(dest))
            if len(calls) == 2: raise OSError("INJECT_COPY_FAILURE")
            return original(source, dest)
        with mock.patch.object(composition.shutil, "copyfile", side_effect=fail):
            with self.assertRaisesRegex(OSError, "INJECT_COPY_FAILURE"): self.run_compose()
        self.assertEqual(len(calls), 2)
        self.assertFalse(self.output.exists())
        self.assertEqual(before, (digest_tree(self.catalog), digest_tree(self.docs)))

    def test_failed_cleanup_retains_named_ownership_and_no_ready_manifest(self):
        """Do not pretend a failed removal succeeded or forget the partial output."""
        receipt = io.StringIO()
        with mock.patch.object(composition.shutil, "copyfile", side_effect=OSError("INJECT_COPY_FAILURE")), \
             mock.patch.object(composition.shutil, "rmtree", side_effect=PermissionError("INJECT_CLEANUP_FAILURE")), \
             contextlib.redirect_stderr(receipt):
            with self.assertRaisesRegex(OSError, "INJECT_COPY_FAILURE"):
                composition.compose(self.catalog, self.docs, self.output)
        self.assertTrue(self.output.is_dir())
        self.assertFalse((self.output / composition.READY).exists())
        self.assertIn("RETAINED", receipt.getvalue())
        self.assertIn(str(self.output), receipt.getvalue())

    def test_cli_sigterm_during_copy_is_loud_and_preserves_inputs(self):
        """Send a real signal through the CLI boundary, not just a local exception."""
        before = (digest_tree(self.catalog), digest_tree(self.docs))
        code = '''import os,signal,sys
sys.path.insert(0, sys.argv[1])
import compose_pages as c
original = c.shutil.copyfile
def interrupt(source, dest):
    result=original(source,dest)
    print("INJECT_SIGTERM_AFTER_COPY",flush=True)
    os.kill(os.getpid(),signal.SIGTERM)
    return result
c.shutil.copyfile=interrupt
sys.argv=["compose_pages.py","--catalog",sys.argv[2],"--docs",sys.argv[3],"--output",sys.argv[4]]
raise SystemExit(c.main())
'''
        p = subprocess.run([sys.executable, "-c", code, str(ROOT / "tools"), str(self.catalog), str(self.docs), str(self.output)],
                           text=True, capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("INJECT_SIGTERM_AFTER_COPY", p.stdout)
        self.assertIn("Owned incomplete", p.stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(before, (digest_tree(self.catalog), digest_tree(self.docs)))


class ManifestTests(unittest.TestCase):
    def test_required_status_cannot_be_hidden(self):
        """A policy edit cannot waive the safety page through a new exception."""
        manifest = json.loads((ROOT / "site/docs-manifest.json").read_text())
        manifest["source_only"].append("docs/STATUS.md")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "site").mkdir()
            (root / "site/docs-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): load_manifest(root, check_inventory=False)

    def test_publication_routes_cannot_escape_or_overwrite_homepage(self):
        for route in ["index.html", "../index.html", "docs/../index.html", "/docs/STATUS.html"]:
            manifest = json.loads((ROOT / "site/docs-manifest.json").read_text())
            manifest["pages"]["docs/STATUS.md"] = route
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); (root / "site").mkdir()
                (root / "site/docs-manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError, msg=route): load_manifest(root, check_inventory=False)


class GuideSafetyTests(unittest.TestCase):
    def test_current_install_guide_does_not_instruct_destructive_bypass(self):
        """Restore current docs without carrying the legacy downgrade-delete recipe."""
        text = (ROOT / "docs/INSTALL_FROM_HUB.md").read_text()
        self.assertIn("If FBI refuses a downgrade, **stop**", text)
        self.assertNotIn("delete the title in **FBI", text)
        self.assertNotIn("page currently live at that URL is the older", text)
        self.assertNotIn("have **not** been independently reviewed, merged", text)
        self.assertIn("60269b3", text)
        self.assertIn("A versioned URL alone does not establish immutable bytes", text)


class RunbookControlTests(unittest.TestCase):
    def test_exact_standalone_journey_stops_and_preserves_original_failure(self):
        """PATH seams prove shell sequencing; real runtime gates remain separate."""
        script = ROOT / "tests/pages/validate_composed.sh"
        with tempfile.TemporaryDirectory(prefix="pages-runbook-") as temporary:
            folder = Path(temporary); binaries = folder / "bin"; binaries.mkdir()
            workspaces = folder / "workspaces"; workspaces.mkdir()
            for name in ["python3", "podman", "sh", "npm", "node"]:
                stub = binaries / name
                stub.write_text('#!/bin/sh\nprintf "%s %s\\n" "$(basename "$0")" "$*" >> "$CALL_LOG"\n'
                                'if [ "$FAIL_FIRST" = 1 ] && [ ! -f "$MARKER" ]; then\n'
                                ' touch "$MARKER"; echo "INJECT_PREREQUISITE_EXIT_23"; exit 23\nfi\nexit 0\n')
                stub.chmod(0o755)
            canary = folder / "canary.sh"
            source = script.read_text()
            needle = '  [ "$status" -eq 0 ] || exit "$status"'
            self.assertEqual(source.count(needle), 1)
            canary.write_text(source.replace(needle, "  : # deliberately swallow the error"))
            observed = []
            for label, target, inject in [("control", script, False), ("failure", script, True), ("canary", canary, True)]:
                calls = folder / (label + ".calls"); marker = folder / (label + ".marker")
                env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                           TMPDIR=str(workspaces), CHROMIUM_EXECUTABLE="/bin/true", CALL_LOG=str(calls),
                           MARKER=str(marker), FAIL_FIRST="1" if inject else "0")
                p = subprocess.run(["/bin/sh", str(target)], cwd=ROOT, env=env, text=True, capture_output=True, timeout=20)
                log = calls.read_text().splitlines(); observed.append((p, log))
                if inject: self.assertTrue(marker.exists(), "failure injection did not execute")
                if label == "failure":
                    self.assertEqual(p.returncode, 23)
                    self.assertEqual(len(log), 1)
                    self.assertIn("INJECT_PREREQUISITE_EXIT_23", p.stdout)
                    self.assertTrue(any("INJECT_PREREQUISITE_EXIT_23" in f.read_text() for f in workspaces.glob("*/privacy.log")))
            self.assertEqual(observed[0][0].returncode, 0)
            self.assertEqual(len(observed[0][1]), 9)
            self.assertEqual(observed[2][0].returncode, 0)
            self.assertGreater(len(observed[2][1]), 1)  # Harness observes that the canary violates the stop contract.


class WorkflowIntegrationTests(unittest.TestCase):
    def test_only_composed_artifact_can_be_uploaded_after_browser_gates(self):
        """Prevent a green catalogue build from silently dropping docs again."""
        text = (ROOT / ".github/workflows/pages.yml").read_text()
        compose = text.index("python3 tools/compose_pages.py --catalog _site")
        browser = text.index("node tests/pages/test_pages.cjs --site-dir")
        upload = text.index("- name: Upload Pages artifact")
        self.assertLess(compose, browser)
        self.assertLess(browser, upload)
        self.assertIn("path: ${{ runner.temp }}/3ds-pages-publication", text)
        self.assertIn('CONTAINER_RUNTIME: docker', text)
        self.assertIn('needs: build', text)

    def test_docs_changes_trigger_the_existing_publisher(self):
        """Docs fixes must reach Pages rather than waiting on an unrelated release."""
        text = (ROOT / ".github/workflows/pages.yml").read_text()
        for path in ["docs/**", "specs/**", "_includes/**", "assets/**", "site/**", "tests/pages/**",
                     "tools/compose_pages.py", "tools/pages_docs.py", "tests/test_pages_integration.py"]:
            self.assertIn("- '" + path + "'", text)


if __name__ == "__main__":
    unittest.main()
