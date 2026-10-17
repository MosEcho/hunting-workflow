import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CaseFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.case_dir = self.base / "case"
        shutil.copytree(ROOT / "examples/complete-case", self.case_dir)
        self.path = self.case_dir / "case.json"
        self.case = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self):
        self.path.write_text(json.dumps(self.case, ensure_ascii=False), encoding="utf-8")
        return self.path
