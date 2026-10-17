import csv
import json
import tempfile
import unittest
from pathlib import Path

from hunting_workflow.assets import endpoint, export_inventory, normalize, read_rows
from hunting_workflow.io import WorkflowError


class AssetsTests(unittest.TestCase):
    def test_default_port_and_path_dedup(self):
        result = normalize([{"url": "https://Console.Example.Invalid/a"},
                            {"host": "console.example.invalid:443/b", "protocol": "https"}])
        self.assertEqual(result["summary"]["services"], 1)
        self.assertEqual(result["assets"][0]["source_rows"], [1, 2])

    def test_distinct_protocols_and_ports_stay_distinct(self):
        result = normalize([{"host": value} for value in
                            ["http://console.example.invalid", "https://console.example.invalid",
                             "http://console.example.invalid:8080"]])
        self.assertEqual(result["summary"]["services"], 3)

    def test_ipv6_and_idna(self):
        self.assertEqual(endpoint("2001:db8::1")["service"], "http://[2001:db8::1]")
        self.assertEqual(endpoint("https://[2001:db8::1]:8443/a")["port"], 8443)
        self.assertEqual(endpoint("https://例子.invalid")["host"], "xn--fsqu00a.invalid")

    def test_credentials_rejected_without_echo(self):
        result = normalize([{"url": "https://demo-user:DEMO-SECRET@console.example.invalid"}])
        self.assertEqual(result["summary"]["rejected_rows"], 1)
        self.assertNotIn("DEMO-SECRET", json.dumps(result))

    def test_invalid_ports_and_urls(self):
        for value in ["https://[broken", "http://console.example.invalid:70000", "ftp://console.example.invalid", "bad host"]:
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                endpoint(value)
        with self.assertRaises(WorkflowError):
            endpoint("http://console.example.invalid:8080", port="8081")

    def test_input_claims_never_become_verified_impact(self):
        result = normalize([{"host": "192.0.2.10", "organization": "Example Org", "status": "verified_affected"},
                            {"host": "192.0.2.11", "organization": "Example Org"}])
        self.assertEqual(result["summary"]["unique_hosts"], 2)
        self.assertEqual(result["summary"]["declared_organizations"], 1)
        self.assertIsNone(result["summary"]["verified_affected_instances"])
        self.assertTrue(all(x["evidence_status"] == "indexed_only" for x in result["assets"]))

    def test_csv_bom_text_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "assets.csv").write_text("\ufeffhost\nconsole.example.invalid\n", encoding="utf-8")
            self.assertEqual(len(read_rows(p / "assets.csv")), 1)
            (p / "assets.txt").write_text("# source\n\nconsole.example.invalid\n", encoding="utf-8")
            self.assertEqual(len(read_rows(p / "assets.txt")), 1)
            (p / "bad.json").write_text('{}', encoding="utf-8")
            with self.assertRaises(WorkflowError):
                read_rows(p / "bad.json")

    def test_output_is_new_and_json_lists_survive_csv(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "new"
            export_inventory(normalize([{"host": "console.example.invalid", "vendor": "Example Vendor"}]), output)
            with (output / "assets.csv").open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(json.loads(row["vendors"]), ["Example Vendor"])
            with self.assertRaises(WorkflowError):
                export_inventory(normalize([]), output)
