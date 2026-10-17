import tempfile
import unittest
from pathlib import Path

from tools.audit_public import audit, scan_text


class PublicationTests(unittest.TestCase):
    def test_example_domains_and_documentation_addresses_are_allowed(self):
        self.assertEqual(scan_text("researcher@example.invalid 192.0.2.10 198.51.100.20 203.0.113.1"), [])

    def test_private_details_are_detected_without_echo(self):
        address = "8" + ".8" * 3
        token = "gh" + "p_" + "A" * 32
        findings = scan_text("person@" + "private.invalid-domain.com\n" + address + "\n" + token)
        labels = {x[0] for x in findings}
        self.assertTrue({"non-example-email", "non-example-ip", "token"} <= labels)
        self.assertNotIn(token, str(findings))

    def test_unapproved_file_is_not_published(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("safe", encoding="utf-8")
            (root / "private-export.json").write_text("{}", encoding="utf-8")
            result = audit(root)
            self.assertFalse(result["ok"])
            self.assertEqual(result["findings"][0]["kind"], "outside-public-allowlist")

    def test_even_internal_symlinks_fail_publication_check(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("safe", encoding="utf-8")
            try:
                (root / "NOTICE.md").symlink_to("README.md")
            except OSError as exc:
                self.skipTest(str(exc))
            result = audit(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any(x["kind"] == "symlink" for x in result["findings"]))
