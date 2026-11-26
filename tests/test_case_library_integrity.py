from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_case_library_integrity.py"
LIBRARY = ROOT / "skills" / "mathematical-modeling" / "assets" / "case-library"


class CaseLibraryIntegrityTest(unittest.TestCase):
    def test_real_library_passes(self):
        result = subprocess.run(
            [sys.executable, str(CHECK), "--library", str(LIBRARY)],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_missing_card_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(LIBRARY, tmp, dirs_exist_ok=True)
            # Delete one card referenced by the index, then re-check.
            index = json.loads((Path(tmp) / "index.json").read_text(encoding="utf-8"))
            victim = Path(tmp) / index["cases"][0]["card_path"].split("/")[-1]
            victim.unlink()
            result = subprocess.run(
                [sys.executable, str(CHECK), "--library", str(tmp)],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CL-", result.stdout)

    def test_json_report_shape(self):
        result = subprocess.run(
            [sys.executable, str(CHECK), "--library", str(LIBRARY), "--json"],
            text=True, capture_output=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["pass"])
        self.assertEqual(payload["errors"], [])


if __name__ == "__main__":
    unittest.main()
