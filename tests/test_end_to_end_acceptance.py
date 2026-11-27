#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端验收：模拟一个真实用户从空目录跑到交付，全程只用 CLI 命令。

与既有单测的区别：本项目其余测试多为"隔离验证某道门禁"，本文件验证
**这些门禁串起来能否走通一条完整路径**，以及"卡住时给出的报错是否可执行"。

设计原则：
  · 只调 `state/state_utils.py` 与随项目分发的脚本，不 import 内部函数；
  · 覆盖 N0→N8 主链路（含迭代节点 N4/N5 的 round 环）；
  · 每个用例自洽：前置状态由 `bootstrap_project()` 幂等方式铺好，
    因此 `pytest -k <单个用例>` 也能独立跑通；
  · 失败时输出完整 stderr，便于定位是产品缺陷还是测试假设错误。
"""
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
STATE = ROOT / "shared" / "state-engine" / "state_utils.py"
PROBLEM_GUARD = ROOT / "shared" / "state-engine" / "problem_guard.py"

NODE_SKILLS = {
    "N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
    "N2": "academic-orchestrator:mm-data-preprocessing",
    "N3": "academic-orchestrator:mm-model-library",
    "N4": "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,"
          "academic-orchestrator:code-review",
    "N5": "academic-orchestrator:mm-model-tuning,academic-orchestrator:mm-iteration-engine",
    "N6": "academic-orchestrator:mm-visualization,academic-orchestrator:mm-iteration-engine,"
          "academic-orchestrator:figure-table-benchmark",
    "N7": "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-latex-writing,"
          "academic-orchestrator:mm-self-review,academic-orchestrator:figure-table-benchmark",
    "N8": "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-latex-writing,"
          "academic-orchestrator:mm-self-review",
}
NODE_AGENTS = {
    "N1": "selector", "N2": "dataprep", "N3": "modeler", "N4": "coder",
    "N5": "tuner", "N6": "visualization", "N7": "writing", "N8": "reviewer",
}
REVIEWER_SKILLS = {
    "N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
    "N2": "academic-orchestrator:mm-data-preprocessing",
    "N3": "academic-orchestrator:mm-model-library",
    "N4": "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,"
          "academic-orchestrator:code-review",
    "N5": "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,"
          "academic-orchestrator:code-review,academic-orchestrator:mm-model-tuning",
    "N6": "academic-orchestrator:mm-visualization,academic-orchestrator:mm-iteration-engine",
    "N7": "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-latex-writing,"
          "academic-orchestrator:mm-self-review",
    "N8": "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-latex-writing,"
          "academic-orchestrator:mm-self-review",
}
REVIEWER_AGENT = {"N4": "mm-code-reviewer", "N5": "mm-code-reviewer", "N6": "mm-viz-reviewer"}

ARTIFACTS = {
    "N1": ["ProblemInfo/ProblemNotes.md"],
    "N2": ["Data/DataLog.md"],
    "N3": ["ModelDocs/model-framework.md"],
    "N4": ["Code/main.py", "Code/output/run.json"],
    "N5": ["ModelDocs/sensitivity-analysis.md"],
    "N6": ["ResultFigures/figure-list.md"],
    "N7": ["ReportPaper/LaTeX/main.tex"],
    "N8": ["SubmissionPackage/参赛提交清单.md"],
}
# 迭代节点由 PROFILE_OF 决定（code: N4/N5，paper: N7/N8），必须走 round-start 环。
# 非迭代节点（N1/N2/N3/N6）走 node-finish。
ITER_NODES = ("N4", "N5", "N7", "N8")
MCP_BY_NODE = {"N1": "paper-mcp, tokenhub-tools", "N3": "context7, paper-mcp",
               "N4": "context7, github", "N5": "github, tokenhub-tools",
               "N6": "paper-mcp, tokenhub-tools", "N7": "paper-mcp"}
PAPER_NODES = ("N7", "N8")
# 两套评分口径：code 环五维（英文键）、paper 环国赛五维（中文键）。
# 这不是冗余——两环的评审标准本就不同，混用会被 round-score 拒绝。
DIMS_CODE = '{"correctness":9,"efficiency":9,"readability":9,"robustness":9,"innovation":9}'
DIMS_PAPER = '{"假设合理性":9,"建模创造性":9,"结果正确性":9,"表述清晰性":9,"格式规范性":9}'


# ---------------------------------------------------------------- 纯函数工具

def run_cli(project: Path, env: dict, *args):
    """调项目内 state_utils（验证"项目自包含"而不是源码树可用）。"""
    script = project / "state" / "state_utils.py"
    if not script.exists():
        script = STATE
    return subprocess.run([sys.executable, str(script), *args, "--dir", str(project)],
                          text=True, capture_output=True, env=env)


def state_of(project: Path) -> dict:
    return json.loads((project / "state" / "decision_log.json").read_text(encoding="utf-8"))


def touch(project: Path, rel: str, text: str = "验收产物\n") -> Path:
    p = project / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def seed_mcp(project: Path, node: str, round_no=None):
    reports = project / "state" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    rec = {"node": node, "mcp": MCP_BY_NODE.get(node, "paper-mcp"), "query": "e2e",
           "ts": "2026-01-01T00:00:00Z", "result": "ok", "card": "card"}
    if round_no is not None:
        rec["round"] = round_no
    with (reports / "mcp-calls.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def seed_case(project: Path, node: str, round_no: int):
    idx = project / "state" / "cases" / "index.json"
    doc = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {"version": "1.0", "cases": []}
    doc.setdefault("cases", []).append({
        "id": f"e2e_{node}_{round_no}", "title": "e2e", "source": "s",
        "source_type": "paper-academic", "node": node, "search_query": "q",
        "used_in_rounds": [round_no]})
    idx.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def write_benchmark_matrix(project: Path, node: str, round_no: int = 1) -> Path:
    """造一份 schema 合规的 B1 对标矩阵（≥1 条 entry、每条 ≥1 篇同行、七维齐全）。

    B1 是硬门禁：缺矩阵不让 PASS。这里给出"最小合规样本"，
    验证的是门禁接线与 schema 校验能跑通，不是对标质量本身。
    """
    dim = {"state": "PASS", "evidence": "peer fig.2 / tab.3 同样给出该列"}
    matrix = {
        "schema_version": "figure-table-benchmark/1.0",
        "project_id": "e2e",
        "node": node,
        "round": round_no,
        "generated_at": "2026-01-01T00:00:00Z",
        "entries": [{
            "artifact_id": "tab-1",
            "artifact_kind": "table",
            "supported_claim": "模型在测试集上的误差优于基线",
            "our_spec": {
                "chart_type": "three-line table",
                "columns": ["Method", "MAPE", "Runtime(s)"],
                "statistics": ["mean", "std"],
                "units": ["%", "s"],
                "sample_size": "30",
            },
            "benchmarked": [
                {"paper_id": "peer-A", "venue": "J. Test", "year": 2023,
                 "artifact_ref": "Table 2", "locator": "p.7", "channel": "paper-mcp",
                 "query": "MAPE comparison table"},
                {"paper_id": "peer-B", "venue": "Conf. B", "year": 2024,
                 "artifact_ref": "Table 3", "locator": "p.11", "channel": "arxiv",
                 "query": "forecasting error std table"},
                {"paper_id": "peer-C", "venue": "J. C", "year": 2022,
                 "artifact_ref": "Tab. 1", "locator": "p.4", "channel": "websearch",
                 "query": "runtime comparison table"},
            ],
            "peer_specs": {
                "union_columns": ["Method", "MAPE", "Runtime(s)", "Params"],
                "intersection_columns": ["Method", "MAPE"],
                "common_statistics": ["mean", "std"],
            },
            "dimensions": {k: dict(dim) for k in
                           ("data_columns", "statistics", "units", "comparability",
                            "grouping", "chart_fit", "academic_form")},
            "gaps": [],
            "verdict": "COMPLETE",
            "notes": "e2e 最小合规样本",
        }],
    }
    out = project / "state" / "reports" / "figure-table-benchmark" / f"{node}_{round_no}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def finish_node(project: Path, env: dict, node: str) -> subprocess.CompletedProcess:
    """把一个节点推到 completed 且审阅 PASS（非迭代 / 迭代两条路径）。"""
    r = run_cli(project, env, "node-start", node)
    if r.returncode != 0:
        return r
    for rel in ARTIFACTS[node]:
        touch(project, rel)
    reviewer = REVIEWER_AGENT.get(node, "reviewer")
    # 分阶段归档是硬要求，迭代/非迭代节点都要落快照（中断后可续跑）
    r = run_cli(project, env, "checkpoint", node, "--phase", "Phase 1 交付",
                "--done", "产物已生成", "--artifact", ARTIFACTS[node][0])
    if r.returncode != 0:
        return r
    if node in ITER_NODES:
        seed_mcp(project, node, 1)
        seed_case(project, node, 1)
        r = run_cli(project, env, "round-start", node)
        if r.returncode != 0:
            return r
        r = run_cli(project, env, "round-score", node, "--round", "1", "--total", "9",
                    "--dims", DIMS_PAPER if node in PAPER_NODES else DIMS_CODE,
                    "--judge", reviewer, "--skills-read", REVIEWER_SKILLS[node],
                    "--allow-missing-mcp", "--evidence", ARTIFACTS[node][0])
        if r.returncode != 0:
            return r
        r = run_cli(project, env, "round-decide", node, "--round", "1")
        if r.returncode != 0:
            return r
    else:
        r = run_cli(project, env, "node-finish", node, "--agent", NODE_AGENTS[node],
                    "--skills", NODE_SKILLS[node])
        if r.returncode != 0:
            return r
        seed_mcp(project, node)
    r = run_cli(project, env, "node-review", node, "--agent", reviewer, "--result", "PASS",
                "--skills", REVIEWER_SKILLS[node], "--summary", "e2e ok",
                "--allow-missing-lineage", "--allow-missing-mcp",
                "--evidence", ARTIFACTS[node][0])
    if r.returncode != 0:
        return r
    # N6/N7 另有 B1（图表/表格文献对标），由第二审阅者 mm-figure-table-benchmarker 独立落盘。
    # 这是真实的双审阅设计，不是重复校验：主审阅管规范，第二审阅管"同行会放什么我们漏了"。
    if node in ("N6", "N7"):
        matrix = write_benchmark_matrix(project, node, 1)
        r = run_cli(project, env, "node-review", node, "--agent", "mm-figure-table-benchmarker",
                    "--result", "PASS",
                    "--skills", "figure-table-benchmark,mm-iteration-engine",
                    "--summary", "e2e benchmark ok",
                    "--allow-missing-mcp",
                    "--evidence", str(matrix.relative_to(project)).replace("\\", "/"))
    return r


def bootstrap_project(project: Path, env: dict) -> subprocess.CompletedProcess:
    """幂等：把项目推进到"可开工任意节点"的状态（init + N0..N3 完成）。"""
    if (project / "state" / "decision_log.json").exists():
        st = state_of(project)
        if st.get("nodes", {}).get("N3", {}).get("status") == "completed":
            return subprocess.CompletedProcess([], 0, "", "")
    problem = project.parent / "problem.md"
    problem.parent.mkdir(parents=True, exist_ok=True)
    problem.write_text("# 赛题\n目标与约束\n", encoding="utf-8")
    steps = [
        ("init", "--name", "E2E"),
        ("node-start", "N0"),
        ("node-finish", "N0"),
    ]
    for args in steps:
        r = run_cli(project, env, *args)
        if r.returncode != 0 and "已存在" not in r.stderr and "已初始化" not in r.stderr:
            return r
    gp = subprocess.run([sys.executable, str(PROBLEM_GUARD), "create",
                         "--project", str(project), "--source", str(problem),
                         "--figure-mode", "none",
                         "--objectives", '["最小化成本"]',
                         "--constraints", '["预算上限"]',
                         "--preconditions", '["历史数据可得"]',
                         "--data-requirements", '["销量与价格"]',
                         "--evaluation-metrics", '["MAPE"]'],
                        capture_output=True, text=True)
    if gp.returncode != 0:
        return gp
    for node in ("N1", "N2", "N3"):
        r = finish_node(project, env, node)
        if r.returncode != 0:
            return r
    return subprocess.CompletedProcess([], 0, "", "")


class AcceptanceBase(unittest.TestCase):
    """每个用例独立：setUp 建全新项目并 bootstrap，用例内推进到目标状态。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_e2e_"))
        self.project = self.tmp / "ReviewPaper"
        self.skill_root = self.tmp / "skills"
        self.skill_root.mkdir()
        for name in ("mm-problem-analysis", "mm-self-review", "mm-data-preprocessing",
                     "mm-model-library", "mm-iteration-engine", "mm-algorithm-dev",
                     "code-review", "mm-model-tuning", "mm-visualization",
                     "mm-latex-writing", "figure-table-benchmark"):
            d = self.skill_root / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {name} e2e fixture\n---\n", encoding="utf-8")
        self.env = dict(os.environ)
        self.env["MM_SKILL_ROOTS"] = str(self.skill_root)
        r = bootstrap_project(self.project, self.env)
        if r.returncode != 0:
            self.fail(f"bootstrap 失败: {r.stderr}\n{r.stdout}")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args):
        return run_cli(self.project, self.env, *args)

    def advance(self, node):
        r = finish_node(self.project, self.env, node)
        self.assertEqual(r.returncode, 0,
                         f"{node} 推进失败\n--- stderr ---\n{r.stderr}\n--- stdout ---\n{r.stdout}")
        return r

    def state_json(self):
        return state_of(self.project)


class ProjectLifecycleTest(AcceptanceBase):
    """N0 → N8 全链路能否走通。每个用例从 bootstrap 状态自行推进。"""

    def test_init_creates_self_contained_project(self):
        for rel in ("state/decision_log.json", "state/registry.json",
                    "state/state_utils.py", "README-项目总说明.md"):
            self.assertTrue((self.project / rel).exists(), f"init 应生成 {rel}")
        self.assertTrue((self.project / "state" / "contracts" / "gates-registry.json").exists(),
                        "门禁登记表必须随项目分发，否则 gate-set 白名单失效")
        r = self.run_state("dump")
        self.assertEqual(r.returncode, 0, f"项目内 state_utils 应可用: {r.stderr}")

    def test_n0_to_n3_non_iter_nodes(self):
        st = self.state_json()
        for n in ("N0", "N1", "N2", "N3"):
            self.assertEqual(st["nodes"][n]["status"], "completed", f"{n} 应 completed")
        for gate in ("M1", "D1", "P1"):
            self.assertIn(st["gates"][gate]["status"], ("PASS", "auto_passed", "confirmed"),
                          f"{gate} 应通过")

    def test_n4_iteration_round(self):
        self.advance("N4")
        st = self.state_json()
        self.assertEqual(st["nodes"]["N4"]["status"], "completed")
        self.assertTrue(any(r.get("node") == "N4" and r.get("status") == "completed"
                            for r in st["rounds"]), "N4 的轮次应 completed")

    def test_n5_tuning(self):
        self.advance("N4")
        self.advance("N5")
        self.assertEqual(self.state_json()["nodes"]["N5"]["status"], "completed")

    def test_n6_figures(self):
        self.advance("N4")
        self.advance("N5")
        self.advance("N6")
        self.assertEqual(self.state_json()["nodes"]["N6"]["status"], "completed")

    def test_n7_paper(self):
        for n in ("N4", "N5", "N6"):
            self.advance(n)
        self.advance("N7")
        self.assertEqual(self.state_json()["nodes"]["N7"]["status"], "completed")

    def test_n8_full_chain_completes(self):
        """整条链路跑到底，N8 与 A3 都过。"""
        for n in ("N4", "N5", "N6", "N7", "N8"):
            self.advance(n)
        st = self.state_json()
        self.assertEqual(st["nodes"]["N8"]["status"], "completed")
        self.assertIn(st["gates"]["A3"]["status"], ("PASS", "auto_passed", "confirmed"))

    def test_audit_clean_after_full_run(self):
        for n in ("N4", "N5", "N6", "N7", "N8"):
            self.advance(n)
        r = self.run_state("project-audit")
        self.assertEqual(r.returncode, 0, f"project-audit 应可运行: {r.stderr}")
        out = r.stdout + r.stderr
        for keyword in ("哈希链断裂", "结构缺失", "状态文件损坏"):
            self.assertNotIn(keyword, out, f"全流程后不应出现: {keyword}")


class ErrorMessageQualityTest(unittest.TestCase):
    """错误信息必须可执行：说清"哪里错了 + 怎么修"。空话报错等于没有门禁。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_errmsg_"))
        self.project = self.tmp / "p"
        self.project.mkdir()
        self.env = dict(os.environ)
        self.env["MM_SKILL_ROOTS"] = str(self.tmp / "skills-empty")
        self.run_state("init", "--name", "T")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args):
        return run_cli(self.project, self.env, *args)

    def test_not_started_error_is_actionable(self):
        r = self.run_state("node-finish", "N1", "--agent", "selector",
                           "--skills", "mm-problem-analysis,mm-self-review")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("node-start", r.stderr, "报错必须提示先 node-start")
        self.assertIn("N1", r.stderr, "报错必须指明节点")

    def test_illegal_gate_error_lists_valid_values(self):
        r = self.run_state("gate-set", "NOT_A_GATE", "PASS", "--agent", "x")
        self.assertNotEqual(r.returncode, 0)
        low = r.stderr.lower()
        self.assertTrue(any(k in low for k in ("合法", "unknown", "invalid", "不存在", "允许")),
                        f"非法门禁应列出合法值，实际: {r.stderr[:400]}")

    def test_evidence_missing_says_how_to_fix(self):
        r = self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "mm-problem-analysis,mm-self-review",
                           "--allow-missing-mcp", "--evidence", "no/such/file.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("证据", r.stderr)

    def test_unknown_command_exits_nonzero(self):
        r = self.run_state("definitely-not-a-command")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(r.stderr.strip(), "未知命令必须有 stderr 说明")


if __name__ == "__main__":
    unittest.main()
