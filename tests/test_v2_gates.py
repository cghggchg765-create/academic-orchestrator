#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2.0.0 新增校验的正式测试：空产物拦截、gate-set 防伪造、数据血缘、落位与孤儿扫描。

这些是此前只有手工脚本覆盖的能力，入库为 pytest 以便进 CI。
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
LINEAGE = ROOT / "scripts" / "validate_data_lineage.py"
RAW_LOCK = ROOT / "scripts" / "raw_lock.py"


def run(*args, cwd=None, check=True):
    return subprocess.run([sys.executable, *map(str, args)], text=True,
                          capture_output=True, check=check, cwd=cwd)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_gate_"))
        self.project = self.tmp / "project"
        # 固定 skill 扫描根：路由结果可复现，不随本机已装 skill 漂移
        self.skill_root = self.tmp / "skills"
        self.skill_root.mkdir(parents=True, exist_ok=True)
        run(STATE, "init", "--dir", self.project, "--name", "t")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self, *args, check=True):
        env = dict(os.environ)
        env["MM_SKILL_ROOTS"] = str(self.skill_root)
        return subprocess.run([sys.executable, STATE, *args, "--dir", self.project],
                              text=True, capture_output=True, check=check, env=env)

    def decision(self):
        return json.loads((self.project / "state" / "decision_log.json").read_text(encoding="utf-8"))

    def lock_problem(self):
        """N1 之后节点需要题目事实锁定（problem_lock），否则 node-start 被拒。
        problem_guard 的五个事实字段要求 JSON 数组。"""
        guard = ROOT / "shared" / "state-engine" / "problem_guard.py"
        problem = self.tmp / "problem.md"
        problem.write_text("# Problem\n最小化成本、满足预算\n", encoding="utf-8")
        run(guard, "create", "--project", self.project, "--source", problem,
            "--figure-mode", "none",
            "--objectives", '["最小化总成本"]',
            "--constraints", '["预算不超过上限"]',
            "--preconditions", '["历史数据可得"]',
            "--data-requirements", '["历史销量与价格"]',
            "--evaluation-metrics", '["MAPE"]', check=False)
        run(guard, "verify", "--project", self.project, check=False)

    def reach_n2(self):
        """推进到 N2 可开工的状态：N0 完成 + 题目锁定 + N1 完成且审阅 PASS。"""
        self.state("node-finish", "N0")
        self.lock_problem()
        self.state("node-start", "N1")
        # 覆盖脚手架预建的占位模板（否则被"空模板不算产出"判为无产出）
        (self.project / "ProblemInfo" / "ProblemNotes.md").write_text(
            "# 选题拆解\n\n## 目标\n最小化总成本，满足预算与产能约束。\n\n"
            "## 约束\n预算上限、产能上限、交付期。\n\n"
            "## 数据清单\n历史销量、价格、产能表（赛题附件）。\n\n"
            "## 题型判定\n优化类（连续变量）。\n", encoding="utf-8")
        # 分阶段归档是 node-finish 硬要求
        self.state("checkpoint", "N1", "--phase", "Phase 1 选题拆解",
                   "--done", "目标/约束/数据清单", "--artifact", "ProblemInfo/ProblemNotes.md")
        self.state("node-finish", "N1", "--agent", "selector",
                   "--skills", "mm-problem-analysis,mm-self-review")
        self.state("node-review", "N1", "--agent", "reviewer", "--result", "PASS",
                   "--skills", "mm-problem-analysis,mm-self-review",
                   "--summary", "ok", "--allow-missing-mcp")
        self.state("node-start", "N2")


class EmptyArtifactTest(Base):
    """空产物不得标完成（防止"什么都没做也算完成"）。"""

    def test_rejects_missing_checkpoint(self):
        """分阶段归档是硬要求：无快照时 node-finish 被拒（先于产物校验）。"""
        self.reach_n2()
        r = self.state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "mm-data-preprocessing", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("没有任何进度快照", r.stderr)

    def test_rejects_empty_artifacts(self):
        """有快照但无真实产物 → 拒绝（空产物不得标完成）。"""
        self.reach_n2()
        self.state("checkpoint", "N2", "--phase", "Phase 0 数据探查",
                   "--done", "探查完成", "--pending", "清洗")
        r = self.state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "mm-data-preprocessing", check=False)
        self.assertNotEqual(r.returncode, 0, "空产物应被拒绝")
        self.assertIn("没有任何实际产出文件", r.stderr)

    def test_allows_when_real_output_exists(self):
        self.reach_n2()
        (self.project / "Data" / "raw").mkdir(parents=True, exist_ok=True)
        (self.project / "Data" / "raw" / "d.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        self.state("checkpoint", "N2", "--phase", "Phase 1 清洗",
                   "--done", "生成清洗数据", "--artifact", "Data/raw/d.csv")
        r = self.state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "mm-data-preprocessing")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unfilled_template_not_counted_as_output(self):
        """脚手架预建的 DataLog 模板（带占位哨兵）不算产出。"""
        self.reach_n2()
        datalog = self.project / "Data" / "DataLog.md"
        self.assertTrue(datalog.exists(), "脚手架应预建 DataLog.md")
        self.state("checkpoint", "N2", "--phase", "Phase 0", "--done", "探查")
        r = self.state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "mm-data-preprocessing", check=False)
        self.assertNotEqual(r.returncode, 0, "仅空模板时应被拒绝")

    def test_explicit_exemption(self):
        self.reach_n2()
        r = self.state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "mm-data-preprocessing",
                       "--allow-empty-artifacts", "--allow-no-checkpoint")
        self.assertEqual(r.returncode, 0, r.stderr)


class GateSetForgeryTest(Base):
    """审阅类门禁不得用 gate-set 直接伪造 PASS。"""

    REVIEW_GATES = ("M1", "D1", "P1", "P2", "T1", "V1", "B1", "W2", "A3")

    def test_review_gates_cannot_be_faked(self):
        for gate in self.REVIEW_GATES:
            r = self.state("gate-set", gate, "PASS", "--agent", "fake", check=False)
            self.assertNotEqual(r.returncode, 0, f"{gate} 应拒绝 gate-set 伪造 PASS")
            self.assertIn("审阅类门禁", r.stderr)

    def test_review_gate_fail_still_allowed(self):
        """FAIL/BLOCKED 可以直写（用于人工排查场景），只有 PASS 被禁。"""
        r = self.state("gate-set", "D1", "FAIL", "--agent", "tester", check=False)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_auto_gates_not_affected(self):
        """自动门禁（S<n>-Nx）与人工门禁不在禁止列表内。"""
        r = self.state("gate-set", "S1-N4", "PASS", "--agent", "round-score", check=False)
        self.assertEqual(r.returncode, 0, r.stderr)


class DataLineageTest(Base):
    """数据血缘：raw 篡改 / 断链 / 缺过程记录 都应 FAIL。"""

    def _fixture(self):
        d = self.project / "Data"
        (d / "raw").mkdir(parents=True, exist_ok=True)
        (d / "processed").mkdir(parents=True, exist_ok=True)
        (self.project / "transform").mkdir(parents=True, exist_ok=True)
        (d / "raw" / "src.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        (d / "processed" / "clean.csv").write_text("a,b,c\n1,2,3\n3,4,7\n", encoding="utf-8")
        (self.project / "transform" / "t.txt").write_text("op: add c\n", encoding="utf-8")

    def _ledger(self):
        import hashlib

        def h(p):
            return hashlib.sha256(Path(p).read_bytes()).hexdigest()

        raw = h(self.project / "Data" / "raw" / "src.csv")
        out = h(self.project / "Data" / "processed" / "clean.csv")
        scr = h(self.project / "transform" / "t.txt")
        return {
            "schema_version": "data-lineage/1.0", "project_id": "t",
            "generated_at": "2026-01-01T00:00:00Z",
            "raw": {"files": [{"path": "Data/raw/src.csv", "sha256": raw, "rows": 2, "cols": 2,
                               "data_class": "contest_provided"}]},
            "stages": [{
                "stage": "processed",
                "inputs": [{"path": "Data/raw/src.csv", "sha256": raw, "source_stage": "raw"}],
                "transform": {"script": "transform/t.txt", "script_sha256": scr,
                              "params": {"add": "c"}, "random_seed": 0,
                              "operations": [{"op": "add_column", "columns": ["c"], "reason": "sum"}]},
                "outputs": [{"path": "Data/processed/clean.csv", "sha256": out, "rows": 2, "cols": 3}],
                "diff": {"rows_delta": 0, "cols_delta": 1},
            }],
            "invariants": {"raw_unmodified": True, "chain_continuous": True, "reproducible": True},
        }

    def _validate(self, ledger=None):
        self._fixture()
        data = ledger if ledger is not None else self._ledger()
        path = self.project / "Data" / "data-lineage.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return run(LINEAGE, path, "--root", self.project, "--json", check=False)

    def test_valid_lineage_passes(self):
        r = self._validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_raw_tamper_detected(self):
        self._fixture()
        ledger = self._ledger()
        (self.project / "Data" / "raw" / "src.csv").write_text("a,b\n9,9\n", encoding="utf-8")
        path = self.project / "Data" / "data-lineage.json"
        path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        r = run(LINEAGE, path, "--root", self.project, "--json", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("哈希不符", r.stdout)

    def test_broken_chain_detected(self):
        self._fixture()
        ledger = self._ledger()
        ledger["stages"][0]["inputs"][0]["path"] = "Data/raw/other.csv"
        r = self._validate(ledger)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("血缘断裂", r.stdout)

    def test_missing_transform_detected(self):
        self._fixture()
        ledger = self._ledger()
        ledger["stages"][0]["transform"] = {}
        r = self._validate(ledger)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("变换脚本", r.stdout)

    def test_d1_blocked_without_lineage(self):
        """无血缘台账时 N2 审阅 PASS 被拒（D1 机器强制）。"""
        self.reach_n2()
        r = self.state("node-review", "N2", "--agent", "reviewer", "--result", "PASS",
                       "--skills", "mm-data-preprocessing", "--evidence", "Data/DataLog.md",
                       "--allow-missing-mcp", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("数据血缘", r.stderr)


class RawLockTest(unittest.TestCase):
    """raw 只读锁定：建立基线后任何改动都应被检出。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_raw_"))
        (self.tmp / "Data" / "raw").mkdir(parents=True)
        (self.tmp / "Data" / "raw" / "d.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lock_create_then_pass(self):
        self.assertEqual(run(RAW_LOCK, "--root", self.tmp).returncode, 0)
        r = run(RAW_LOCK, "--root", self.tmp, "--json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["status"], "PASS")

    def test_tamper_detected(self):
        run(RAW_LOCK, "--root", self.tmp)
        (self.tmp / "Data" / "raw" / "d.csv").write_text("a,b\n9,9\n", encoding="utf-8")
        r = run(RAW_LOCK, "--root", self.tmp, "--json", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["status"], "TAMPERED")

    def test_init_creates_lock_when_data_present(self):
        project = self.tmp / "proj"
        shutil.copytree(self.tmp / "Data", project / "Data")
        run(STATE, "init", "--dir", project, "--name", "p")
        self.assertTrue((project / "Data" / "raw_lock.json").exists(),
                        "init 应在 Data/raw 有数据时自动建立锁定基线")


class ArtifactRegistryTest(Base):
    """产物入库：落位强制 + 路径穿越封堵 + 孤儿扫描。"""

    def test_rejects_path_traversal(self):
        (self.project / "stray.csv").write_text("x\n1\n", encoding="utf-8")
        r = self.state("register-artifact", "N2", "--path", "Data/../stray.csv",
                       "--kind", "dataset", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("产物落位违规", r.stderr)

    def test_accepts_valid_placement(self):
        (self.project / "Data" / "raw").mkdir(parents=True, exist_ok=True)
        (self.project / "Data" / "raw" / "ok.csv").write_text("x\n1\n", encoding="utf-8")
        r = self.state("register-artifact", "N2", "--path", "Data/raw/ok.csv", "--kind", "dataset")
        self.assertEqual(r.returncode, 0, r.stderr)
        reg = json.loads((self.project / "state" / "reports" / "artifacts-registry.json")
                         .read_text(encoding="utf-8"))
        self.assertTrue(any(a["path"] == "Data/raw/ok.csv" for a in reg["artifacts"]))

    def test_orphan_scan_finds_stray_file(self):
        (self.project / "stray.txt").write_text("x", encoding="utf-8")
        r = self.state("orphan-scan")
        report = json.loads(r.stdout)
        self.assertIn("stray.txt", report["orphans"])


class IterationDeliverableTest(Base):
    """P1-8：迭代节点由 round-decide 标完成，绕过了 node-finish 的产物/快照校验。

    round-decide 的完成分支现在必须走同一套 require_node_deliverables。
    """

    def test_require_node_deliverables_blocks_without_checkpoint(self):
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "shared" / "state-engine"))
        import state_nodes  # noqa: E402

        with self.assertRaises(SystemExit) as ctx:
            state_nodes.require_node_deliverables(str(self.project), "N4")
        msg = str(ctx.exception.code)
        self.assertIn("没有任何进度快照", msg)

    def test_require_node_deliverables_blocks_empty_artifacts(self):
        """有快照但仍无真实产出 → 拒绝。

        注意：判定以 node-start 时的产物快照为基准（P1-10），所以必须先走 node-start
        记录 start_artifact_hash，之后产出的文件才算数。
        """
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "shared" / "state-engine"))
        import state_nodes  # noqa: E402

        # 记录开工快照（模拟真实流程）
        state_nodes.artifact_snapshot  # 存在性检查
        st = self.decision()
        st["nodes"]["N4"]["start_artifact_hash"] = state_nodes.artifact_snapshot(
            str(self.project), "N4")
        (self.project / "state" / "decision_log.json").write_text(
            json.dumps(st, ensure_ascii=False), encoding="utf-8")

        ck = self.project / "state" / "checkpoints" / "N4.jsonl"
        ck.parent.mkdir(parents=True, exist_ok=True)
        ck.write_text('{"seq":1,"phase":"P1","done":["x"],"pending":[],"artifacts":[]}\n',
                      encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            state_nodes.require_node_deliverables(str(self.project), "N4")
        self.assertIn("没有任何实际产出文件", str(ctx.exception.code))

    def test_require_node_deliverables_passes_with_both(self):
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "shared" / "state-engine"))
        import state_nodes  # noqa: E402

        ck = self.project / "state" / "checkpoints" / "N4.jsonl"
        ck.parent.mkdir(parents=True, exist_ok=True)
        ck.write_text('{"seq":1,"phase":"P1","done":["x"],"pending":[],"artifacts":[]}\n',
                      encoding="utf-8")
        code = self.project / "Code"
        code.mkdir(parents=True, exist_ok=True)
        (code / "main.py").write_text("# real code\n" * 20, encoding="utf-8")
        state_nodes.require_node_deliverables(str(self.project), "N4")  # 不应抛


class CheckpointSubstanceTest(Base):
    """P1-9：空壳 checkpoint（无 done/pending/artifact）仍可落盘，但要能看出无信息可用。"""

    def test_empty_checkpoint_still_records_but_flags(self):
        r = self.state("checkpoint", "N2", "--phase", "Phase1")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.state("checkpoint-list", "N2", "--latest")
        out = json.loads(r.stdout)
        last = out["checkpoints"][0]
        self.assertEqual(last["done"], [])
        self.assertEqual(last["pending"], [])
        self.assertIn("resume_hint", out)


class CheckpointTest(Base):
    """分阶段归档：快照落盘、可读回、含 resume_hint。"""

    def test_checkpoint_and_resume(self):
        (self.project / "Data" / "raw").mkdir(parents=True, exist_ok=True)
        (self.project / "Data" / "raw" / "a.csv").write_text("x\n1\n", encoding="utf-8")
        r = self.state("checkpoint", "N2", "--phase", "Phase 0 数据探查",
                       "--done", "行列数统计", "--pending", "缺失率分析",
                       "--artifact", "Data/raw/a.csv", "--note", "下一步做缺失率")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.state("checkpoint-list", "N2", "--latest")
        out = json.loads(r.stdout)
        self.assertEqual(out["count"], 1)
        last = out["checkpoints"][0]
        self.assertEqual(last["phase"], "Phase 0 数据探查")
        self.assertIn("缺失率分析", last["pending"])
        self.assertIn("resume_hint", out)


if __name__ == "__main__":
    unittest.main()
