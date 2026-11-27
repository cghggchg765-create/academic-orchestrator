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


def run(*args, cwd=None, check=True, env=None):
    return subprocess.run([sys.executable, *map(str, args)], text=True,
                          capture_output=True, check=check, cwd=cwd, env=env)



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
                   "--summary", "ok", "--allow-missing-mcp",
                   "--evidence", "ProblemInfo/ProblemNotes.md")
        self.state("node-start", "N2")


class CompletionGuardHappyPathTest(Base):
    """统一完成守卫的**成功路径**回归。

    回归用：state_guard.require_completion_allowed 的关键字参数 check_own_gates
    与模块级同名函数冲突，参数遮蔽函数 —— 默认 True 时函数体执行
    `check_own_gates(node, state)` 实际调用的是 bool，必然 TypeError。
    表现：守卫只有"拒绝"能力，任何真正满足全部条件的节点收工会直接崩溃。
    此前全绿是因为所有用例都传 --skip-prereq 提前返回，从未走到成功路径。
    """

    def test_guard_allows_when_all_conditions_met(self):
        """条件全满足时必须正常放行，而不是抛 TypeError。"""
        self.reach_n2()
        (self.project / "Data" / "raw").mkdir(parents=True, exist_ok=True)
        (self.project / "Data" / "raw" / "d.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        self.state("checkpoint", "N2", "--phase", "Phase 1 清洗",
                   "--done", "生成清洗数据", "--artifact", "Data/raw/d.csv")
        # 不传 --skip-prereq：走完整守卫，含 check_own_gates 分支
        r = self.state("node-finish", "N2", "--agent", "dataprep",
                       "--skills", "mm-data-preprocessing", check=False)
        self.assertEqual(r.returncode, 0, f"满足全部条件时应放行，实际: {r.stderr[-600:]}")
        self.assertNotIn("not callable", r.stderr)
        self.assertEqual(self.decision()["nodes"]["N2"]["status"], "completed")

    def test_guard_reports_own_gate_failure_by_name(self):
        """本节点门禁未过时，守卫要报出门禁 id（证明 check_own_gates 分支真的执行了）。

        node-finish 不查本节点门禁（顺序是 finish → review → 门禁），
        故这里直接测守卫函数本身：BLOCKED 的 D1 必须被报出来。
        """
        import importlib.util
        import sys as _sys
        guard_path = ROOT / "shared" / "state-engine" / "state_guard.py"
        spec = importlib.util.spec_from_file_location("_guard_probe", guard_path)
        mod = importlib.util.module_from_spec(spec)
        _sys.path.insert(0, str(ROOT / "shared" / "state-engine"))
        try:
            spec.loader.exec_module(mod)
        finally:
            _sys.path.pop(0)
        errs = mod.check_own_gates("N2", {"gates": {"D1": {"status": "BLOCKED"}}})
        self.assertTrue(any("D1" in e for e in errs), f"应报出 D1 未通过，实际: {errs}")
        ok = mod.check_own_gates("N2", {"gates": {"D1": {"status": "PASS"}}})
        self.assertEqual(ok, [], "门禁 PASS 时不应报错")


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


class ScopePromoteGuardTest(Base):
    """scope-promote 是第 5 条写 completed 的路径，必须过统一完成守卫。

    回归用：修复前 scope 分片全绿即可把父节点置 completed，
    即使该节点从未 node-start、上游未完成、门禁全 pending。
    """

    REVIEW_PHASES = ("DISPATCH", "IMPLEMENT", "RUN", "REVIEW", "SCORE", "DECIDE")

    def _force_all_scopes_green(self, node="N4", round_no=1):
        """把所有 scope 分片的必需阶段伪装成全 completed（模拟"分片都交了"）。"""
        self.state("scope-plan", node, "--round", str(round_no), "--mode", "adaptive")
        base = self.project / "state" / "reviews" / node
        manifests = list(base.rglob("review_workspace_manifest.json"))
        self.assertTrue(manifests, "scope-plan 应生成 review_workspace_manifest.json")
        for mp in manifests:
            data = json.loads(mp.read_text(encoding="utf-8"))
            data["phase_status"] = {p: "completed" for p in self.REVIEW_PHASES}
            data["status"] = "aggregated"
            mp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return manifests

    def test_scope_promote_cannot_bypass_completion_guard(self):
        """分片全绿但未 node-start → 拒绝标 completed。"""
        self._force_all_scopes_green()
        r = self.state("scope-promote", "N4", "--round", "1", check=False)
        self.assertNotEqual(r.returncode, 0, "未 node-start 时 scope-promote 不得推进父节点")
        self.assertIn("从未 node-start", r.stderr)
        self.assertEqual(self.decision()["nodes"]["N4"]["status"], "pending")

    def test_scope_promote_rejects_when_own_gates_not_passed(self):
        """已 node-start、上游齐备，但本节点门禁（P2/A1）未过 → 仍拒绝。

        node-start 本身会校验上游，所以"已开工但上游未完成"在正常路径不可达；
        真实可绕过的场景是：一路推进到本节点、分片全绿，但审阅门禁还没过。
        这里直接构造该状态：N4 已开工 + 分片全绿，P2/A1 保持 pending。
        """
        self.state("node-finish", "N0")
        self.lock_problem()
        # 直接把 N1-N3 标 completed 并放行其门禁（本用例只验证 N4 自身的门禁作用）
        doc = self.decision()
        for n, gate in (("N1", "M1"), ("N2", "D1"), ("N3", "P1")):
            doc["nodes"][n]["status"] = "completed"
            doc["gates"][gate]["status"] = "PASS"
        (self.project / "state" / "decision_log.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.state("node-start", "N4")
        self._force_all_scopes_green()
        gates = self.decision()["gates"]
        self.assertNotIn(gates.get("P2", {}).get("status"), ("PASS", "auto_passed", "confirmed"),
                         "前提：P2 门禁此时应为未通过")
        r = self.state("scope-promote", "N4", "--round", "1", check=False)
        self.assertNotEqual(r.returncode, 0, "本节点门禁未过时 scope-promote 不得推进父节点")
        self.assertIn("门禁", r.stderr)
        self.assertNotEqual(self.decision()["nodes"]["N4"]["status"], "completed",
                            "门禁未过时不得把 N4 标为 completed")


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

    def _lock_raw(self):
        """P1-17：raw.files 非空时必须有处理前锁定基线，否则 D1 应 FAIL。
        用仓库脚本建立基线，保证测试走的是真实入口而不是手搓 json。"""
        r = run(RAW_LOCK, "--root", self.project, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.project / "Data" / "raw_lock.json").exists())

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

    def _validate(self, ledger=None, lock_raw=True):
        self._fixture()
        if lock_raw:
            self._lock_raw()
        data = ledger if ledger is not None else self._ledger()
        path = self.project / "Data" / "data-lineage.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        # P1-14：CI 路径显式要求结构校验，缺 jsonschema 时不得静默降级为 WARN
        return run(LINEAGE, path, "--root", self.project, "--json",
                   "--require-schema", check=False)

    def test_valid_lineage_passes(self):
        r = self._validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_raw_lock_fails(self):
        """P1-17：raw.files 非空却没有 Data/raw_lock.json → 校验器必须 FAIL。

        否则"原始数据只读"只在建立了 lock 之后才成立，D1 可完全绕过 lock 而通过。
        """
        r = self._validate(lock_raw=False)
        self.assertNotEqual(r.returncode, 0, "缺少 raw 锁定基线时应 FAIL")
        self.assertIn("raw_lock", r.stdout)
        self.assertIn("python scripts/raw_lock.py --root", r.stdout)
        self.assertEqual(json.loads(r.stdout)["status"], "FAIL")

    def test_raw_tamper_detected(self):
        self._fixture()
        ledger = self._ledger()
        self._lock_raw()
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

    def test_schema_rejects_empty_stage_inputs(self):
        """P1-14：结构契约必须真正生效——stages[0].inputs 置空必须 FAIL（schema minItems）。"""
        self._fixture()
        ledger = self._ledger()
        ledger["stages"][0]["inputs"] = []
        r = self._validate(ledger)
        self.assertNotEqual(r.returncode, 0, "空 inputs 应被结构契约拒绝")
        self.assertIn("结构契约不符", r.stdout)

    def test_require_schema_turns_missing_jsonschema_into_fail(self):
        """P1-14：jsonschema 不可用时，默认 WARN、--require-schema 时 FAIL。"""
        self._fixture()
        self._lock_raw()
        path = self.project / "Data" / "data-lineage.json"
        path.write_text(json.dumps(self._ledger(), ensure_ascii=False), encoding="utf-8")
        # 用 PYTHONPATH 上的同名模块遮蔽真实 jsonschema，模拟"缺库"环境
        blocker = self.tmp / "no_jsonschema"
        blocker.mkdir(parents=True, exist_ok=True)
        (blocker / "jsonschema.py").write_text(
            'raise ImportError("jsonschema blocked by test")\n', encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(blocker)

        warn = run(LINEAGE, path, "--root", self.project, "--json",
                   check=False, env=env)
        self.assertEqual(warn.returncode, 0, "缺库且未要求时必须放行（WARN）")
        warn_report = json.loads(warn.stdout)
        self.assertEqual(warn_report["status"], "PASS")
        self.assertTrue(any("schema.enforced" in w for w in warn_report["warnings"]))

        strict = run(LINEAGE, path, "--root", self.project, "--json",
                     "--require-schema", check=False, env=env)
        self.assertNotEqual(strict.returncode, 0, "--require-schema 时缺库必须 FAIL")
        strict_report = json.loads(strict.stdout)
        self.assertEqual(strict_report["status"], "FAIL")
        self.assertTrue(any("jsonschema" in e for e in strict_report["errors"]))

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


N8_REVIEW_SKILLS = ("academic-orchestrator:mm-iteration-engine,"
                    "academic-orchestrator:mm-latex-writing,"
                    "academic-orchestrator:mm-self-review")
N6_B1_SKILLS = ("academic-orchestrator:figure-table-benchmark,"
                "academic-orchestrator:mm-iteration-engine")


class CorrectionClosureTest(Base):
    """纠正留痕闭环（CORRECTION_UNACKED）：A3/B1 门禁不再是纸面承诺。

    覆盖矩阵：
      - 无纠正 → A3 通过（不误报）
      - 有纠正无回执 → A3 拒绝
      - 有纠正有回执（本人） → A3 通过
      - 他人代签回执 → 拒绝写入且不闭环
      - 跨节点隔离 → B1 只认本节点回执，A3 认全项目
      - 留痕被改写 → CORRECTION_LEDGER_TAMPERED
      - result-ingest N8 → 同一判据，不能绕过
    """

    def _evidence(self, rel="state/reports/evidence.md"):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 证据占位\n", encoding="utf-8")
        return rel

    def _a3_review(self, result="PASS", check=True):
        return self.state("node-review", "N8", "--agent", "reviewer", "--result", result,
                          "--skills", N8_REVIEW_SKILLS, "--summary", "终审",
                          "--evidence", self._evidence(), check=check)

    def _correction(self, node="N8", agent="reviewer", ctype="门禁风险", check=True):
        r = self.state("correction-add", node, "--agent", agent, "--type", ctype,
                       "--finding", "state/reports/x.md 缺检索留痕",
                       "--requirement", "补检索并重跑", "--delivery", "steered",
                       check=check)
        if not check:
            return r
        return json.loads(r.stdout)["correction_id"]

    def test_no_correction_passes(self):
        """没有纠正记录 → A3 正常 PASS（不产生误报）。"""
        r = self._a3_review()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("门禁 A3", r.stdout)

    def test_correction_without_ack_blocks_a3(self):
        """有纠正无回执 → A3 拒绝，错误码 CORRECTION_UNACKED。"""
        cid = self._correction()
        r = self._a3_review(check=False)
        self.assertNotEqual(r.returncode, 0, "未回执的纠正必须拦住 A3")
        self.assertIn("CORRECTION_UNACKED", r.stderr)
        self.assertIn(cid, r.stderr)
        self.assertIn("correction-ack", r.stderr)
        # 门禁不得被写成 PASS
        state = self.decision()
        self.assertNotEqual((state["gates"].get("A3") or {}).get("status"), "PASS")

    def test_correction_with_ack_passes(self):
        """本人回执后 → A3 PASS。"""
        cid = self._correction()
        ack = self.state("correction-ack", cid, "--agent", "reviewer", "--note", "已补检索")
        self.assertEqual(ack.returncode, 0, ack.stderr)
        r = self._a3_review()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("纠正留痕闭环通过", r.stdout)
        self.assertEqual(self.decision()["gates"]["A3"]["status"], "PASS")

    def test_forged_ack_by_other_agent_rejected(self):
        """主 Agent（或任何非被纠正者）代签回执 → 命令拒绝，A3 仍被拦。"""
        cid = self._correction(agent="reviewer")
        forged = self.state("correction-ack", cid, "--agent", "main-agent", check=False)
        self.assertNotEqual(forged.returncode, 0, "非本人回执必须被拒")
        self.assertIn("回执必须由被纠正的 Agent 本人提交", forged.stderr)
        r = self._a3_review(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CORRECTION_UNACKED", r.stderr)

    def test_ack_of_unknown_correction_rejected(self):
        """凭空捏造 correction_id 的回执被拒（不能靠伪造回执刷闭环）。"""
        r = self.state("correction-ack", "corr_deadbeefdeadbeef", "--agent", "reviewer", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("纠正不存在", r.stderr)

    def test_a3_covers_all_nodes_but_b1_is_node_scoped(self):
        """A3 查全项目；B1 只查本节点（别的节点的回执不能顶替本节点）。"""
        # N7 的纠正（writing）
        cid_n7 = self._correction(node="N7", agent="writing")
        # 造一份合法的 N6 对标矩阵，让 B1 只卡在纠正闭环这一步
        bdir = self.project / "state" / "reports" / "figure-table-benchmark"
        bdir.mkdir(parents=True, exist_ok=True)
        matrix = {
            "schema_version": "figure-table-benchmark/1.0", "project_id": "t",
            "node": "N6", "round": 1,
            "entries": [{
                "artifact_id": "fig1", "artifact_kind": "figure", "supported_claim": "趋势",
                "our_spec": {}, "gaps": [], "verdict": "COMPLETE",
                "benchmarked": [{"paper_id": f"p{i}", "year": 2020 + i, "locator": "p.3",
                                 "channel": "paper-mcp", "query": "q"} for i in range(3)],
                "dimensions": {k: {"state": "PASS", "evidence": "e"} for k in (
                    "data_columns", "statistics", "units", "comparability",
                    "grouping", "chart_fit", "academic_form")},
            }],
        }
        (bdir / "m.json").write_text(json.dumps(matrix, ensure_ascii=False), encoding="utf-8")
        # N6 无纠正 → B1 通过（N7 的未回执纠正不影响 N6 的 B1）
        ok = self.state("node-review", "N6", "--agent", "mm-figure-table-benchmarker",
                        "--result", "PASS", "--skills", N6_B1_SKILLS, "--summary", "对标通过",
                        "--evidence", "state/reports/figure-table-benchmark/m.json",
                        "--allow-missing-mcp", check=False)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        # N6 自己加一条纠正 → B1 立即被拦（node 作用域生效）
        self._correction(node="N6", agent="visualization")
        blocked = self.state("node-review", "N6", "--agent", "mm-figure-table-benchmarker",
                             "--result", "PASS", "--skills", N6_B1_SKILLS, "--summary", "对标通过",
                             "--evidence", "state/reports/figure-table-benchmark/m.json",
                             "--allow-missing-mcp", check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("节点 N6", blocked.stderr)
        self.assertIn("CORRECTION_UNACKED", blocked.stderr)
        # A3 仍能看到 N7 那条未回执的纠正
        a3 = self._a3_review(check=False)
        self.assertNotEqual(a3.returncode, 0)
        self.assertIn(cid_n7, a3.stderr)

    def test_one_ack_does_not_cover_multiple_corrections(self):
        """多条纠正必须逐条回执：只回一条不能闭环。"""
        first = self._correction(ctype="门禁风险")
        self._correction(ctype="范围纠正")
        self.state("correction-ack", first, "--agent", "reviewer")
        r = self._a3_review(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("有 1 条纠正未收到", r.stderr)

    def test_tampered_ledger_blocks_a3(self):
        """改写 corrections.jsonl → 哈希链断裂，判 CORRECTION_LEDGER_TAMPERED。"""
        cid = self._correction()
        self.state("correction-ack", cid, "--agent", "reviewer")
        ledger = self.project / "state" / "reports" / "corrections.jsonl"
        records = [json.loads(line) for line in
                   ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        records[0]["finding"] = "被事后改写的发现"
        ledger.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                          encoding="utf-8")
        r = self._a3_review(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CORRECTION_LEDGER_TAMPERED", r.stderr)

    def test_correction_requires_finding_and_requirement(self):
        """纠正记录必须给发现与要求（空壳纠正无审计价值）。"""
        r = self.state("correction-add", "N8", "--agent", "reviewer", "--type", "门禁风险",
                       "--finding", "只有发现没有要求", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--requirement", r.stderr)

    def test_result_ingest_n8_blocked_by_unacked_correction(self):
        """result-ingest（N8 completed）是 A3 的第二条写入路径，必须同样被拦。"""
        self._correction(node="N7", agent="writing")
        (self.project / "SubmissionPackage").mkdir(parents=True, exist_ok=True)
        artifact = self.project / "SubmissionPackage" / "checklist.md"
        artifact.write_text("# checklist\n", encoding="utf-8")
        import hashlib as _hashlib
        result = {
            "schema_version": "1.0", "agent_id": "reviewer", "node_id": "N8", "run_id": "N8-x",
            "status": "completed",
            "artifacts": [{"path": "SubmissionPackage/checklist.md",
                           "sha256": _hashlib.sha256(artifact.read_bytes()).hexdigest()}],
            "checks": [], "feedback": [],
            "timestamps": {"started_at": "2026-01-01T00:00:00Z",
                           "finished_at": "2026-01-01T01:00:00Z"},
            "payload": {},
        }
        result_path = self.project / "state" / "agents" / "reviewer" / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result), encoding="utf-8")
        # 即使 --skip-prereq（跳过上游守卫），A3 的纠正闭环判据也不放宽
        r = self.state("result-ingest", str(result_path), "--node", "N8", "--skip-prereq",
                       check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CORRECTION_UNACKED", r.stderr)


class DispatchLifecycleTest(Base):
    """派发句柄 dispatch.json：创建/续期/收尾/僵尸判定。"""

    def _summary(self):
        return json.loads(self.state("dispatch-list").stdout)

    def test_start_and_close(self):
        r = self.state("dispatch-start", "agent_abc123", "--node", "N4", "--round", "1",
                       "--must-load", "mm-iteration-engine,mm-algorithm-dev",
                       "--task", "实现 Q1")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads(r.stdout)
        self.assertEqual(rec["status"], "running")
        self.assertEqual(rec["must_load"], ["mm-iteration-engine", "mm-algorithm-dev"])
        self.assertTrue((self.project / "state" / "agents" / "agent_abc123"
                         / "dispatch.json").is_file())
        summary = self._summary()
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["by_status"], {"running": 1})
        closed = self.state("dispatch-close", "agent_abc123", "--status", "done",
                            "--artifact", "state/decision_log.json")
        self.assertEqual(closed.returncode, 0, closed.stderr)
        out = json.loads(closed.stdout)
        self.assertEqual(out["status"], "done")
        self.assertEqual(out["artifacts"][0]["state"], "present")
        self.assertEqual(self._summary()["by_status"], {"done": 1})

    def test_zombie_detected_when_idle_beyond_ttl(self):
        """超 ttl 无活动 → 僵尸；checkpoint 续期后不再算僵尸（正常工作不被误判）。"""
        self.state("dispatch-start", "agent_z1", "--node", "N4", "--ttl", "1")
        self.assertEqual(self._summary()["running"][0]["ttl_s"], 1)
        dispatch = self.project / "state" / "agents" / "agent_z1" / "dispatch.json"
        record = json.loads(dispatch.read_text(encoding="utf-8"))
        record["last_activity_at"] = "2020-01-01T00:00:00Z"   # 硬构造：远超 ttl
        dispatch.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        zombies = self._summary()["zombies"]
        self.assertEqual(len(zombies), 1)
        self.assertEqual(zombies[0]["agentId"], "agent_z1")
        self.assertTrue(zombies[0]["zombie"])
        # checkpoint 由该 agent_id 提交 → 续期，僵尸消失
        self.state("checkpoint", "N4", "--phase", "Phase 1", "--done", "x", "--by", "agent_z1")
        self.assertEqual(self._summary()["zombies"], [])

    def test_duplicate_running_dispatch_rejected(self):
        """同一 agentId 仍有有效 running 句柄时拒绝重复派发（防重复投递）。"""
        self.state("dispatch-start", "agent_dup", "--node", "N4", "--ttl", "3600")
        r = self.state("dispatch-start", "agent_dup", "--node", "N4", "--ttl", "3600", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--force", r.stderr)

    def test_agent_id_traversal_rejected(self):
        """agentId 会拼进 state/agents/<id>/，必须拒绝路径穿越。"""
        r = self.state("dispatch-start", "../../evil", "--node", "N4", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("非法 agent_id", r.stderr)

    def test_dispatch_list_flags_unacked_corrections(self):
        """句柄上能看出还有几条纠正待回执（主 Agent 回收前一眼可查）。"""
        self.state("dispatch-start", "agent_c1", "--node", "N4")
        self.state("correction-add", "N4", "--agent", "agent_c1", "--type", "门禁风险",
                   "--finding", "f", "--requirement", "r")
        summary = self._summary()
        self.assertEqual(summary["running"][0]["corrections"], 1)
        self.assertEqual(summary["running"][0]["unacked_corrections"], 1)

    def test_write_conflict_between_parallel_agents_detected(self):
        """两个并行 Agent 声明同一写入目标 → 冲突（「同一业务文件只允许一个写入者」）。"""
        self.state("dispatch-start", "agent_w1", "--node", "N4",
                   "--writes", "Code/Q1/solve.py")
        self.state("dispatch-start", "agent_w2", "--node", "N6",
                   "--writes", "Code/Q1")
        conflicts = self._summary()["conflicts"]
        self.assertEqual(len(conflicts), 1, conflicts)
        self.assertEqual(sorted(conflicts[0]["agents"]), ["agent_w1", "agent_w2"])
        # 关闭其中一个 → 冲突消失（说明判定只看在途句柄）
        self.state("dispatch-close", "agent_w2", "--status", "done")
        self.assertEqual(self._summary()["conflicts"], [])

    def test_no_false_conflict_for_disjoint_writes(self):
        self.state("dispatch-start", "agent_d1", "--node", "N4", "--writes", "Code/Q1")
        self.state("dispatch-start", "agent_d2", "--node", "N6", "--writes", "ResultFigures")
        self.assertEqual(self._summary()["conflicts"], [])

    def test_checkpoint_list_exposes_dispatch_progress(self):
        """中断续跑时 checkpoint-list 同时给出在途 Agent 的最后活动（审计 B-5）。"""
        self.state("dispatch-start", "agent_p1", "--node", "N4")
        self.state("checkpoint", "N4", "--phase", "Phase 2 建模", "--done", "公式推导",
                   "--by", "agent_p1")
        out = json.loads(self.state("checkpoint-list", "N4", "--latest").stdout)
        self.assertIsNotNone(out["dispatch"])
        agent = out["dispatch"]["agents"][0]
        self.assertEqual(agent["agentId"], "agent_p1")
        self.assertEqual(agent["last_checkpoint"]["phase"], "Phase 2 建模")
        self.assertEqual(agent["last_activity_source"], "checkpoint")


class ResultCorrectionsAckTest(Base):
    """回执的机器可验证载体：result.json 的 corrections_ack（审计 B-2）。

    RespondToCoordinator 是宿主侧工具，插件无法强制；result.json 则是必须交付、
    且已被 result-ingest 机器校验（schema / 产物哈希 / agent_id）的载体。
    把回执挂到这里，闭环就不再依赖"子 Agent 自觉"。
    """

    def _write_result(self, acks=None, agent="writing", node="N7"):
        artifact = self.project / "ReportPaper" / "draft.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("# 初稿\n", encoding="utf-8")
        import hashlib as _hashlib
        result = {
            "schema_version": "1.0", "agent_id": agent, "node_id": node, "run_id": f"{node}-r1",
            "status": "review_pending",
            "artifacts": [{"path": "ReportPaper/draft.md",
                           "sha256": _hashlib.sha256(artifact.read_bytes()).hexdigest()}],
            "checks": [], "feedback": [],
            "timestamps": {"started_at": "2026-01-01T00:00:00Z",
                           "finished_at": "2026-01-01T01:00:00Z"},
            "payload": {},
        }
        if acks is not None:
            result["corrections_ack"] = acks
        path = self.project / "state" / "agents" / agent / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
        return path

    def _correction(self, node="N7", agent="writing"):
        r = self.state("correction-add", node, "--agent", agent, "--type", "前提失效",
                       "--finding", "上游图1 重画", "--requirement", "同步正文图号")
        return json.loads(r.stdout)["correction_id"]

    def test_result_ack_closes_the_loop(self):
        """result.json 声明 corrections_ack → 回执落盘，A3 通过（无需宿主回执）。"""
        cid = self._correction()
        result_path = self._write_result(acks=[{"correction_id": cid, "note": "已同步图号"}])
        r = self.state("result-ingest", str(result_path), "--node", "N7")
        self.assertEqual(r.returncode, 0, r.stderr)
        state = self.decision()
        self.assertEqual(state["nodes"]["N7"]["last_result"]["corrections_acked"], [cid])
        a3 = self.state("node-review", "N8", "--agent", "reviewer", "--result", "PASS",
                        "--skills", N8_REVIEW_SKILLS, "--summary", "终审",
                        "--evidence", self._evidence_file())
        self.assertEqual(a3.returncode, 0, a3.stderr)
        self.assertIn("纠正留痕闭环通过", a3.stdout)

    def _evidence_file(self):
        path = self.project / "state" / "reports" / "evidence.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 证据占位\n", encoding="utf-8")
        return "state/reports/evidence.md"

    def test_result_ack_by_wrong_agent_rejected(self):
        """result.json 的 agent_id 不是被纠正者 → 整份结果被拒（不能代签）。"""
        cid = self._correction(node="N7", agent="writing")
        result_path = self._write_result(acks=[cid], agent="reviewer", node="N8")
        r = self.state("result-ingest", str(result_path), "--node", "N8", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("代签无效", r.stderr)

    def test_result_ack_unknown_correction_rejected(self):
        result_path = self._write_result(acks=["corr_0000000000000000"])
        r = self.state("result-ingest", str(result_path), "--node", "N7", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("不存在的纠正", r.stderr)

    def test_result_without_ack_leaves_loop_open(self):
        """result.json 不带 corrections_ack → 不回执，A3 仍被拦（可见"自觉回执"确实不可靠）。"""
        self._correction()
        result_path = self._write_result(acks=None)
        r = self.state("result-ingest", str(result_path), "--node", "N7")
        self.assertEqual(r.returncode, 0, r.stderr)  # ingest 本身允许（非 N8）
        a3 = self.state("node-review", "N8", "--agent", "reviewer", "--result", "PASS",
                        "--skills", N8_REVIEW_SKILLS, "--summary", "终审",
                        "--evidence", self._evidence_file(), check=False)
        self.assertNotEqual(a3.returncode, 0)
        self.assertIn("CORRECTION_UNACKED", a3.stderr)


class ReadSkillsCoverageTest(Base):
    """审计 B-1：文档要求"回收时校验 read_skills 覆盖 must_load"，此前无任何机器校验。"""

    def _write_manifest(self, node, must_load):
        path = self.project / "state" / "skill-routing" / f"{node}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"node": node, "must_load": must_load,
                                    "generated_at": "2026-01-01T00:00:00Z"},
                                   ensure_ascii=False), encoding="utf-8")

    def _write_result(self, read_skills, node="N7", agent="writing"):
        artifact = self.project / "ReportPaper" / "draft.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("# 初稿\n", encoding="utf-8")
        import hashlib as _hashlib
        result = {
            "schema_version": "1.0", "agent_id": agent, "node_id": node, "run_id": f"{node}-r1",
            "status": "review_pending",
            "artifacts": [{"path": "ReportPaper/draft.md",
                           "sha256": _hashlib.sha256(artifact.read_bytes()).hexdigest()}],
            "checks": [], "feedback": [],
            "timestamps": {"started_at": "2026-01-01T00:00:00Z",
                           "finished_at": "2026-01-01T01:00:00Z"},
            "payload": {},
        }
        if read_skills is not None:
            result["read_skills"] = read_skills
        path = self.project / "state" / "agents" / agent / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
        return path

    def test_full_coverage_reported_ok(self):
        self._write_manifest("N7", ["mm-latex-writing", "mm-self-review"])
        path = self._write_result(["academic-orchestrator:mm-latex-writing", "mm-self-review"])
        r = self.state("result-validate", str(path), "--node", "N7")
        coverage = json.loads(r.stdout)["skill_coverage"]
        self.assertTrue(coverage["ok"], coverage)
        self.assertEqual(coverage["missing"], [])
        self.assertIsNone(coverage["warning"])

    def test_missing_skill_flagged(self):
        """缺少 must_load 中的 skill → ok=False 且告警（不再静默当作通过）。"""
        self._write_manifest("N7", ["mm-latex-writing", "mm-self-review"])
        path = self._write_result(["mm-latex-writing"])
        r = self.state("result-validate", str(path), "--node", "N7")
        coverage = json.loads(r.stdout)["skill_coverage"]
        self.assertFalse(coverage["ok"])
        self.assertIn("mm-self-review", coverage["missing"])
        self.assertIn("未覆盖", r.stderr)
        # 命名空间前缀等价：带前缀写法不应误判为缺失
        path2 = self._write_result(["academic-orchestrator:mm-latex-writing",
                                    "academic-orchestrator:mm-self-review"])
        ok = json.loads(self.state("result-validate", str(path2), "--node", "N7").stdout)
        self.assertTrue(ok["skill_coverage"]["ok"])

    def test_undeclared_read_skills_flagged(self):
        """完全未声明 read_skills → 不能视为通过（告警暴露，不静默）。"""
        self._write_manifest("N7", ["mm-latex-writing"])
        path = self._write_result(None)
        r = self.state("result-validate", str(path), "--node", "N7")
        coverage = json.loads(r.stdout)["skill_coverage"]
        self.assertFalse(coverage["ok"])
        self.assertIn("未声明 read_skills", coverage["warning"])

    def test_no_manifest_no_noise(self):
        """无派发清单（未启用 skill 路由）→ 不产生噪音。"""
        path = self._write_result(["anything"])
        r = self.state("result-validate", str(path), "--node", "N7")
        coverage = json.loads(r.stdout)["skill_coverage"]
        self.assertEqual(coverage["manifest"], "empty")
        self.assertTrue(coverage["ok"])


class DispatchArtifactReconciliationTest(Base):
    """协议 E.2/E.3：回收时核对产物哈希与 dispatch.json 一致，并自动收尾句柄。"""

    def _write_result(self, tamper=False, agent="writing", node="N7"):
        artifact = self.project / "ReportPaper" / "draft.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("# 初稿\n", encoding="utf-8")
        import hashlib as _hashlib
        declared = _hashlib.sha256(artifact.read_bytes()).hexdigest()
        if tamper:
            artifact.write_text("# 被替换的内容\n", encoding="utf-8")
        result = {
            "schema_version": "1.0", "agent_id": agent, "node_id": node, "run_id": f"{node}-r1",
            "status": "review_pending",
            "artifacts": [{"path": "ReportPaper/draft.md", "sha256": declared}],
            "checks": [], "feedback": [],
            "timestamps": {"started_at": "2026-01-01T00:00:00Z",
                           "finished_at": "2026-01-01T01:00:00Z"},
            "payload": {},
        }
        path = self.project / "state" / "agents" / agent / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
        return path

    def test_result_ingest_closes_dispatch_handle(self):
        """result-ingest 即回收：running 句柄自动收尾为 done（不会永久停在 running）。"""
        self.state("dispatch-start", "writing", "--node", "N7", "--task", "写 3.1 节")
        self.assertEqual(json.loads(self.state("dispatch-list").stdout)["by_status"], {"running": 1})
        path = self._write_result()
        r = self.state("result-ingest", str(path), "--node", "N7")
        self.assertEqual(r.returncode, 0, r.stderr)
        summary = json.loads(self.state("dispatch-list").stdout)
        self.assertEqual(summary["by_status"], {"done": 1})
        self.assertEqual(summary["zombies"], [])

    def test_dispatch_recorded_artifact_tampered_is_rejected(self):
        """dispatch-close 记录产物后再改动文件 → result-ingest 拒绝（防伪完成）。

        注意这里 result.json 声明的是**改动后**的真实哈希（所以能过 result 自身的哈希校验），
        被抓住的是"与 dispatch 记录不符"这一步——这正是 E.2 要求的独立复核。
        """
        artifact_rel = "ReportPaper/draft.md"
        artifact = self.project / artifact_rel
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("# 初稿\n", encoding="utf-8")
        self.state("dispatch-start", "writing", "--node", "N7")
        self.state("dispatch-close", "writing", "--status", "done", "--artifact", artifact_rel)
        # 收尾后把产物换掉（模拟伪完成/空返回），result.json 跟着声明新哈希
        artifact.write_text("# 换掉的内容\n", encoding="utf-8")
        import hashlib as _hashlib
        result = {
            "schema_version": "1.0", "agent_id": "writing", "node_id": "N7", "run_id": "N7-r1",
            "status": "review_pending",
            "artifacts": [{"path": artifact_rel,
                           "sha256": _hashlib.sha256(artifact.read_bytes()).hexdigest()}],
            "checks": [], "feedback": [],
            "timestamps": {"started_at": "2026-01-01T00:00:00Z",
                           "finished_at": "2026-01-01T01:00:00Z"},
            "payload": {},
        }
        path = self.project / "state" / "agents" / "writing" / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
        r = self.state("result-ingest", str(path), "--node", "N7", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("已被改动", r.stderr)

    def test_no_dispatch_handle_does_not_block(self):
        """手工单节点执行（无 dispatch 句柄）不该被回收核对卡住。"""
        path = self._write_result()
        r = self.state("result-ingest", str(path), "--node", "N7")
        self.assertEqual(r.returncode, 0, r.stderr)


class CorrectionAuditSummaryTest(Base):
    """project-audit 必须汇总纠正留痕与派发僵尸（供 N8 终检消费）。"""

    def test_audit_reports_unacked_and_zombie(self):
        self.state("dispatch-start", "agent_z9", "--node", "N4", "--ttl", "1")
        dispatch = self.project / "state" / "agents" / "agent_z9" / "dispatch.json"
        record = json.loads(dispatch.read_text(encoding="utf-8"))
        record["last_activity_at"] = "2020-01-01T00:00:00Z"
        dispatch.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        self.state("correction-add", "N7", "--agent", "writing", "--type", "需求变更",
                   "--finding", "f", "--requirement", "r")
        report = json.loads(self.state("project-audit").stdout)
        self.assertEqual(report["corrections"]["total"], 1)
        self.assertEqual(report["corrections"]["unacked"], 1)
        self.assertEqual(report["corrections"]["unacked_details"][0]["agent_id"], "writing")
        self.assertEqual(len(report["dispatch"]["zombies"]), 1)
        self.assertFalse(report["summary"]["healthy"])
        joined = " ".join(report["summary"]["issues"])
        self.assertIn("CORRECTION_UNACKED", joined)
        self.assertIn("派发句柄僵尸", joined)

    def test_audit_clean_without_corrections_or_dispatch(self):
        """无纠正、无派发句柄 → 两项不产生噪音（不误报）。"""
        report = json.loads(self.state("project-audit").stdout)
        self.assertEqual(report["corrections"]["total"], 0)
        self.assertEqual(report["corrections"]["unacked"], 0)
        self.assertEqual(report["dispatch"]["total"], 0)
        self.assertEqual(report["dispatch"]["zombies"], [])
        self.assertNotIn("CORRECTION_UNACKED", " ".join(report["summary"]["issues"]))
        self.assertNotIn("派发句柄僵尸", " ".join(report["summary"]["issues"]))


if __name__ == "__main__":
    unittest.main()


class CodeScaffoldNoShellTest(Base):
    """脚手架不得预建空壳 .py（回归用）。

    回归背景：原 init 无条件给 4 个问题各建 pX_solver/pX_analysis/pX_param
    三个空壳（共 12 个）+ 4 个 vis_p*.py + 5 个 utils 空模板。后果：
      ① 目录结构被固定文件名锁死，无法按工程职责拆分；
      ② 空壳诱导把所有逻辑塞进那个"已存在"的 solver 文件 → 单文件膨胀到上千行；
      ③ 没做的题留下永久噪音。
    现在只建目录，文件由 coder 按 mm-algorithm-dev 的职责槽位 + 300 行阈值决定。
    """

    def test_init_does_not_create_shell_modules(self):
        """Base.setUp 已完成 init，此处直接检查其产物。"""
        code = self.project / "Code"
        shells = ("p1_solver.py", "p1_analysis.py", "p1_param.py",
                  "p2_solver.py", "p3_solver.py", "p4_solver.py",
                  "vis_p1.py", "vis_p2.py", "vis_p3.py", "vis_p4.py",
                  "data_io.py", "preprocess.py", "metrics.py", "logger.py",
                  "model_utils.py", "plot_base.py")
        found = [name for name in shells if list(code.rglob(name))]
        self.assertEqual(found, [], f"init 不应预建空壳模块，实际生成: {found}")

    def test_init_keeps_directories_and_entrypoints(self):
        """去空壳不等于去结构：目录与真正的入口文件必须还在。"""
        code = self.project / "Code"
        for rel in ("main.py", "config.py", "requirements.txt", "README-Code.md",
                    "utils/__init__.py"):
            self.assertTrue((code / rel).exists(), f"应保留 {rel}")
        for n in (1, 2, 3, 4):
            self.assertTrue((code / f"problem_{n}").is_dir(), f"应保留 problem_{n}/ 目录")

    def test_structure_audit_flags_long_files_and_shells(self):
        """审计脚本对超长文件/空壳/版本副本必须真的报错（非空壳检查）。"""
        code = self.project / "Code"
        (code / "problem_1" / "big.py").write_text(
            "def f():\n" + "    x = 1\n" * 340 + "    return x\n", encoding="utf-8")
        (code / "problem_1" / "shell.py").write_text(
            '"""占位"""\n\ndef solve():\n    raise NotImplementedError("todo")\n', encoding="utf-8")
        (code / "problem_1" / "solver_v2.py").write_text(
            "def solve():\n    return 1\n", encoding="utf-8")
        audit = ROOT / "scripts" / "code_structure_audit.py"
        r = run(audit, "--root", self.project, "--strict", check=False)
        self.assertNotEqual(r.returncode, 0, "有结构缺陷时 --strict 应退出码非 0")
        for keyword in ("300", "空壳", "版本后缀"):
            self.assertIn(keyword, r.stdout, f"应报出 {keyword} 相关问题，实际: {r.stdout[:400]}")

    def test_audit_does_not_flag_defensive_raise_as_shell(self):
        """含 raise ValueError 的防御性代码是真实实现，不得判空壳。

        回归用：_is_shell 曾把所有 `raise` 都当占位标志，
        于是"带参数校验的小模块"被误报为空壳，作者被迫删掉校验才能过审。
        """
        code = self.project / "Code"
        (code / "problem_1" / "guard.py").write_text(
            "def check(x):\n"
            "    if x < 0:\n"
            '        raise ValueError("x must be >= 0")\n'
            "    return x\n", encoding="utf-8")
        audit = ROOT / "scripts" / "code_structure_audit.py"
        r = run(audit, "--root", self.project, "--json", check=False)
        report = json.loads(r.stdout)
        shells = [f["path"] for f in report["fails"] if f["kind"] == "empty_shell"]
        self.assertNotIn("problem_1/guard.py", shells,
                         f"raise ValueError 不应被判空壳，实际失败项: {shells}")

    def test_audit_excludes_docstring_from_line_count(self):
        """docstring 不计入 300/50 行阈值，否则"文档写得详细"反被判超长。"""
        code = self.project / "Code"
        doc_heavy = ('"""\n' + "文档行\n" * 100 + '"""\n'
                     "def documented():\n"
                     '    """\n' + "    函数说明\n" * 50 + '    """\n'
                     "    return 1\n")
        (code / "problem_1" / "documented.py").write_text(doc_heavy, encoding="utf-8")
        audit = ROOT / "scripts" / "code_structure_audit.py"
        r = run(audit, "--root", self.project, "--json", check=False)
        report = json.loads(r.stdout)
        long_files = [f["path"] for f in report["fails"] if f["kind"] == "file_too_long"]
        long_funcs = [f["path"] for f in report["fails"] if f["kind"] == "function_too_long"]
        self.assertNotIn("problem_1/documented.py", long_files,
                         "100 行 docstring 不应计入文件行数")
        self.assertNotIn("problem_1/documented.py", long_funcs,
                         "50 行 docstring 不应计入函数行数")


class LegacyMaterialMigrationTest(Base):
    """旧版 Material/similar_papers 自动迁移到 External/refs/papers。

    回归背景：similar_papers 曾放同行论文，与 External/refs/ 职责重叠——
    同一件事两个入口，迟早放错地方。统一收进只读引用区后，
    老项目必须能自动搬迁，否则用户升级会丢材料。
    """

    def test_material_papers_dir_removed_from_scaffold(self):
        """新项目不再建 Material/similar_papers 与 Material/template。"""
        self.assertFalse((self.project / "Material" / "similar_papers").exists(),
                         "新项目不应再建 Material/similar_papers/")
        self.assertFalse((self.project / "Material" / "template").exists(),
                         "Material/template 零引用，不应再建")
        self.assertTrue((self.project / "External" / "refs" / "papers").is_dir(),
                        "应改为 External/refs/papers/")

    def test_upgrade_heal_moves_papers_with_structure(self):
        """旧目录内容（含子目录）应完整搬到新位置，旧目录清空。"""
        old = self.project / "Material" / "similar_papers"
        (old / "2023-A").mkdir(parents=True, exist_ok=True)
        (old / "paper1.md").write_text("# 论文1\n", encoding="utf-8")
        (old / "2023-A" / "paper2.md").write_text("# 论文2\n", encoding="utf-8")

        r = self.state("upgrade-heal", "--apply", check=False)
        self.assertEqual(r.returncode, 0, f"upgrade-heal 失败: {r.stderr}")

        new = self.project / "External" / "refs" / "papers"
        self.assertTrue((new / "paper1.md").is_file(), "顶层文件应迁移")
        self.assertTrue((new / "2023-A" / "paper2.md").is_file(), "子目录结构应保留")
        self.assertFalse(old.exists() and any(old.iterdir()), "旧目录应被清空")

    def test_migration_is_previewable(self):
        """不加 --apply 时只预览，不动文件。"""
        old = self.project / "Material" / "similar_papers"
        old.mkdir(parents=True, exist_ok=True)
        (old / "keep.md").write_text("# 保留\n", encoding="utf-8")
        r = self.state("upgrade-heal", check=False)
        self.assertIn("迁移旧目录", r.stdout)
        self.assertIn("预览模式", r.stdout)
        self.assertTrue((old / "keep.md").is_file(), "预览不应搬走文件")
