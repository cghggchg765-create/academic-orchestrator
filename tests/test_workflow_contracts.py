from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "shared" / "state-engine" / "state_utils.py"
GUARD = ROOT / "shared" / "state-engine" / "problem_guard.py"
IMPORTER = ROOT / "shared" / "state-engine" / "sync_import.py"
ORCH = ROOT / "shared" / "state-engine" / "orchestrator_runtime.py"
LINT = ROOT / "scripts" / "lint_contracts.py"
SCHEMA = ROOT / "spec" / "result.schema.json"


class WorkflowContractsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_contract_"))
        self.project = self.tmp / "project"
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.project.mkdir()
        self.skill_root = self._seed_skill_root()
        self.run_state("init", "--dir", str(self.project), "--name", "Test")
        # 种子化核心节点 MCP 检索留痕（round-score/node-review 的"禁止纯内生"机器门禁依赖）。
        # 真实流程中由 orchestrator 各节点执行 SEARCH/MCP 调用自动写入；此处仅为测试提供等价留痕。
        self.seed_search_evidence()

    def _seed_skill_root(self) -> Path:
        """为技能路由铺一个固定 skill 根目录。

        路由是运行时发现（扫描本机已装 skill），测试若依赖真实环境会随机器漂移。
        这里用一个最小可控根：每个节点能力都至少有一个同名可用 skill，
        使 must_load 恰好等于节点 required_skills，测试只验证门禁接线而非匹配质量。
        """
        root = self.tmp / "skills"
        root.mkdir()
        for name in ("mm-problem-analysis", "mm-self-review", "mm-data-preprocessing",
                     "mm-model-library", "mm-iteration-engine", "mm-algorithm-dev",
                     "code-review", "mm-model-tuning", "mm-visualization",
                     "mm-latex-writing"):
            d = root / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {name} test fixture\n---\n", encoding="utf-8")
        return root

    def seed_search_evidence(self):
        """为核心节点（N1/N3 非轮次 + N4/N5/N7 round1）写检索留痕：mcp-calls.jsonl + cases/index.json。"""
        reports = self.project / "state" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        calls = [
            {"node": "N1", "mcp": "paper-mcp, tokenhub-tools", "query": "CUMCM 案例", "ts": "t", "result": "test", "card": "card"},
            {"node": "N3", "mcp": "context7, paper-mcp", "query": "模型选型", "ts": "t", "result": "test", "card": "card"},
            {"node": "N4", "round": 1, "mcp": "context7, github", "query": "算法 python", "ts": "t", "result": "test", "card": "card"},
            {"node": "N5", "round": 1, "mcp": "github, tokenhub-tools", "query": "SOTA", "ts": "t", "result": "test", "card": "card"},
            {"node": "N6", "mcp": "paper-mcp, tokenhub-tools", "query": "可视化方案", "ts": "t", "result": "test", "card": "card"},
            {"node": "N7", "round": 1, "mcp": "paper-mcp", "query": "文献", "ts": "t", "result": "test", "card": "card"},
        ]
        (reports / "mcp-calls.jsonl").write_text(
            "\n".join(json.dumps(c, ensure_ascii=False) for c in calls) + "\n", encoding="utf-8")
        cases = {"version": "1.0", "cases": [
            {"id": "case_t1", "title": "test", "source": "s", "source_type": "paper-academic",
             "search_query": "q", "used_in_rounds": [1]},
        ]}
        (self.project / "state" / "cases" / "index.json").write_text(
            json.dumps(cases, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args, check=True):
        env = dict(os.environ)
        # 固定 skill 扫描根：路由结果可复现，不随本机已装 skill 漂移
        env["MM_SKILL_ROOTS"] = str(self.skill_root)
        argv = list(args)
        # 本文件用例验证状态机流转，不验证产物产出；空产物校验由 test_workflow_gates 的
        # 专门用例覆盖。故对 node-finish 统一补豁免，避免用例被迫造假产物。
        if argv and argv[0] == "node-finish" and "--allow-empty-artifacts" not in argv:
            argv.append("--allow-empty-artifacts")
        return subprocess.run(["python", str(STATE), *argv], text=True, capture_output=True,
                              check=check, env=env)

    def complete_n0(self):
        """完成 N0（其产物 ProblemInfo/TimePlan.md 由 init 预建）。"""
        self.run_state("node-start", "N0", "--dir", str(self.project))
        self.run_state("node-finish", "N0", "--dir", str(self.project))

    def lock_problem(self):
        problem = self.source / "problem.md"
        problem.write_text("# Problem\n目标与约束\n", encoding="utf-8")
        subprocess.run([
            "python", str(GUARD), "create", "--project", str(self.project), "--source", str(problem),
            "--objectives", '["目标"]', "--constraints", '["约束"]',
            "--preconditions", '["条件"]', "--data-requirements", '["数据"]',
            "--evaluation-metrics", '["指标"]',
        ], check=True, capture_output=True, text=True)
        return problem

    def test_init_has_semantic_state_and_latex_only(self):
        state_nodes = self.project / "state" / "nodes"
        self.assertTrue((state_nodes / "代码").is_dir())
        self.assertFalse((state_nodes / "N4-代码").exists())
        self.assertTrue((self.project / "ReportPaper" / "LaTeX" / "main.tex").exists())
        self.assertFalse((self.project / "ReportPaper" / "Word_Version").exists())
        self.assertTrue((self.project / "state" / "problem_lock.json").exists())

    def test_init_latex_standard_layout(self):
        """LaTeX 国赛标准模板：目录布局、UTF-8 bibtex、标题黑体、页眉队伍编号、行距与参考文献格式。"""
        latex = self.project / "ReportPaper" / "LaTeX"
        for sub in ("img", "tables", "build", "sections"):
            self.assertTrue((latex / sub).is_dir(), f"LaTeX 缺少标准目录 {sub}")
        self.assertTrue((latex / ".latexmkrc").exists())
        self.assertIn("bibtex8", (latex / ".latexmkrc").read_text(encoding="utf-8"))
        preamble = (latex / "preamble.tex").read_text(encoding="utf-8")
        self.assertIn("gbt7714", preamble)
        self.assertIn("bibfont", preamble)          # 参考文献五号
        self.assertIn("linespread{1.5}", preamble)  # 1.5 倍行距
        self.assertIn("ctexset", preamble)          # 标题黑体
        self.assertIn("\\heiti", preamble)
        self.assertIn("fancyhdr", preamble)         # 页眉队伍编号
        self.assertIn("\\teamid", preamble)
        config = (latex / "config.tex").read_text(encoding="utf-8")
        self.assertIn("\\teamid", config)
        self.assertIn("\\keywords", config)
        abstract = (latex / "sections/abstract.tex").read_text(encoding="utf-8")
        self.assertIn("\\maketitle", abstract)

    def test_init_no_duplicate_directories(self):
        """init 后不得出现近义重复目录（draftbackup/draft-backup 等）。"""
        backup = self.project / "BackupArchive"
        defense = self.project / "DefenseMaterial"
        self.assertTrue((backup / "draft-backup").is_dir())
        self.assertTrue((backup / "mid-backup").is_dir())
        self.assertTrue((backup / "final-backup").is_dir())
        self.assertTrue((defense / "show-figures").is_dir())
        for legacy in ("draftbackup", "midbackup", "finalbackup", "showfigures"):
            self.assertFalse((backup / legacy).exists(), f"近义重复目录不应存在: {legacy}")
            self.assertFalse((defense / legacy).exists(), f"近义重复目录不应存在: {legacy}")

    def test_problem_drift_blocks_node_start(self):
        problem = self.lock_problem()
        # 先完成 N0，N1 才能 start（批次 A 新增 node-start 上游校验）
        self.complete_n0()
        self.run_state("node-start", "N1", "--dir", str(self.project))
        problem.write_text("# Changed\n", encoding="utf-8")
        result = self.run_state("node-start", "N2", "--dir", str(self.project), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr + result.stdout)

    def test_import_preserves_source_and_stages_markdown_for_review(self):
        self.lock_problem()
        (self.source / "solver.py").write_text("print('ok')\n", encoding="utf-8")
        paper = self.source / "paper.md"
        paper.write_text("# 结果\n\n结论文本\n", encoding="utf-8")
        subprocess.run(["python", str(IMPORTER), "--source", str(self.source), "--project", str(self.project), "--apply"], check=True, capture_output=True, text=True)
        self.assertTrue((self.project / "Code" / "legacy" / "solver.py").exists())
        self.assertFalse((self.project / "ReportPaper" / "LaTeX" / "imports" / "paper.tex").exists())
        draft = self.project / "ReportPaper" / "LaTeX" / "drafts" / "import-paper" / "source.md"
        self.assertTrue(draft.exists())
        self.assertIn("AI 专用 Agent 必须复核", draft.read_text(encoding="utf-8"))
        self.assertTrue((draft.parent / "conversion_task.json").exists())
        self.assertTrue(paper.exists())
        manifest = json.loads((self.project / "state" / "compatibility_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["policy"]["originals_preserved"], True)
        entry = next(item for item in manifest["entries"] if item["relative"] == "paper.md")
        self.assertEqual(entry["sha256"], __import__("hashlib").sha256(paper.read_bytes()).hexdigest())
        self.assertEqual(entry["conversion"], "legacy_preview_only")

    def test_non_markdown_paper_gets_conversion_task_without_canonical_source(self):
        self.lock_problem()
        paper = self.source / "paper.pdf"
        paper.write_bytes(b"pdf-source")
        subprocess.run(["python", str(IMPORTER), "--source", str(self.source), "--project", str(self.project), "--apply"], check=True, capture_output=True, text=True)
        self.assertFalse((self.project / "ReportPaper" / "LaTeX" / "imports" / "paper.tex").exists())
        task = self.project / "state" / "latex_conversion" / "paper" / "task.json"
        self.assertTrue(task.exists())
        payload = json.loads(task.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_type"], "document_to_latex")
        self.assertEqual(payload["source_files"][0]["sha256"], __import__("hashlib").sha256(paper.read_bytes()).hexdigest())

    def test_low_score_enters_repair_pending(self):
        self.lock_problem()
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "6", "--dims", '{"correctness":6}',
                       "--judge", "mm-code-reviewer", "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        self.run_state("round-decide", "N4", "--round", "1", "--feedback", "修复后重跑",
                       "--reason", "正确性低于 pass：核心公式实现有误，根因=边界条件处理缺失，下轮在 SEARCH 后重写求解核心",
                       "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["rounds"][0]["status"], "repair_pending")
        self.assertIn("failure_analysis", state["rounds"][0]["decision"])
        self.assertEqual(state["rounds"][0]["decision"]["action"], "repair_and_rerun")

    # ---------------------------------------------------------------- 批次 A 新增测试

    def test_n4_start_blocked_by_missing_upstream(self):
        """N4 node-start 在 N3 未 completed 时阻断，非零退出且含前置信息。"""
        self.lock_problem()
        result = self.run_state("node-start", "N4", "--dir", str(self.project), check=False)
        self.assertNotEqual(result.returncode, 0)
        output = (result.stderr + result.stdout).lower()
        self.assertIn("前置条件", output)
        self.assertIn("n3", output)
        # 确认节点未被置为 in_progress
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertNotEqual(state["nodes"]["N4"]["status"], "in_progress")

    def test_node_review_blocked_sets_gate_blocked(self):
        """node-review 传入 BLOCKED 时，门禁状态为 BLOCKED，result 含 BLOCKED 前缀。"""
        self.lock_problem()
        result = self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "BLOCKED",
                                "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                                "--evidence", "ProblemInfo/ProblemNotes.md",
                                "--summary", "缺少关键假设说明", "--dir", str(self.project))
        self.assertEqual(result.returncode, 0)
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        gate = state["gates"].get("M1", {})
        self.assertEqual(gate.get("status"), "BLOCKED")
        self.assertIn("BLOCKED", gate.get("result", ""))

    def test_result_schema_has_repair_pending(self):
        """result.schema.json 的 status 枚举包含 repair_pending。"""
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        status_enum = schema["properties"]["status"]["enum"]
        self.assertIn("repair_pending", status_enum)

    def test_orchestrator_strict_blocks_on_missing_artifact(self):
        """orchestrator_runtime.prepare_node(strict=True) 在产物缺失时返回 blocked 状态。"""
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("orchestrator_runtime", ORCH)
        orch = importlib.util.module_from_spec(spec)
        sys.modules["orchestrator_runtime"] = orch
        spec.loader.exec_module(orch)

        self.lock_problem()
        # 先完成 N0, N1, N2, N3 使 N4 前置满足
        self.complete_n0()
        executors = {"N1": "selector", "N2": "dataprep", "N3": "modeler"}
        skills = {"N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "N2": "academic-orchestrator:mm-data-preprocessing", "N3": "academic-orchestrator:mm-model-library"}
        for n in ("N1", "N2", "N3"):
            self.run_state("node-start", n, "--dir", str(self.project))
            self.run_state("node-finish", n, "--agent", executors[n], "--skills", skills[n], "--dir", str(self.project))
            # 审阅-修改循环：上游必须审阅 PASS 才能被下游 node-start 放行
            # N2 额外要求数据血缘台账（2.0.0 D1 门禁），此处豁免以聚焦管线前置条件测试
            self.run_state("node-review", n, "--agent", "reviewer", "--result", "PASS",
                           "--skills", skills[n], "--summary", "ok",
                           "--allow-missing-lineage", "--dir", str(self.project))
        # 删除 N3 的 artifact 目录 ModelDocs 模拟缺失
        shutil.rmtree(str(self.project / "ModelDocs"), ignore_errors=True)
        prep = orch.prepare_node(str(self.project), "N4", strict=True)
        self.assertFalse(prep["ready"])
        self.assertEqual(prep["status"], "blocked")
        self.assertIsNotNone(prep["blocked_reasons"])
        self.assertTrue(any("ModelDocs" in r for r in prep["blocked_reasons"]))

    # ---------------------------------------------------------------- result 协议闭环

    def _write_result(self, node="N4", agent="coder", status="completed", tamper_after=False):
        artifact = self.project / "Code" / "output.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"ok": true}', encoding="utf-8")
        sha = __import__("hashlib").sha256(artifact.read_bytes()).hexdigest()
        result = {
            "schema_version": "1.0",
            "agent_id": agent,
            "node_id": node,
            "run_id": f"{node}-2026-01-01T00:00:00Z",
            "status": status,
            "artifacts": [{"path": "Code/output.json", "sha256": sha}],
            "checks": [{"name": "run", "status": "PASS", "evidence": "Code/output/run.json"}],
            "feedback": [],
            "timestamps": {"started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T01:00:00Z"},
            "payload": {},
        }
        result_path = self.project / "state" / "agents" / agent / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        if tamper_after:
            artifact.write_text('{"tampered": true}', encoding="utf-8")
        return result_path

    def test_result_validate_and_ingest_completed(self):
        self.lock_problem()
        result_path = self._write_result()
        r = self.run_state("result-validate", str(result_path), "--node", "N4", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0)
        r = self.run_state("result-ingest", str(result_path), "--node", "N4", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0)
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["nodes"]["N4"]["status"], "completed")
        self.assertEqual(state["nodes"]["N4"]["last_result"]["run_id"], "N4-2026-01-01T00:00:00Z")

    def test_result_ingest_rejects_artifact_hash_mismatch(self):
        self.lock_problem()
        result_path = self._write_result(tamper_after=True)
        r = self.run_state("result-validate", str(result_path), "--node", "N4", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SHA-256", r.stderr + r.stdout)
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertNotIn("last_result", state["nodes"]["N4"])

    def test_result_ingest_blocked_keeps_node_blocked(self):
        self.lock_problem()
        result_path = self._write_result(status="blocked")
        self.run_state("result-ingest", str(result_path), "--node", "N4", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["nodes"]["N4"]["status"], "blocked")

    def test_result_ingest_rejects_non_reviewer_verdict(self):
        """带 review_verdict 的结果必须由注册的独立审阅 Agent 提交，执行 Agent 自评被拒。"""
        self.lock_problem()
        result = {
            "schema_version": "1.0",
            "agent_id": "coder",  # N4 执行 Agent，不是审阅 Agent
            "node_id": "N4",
            "run_id": "N4-2026-01-01T00:00:00Z",
            "status": "completed",
            "artifacts": [],
            "checks": [],
            "feedback": [],
            "timestamps": {"started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T01:00:00Z"},
            "payload": {},
            "review_verdict": "PASS",
        }
        result_path = self.project / "state" / "agents" / "coder" / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result), encoding="utf-8")
        r = self.run_state("result-ingest", str(result_path), "--node", "N4", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("独立审阅 Agent", r.stderr + r.stdout)

    def test_project_audit_and_repair(self):
        """project-audit 报告结构/锁定问题；project-repair --apply 补建缺失的标准设施。"""
        self.lock_problem()
        shutil.rmtree(str(self.project / "ModelDocs"), ignore_errors=True)
        r = self.run_state("project-audit", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0)
        audit = json.loads(r.stdout)
        self.assertTrue(audit["initialized"])
        self.assertFalse(audit["problem_lock"]["drift"])
        self.assertIn("ModelDocs", audit["structure"]["missing_dirs"])
        r = self.run_state("project-repair", "--apply", "--dir", str(self.project))
        self.assertEqual(r.returncode, 0)
        self.assertTrue((self.project / "ModelDocs").is_dir())
        self.assertTrue((self.project / "state" / "registry.json").exists())
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertNotIn("ModelDocs", audit["structure"]["missing_dirs"])
        self.assertTrue(audit["summary"]["healthy"])

    def test_project_audit_detects_state_artifact_drift(self):
        """节点 completed 但产物缺失时，audit 报告状态-产物漂移。"""
        self.lock_problem()
        self.complete_n0()
        (self.project / "ProblemInfo" / "TimePlan.md").unlink()
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertTrue(any("TimePlan.md" in item for item in audit["state_artifact_drift"]))
        self.assertFalse(audit["summary"]["healthy"])

    def test_iteration_plan_blocked_then_ready(self):
        """iteration_plan：前置缺失时 blocked；补齐后 ready 且包含完整迭代步骤。"""
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("orchestrator_runtime", ORCH)
        orch = importlib.util.module_from_spec(spec)
        sys.modules["orchestrator_runtime"] = orch
        spec.loader.exec_module(orch)
        self.lock_problem()
        plan = orch.iteration_plan(str(self.project), "N4")
        self.assertEqual(plan["status"], "blocked")
        self.complete_n0()
        executors = {"N1": "selector", "N2": "dataprep", "N3": "modeler"}
        skills = {"N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "N2": "academic-orchestrator:mm-data-preprocessing", "N3": "academic-orchestrator:mm-model-library"}
        for n in ("N1", "N2", "N3"):
            self.run_state("node-start", n, "--dir", str(self.project))
            self.run_state("node-finish", n, "--agent", executors[n], "--skills", skills[n], "--dir", str(self.project))
            # 审阅-修改循环：上游必须审阅 PASS 才能被下游 node-start 放行
            # N2 额外要求数据血缘台账（2.0.0 D1 门禁），此处豁免以聚焦管线前置条件测试
            self.run_state("node-review", n, "--agent", "reviewer", "--result", "PASS",
                           "--skills", skills[n], "--summary", "ok",
                           "--allow-missing-lineage", "--dir", str(self.project))
        plan = orch.iteration_plan(str(self.project), "N4")
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["reviewer"], "mm-code-reviewer")
        kinds = [step["kind"] for step in plan["steps"]]
        self.assertIn("round-start", kinds)
        self.assertIn("agent_execute", kinds)
        self.assertIn("round-score", kinds)
        self.assertIn("round-decide", kinds)

    def test_round_reports_are_retained(self):
        """每次迭代的独立审阅/决策报告自动留存到 state/reports/ 并可查询。"""
        self.lock_problem()
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "7.5", "--dims", '{"correctness":8,"efficiency":7}',
                       "--judge", "mm-code-reviewer", "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json", "--dir", str(self.project))
        self.run_state("round-decide", "N4", "--round", "1", "--feedback", "可继续优化", "--dir", str(self.project))
        reports = self.project / "state" / "reports"
        self.assertTrue((reports / "index.json").exists())
        index = json.loads((reports / "index.json").read_text(encoding="utf-8"))
        kinds = {e["kind"] for e in index["entries"]}
        self.assertIn("review", kinds)
        self.assertIn("decision", kinds)
        review_files = [e for e in index["entries"] if e["kind"] == "review"]
        self.assertEqual(review_files[0]["agent"], "mm-code-reviewer")
        self.assertTrue((self.project / review_files[0]["path"]).exists())
        r = self.run_state("report-list", "--node", "N4", "--json", "--dir", str(self.project))
        listing = json.loads(r.stdout)
        self.assertEqual(listing["count"], 2)

    def test_result_ingest_archives_report(self):
        """result-ingest 将完整 result 归档到 reports/。"""
        self.lock_problem()
        result_path = self._write_result()
        self.run_state("result-ingest", str(result_path), "--node", "N4", "--dir", str(self.project))
        index = json.loads((self.project / "state" / "reports" / "index.json").read_text(encoding="utf-8"))
        result_entries = [e for e in index["entries"] if e["kind"] == "result"]
        self.assertEqual(len(result_entries), 1)
        archived = json.loads((self.project / result_entries[0]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(archived["run_id"], "N4-2026-01-01T00:00:00Z")
        self.assertEqual(archived["node_id"], "N4")

    # ---------------------------------------------------------------- 容错与自动核查

    def _import_resilience(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("resilience", ROOT / "shared" / "state-engine" / "resilience.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["resilience"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_resilience_retry_and_degrade(self):
        """容错工具：失败自动重试成功；限流时并发自动降级到串行并如实记录失败。"""
        res = self._import_resilience()
        calls = {"n": 0}
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("rate limit")
            return "ok"
        self.assertEqual(res.retry_with_backoff(flaky, attempts=4, base_delay=0.01), "ok")
        self.assertEqual(calls["n"], 3)
        degraded = []
        def worker(item):
            raise TimeoutError("rate limited")
        out = res.adaptive_parallel([0, 1, 2, 3], worker, max_workers=4, min_workers=1,
                                    attempts_per_item=1, base_delay=0.01, on_degrade=lambda w: degraded.append(w))
        self.assertEqual(out["final_workers"], 1)
        self.assertEqual(len(out["failures"]), 4)
        self.assertTrue(degraded)

    def test_auto_check_and_h_confirm(self):
        """H 门禁自动核查：auto-check 置 auto_passed + 生成核查报告 + 不挂起；h-confirm 追认。"""
        self.lock_problem()
        # 模拟 N4 已执行，H2 待处理
        self.run_state("auto-check", "N4", "--gate", "H2", "--agent", "mm-code-reviewer",
                       "--skills", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--summary", "数值量级与代码输出一致", "--round", "1", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["gates"]["H2"]["status"], "auto_passed")
        self.assertFalse(state["gates"]["H2"]["confirmed"])
        # 核查报告已生成
        index = json.loads((self.project / "state" / "reports" / "index.json").read_text(encoding="utf-8"))
        ver = [e for e in index["entries"] if e["kind"] == "verification"]
        self.assertEqual(len(ver), 1)
        self.assertTrue((self.project / ver[0]["path"]).exists())
        # human_checkpoint 登记待追认
        checkpoint = (self.project / "state" / "human_checkpoint.md").read_text(encoding="utf-8")
        self.assertIn("H2", checkpoint)
        # 人工追认
        self.run_state("h-confirm", "H2", "--note", "用户确认", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["gates"]["H2"]["status"], "confirmed")
        self.assertTrue(state["gates"]["H2"]["confirmed"])
        # 核查 Agent 必须独立（执行 Agent 自核被拒）
        r = self.run_state("auto-check", "N4", "--gate", "H2", "--agent", "coder",
                           "--skills", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                           "--summary", "x", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)

    def test_review_loop_and_anti_laziness(self):
        """审阅-修改-再审阅循环：生成审阅/修改/复审/上限序列；FAIL 审阅无证据被拒；空修改检测。"""
        self.lock_problem()
        # review-loop 序列
        r = self.run_state("review-loop", "N1", "--dir", str(self.project))
        loop = json.loads(r.stdout)
        self.assertEqual(loop["reviewer"], "reviewer")
        self.assertEqual(loop["executor"], "selector")
        kinds = [s["kind"] for s in loop["steps"]]
        self.assertIn("review", kinds)
        self.assertIn("modify", kinds)
        self.assertIn("re_review", kinds)  # 审阅→修改→再审阅往复
        self.assertEqual(loop["max_modify_attempts"], 2)
        self.assertIn("escalate", kinds)  # 防死循环出口
        modify_step = next(s for s in loop["steps"] if s["kind"] == "modify")
        self.assertEqual(modify_step["modify_agent"], "selector")
        self.assertIn("academic-orchestrator:mm-problem-analysis", modify_step["modify_skills"])  # 修改时必须加载 skill
        # 审阅偷懒拦截：FAIL 无 evidence 被拒
        result = self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "FAIL",
                                "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                                "--summary", "缺依据", "--dir", str(self.project), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence", result.stderr + result.stdout)
        # 带证据的 FAIL 可落盘
        result = self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "FAIL",
                                "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                                "--evidence", "ProblemInfo/ProblemNotes.md",
                                "--summary", "缺隐性约束", "--dir", str(self.project))
        self.assertEqual(result.returncode, 0)
        # 空返修检测：快照后无变化 → EMPTY_REPAIR
        self.run_state("node-repair-check", "N1", "--attempt", "1", "--dir", str(self.project))
        r = self.run_state("node-repair-check", "N1", "--attempt", "2", "--dir", str(self.project))
        check = json.loads(r.stdout)
        self.assertEqual(check["status"], "EMPTY_REPAIR")

    def test_detect_existing_materials(self):
        """已有材料检测：扫描论文/代码/数据并给出复用计划；脚手架占位不算已有材料。"""
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("orchestrator_runtime", ORCH)
        orch = importlib.util.module_from_spec(spec)
        sys.modules["orchestrator_runtime"] = orch
        spec.loader.exec_module(orch)
        # 模拟已有材料
        (self.project / "Material" / "similar_papers" / "参考论文.md").write_text("# 旧论文\n", encoding="utf-8")
        (self.project / "BackupArchive" / "旧代码").mkdir(parents=True, exist_ok=True)
        (self.project / "BackupArchive" / "旧代码" / "solver_old.py").write_text("print('old')\n", encoding="utf-8")
        (self.project / "Data" / "raw" / "history.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        det = orch.detect_existing_materials(str(self.project))
        self.assertTrue(det["has_existing"])
        self.assertIn("Material/similar_papers/参考论文.md", det["found"]["paper"])
        self.assertIn("BackupArchive/旧代码/solver_old.py", det["found"]["code"])
        self.assertIn("Data/raw/history.csv", det["found"]["data"])
        self.assertIsNotNone(det["reuse_plan"])
        self.assertIn("sync_import", det["reuse_plan"]["steps"][0])
        # 脚手架占位不算已有材料
        self.assertNotIn("Code/main.py", det["found"]["code"])
        self.assertNotIn("ReportPaper/LaTeX/main.tex", det["found"]["paper"])
        # AI 内容整理任务包：每个文件必须读取内容，含提取要点/归类/登记字段
        plan = orch.material_intake_plan(str(self.project))
        self.assertTrue(plan["has_existing"])
        self.assertEqual(plan["total"], 3)
        by_file = {t["file"]: t for t in plan["tasks"]}
        self.assertTrue(by_file["Material/similar_papers/参考论文.md"]["must_read_content"])
        self.assertTrue(any("关键结论" in e for e in by_file["Material/similar_papers/参考论文.md"]["extract"]))
        self.assertIn("字段与含义", by_file["Data/raw/history.csv"]["extract"])
        self.assertTrue(any("对应第几问" in e for e in by_file["BackupArchive/旧代码/solver_old.py"]["extract"]))
        self.assertEqual(plan["register_file"], "state/material_index.json")
        self.assertIn("禁止只按扩展名归类", plan["rule"])

    def test_upgrade_heal_migrates_legacy_project(self):
        """升级自愈：旧版遗留（00_State 目录、旧文件名、旧节点目录）自动迁移修复并复检。"""
        import shutil as _sh
        # 模拟旧版项目：state -> 00_State，旧文件名，旧节点目录
        _sh.move(str(self.project / "state"), str(self.project / "00_State"))
        _sh.move(str(self.project / "Data" / "DataLog.md"), str(self.project / "Data" / "Data_Log.md"))
        _sh.move(str(self.project / "00_State" / "nodes" / "代码"), str(self.project / "00_State" / "nodes" / "N4-代码"))
        # 预览模式：只输出计划
        r = self.run_state("upgrade-heal", "--dir", str(self.project))
        out = r.stdout
        self.assertIn("00_State", out)
        self.assertIn("Data_Log.md", out)
        # 执行迁移
        self.run_state("upgrade-heal", "--apply", "--dir", str(self.project))
        self.assertTrue((self.project / "state" / "decision_log.json").exists())
        self.assertFalse((self.project / "00_State").exists())
        self.assertTrue((self.project / "Data" / "DataLog.md").exists())
        self.assertFalse((self.project / "Data" / "Data_Log.md").exists())
        self.assertTrue((self.project / "state" / "nodes" / "代码").is_dir())
        self.assertFalse((self.project / "state" / "nodes" / "N4-代码").exists())
        # 复检：无旧命名残留
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertEqual(audit["legacy_names"], [])
        # JSON 引用已更新
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertIn("state/nodes", state["nodes"]["N4"]["homepage"])

    def test_self_check_script(self):
        """插件升级自检脚本：契约 + 用户级同步检测。

        该测试依赖「本仓库版本已安装到插件缓存」。开发期源码版本领先于已安装版本
        （例如源码 2.0.0 而缓存仍为 1.8.0）时，self_check 会如实报告
        「插件缓存缺失」——这是正确的部署告警，不是代码缺陷。因此这里只断言
        报告结构与契约检查通过；缓存未同步时跳过 healthy 断言，并说明原因。
        """
        r = subprocess.run(["python", str(ROOT / "scripts" / "self_check.py"), "--fix", "--json"],
                           capture_output=True, text=True)
        report = json.loads(r.stdout)
        self.assertIn("repo_version", report)
        self.assertIn("contract_ok", report)
        self.assertIn("user_sync_ok", report)
        self.assertIn("healthy", report)
        # 契约必须干净（与是否安装无关）
        self.assertTrue(report["contract_ok"], f"契约检查未通过: {report.get('issues')}")
        issues = report.get("issues") or []
        cache_missing = any("插件缓存缺失" in str(i) for i in issues)
        if cache_missing:
            self.skipTest("本仓库版本尚未安装到插件缓存；self_check 的 healthy 断言需在安装后验证")
        self.assertTrue(report["healthy"], f"自检未健康: {issues}")

    def test_node_finish_enforces_executor_and_iteration(self):
        """node-finish 强制：错 Agent 代做被拒；迭代节点无 round 直接标完成被拒。"""
        self.lock_problem()
        self.complete_n0()
        # 错 Agent 代做 N1 被拒（应 selector 执行）
        r = self.run_state("node-finish", "N1", "--agent", "coder",
                           "--artifact", "ProblemInfo/ProblemNotes.md", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("selector", r.stderr + r.stdout)
        # 迭代节点 N4 无 round 直接 finish 被拒（技能声明正确，触发迭代强制）
        r = self.run_state("node-finish", "N4", "--agent", "coder",
                           "--skills", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                           "--artifact", "Code/main.py", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("round-start", r.stderr + r.stdout)
        # 正确 Agent + 技能 + 非迭代节点可完成
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                       "--artifact", "ProblemInfo/ProblemNotes.md", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["nodes"]["N1"]["status"], "completed")
        self.assertEqual(state["nodes"]["N1"]["executed_by"], "selector")
        # 技能缺失被拒（强制子 Agent 先加载 required_skills）
        r = self.run_state("node-finish", "N2", "--agent", "dataprep",
                           "--skills", "academic-orchestrator:mm-model-library", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("academic-orchestrator:mm-data-preprocessing", r.stderr + r.stdout)

    def test_audit_detects_fake_state(self):
        """状态真实性：手工伪造的 decision_log（无 generator 标记）会被 audit 识别为绕过 CLI。"""
        self.lock_problem()
        # 模拟主 agent 手工伪造状态（去掉 generator 标记、删节点）
        state_file = self.project / "state" / "decision_log.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["meta"].pop("generator", None)
        state.pop("nodes", None)
        state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertTrue(any("generator" in item or "伪造" in item or "绕过" in item for item in audit["state_authenticity"]))
        self.assertFalse(audit["summary"]["healthy"])
        # init 生成的正规状态应通过真实性检查
        self.run_state("init", "--force", "--dir", str(self.project), "--name", "Test")
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertEqual(audit["state_authenticity"], [])

    # ---------------------------------------------------------------- 动态进度更新：node-log / todo

    def test_node_log_records_small_steps(self):
        """node-log 逐条记录执行小步骤到 state/nodes/<name>/steps.md（时间线留痕）。"""
        self.run_state("node-log", "N4", "--step", "完成数据加载与清洗", "--by", "coder", "--dir", str(self.project))
        self.run_state("node-log", "N4", "--step", "向量化重写距离计算", "--dir", str(self.project))
        steps = (self.project / "state" / "nodes" / "代码" / "steps.md").read_text(encoding="utf-8")
        self.assertIn("完成数据加载与清洗", steps)
        self.assertIn("向量化重写距离计算", steps)
        self.assertIn("(coder)", steps)
        r = self.run_state("node-log", "N4", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)  # 缺 --step 拒绝

    def test_todo_add_done_list(self):
        """todo 命令动态更新任务清单：add 新增、done 标记完成（[x]+时间戳）、list 可见。"""
        self.run_state("todo", "add", "实现求解器核心", "--node", "N4", "--dir", str(self.project))
        self.run_state("todo", "add", "画图", "--node", "N6", "--dir", str(self.project))
        self.run_state("todo", "done", "求解器核心", "--dir", str(self.project))
        text = (self.project / "state" / "todo.md").read_text(encoding="utf-8")
        self.assertIn("- [x] [N4] 实现求解器核心", text)
        self.assertIn("- [ ] [N6] 画图", text)
        r = self.run_state("todo", "list", "--dir", str(self.project))
        self.assertIn("[N4] 实现求解器核心", r.stdout)

    def test_audit_detects_inline_execution_without_executor_evidence(self):
        """执行者证据：节点推进但执行 Agent 无 result.json → audit 报告疑似内联代做。"""
        self.lock_problem()
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                       "--dir", str(self.project))
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertTrue(any(m["node"] == "N1" for m in audit["executor_evidence_missing"]))
        self.assertTrue(any("内联代做" in i for i in audit["summary"]["issues"]))
        # 子 Agent 正常写 result.json 后不再标记
        result_dir = self.project / "state" / "agents" / "selector"
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "result.json").write_text(json.dumps({
            "agent": "selector", "node": "N1", "round": None, "artifacts": [],
            "summary": "选题拆解完成"}, ensure_ascii=False), encoding="utf-8")
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertFalse(any(m["node"] == "N1" for m in audit["executor_evidence_missing"]))

    # ---------------------------------------------------------------- 联动同步与全流程覆盖

    def test_cascade_invalidate_resets_downstream(self):
        """级联失效：上游产物变更 → 下游 completed 节点与门禁重置 pending（联动同步）。"""
        self.lock_problem()
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--dir", str(self.project))
        self.run_state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "academic-orchestrator:mm-data-preprocessing", "--dir", str(self.project))
        # 预览模式不修改
        (self.project / "ProblemInfo" / "ProblemNotes.md").write_text("追加内容\n", encoding="utf-8")
        r = self.run_state("cascade-invalidate", "--dir", str(self.project))
        plan = json.loads(r.stdout)
        self.assertTrue(plan["preview"])
        self.assertEqual(plan["downstream_reset"], ["N2"])
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["nodes"]["N2"]["status"], "completed")  # 预览未生效
        # apply 实际重置 N2 并在 meta.cascade_invalidations 留痕
        r = self.run_state("cascade-invalidate", "--apply", "--dir", str(self.project))
        plan = json.loads(r.stdout)
        self.assertEqual(plan["downstream_reset"], ["N2"])
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["nodes"]["N2"]["status"], "pending")
        self.assertTrue(state["meta"]["cascade_invalidations"])

    def test_todo_plan_generates_full_pipeline_tasks(self):
        """todo plan：按状态自动生成全流程执行+审阅任务；节点完成且门禁通过后自动标完成。"""
        self.lock_problem()
        r = self.run_state("todo", "plan", "--dir", str(self.project))
        self.assertIn("新增 16 条", r.stdout)
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--dir", str(self.project))
        self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--summary", "ok",
                       "--dir", str(self.project))
        r = self.run_state("todo", "plan", "--dir", str(self.project))
        self.assertIn("标记完成 2 条", r.stdout)
        text = (self.project / "state" / "todo.md").read_text(encoding="utf-8")
        self.assertIn("- [x] [N1] 选题拆解 执行（selector）", text)
        self.assertIn("- [x] [N1] 选题拆解 审阅（reviewer）", text)
        self.assertIn("- [ ] [N4] 代码/代码迭代 执行（coder）", text)

    def test_flow_coverage_reports_missing_agents(self):
        """flow-coverage：按状态实际记录对照预期调用集，报告未调用 Agent/Skill。"""
        self.lock_problem()
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--dir", str(self.project))
        self.run_state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "academic-orchestrator:mm-data-preprocessing", "--dir", str(self.project))
        r = self.run_state("flow-coverage", "--dir", str(self.project))
        coverage = json.loads(r.stdout)
        self.assertIn("selector", coverage["used_agents"])
        self.assertIn("dataprep", coverage["used_agents"])
        self.assertIn("coder", coverage["missing_agents"])
        self.assertIn("humanize", coverage["expected_agents"])  # 去AI化专项必须在预期集
        self.assertFalse(coverage["summary"]["complete"])

    def test_audit_detects_unreviewed_completion(self):
        """审阅-修改循环：节点 completed 但门禁未通过 → audit 报告未审阅即完成；门禁 PASS 后消除。"""
        self.lock_problem()
        # 直接标完成、不审阅（门禁 M1 保持 pending）
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--dir", str(self.project))
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertTrue(any(m["node"] == "N1" for m in audit["unreviewed_completion"]))
        self.assertTrue(any("未审阅即完成" in i for i in audit["summary"]["issues"]))
        # 补上独立审阅 PASS 后不再标记
        self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--summary", "ok",
                       "--evidence", "ProblemInfo/ProblemNotes.md", "--dir", str(self.project))
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertFalse(any(m["node"] == "N1" for m in audit["unreviewed_completion"]))

    def test_node_start_blocks_unreviewed_upstream_and_handoff(self):
        """阶段联动：上游 completed 但审阅门禁未过 → 下游 node-start 拦截；审阅 PASS 后开工并刷新 handoff。"""
        self.lock_problem()
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--dir", str(self.project))
        # 上游未审阅（M1 pending）→ N2 不可开工
        r = self.run_state("node-start", "N2", "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("审阅门禁", r.stderr + r.stdout)
        # 审阅 PASS 后可开工，且 handoff 交接文件自动生成
        self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--summary", "ok",
                       "--evidence", "ProblemInfo/ProblemNotes.md", "--dir", str(self.project))
        self.run_state("node-start", "N2", "--goal", "清洗数据", "--dir", str(self.project))
        handoff = self.project / "state" / "nodes" / "数据处理" / "handoff.md"
        self.assertTrue(handoff.exists())
        text = handoff.read_text(encoding="utf-8")
        self.assertIn("N1", text)          # 上游交接
        self.assertIn("M1", text)          # 上游门禁
        self.assertIn("就绪", text)        # 就绪判定
        self.assertIn("执行 Agent", text)  # 本阶段角色

    def test_audit_detects_premature_progression(self):
        """阶段不完全即推进：下游已推进但上游未 completed/未审阅 → audit 报告（绕过 node-start 校验的情况）。"""
        self.lock_problem()
        # 手工把 N3 改为 in_progress（绕过 node-start：N2 尚未完成）
        state_file = self.project / "state" / "decision_log.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["nodes"]["N3"]["status"] = "in_progress"
        state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        r = self.run_state("project-audit", "--dir", str(self.project))
        audit = json.loads(r.stdout)
        self.assertTrue(any(m["node"] == "N3" and m["upstream"] == "N2" for m in audit["premature_progression"]))
        self.assertTrue(any("阶段不完全即推进" in i for i in audit["summary"]["issues"]))

    def test_handover_review_flags_completed_without_review(self):
        """接手复核：completed 但门禁未过 → 强制复核；审阅 PASS 后 → 复核确认；产物漂移 → 强制复核。"""
        self.lock_problem()
        self.run_state("node-finish", "N1", "--agent", "selector",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--dir", str(self.project))
        r = self.run_state("handover-review", "--dir", str(self.project))
        plan = json.loads(r.stdout)
        self.assertIn("强制复核", plan["nodes"]["N1"]["action"])
        self.assertIn("N1", plan["summary"]["forced_review"])
        self.assertIn("待执行", plan["nodes"]["N2"]["action"])
        # 审阅 PASS 后为复核确认
        self.run_state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                       "--skills", "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review", "--summary", "ok",
                       "--evidence", "ProblemInfo/ProblemNotes.md", "--dir", str(self.project))
        r = self.run_state("handover-review", "--dir", str(self.project))
        plan = json.loads(r.stdout)
        self.assertIn("复核确认", plan["nodes"]["N1"]["action"])
        # 产物漂移 → 强制复核
        (self.project / "ProblemInfo" / "ProblemNotes.md").write_text("新增内容" + chr(10), encoding="utf-8")
        r = self.run_state("handover-review", "--dir", str(self.project))
        plan = json.loads(r.stdout)
        self.assertIn("强制复核", plan["nodes"]["N1"]["action"])
        self.assertTrue(plan["nodes"]["N1"]["artifact_drift"])

    # ---------------------------------------------------------------- 门禁落盘路径与评分口径

    def test_round_score_rejects_unknown_dimension_keys(self):
        """五维口径：round-score 拒绝非法维度键名（防乱写维度/口径漂移）。"""
        self.lock_problem()
        self.complete_n0()
        for n in ("N1", "N2", "N3"):
            self.run_state("node-start", n, "--dir", str(self.project))
            self.run_state("node-finish", n, "--agent", {"N1": "selector", "N2": "dataprep", "N3": "modeler"}[n],
                           "--skills", {"N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                                        "N2": "academic-orchestrator:mm-data-preprocessing", "N3": "academic-orchestrator:mm-model-library"}[n],
                           "--dir", str(self.project))
            self.run_state("node-review", n, "--agent", "reviewer", "--result", "PASS",
                           "--skills", {"N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                                        "N2": "academic-orchestrator:mm-data-preprocessing", "N3": "academic-orchestrator:mm-model-library"}[n],
                           "--summary", "ok", "--allow-missing-lineage", "--dir", str(self.project))
        self.run_state("round-start", "N4", "--dir", str(self.project))
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8", "--judge", "mm-code-reviewer",
                           "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                           "--evidence", "Code/output/run.json",
                           "--dims", '{"correctness":8,"wrong_dim":7}', "--dir", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("维度键名非法", r.stderr + r.stdout)
        # 合法键名通过
        self.run_state("round-score", "N4", "--round", "1", "--total", "8", "--judge", "mm-code-reviewer",
                       "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json",
                       "--dims", '{"correctness":8,"efficiency":8,"readability":8,"robustness":8,"innovation":8}',
                       "--dir", str(self.project))

    def test_aux_gates_auto_pass(self):
        """门禁落盘路径闭环：N4 达标 → A1 自动 PASS；N7 开工且 V1 已过 → W1 自动 PASS。"""
        self.lock_problem()
        self.complete_n0()
        for n in ("N1", "N2", "N3"):
            self.run_state("node-start", n, "--dir", str(self.project))
            self.run_state("node-finish", n, "--agent", {"N1": "selector", "N2": "dataprep", "N3": "modeler"}[n],
                           "--skills", {"N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                                        "N2": "academic-orchestrator:mm-data-preprocessing", "N3": "academic-orchestrator:mm-model-library"}[n],
                           "--dir", str(self.project))
            self.run_state("node-review", n, "--agent", "reviewer", "--result", "PASS",
                           "--skills", {"N1": "academic-orchestrator:mm-problem-analysis,academic-orchestrator:mm-self-review",
                                        "N2": "academic-orchestrator:mm-data-preprocessing", "N3": "academic-orchestrator:mm-model-library"}[n],
                           "--summary", "ok", "--allow-missing-lineage", "--dir", str(self.project))
        # N4 round-score 达标 → A1 自动 PASS
        self.run_state("round-start", "N4", "--dir", str(self.project))
        self.run_state("round-score", "N4", "--round", "1", "--total", "8", "--judge", "mm-code-reviewer",
                       "--skills-read", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--evidence", "Code/output/run.json",
                       "--dims", '{"correctness":8,"efficiency":8,"readability":8,"robustness":8,"innovation":8}',
                       "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["gates"]["A1"]["status"], "PASS")
        # 推 N4 到 completed（round-decide early_stop）+ N5 + N6（含 V1 审阅）→ N7 开工自动 W1
        self.run_state("round-decide", "N4", "--round", "1", "--dir", str(self.project))
        # 迭代节点 completed 后需 node-review 落 P2 门禁（下游 N5 开工校验上游门禁）
        self.run_state("node-review", "N4", "--agent", "mm-code-reviewer", "--result", "PASS",
                       "--skills", "academic-orchestrator:mm-iteration-engine,academic-orchestrator:mm-algorithm-dev,academic-orchestrator:code-review",
                       "--summary", "ok", "--evidence", "Code/output/run.json", "--dir", str(self.project))
        # N5 迭代节点：round-start → score → decide → node-review（T1）
        self.run_state("node-start", "N5", "--dir", str(self.project))
        self.run_state("round-start", "N5", "--dir", str(self.project))
        self.run_state("round-score", "N5", "--round", "1", "--total", "8", "--judge", "mm-code-reviewer",
                       "--skills-read", "academic-orchestrator:mm-model-tuning,academic-orchestrator:mm-iteration-engine",
                       "--evidence", "ModelDocs/sensitivity-analysis.md",
                       "--dims", '{"correctness":8,"efficiency":8,"readability":8,"robustness":8,"innovation":8}',
                       "--dir", str(self.project))
        self.run_state("round-decide", "N5", "--round", "1", "--dir", str(self.project))
        self.run_state("node-review", "N5", "--agent", "mm-code-reviewer", "--result", "PASS",
                       "--skills", "academic-orchestrator:mm-model-tuning,academic-orchestrator:mm-iteration-engine",
                       "--summary", "ok", "--evidence", "ModelDocs/sensitivity-analysis.md", "--dir", str(self.project))
        # N6 非迭代节点：node-finish + node-review（V1）
        self.run_state("node-start", "N6", "--dir", str(self.project))
        self.run_state("node-finish", "N6", "--agent", "visualization",
                       "--skills", "academic-orchestrator:mm-visualization,academic-orchestrator:mm-iteration-engine,academic-orchestrator:figure-table-benchmark", "--dir", str(self.project))
        self.run_state("node-review", "N6", "--agent", "mm-viz-reviewer", "--result", "PASS",
                       "--skills", "academic-orchestrator:mm-visualization,academic-orchestrator:mm-iteration-engine,academic-orchestrator:figure-table-benchmark",
                       "--summary", "ok", "--evidence", "ResultFigures/figure-list.md", "--dir", str(self.project))
        self.run_state("node-start", "N7", "--dir", str(self.project))
        state = json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual(state["gates"]["W1"]["status"], "PASS")

    # ---------------------------------------------------------------- PDF 题目图形处理

    def run_guard(self, *args, check=True):
        return subprocess.run(["python", str(GUARD), *args], text=True, capture_output=True, check=check)

    def test_pdf_figure_human_mode_roundtrip(self):
        """无视觉能力：figures --mode human 生成人工描述请求单；未描述时 verify 阻断；描述后通过。"""
        problem = self.source / "problem.pdf"
        problem.write_bytes(b"%PDF-1.4 test with figures")
        self.run_guard("create", "--project", str(self.project), "--source", str(problem),
                       "--figure-mode", "human",
                       "--objectives", '["目标"]', "--constraints", '["约束"]',
                       "--preconditions", '["条件"]', "--data-requirements", '["数据"]',
                       "--evaluation-metrics", '["指标"]')
        self.run_guard("figures", "--project", str(self.project), "--source", str(problem), "--mode", "human")
        request = self.project / "state" / "problem_figure_request.md"
        self.assertTrue(request.exists())
        r = self.run_guard("verify", "--project", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("人工描述", r.stderr + r.stdout)
        self.run_guard("figures-read", "--project", str(self.project), "--mode", "human",
                       "--description", "第2页有趋势图：横轴时间、纵轴销量，整体上升后回落")
        r = self.run_guard("verify", "--project", str(self.project))
        self.assertEqual(r.returncode, 0)
        lock = json.loads((self.project / "state" / "problem_lock.json").read_text(encoding="utf-8"))
        self.assertTrue(lock["figure"]["figures_read"])
        self.assertIn("趋势图", lock["figure"]["human_description"])

    def test_pdf_figure_vision_mode_blocks_without_reading(self):
        """有视觉能力：figures --mode vision 未登记/未阅读时 verify 阻断；登记并阅读后通过。"""
        problem = self.source / "problem.pdf"
        problem.write_bytes(b"%PDF-1.4 test with figures")
        self.run_guard("create", "--project", str(self.project), "--source", str(problem),
                       "--figure-mode", "vision",
                       "--objectives", '["目标"]', "--constraints", '["约束"]',
                       "--preconditions", '["条件"]', "--data-requirements", '["数据"]',
                       "--evaluation-metrics", '["指标"]')
        r = self.run_guard("verify", "--project", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("vision", r.stderr + r.stdout)
        # 无 pdftoppm 环境时，figures --mode vision 应输出 BLOCKED 提示而不崩溃
        import shutil
        if shutil.which("pdftoppm") is None:
            r = self.run_guard("figures", "--project", str(self.project), "--source", str(problem), "--mode", "vision")
            self.assertEqual(r.returncode, 0)
            self.assertIn("BLOCKED", r.stdout)
        # 手工登记图形（模拟 pdftoppm 产出 + 视觉模型阅读确认）
        import hashlib as _hashlib
        fig = self.project / "ProblemInfo" / "figures" / "page-1.png"
        fig.parent.mkdir(parents=True, exist_ok=True)
        fig.write_bytes(b"png-bytes")
        lock = json.loads((self.project / "state" / "problem_lock.json").read_text(encoding="utf-8"))
        lock["figure"] = {"mode": "vision",
                          "figures": [{"path": "ProblemInfo/figures/page-1.png", "sha256": _hashlib.sha256(fig.read_bytes()).hexdigest()}],
                          "figures_read": False, "human_description": None, "request_path": None}
        (self.project / "state" / "problem_lock.json").write_text(json.dumps(lock, ensure_ascii=False), encoding="utf-8")
        r = self.run_guard("verify", "--project", str(self.project), check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("figures_read", r.stderr + r.stdout)
        self.run_guard("figures-read", "--project", str(self.project), "--mode", "vision")
        r = self.run_guard("verify", "--project", str(self.project))
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
