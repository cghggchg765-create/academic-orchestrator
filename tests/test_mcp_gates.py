"""核心节点 MCP 必调机器门禁测试（"禁止纯内生输出"强制闭环）。

覆盖：
- node-review（N1/N3）PASS 前检索留痕校验：无留痕拒绝 / 有留痕通过 / --allow-missing-mcp 显式豁免；
- round-score（N4/N5/N7）每轮检索留痕校验：本轮无留痕拒绝 / 有留痕通过 / 跨轮留痕不通用；
- round-decide 未达标分支（repair_and_rerun / keep_best）强制 --reason 失败原因分析；达标分支不强制；
- search-evidence 汇总命令产出派发清单；
- N8（非核心节点）不施加 MCP 必调门禁。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "shared" / "state-engine" / "state_utils.py"
GUARD = ROOT / "shared" / "state-engine" / "problem_guard.py"


class MCPGatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_mcp_"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.run_state("init", "--dir", str(self.project), "--name", "Test")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args, check=True):
        argv = list(args)
        # 本文件用例验证门禁/评分逻辑，不验证交付物产出，也不搭建完整上游链；
        # 交付物校验由 tests/test_v2_gates.py 的 IterationDeliverableTest 覆盖，
        # 上游完成守卫由 test_v2_gates 的分阶段用例覆盖。
        if argv:
            if argv[0] == "round-decide":
                for flag in ("--allow-empty-artifacts", "--allow-no-checkpoint"):
                    if flag not in argv:
                        argv.append(flag)
            if argv[0] in ("round-start", "round-decide", "result-ingest"):
                if "--skip-prereq" not in argv:
                    argv.append("--skip-prereq")
        return subprocess.run(["python", str(STATE), *argv], text=True, capture_output=True, check=check)

    def lock_problem(self):
        problem = self.tmp / "problem.md"
        problem.write_text("# Problem\n目标与约束\n", encoding="utf-8")
        subprocess.run([
            "python", str(GUARD), "create", "--project", str(self.project), "--source", str(problem),
            "--objectives", '["目标"]', "--constraints", '["约束"]',
            "--preconditions", '["条件"]', "--data-requirements", '["数据"]',
            "--evaluation-metrics", '["指标"]',
        ], check=True, capture_output=True, text=True)

    @staticmethod
    def seed_mcp_calls(project, node, round_no=None):
        reports = project / "state" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        required = {
            "N1": "paper-mcp, tokenhub-tools", "N3": "context7, paper-mcp",
            "N4": "context7, github", "N5": "github, tokenhub-tools",
            "N6": "paper-mcp, tokenhub-tools", "N7": "paper-mcp",
        }
        rec = {"node": node, "mcp": required.get(node, "paper-mcp"), "query": "q", "ts": "t", "result": "test-result", "card": "test-card"}
        if round_no is not None:
            rec["round"] = round_no
        with (reports / "mcp-calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @staticmethod
    def seed_case_round(project, round_no):
        index = project / "state" / "cases" / "index.json"
        doc = {"version": "1.0", "cases": [
            {"id": "case_t", "title": "t", "source": "s", "source_type": "paper-academic",
             "node": "N4", "mcp": "context7, github", "query": "q", "timestamp": "t",
             "result": "test-result", "card": "test-card", "search_query": "q", "used_in_rounds": [round_no]}]}
        index.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    # ---- node-review 检索留痕门禁 ----

    def test_n1_node_review_pass_blocks_without_mcp_evidence(self):
        r = self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("禁止纯内生", r.stderr)

    def test_n1_node_review_pass_allows_with_mcp_evidence(self):
        self.seed_mcp_calls(self.project, "N1")
        r = self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                           "--evidence", "ProblemInfo/ProblemNotes.md", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["gates"]["M1"]["status"], "PASS")

    def test_n1_node_review_pass_allows_explicit_exemption(self):
        r = self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                           "--allow-missing-mcp", "--evidence", "ProblemInfo/ProblemNotes.md",
                           "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_n2_node_review_pass_not_gated_by_mcp(self):
        """N2 不受 MCP 检索留痕门禁约束（MCP 只强制 N1/N3/N4/N5/N7）。"""
        r = self.run_state("node-review", "N2", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "academic-orchestrator:mm-data-preprocessing", "--evidence", "Data/DataLog.md",
                           "--allow-missing-lineage", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_n2_node_review_requires_data_lineage(self):
        """2.0.0：N2 的 D1 门禁强制数据血缘台账（处理内容/过程/结果可交叉检验）。

        无 Data/data-lineage.json → 拒绝 D1 落盘，并给出修复指引。
        """
        r = self.run_state("node-review", "N2", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "academic-orchestrator:mm-data-preprocessing", "--evidence", "Data/DataLog.md",
                           "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0, "缺少血缘台账时应拒绝 D1 放行")
        self.assertIn("数据血缘", r.stderr, f"应提示血缘缺失，实际: {r.stderr[:200]}")

    def test_n2_node_review_lineage_exemption(self):
        """显式豁免 --allow-missing-lineage 时可通过（仅离线/人工特批场景）。"""
        r = self.run_state("node-review", "N2", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "academic-orchestrator:mm-data-preprocessing", "--evidence", "Data/DataLog.md",
                           "--allow-missing-lineage", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)

    # ---- round-score 每轮检索留痕门禁 ----

    def test_n4_round_score_blocks_without_round_evidence(self):
        self.lock_problem()
        self.run_state("round-start", "N4", "--dir", str(self.project))
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8",
                           "--dims", '{"correctness":8,"efficiency":7,"readability":7,"robustness":8,"innovation":8}',
                           "--judge", "mm-code-reviewer",
                           "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                           "--evidence", "Code/output/run.json", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("禁止纯内生", r.stderr)

    def test_n4_round_score_allows_with_case_evidence(self):
        self.lock_problem()
        self.seed_case_round(self.project, 1)
        self.run_state("round-start", "N4", "--dir", str(self.project))
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8",
                           "--dims", '{"correctness":8,"efficiency":7,"readability":7,"robustness":8,"innovation":8}',
                           "--judge", "mm-code-reviewer",
                           "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                           "--evidence", "Code/output/run.json", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["gates"].get("S1-N4", {}).get("status"), "PASS")

    def test_n4_round_score_cross_round_evidence_not_reused(self):
        """round1 留痕不能给 round2 用（迭代每轮都要重新检索）。"""
        self.lock_problem()
        self.seed_mcp_calls(self.project, "N4", round_no=1)
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "9",
                       "--dims", '{"correctness":9,"efficiency":8,"readability":8,"robustness":9,"innovation":9}',
                       "--judge", "mm-code-reviewer",
                       "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        self.run_state("round-decide", "N4", "--round", "1", "--dir", str(self.project))
        self.run_state("round-start", "N4", "--dir", str(self.project))  # round2
        r = self.run_state("round-score", "N4", "--round", "2", "--total", "9",
                           "--dims", '{"correctness":9,"efficiency":8,"readability":8,"robustness":9,"innovation":9}',
                           "--judge", "mm-code-reviewer",
                           "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                           "--evidence", "Code/output/run.json", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("禁止纯内生", r.stderr)

    # ---- round-decide 失败原因 ----

    def test_round_decide_repair_requires_reason(self):
        self.lock_problem()
        self.seed_mcp_calls(self.project, "N4", round_no=1)
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "5",
                       "--dims", '{"correctness":5}',
                       "--judge", "mm-code-reviewer",
                       "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        r = self.run_state("round-decide", "N4", "--round", "1", "--feedback", "重跑",
                           "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("失败原因分析", r.stderr)

    def test_round_decide_repair_with_reason_ok(self):
        self.lock_problem()
        self.seed_mcp_calls(self.project, "N4", round_no=1)
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "5",
                       "--dims", '{"correctness":5}',
                       "--judge", "mm-code-reviewer",
                       "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        r = self.run_state("round-decide", "N4", "--round", "1", "--feedback", "重跑",
                           "--reason", "根因=算法边界溢出；差距=正确性5；下轮方案=修正索引并重跑验证",
                           "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertIn("failure_analysis", state["rounds"][0]["decision"])

    def test_round_decide_early_stop_no_reason_ok(self):
        self.lock_problem()
        self.seed_mcp_calls(self.project, "N4", round_no=1)
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "9",
                       "--dims", '{"correctness":9,"efficiency":8,"readability":8,"robustness":9,"innovation":9}',
                       "--judge", "mm-code-reviewer",
                       "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        r = self.run_state("round-decide", "N4", "--round", "1", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)

    # ---- N8 非核心节点不施加 MCP 必调 ----

    def test_n8_round_score_not_gated_by_mcp(self):
        self.lock_problem()
        self.run_state("round-start", "N8", "--dir", str(self.project))
        r = self.run_state("round-score", "N8", "--round", "1", "--total", "8",
                           "--dims", '{"假设合理性":8,"建模创造性":8,"结果正确性":8,"表述清晰性":8,"格式规范性":8}',
                           "--judge", "reviewer",
                           "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-latex-writing,academic-orchestrator:mm-self-review",
                           "--evidence", "ReportPaper/LaTeX/main.tex", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)

    # ---- search-evidence 派发清单 ----

    def test_search_evidence_lists_cards_and_cases(self):
        self.seed_mcp_calls(self.project, "N4", round_no=1)
        cards = self.project / "state" / "reports" / "mcp-cards"
        cards.mkdir(parents=True, exist_ok=True)
        (cards / "n4_case.md").write_text("# 卡片", encoding="utf-8")
        r = self.run_state("search-evidence", "N4", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("N4 检索证据派发清单", r.stdout)
        self.assertIn("n4_case.md", r.stdout)
        self.assertIn("检索留痕: mcp-calls", r.stdout)

    def test_search_evidence_empty_warns(self):
        r = self.run_state("search-evidence", "N1", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("先补 SEARCH", r.stdout)


if __name__ == "__main__":
    unittest.main()
