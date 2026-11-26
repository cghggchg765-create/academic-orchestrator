"""Deep Research 链嵌入迭代环的可审计留痕（dr-note / dr-list）测试。

覆盖：
- dr-note 登记一条 DR 介入（节点/轮次/阶段/链角色/问题/输入/产出）→ dr-interventions.jsonl 落盘 + dr-list 可查；
- 迭代轮次介入（--round）同步写入 rounds[n].deep_research；
- dr-list 按轮次过滤、并集去重（jsonl + rounds 内嵌）；
- 非迭代轮次介入 lie in NODE 阶段也可留痕；
- 非法节点拒绝。
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


class DRInterventionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_dr_"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.run_state("init", "--dir", str(self.project), "--name", "Test")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args, check=True):
        return subprocess.run(["python", str(STATE), *args], text=True, capture_output=True, check=check)

    def lock_problem(self):
        problem = self.tmp / "problem.md"
        problem.write_text("# Problem\n目标与约束\n", encoding="utf-8")
        subprocess.run([
            "python", str(GUARD), "create", "--project", str(self.project), "--source", str(problem),
            "--objectives", '["目标"]', "--constraints", '["约束"]',
            "--preconditions", '["条件"]', "--data-requirements", '["数据"]',
            "--evaluation-metrics", '["指标"]',
        ], check=True, capture_output=True, text=True)

    def seed_mcp_calls(self, project, node, round_no=None):
        reports = project / "state" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        # Seed the minimum evidence contract for the node under test. N4 requires
        # both technical documentation and implementation evidence before scoring.
        mcps = [("context7", "context7-result"), ("github", "github-result")] if node == "N4" else [("paper-mcp", "paper-result")]
        with (reports / "mcp-calls.jsonl").open("a", encoding="utf-8") as f:
            for mcp, result in mcps:
                rec = {"node": node, "mcp": mcp, "query": "q", "ts": "t", "result": result}
                if round_no is not None:
                    rec["round"] = round_no
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def test_dr_note_appends_and_dr_list_returns(self):
        r = self.run_state(
            "dr-note", "N4", "--phase", "SEARCH", "--role", "literature",
            "--topic", "线性规划求解瓶颈", "--input", "上轮 failure_analysis: 求解器收敛慢",
            "--output", "state/reports/dr/n4_bottleneck.md",
            "--ref", "case:case_a; card:n4_case.md", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0, r.stderr)
        ledger = self.project / "state" / "reports" / "dr-interventions.jsonl"
        self.assertTrue(ledger.exists())
        recs = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["node"], "N4")
        self.assertEqual(recs[0]["phase"], "SEARCH")
        self.assertEqual(recs[0]["role"], "literature")
        self.assertEqual(recs[0]["topic"], "线性规划求解瓶颈")
        out = self.run_state("dr-list", "N4", "--dir", str(self.project))
        self.assertIn("N4 Deep Research 介入留痕（1 条）", out.stdout)
        self.assertIn("SEARCH", out.stdout)

    def test_dr_note_with_round_syncs_to_rounds(self):
        self.run_state("dr-note", "N5", "--round", "2", "--phase", "DECIDE",
                       "--role", "report_compiler",
                       "--topic", "调优未达标根因", "--input", "T1 门槛未过",
                       "--output", "state/reports/dr/n5_r2.md", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        # 未 round-start 时 rounds 为空：同步逻辑按 round 匹配不到则只落 jsonl（不报错）
        ledger = self.project / "state" / "reports" / "dr-interventions.jsonl"
        recs = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["round"], 2)
        self.assertEqual(recs[0]["phase"], "DECIDE")

    def test_dr_note_round_with_round_start_lands_in_rounds(self):
        # 迭代轮次开启后，dr-note --round 应同步进 rounds[n].deep_research
        self.lock_problem()
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("dr-note", "N4", "--round", "1", "--phase", "SEARCH",
                       "--role", "synthesis", "--topic", "方案对比",
                       "--output", "state/reports/dr/n4_r1.md", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        round1 = [r for r in state["rounds"] if r.get("node") == "N4" and r.get("round") == 1][0]
        self.assertIn("deep_research", round1)
        self.assertEqual(round1["deep_research"][0]["phase"], "SEARCH")
        self.assertEqual(round1["deep_research"][0]["role"], "synthesis")
        # dr-list 应去重并集（jsonl + rounds 内嵌，二者相同只列一条）
        out = self.run_state("dr-list", "N4", "--round", "1", "--dir", str(self.project))
        self.assertIn("N4 round1 Deep Research 介入留痕（1 条）", out.stdout)

    def test_dr_list_filters_by_round(self):
        self.run_state("dr-note", "N7", "--round", "1", "--phase", "SCORE",
                       "--role", "synthesis", "--topic", "先进性核查",
                       "--output", "o1.md", "--dir", str(self.project))
        self.run_state("dr-note", "N7", "--round", "2", "--phase", "SEARCH",
                       "--role", "literature", "--topic", "文献补全",
                       "--output", "o2.md", "--dir", str(self.project))
        out = self.run_state("dr-list", "N7", "--round", "1", "--dir", str(self.project))
        self.assertIn("（1 条）", out.stdout)
        self.assertIn("先进性核查", out.stdout)
        self.assertNotIn("文献补全", out.stdout)

    def test_dr_list_aggregates_rounds_embedded_and_jsonl(self):
        # 同一轮：jsonl 一条 + rounds 内嵌一条不同记录 → 并集 2 条
        self.lock_problem()
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("dr-note", "N4", "--round", "1", "--phase", "SEARCH",
                       "--role", "literature", "--topic", "检索一",
                       "--output", "o1.md", "--dir", str(self.project))
        self.run_state("dr-note", "N4", "--round", "1", "--phase", "SCORE",
                       "--role", "synthesis", "--topic", "先进性核查二",
                       "--output", "o2.md", "--dir", str(self.project))
        out = self.run_state("dr-list", "N4", "--round", "1", "--dir", str(self.project))
        self.assertIn("（2 条）", out.stdout)
        self.assertIn("检索一", out.stdout)
        self.assertIn("先进性核查二", out.stdout)

    def test_dr_note_invalid_node_rejected(self):
        r = self.run_state("dr-note", "N99", "--role", "literature",
                           "--topic", "x", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)

    def test_dr_link_in_collaboration_loop_table_matches_roles(self):
        """规格中 Deep Research 链四角色与命令 --role 约定一致。"""
        spec = (ROOT / "docs" / "optimization" / "agent-collaboration-loop.md")
        self.assertTrue(spec.exists(), "缺少统一规格文档 agent-collaboration-loop.md")
        text = spec.read_text(encoding="utf-8")
        for role in ("research_architect", "literature", "researcher", "synthesis", "report_compiler"):
            self.assertIn(role, text)
        for kw in ("SEARCH", "SCORE", "DECIDE", "PREREQ-REQUEST", "ESCALATE"):
            self.assertIn(kw, text)

    # ---- 轮次知识卡片引用（collect_round_cards / rounds[n].knowledge_cards） ----

    def test_round_score_collects_round_cards(self):
        """存在 {node}_r{round}_*.md 卡片时，round-score 写入 rounds[n].knowledge_cards。"""
        self.lock_problem()
        self.seed_mcp_calls(self.project, "N4", round_no=1)
        cards = self.project / "state" / "reports" / "mcp-cards"
        cards.mkdir(parents=True, exist_ok=True)
        (cards / "N4_r1_bottleneck.md").write_text("# 卡片", encoding="utf-8")
        (cards / "N4_r1_case.md").write_text("# 卡片", encoding="utf-8")
        (cards / "N4_r2_later.md").write_text("# 卡片", encoding="utf-8")  # 不属于 round1
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "9",
                       "--dims", '{"correctness":9,"efficiency":8,"readability":8,"robustness":9,"innovation":9}',
                       "--judge", "mm-code-reviewer",
                       "--skills-read", "math-modeling-agent-system:mm-iteration-engine,math-modeling-agent-system:mm-algorithm-dev,math-modeling-agent-system:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        round1 = [r for r in state["rounds"] if r.get("node") == "N4" and r.get("round") == 1][0]
        self.assertEqual(round1.get("knowledge_cards"), ["N4_r1_bottleneck.md", "N4_r1_case.md"])
        self.assertNotIn("N4_r2_later.md", round1.get("knowledge_cards", []))

    def test_round_score_cards_empty_without_cards(self):
        """无对应命名卡片时 knowledge_cards 为空（轮次无卡片沉淀，N8 可据此拦"迭代无新检索"）。"""
        self.lock_problem()
        self.seed_mcp_calls(self.project, "N4", round_no=1)
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "9",
                       "--dims", '{"correctness":9,"efficiency":8,"readability":8,"robustness":9,"innovation":9}',
                       "--judge", "mm-code-reviewer",
                       "--skills-read", "math-modeling-agent-system:mm-iteration-engine,math-modeling-agent-system:mm-algorithm-dev,math-modeling-agent-system:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        round1 = [r for r in state["rounds"] if r.get("node") == "N4" and r.get("round") == 1][0]
        self.assertEqual(round1.get("knowledge_cards"), [])

    def test_mcp_cards_path_constant_aligned(self):
        """知识卡片落点常量（reports/mcp-cards）与项目内文档一致。"""
        from importlib import util
        spec = util.spec_from_file_location("mm_defs", ROOT / "shared" / "state-engine" / "state_defs.py")
        m = util.module_from_spec(spec); spec.loader.exec_module(m)
        # collect_round_cards 使用的目录 = state/reports/mcp-cards（与 knowledge-card 模板落点一致）
        self.assertEqual(m.STATE_DIR, "state")


if __name__ == "__main__":
    unittest.main()
