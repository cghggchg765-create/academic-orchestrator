from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "shared" / "state-engine"
STATE = SCRIPTS / "state_utils.py"
LIBRARY = ROOT / "skills" / "mathematical-modeling" / "assets" / "case-library"

sys.path.insert(0, str(SCRIPTS))
import case_search_lib as search  # noqa: E402


class CaseSearchLibraryTest(unittest.TestCase):
    def test_chinese_alias_tokens_and_tag(self):
        values = search.tokens("小样本 多目标 稳健优化")
        self.assertIn("小样本", values)
        self.assertIn("tag:小样本", values)
        self.assertIn("tag:多目标", values)
        self.assertIn("tag:不确定性", values)

    def test_score_cases_prefers_structural_match(self):
        cases = [
            {
                "case_id": "case-001", "year": 2020, "title": "多目标约束调度",
                "core_problem": "资源分配与调度", "problem_types": ["多目标优化"],
                "models": ["整数规划"], "keywords": ["容量约束"],
                "validation_methods": ["约束可行性检查"],
                "transferable_patterns": ["预测后做鲁棒优化"],
            },
            {
                "case_id": "case-002", "year": 2025, "title": "时间序列预测",
                "core_problem": "单变量趋势预测", "problem_types": ["预测"],
                "models": ["ARIMA"], "keywords": ["滚动验证"],
                "validation_methods": ["交叉验证"], "transferable_patterns": [],
            },
        ]
        ranked = search.score_cases("多目标 约束 调度", cases)
        self.assertEqual(ranked[0][1]["case_id"], "case-001")
        self.assertIn("多目标", ranked[0][2])

    def test_filter_cases(self):
        cases = [
            {"case_id": "a", "year": 2020, "problem_types": ["优化"], "models": ["遗传算法"]},
            {"case_id": "b", "year": 2021, "problem_types": ["预测"], "models": ["ARIMA"]},
        ]
        self.assertEqual([c["case_id"] for c in search.filter_cases(cases, year=2020)], ["a"])
        self.assertEqual([c["case_id"] for c in search.filter_cases(cases, problem_type="优化")], ["a"])
        self.assertEqual([c["case_id"] for c in search.filter_cases(cases, model="ARIMA")], ["b"])

    def test_locate_skill_root_explicit(self):
        self.assertEqual(search.locate_skill_root(ROOT), ROOT.resolve())

    def test_locate_skill_root_fail_closed(self):
        old = os.environ.pop("MM_SKILL_ROOT", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                # An explicit nonexistent root must not silently select another library.
                with self.assertRaises(FileNotFoundError):
                    search.locate_skill_root(Path(tmp) / "does-not-exist")
        finally:
            if old is not None:
                os.environ["MM_SKILL_ROOT"] = old


class CaseSearchCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_case_search_"))
        self.project = self.tmp / "project"
        self.project.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(STATE), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_json_output_and_skill_root(self):
        result = self.run_state(
            "case-search", "多目标 约束 调度", "--type", "优化", "--top", "2",
            "--json", "--skill-root", str(ROOT),
        )
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(len(payload), 1)
        self.assertLessEqual(len(payload), 2)
        self.assertIn("case_id", payload[0])
        self.assertIn("score", payload[0])

    def test_save_records_hits_in_project_state(self):
        self.run_state("init", "--dir", str(self.project), "--name", "CaseSearch")
        result = self.run_state(
            "case-search", "小样本 综合评价", "--top", "2", "--save",
            "--skill-root", str(ROOT), "--dir", str(self.project),
        )
        self.assertIn("沉淀", result.stdout)
        index = json.loads((self.project / "state" / "cases" / "index.json").read_text(encoding="utf-8"))
        saved = [c for c in index["cases"] if c.get("source_type") == "pro-case-library"]
        self.assertGreaterEqual(len(saved), 1)
        self.assertTrue(all((self.project / "state" / "cases" / f"{c['id']}.json").is_file() for c in saved))

    def test_no_match_returns_nonzero_but_does_not_crash(self):
        result = self.run_state(
            "case-search", "zzzz-unseen-token", "--skill-root", str(ROOT), check=False,
        )
        # The command is a valid invocation even when no card matches; it reports the empty result.
        self.assertEqual(result.returncode, 0)
        self.assertIn("未命中", result.stdout)


if __name__ == "__main__":
    unittest.main()
