import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "venv_guard.py"


class VenvGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("venv_guard", SCRIPT)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_missing_environment_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.module.check(Path(tmp))
        self.assertFalse(result["ok"])
        self.assertFalse(result["venv_exists"])

    def test_guard_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            before = sorted(project.iterdir())
            self.module.check(project)
            self.assertEqual(before, sorted(project.iterdir()))


if __name__ == "__main__":
    unittest.main()
