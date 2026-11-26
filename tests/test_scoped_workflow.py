from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "shared" / "state-engine" / "state_utils.py"
SCOPES = ROOT / "shared" / "state-engine" / "state_scopes.py"
RESILIENCE = ROOT / "shared" / "state-engine" / "resilience.py"


class ScopedWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_scoped_"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.run_state("init", "--dir", str(self.project), "--name", "Scoped")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args, check=True):
        return subprocess.run(
            ["python", str(STATE), *args],
            text=True,
            capture_output=True,
            check=check,
        )

    @staticmethod
    def load_module(name, path):
        sys.path.insert(0, str(path.parent))
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            sys.path.pop(0)

    def test_adaptive_n7_plan_splits_sections_and_oversized_solution(self):
        latex = self.project / "ReportPaper" / "LaTeX"
        (latex / "sections" / "model_solution.tex").write_text(
            "\\subsection{问题1模型}\n" + "A" * 120 +
            "\n\\subsection{问题2模型}\n" + "B" * 120,
            encoding="utf-8",
        )
        (latex / "sections" / "abstract.tex").write_text("摘要内容\n", encoding="utf-8")
        (latex / "main.tex").write_text(
            "\\input{sections/abstract}\n\\input{sections/model_solution}\n",
            encoding="utf-8",
        )

        result = self.run_state(
            "scope-plan", "N7", "--round", "1", "--mode", "adaptive",
            "--max-chars", "240", "--dir", str(self.project),
        )
        plan = json.loads(result.stdout)
        scope_ids = {item["scope_id"] for item in plan["scopes"]}
        self.assertIn("section_abstract", scope_ids)
        self.assertIn("section_model_solution_q1", scope_ids)
        self.assertIn("section_model_solution_q2", scope_ids)
        self.assertEqual(scope_ids, set(sorted(scope_ids)))

    def test_n4_question_plan_honors_target(self):
        (self.project / "Code" / "problem_2" / "p2_solver.py").write_text(
            "def solve():\n    return 2\n", encoding="utf-8"
        )
        result = self.run_state(
            "scope-plan", "N4", "--round", "1", "--target", "question_2",
            "--dir", str(self.project),
        )
        plan = json.loads(result.stdout)
        self.assertEqual([item["scope_id"] for item in plan["scopes"]], ["question_2"])
        self.assertTrue(any("Code/problem_2" in path for path in plan["scopes"][0]["inputs"]))

    def test_manifest_has_utc_timestamps_and_hashes(self):
        result = self.run_state(
            "scope-plan", "N4", "--round", "1", "--target", "question_1",
            "--dir", str(self.project),
        )
        plan = json.loads(result.stdout)
        workspace = self.project / plan["scopes"][0]["workspace"]
        manifest_path = workspace / "review_workspace_manifest.json"
        input_path = workspace / "input_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertRegex(manifest["created_at"], r"Z$")
        self.assertEqual(manifest["round"], 1)
        self.assertEqual(manifest["scope_id"], "question_1")
        self.assertIn("registry_sha256", manifest)
        self.assertIn("base_artifact_sha256", manifest)
        self.assertEqual(
            manifest["input_manifest_sha256"],
            hashlib.sha256(input_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(manifest["phase"], "PLAN")
        self.assertEqual(manifest["status"], "planned")
        self.assertTrue(input_path.exists())

    def test_scope_and_target_path_traversal_are_rejected(self):
        scopes = self.load_module("state_scopes_for_test", SCOPES)
        with self.assertRaises(ValueError):
            scopes.safe_scope_id("../escape")
        result = self.run_state(
            "scope-plan", "N7", "--round", "1", "--target", "../escape",
            "--dir", str(self.project), check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.tmp / "escape").exists())

    def test_same_node_round_scopes_have_noncolliding_workspaces(self):
        first = json.loads(self.run_state(
            "scope-plan", "N4", "--round", "1", "--scope-id", "question_1",
            "--dir", str(self.project),
        ).stdout)
        second = json.loads(self.run_state(
            "scope-plan", "N4", "--round", "1", "--scope-id", "question_2",
            "--dir", str(self.project),
        ).stdout)
        self.assertNotEqual(first["scopes"][0]["workspace"], second["scopes"][0]["workspace"])
        self.assertTrue((self.project / first["scopes"][0]["workspace"]).is_dir())
        self.assertTrue((self.project / second["scopes"][0]["workspace"]).is_dir())

    def test_scope_aggregate_blocks_when_required_phases_are_missing(self):
        self.run_state(
            "scope-plan", "N4", "--round", "1", "--target", "question_1",
            "--dir", str(self.project),
        )
        result = self.run_state(
            "scope-aggregate", "N4", "--round", "1", "--dir", str(self.project),
        )
        aggregate = json.loads(result.stdout)
        self.assertEqual(aggregate["status"], "BLOCKED")
        self.assertTrue(aggregate["missing_phases"])

    def test_scope_promote_does_not_complete_parent_until_all_scopes_pass(self):
        plan = json.loads(self.run_state(
            "scope-plan", "N4", "--round", "1", "--dir", str(self.project),
        ).stdout)
        first = next(item for item in plan["scopes"] if item["scope_id"] == "question_1")
        manifest_path = self.project / first["workspace"] / "review_workspace_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for phase in plan["required_phases"]:
            manifest["phase_status"][phase] = "completed"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result = self.run_state(
            "scope-promote", "N4", "--round", "1", "--scope-id", "question_1",
            "--dir", str(self.project),
        )
        promoted = json.loads(result.stdout)
        self.assertEqual(promoted["status"], "PROMOTED")
        self.assertFalse(promoted["parent_completed"])
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertNotEqual(state["nodes"]["N4"]["status"], "completed")

    def test_legacy_report_list_remains_compatible(self):
        audit = self.load_module(
            "state_audit_for_test",
            ROOT / "shared" / "state-engine" / "state_audit.py",
        )
        audit.save_round_report(
            str(self.project), "N4", 1, "review", {"agent": "reviewer", "timestamp": "2026-01-01T00:00:00Z"}
        )
        result = self.run_state("report-list", "--node", "N4", "--json", "--dir", str(self.project))
        listing = json.loads(result.stdout)
        self.assertEqual(listing["count"], 1)
        self.assertNotIn("scope_id", listing["entries"][0])

    def test_retry_with_nonempty_retries_whitespace_and_returns_value(self):
        resilience = self.load_module("resilience_for_scoped_test", RESILIENCE)
        calls = {"count": 0}

        def producer():
            calls["count"] += 1
            return "   " if calls["count"] == 1 else {"summary": "ok"}

        value = resilience.retry_with_nonempty(producer, attempts=2)
        self.assertEqual(value, {"summary": "ok"})
        self.assertEqual(calls["count"], 2)

        empty = resilience.retry_with_nonempty(lambda: "", attempts=2)
        self.assertEqual(empty["status"], "EMPTY_RETURN")
        self.assertEqual(empty["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
