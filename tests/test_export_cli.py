import contextlib
import io
import json
import shutil
import socket
import subprocess
import sys
import zipfile
from unittest.mock import patch

from hunting_workflow.cli import demo, main
from hunting_workflow.io import WorkflowError
from hunting_workflow.render import build_case, export_bundle
from tests.helpers import CaseFixture, ROOT


class ExportTests(CaseFixture):
    def test_bundle_is_standalone_and_integrity_checked(self):
        output = self.base / "bundle"
        build_case(self.path, output)
        archive = self.base / "review.zip"
        export_bundle(output, archive)
        with zipfile.ZipFile(archive) as z:
            self.assertIn("manifest.json", z.namelist())
            self.assertIn("report.html", z.namelist())
            self.assertIn(b"SYNTHETIC DEMO", z.read("evidence/001.txt"))
            self.assertTrue(all((x.external_attr >> 16) & 0o170000 != 0o120000 for x in z.infolist()))
        (output / "report.md").write_text("modified", encoding="utf-8")
        with self.assertRaises(WorkflowError):
            export_bundle(output, self.base / "modified.zip")
        self.assertFalse((self.base / "modified.zip").exists())

    def test_export_rejects_manifest_traversal_before_creating_zip(self):
        output = self.base / "bundle"
        build_case(self.path, output)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"][0]["path"] = "../outside.txt"
        (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(WorkflowError):
            export_bundle(output, self.base / "bad.zip")
        self.assertFalse((self.base / "bad.zip").exists())

    def test_malformed_manifest_returns_an_actionable_error(self):
        output = self.base / "bundle"
        build_case(self.path, output)
        (output / "manifest.json").write_text('{"format":"hunting-review-bundle-1","files":null}', encoding="utf-8")
        with self.assertRaises(WorkflowError):
            export_bundle(output, self.base / "bad.zip")

    def test_html_escapes_case_text(self):
        self.case["description"] = "</pre><script>alert('fixture')</script>"
        self.save()
        output = self.base / "html"
        build_case(self.path, output)
        text = (output / "report.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)

    def test_incomplete_drafts_are_labeled_and_build_success_is_separate(self):
        output = self.base / "missing"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["case", "build", str(ROOT / "examples/missing-case/case.json"), "--output", str(output)]), 0)
        review = json.loads((output / "readiness.json").read_text(encoding="utf-8"))
        self.assertFalse(review["materials_complete"])
        self.assertIn("MISSING", (output / "report.md").read_text(encoding="utf-8"))

    def test_case_check_exit_code_and_new_output_protection(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["case", "check", str(self.path)]), 2)
        output = self.base / "bundle"
        build_case(self.path, output)
        before = (output / "report.md").read_bytes()
        with self.assertRaises(WorkflowError):
            build_case(self.path, output)
        self.assertEqual(before, (output / "report.md").read_bytes())

    def test_demo_runs_with_network_and_dns_disabled(self):
        output = self.base / "demo"
        with patch.object(socket, "create_connection", side_effect=AssertionError("network disabled")), \
             patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS disabled")), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("connect disabled")), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(demo(output), 0)
        summary = json.loads((output / "demo-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["inventory"]["services"], 4)
        self.assertEqual(summary["target_requests"], 0)
        self.assertGreater(len(summary["missing_case"]["missing_rules"]), 10)

    def test_cloned_repo_runs_outside_current_directory(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "run.py"), "demo", "--output", str(self.base / "outside")],
                                cwd=self.base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_input_error_is_actionable(self):
        with contextlib.redirect_stderr(io.StringIO()) as stream:
            self.assertEqual(main(["case", "check", str(self.base / "missing.json")]), 1)
        self.assertIn("Cannot read JSON", stream.getvalue())
