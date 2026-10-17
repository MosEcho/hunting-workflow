import hashlib
from pathlib import Path

from hunting_workflow.cases import inspect_case
from hunting_workflow.schema import validate
from tests.helpers import CaseFixture, ROOT


class EvidenceTests(CaseFixture):
    def review(self):
        return inspect_case(self.save())[1]

    def rule(self, ident):
        return next(x for x in self.review()["rules"] if x["id"] == ident)

    def test_complete_synthetic_is_material_complete_but_blocked(self):
        review = self.review()
        self.assertTrue(review["materials_complete"])
        self.assertFalse(review["ready_for_manual_submission_review"])
        self.assertEqual(review["platform_acceptance"], "not_assessed")

    def test_one_instance_has_no_invented_ten_case_threshold(self):
        self.assertEqual(len(self.case["affected_instances"]), 1)
        self.assertEqual(self.rule("instance_records")["state"], "pass")

    def test_missing_case_lists_actionable_missing_fields(self):
        _, review = inspect_case(ROOT / "examples/missing-case/case.json")
        missing = {x["id"] for x in review["rules"] if x["state"] == "missing"}
        self.assertTrue({"versions", "wire_evidence", "originality_record", "remediation"} <= missing)

    def test_changed_evidence_is_rejected(self):
        (self.case_dir / "evidence/response.txt").write_text("Changed bytes", encoding="utf-8")
        self.assertEqual(self.rule("evidence_integrity")["state"], "missing")

    def test_duplicate_ids_and_missing_claim_refs_fail(self):
        self.case["evidence"].append(dict(self.case["evidence"][0]))
        self.case["claims"][0]["evidence_ids"] = ["EV-DOES-NOT-EXIST"]
        review = self.review()
        states = {x["id"]: x["state"] for x in review["rules"]}
        self.assertEqual(states["evidence_integrity"], "missing")
        self.assertEqual(states["claim_traceability"], "missing")

    def test_path_traversal_is_rejected(self):
        outside = self.base / "outside.txt"
        outside.write_text("outside fixture", encoding="utf-8")
        self.case["evidence"][0]["path"] = "../outside.txt"
        self.case["evidence"][0]["sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
        self.assertEqual(self.rule("evidence_integrity")["state"], "missing")

    def test_symlink_evidence_is_rejected(self):
        link = self.case_dir / "evidence/link.txt"
        try:
            link.symlink_to("request.txt")
        except OSError as exc:
            self.skipTest(str(exc))
        self.case["evidence"][0]["path"] = "evidence/link.txt"
        self.assertEqual(self.rule("evidence_integrity")["state"], "missing")

    def test_human_verification_and_originality_are_independent(self):
        self.case["verification"]["human_reviewed"] = False
        self.case["originality"]["status"] = "possible_duplicate"
        states = {x["id"]: x["state"] for x in self.review()["rules"]}
        self.assertEqual(states["human_verification"], "missing")
        self.assertEqual(states["originality_record"], "missing")

    def test_static_claim_is_not_a_verified_impact(self):
        self.case["claims"][0]["status"] = "static"
        self.assertEqual(self.rule("claim_traceability")["state"], "missing")

    def test_wrong_scope_and_version_evidence_fail(self):
        self.case["scope"]["authorized_targets"] = ["https://other.example.invalid"]
        self.case["affected_versions"][0]["evidence_ids"] = ["EV-REQ"]
        states = {x["id"]: x["state"] for x in self.review()["rules"]}
        self.assertEqual(states["scope_record"], "missing")
        self.assertEqual(states["version_evidence"], "missing")

    def test_bad_scope_url_returns_a_finding_not_a_crash(self):
        self.case["scope"]["authorized_targets"] = ["https://[broken"]
        self.assertEqual(self.rule("scope_record")["state"], "missing")

    def test_unknown_scope_and_instance_without_wire_refs_fail(self):
        self.case["scope"]["basis"] = "unknown"
        self.case["affected_instances"][0]["evidence_ids"] = ["EV-VERSION"]
        states = {x["id"]: x["state"] for x in self.review()["rules"]}
        self.assertEqual(states["scope_record"], "missing")
        self.assertEqual(states["instance_records"], "missing")

    def test_changing_demo_flag_does_not_erase_fixture_markers(self):
        self.case["synthetic"] = False
        review = self.review()
        self.assertTrue(review["synthetic"])
        self.assertFalse(review["materials_complete"])
        self.assertFalse(review["ready_for_manual_submission_review"])

    def test_unknown_fields_and_wrong_types_are_schema_errors(self):
        self.case["unexpected_credential"] = "DEMO"
        self.case["verification"]["human_reviewed"] = "true"
        review = self.review()
        self.assertFalse(review["schema_valid"])
        self.assertGreaterEqual(len(review["rules"]), 2)

    def test_schema_engine_rejects_unsupported_keywords(self):
        with self.assertRaises(ValueError):
            validate({}, {"type": "object", "unsupportedRule": True})
