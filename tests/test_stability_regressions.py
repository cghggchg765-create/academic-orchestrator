from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StabilityRegressionTest(unittest.TestCase):
    def test_mcp_real_namespaces_match(self):
        checker = load("mcp_boot_check_regression", ROOT / "scripts" / "mcp_boot_check.py")
        self.assertTrue(checker._category_matches("论文搜索MCP(paper-mcp)", "mcp__paper-mcp"))
        self.assertTrue(checker._category_matches("论文搜索MCP(paper-mcp)", "paper-mcp@1.2.0"))
        self.assertTrue(checker._category_matches("GitHub MCP(github)", "mcp__github"))
        self.assertTrue(checker._category_matches("Context7 MCP(context7)", "context7@v2"))

    def test_n7_scope_uses_paper_phases(self):
        scopes = load("state_scopes_regression", ROOT / "shared" / "state-engine" / "state_scopes.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state").mkdir()
            (root / "state" / "decision_log.json").write_text(
                json.dumps({"scopes": [], "meta": {"seq": 0}}, ensure_ascii=False), encoding="utf-8"
            )
            (root / "ReportPaper" / "LaTeX" / "sections").mkdir(parents=True)
            (root / "ReportPaper" / "LaTeX" / "sections" / "intro.tex").write_text("Intro", encoding="utf-8")
            result = scopes.plan_scopes(str(root), "N7", 1, target="sections/intro.tex")
            self.assertEqual(tuple(result["required_phases"]), scopes.PAPER_PHASES)
            aggregate = json.loads((root / result["aggregate_plan"]).read_text(encoding="utf-8"))
            self.assertEqual(tuple(aggregate["required_phases"]), scopes.PAPER_PHASES)
            workspace = root / result["scopes"][0]["workspace"]
            scoped = json.loads((workspace / "aggregate_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(tuple(scoped["required_phases"]), scopes.PAPER_PHASES)

    def test_runtime_sync_flag_updates_existing_module_without_force(self):
        import shutil
        import subprocess

        source_dir = ROOT / "shared" / "state-engine"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            subprocess.run(["python", str(source_dir / "state_utils.py"), "init",
                            "--dir", str(project), "--name", "sync-test"],
                           check=True, capture_output=True, text=True)
            target = project / "state" / "state_search.py"
            target.write_text("# stale runtime\n", encoding="utf-8")
            # Invoke the canonical source facade so it can bootstrap a stale
            # project copy before importing the project's sibling modules.
            subprocess.run(["python", str(source_dir / "state_utils.py"), "init",
                            "--dir", str(project), "--sync-runtime",
                            "--runtime-source", str(source_dir)],
                           check=True, capture_output=True, text=True)
            self.assertEqual(target.read_bytes(), (source_dir / "state_search.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
