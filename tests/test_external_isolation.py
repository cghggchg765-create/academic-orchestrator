#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部资料隔离机制的正式回归测试。

覆盖三层隔离的每条判据：
  · 只读引用区：init 建区、add 锁定、check 检出增删改
  · 派生登记：derive 记录来源、登记后雷同降级为 INFO
  · 污染检测：位置污染（按文件名）、内容复制（n-gram）、登记失效
以及工程约束：工具随项目分发、项目内 `scripts/` 转发垫片可用。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "shared" / "state-engine" / "state_utils.py"
ISO = ROOT / "scripts" / "external_isolation.py"

# 足够长（> MIN_COMPARE_LINES=12 归一化行）的样本，用于内容复制检测
PEER_LONG = "\n".join([
    "import numpy as np",
    "",
    "def build_objective(costs, demands):",
    "    total = 0.0",
    "    for i in range(len(costs)):",
    "        for j in range(len(demands)):",
    "            total += costs[i][j] * demands[j]",
    "    penalty = 0.0",
    "    for i in range(len(costs)):",
    "        if costs[i][0] < 0:",
    "            penalty += abs(costs[i][0]) * 1000",
    "    weighted = total + penalty",
    "    normalized = weighted / max(len(costs), 1)",
    "    return normalized",
    "",
    "def solve(costs, demands):",
    "    obj = build_objective(costs, demands)",
    "    return {'objective': obj, 'iterations': 100}",
])


def run(*args, cwd=None):
    return subprocess.run([sys.executable, *map(str, args)], text=True,
                          capture_output=True, cwd=cwd)


class IsolationFlowTest(unittest.TestCase):
    """在真实项目里跑完整流程（含项目内垫片）。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_iso_"))
        self.project = self.tmp / "P"
        r = run(STATE, "init", "--name", "T", "--dir", self.project)
        self.assertEqual(r.returncode, 0, f"init 失败: {r.stderr}")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def iso(self, *args, check=True):
        shim = self.project / "scripts" / "external_isolation.py"
        r = run(shim, *args, "--root", self.project)
        if check:
            self.assertEqual(r.returncode, 0, f"命令失败 {args}: {r.stderr}\n{r.stdout}")
        return r

    def peer_file(self, text=PEER_LONG, name="peer_solution.py") -> Path:
        p = self.tmp / name
        p.write_text(text, encoding="utf-8")
        return p

    # -------------------------------------------------- 工程约束

    def test_init_creates_isolation_area(self):
        """init 必须建只读区 + 说明 + 锁定基线，否则隔离机制在项目内不存在。"""
        refs = self.project / "External" / "refs"
        self.assertTrue(refs.is_dir(), "应创建 External/refs/")
        self.assertTrue((refs / "README.md").is_file(), "应写入规则说明")
        self.assertTrue((self.project / "External" / ".readonly").is_file(), "应有只读标记")
        lock = self.project / "External" / "refs.lock.json"
        self.assertTrue(lock.is_file(), "应建立锁定基线")
        self.assertEqual(json.loads(lock.read_text(encoding="utf-8"))["files"], {})

    def test_tools_are_available_inside_project(self):
        """工具必须随项目分发，且 scripts/ 转发垫片可直接使用。"""
        for name in ("external_isolation.py", "code_structure_audit.py",
                     "raw_lock.py", "validate_data_lineage.py"):
            self.assertTrue((self.project / "state" / "tools" / name).is_file(),
                            f"state/tools/{name} 缺失")
            self.assertTrue((self.project / "scripts" / name).is_file(),
                            f"scripts/{name} 转发垫片缺失")

    # -------------------------------------------------- 只读引用区

    def test_add_locks_external_file(self):
        peer = self.peer_file()
        self.iso("add", str(peer), "--note", "同行公开实现")
        self.assertTrue((self.project / "External" / "refs" / "peer_solution.py").is_file())
        lock = json.loads((self.project / "External" / "refs.lock.json").read_text(encoding="utf-8"))
        self.assertIn("External/refs/peer_solution.py", lock["files"])
        self.assertEqual(len(lock["files"]["External/refs/peer_solution.py"]["sha256"]), 64)

    def test_check_detects_modification(self):
        peer = self.peer_file()
        self.iso("add", str(peer))
        ref = self.project / "External" / "refs" / "peer_solution.py"
        ref.write_text(PEER_LONG + "\n# 手改\n", encoding="utf-8")
        r = self.iso("check", "--json", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["status"], "TAMPERED")

    def test_check_detects_deletion(self):
        peer = self.peer_file()
        self.iso("add", str(peer))
        (self.project / "External" / "refs" / "peer_solution.py").unlink()
        r = self.iso("check", "--json", check=False)
        self.assertEqual(json.loads(r.stdout)["status"], "TAMPERED")

    def test_check_detects_unregistered_addition(self):
        """绕过 add 直接往引用区丢文件，也必须检出。"""
        (self.project / "External" / "refs" / "smuggled.py").write_text("x = 1\n", encoding="utf-8")
        r = self.iso("check", "--json", check=False)
        self.assertEqual(json.loads(r.stdout)["status"], "TAMPERED")

    def test_check_passes_when_clean(self):
        peer = self.peer_file()
        self.iso("add", str(peer))
        r = self.iso("check", "--json")
        self.assertEqual(json.loads(r.stdout)["status"], "PASS")

    # -------------------------------------------------- 污染检测

    def test_scan_detects_content_copy_without_derivation(self):
        peer = self.peer_file()
        self.iso("add", str(peer))
        target = self.project / "Code" / "problem_1" / "model.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(PEER_LONG, encoding="utf-8")
        r = self.iso("scan", "--json", check=False)
        rep = json.loads(r.stdout)
        self.assertEqual(rep["status"], "CONTAMINATED")
        copies = [f for f in rep["findings"] if f["kind"] == "content_copy"]
        self.assertTrue(copies, f"应检出内容复制，实际: {rep['findings']}")
        self.assertEqual(copies[0]["severity"], "HIGH")

    def test_scan_downgrades_after_derivation(self):
        """derive 登记后，同样的雷同降级为 INFO（合规参考而非抄袭）。"""
        peer = self.peer_file()
        self.iso("add", str(peer))
        target = self.project / "Code" / "problem_1" / "model.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(PEER_LONG, encoding="utf-8")
        self.iso("derive", "--ref", "External/refs/peer_solution.py",
                 "--target", "Code/problem_1/model.py",
                 "--note", "参考目标函数构造并重写", "--node", "N4")
        r = self.iso("scan", "--json", check=False)
        rep = json.loads(r.stdout)
        highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
        self.assertEqual(highs, [], f"登记后不应再有 HIGH: {rep['findings']}")
        self.assertEqual(rep["status"], "CLEAN")

    def test_scan_detects_location_contamination_for_short_file(self):
        """位置污染按文件名判定，短文件（低于行数门槛）也要检出。"""
        peer = self.peer_file(text="x = 1\n", name="tiny_peer.py")
        self.iso("add", str(peer))
        (self.project / "Code" / "tiny_peer.py").write_text("x = 1\n", encoding="utf-8")
        r = self.iso("scan", "--json", check=False)
        rep = json.loads(r.stdout)
        kinds = {f["kind"] for f in rep["findings"]}
        self.assertIn("location_contamination", kinds, f"应检出位置污染，实际: {rep['findings']}")
        self.assertEqual(rep["status"], "CONTAMINATED")

    def test_scan_clean_on_fresh_project(self):
        r = self.iso("scan", "--json")
        self.assertEqual(json.loads(r.stdout)["status"], "CLEAN")

    def test_scan_flags_stale_derivation(self):
        """登记的目标被删除后应提示（避免登记表与实际脱节）。"""
        peer = self.peer_file()
        self.iso("add", str(peer))
        target = self.project / "Code" / "problem_1" / "model.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
        self.iso("derive", "--ref", "External/refs/peer_solution.py",
                 "--target", "Code/problem_1/model.py", "--note", "参考")
        target.unlink()
        r = self.iso("scan", "--json", check=False)
        rep = json.loads(r.stdout)
        self.assertIn("stale_derivation", {f["kind"] for f in rep["findings"]})

    def test_derive_rejects_non_external_ref(self):
        """只能登记引用区内的资料，防止把产物目录当外部来源。"""
        (self.project / "Code" / "x.py").write_text("x = 1\n", encoding="utf-8")
        r = self.iso("derive", "--ref", "Code/x.py",
                     "--target", "Code/y.py", "--note", "x", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("External/refs", r.stderr)

    def test_derive_exemption_is_per_ref(self):
        """登记的是 ref A，抄的是 ref B → 必须仍判 HIGH（登记一次≠对全部外部文件免疫）。"""
        peer_a = self.peer_file(name="peer_a.py")
        self.iso("add", str(peer_a))
        peer_b = self.peer_file(name="peer_b.py")
        peer_b.write_text("\n".join(f"other_line_{i} = {i} + 7  # different origin"
                                    for i in range(20)), encoding="utf-8")
        self.iso("add", str(peer_b))
        target = self.project / "Code" / "problem_1" / "model.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(f"other_line_{i} = {i} + 7  # different origin"
                                    for i in range(20)), encoding="utf-8")
        self.iso("derive", "--ref", "External/refs/peer_a.py",
                 "--target", "Code/problem_1/model.py", "--note", "登记的是 A")
        r = self.iso("scan", "--json", check=False)
        rep = json.loads(r.stdout)
        highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
        self.assertTrue(highs, f"抄未登记的 peer_b 必须判 HIGH: {rep['findings']}")

    def test_derived_target_survives_iteration(self):
        """登记后正常迭代（target 内容重写、路径不变）不阻断扫描——路径豁免保留。"""
        peer = self.peer_file()
        self.iso("add", str(peer))
        target = self.project / "Code" / "problem_1" / "model.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(PEER_LONG, encoding="utf-8")
        self.iso("derive", "--ref", "External/refs/peer_solution.py",
                 "--target", "Code/problem_1/model.py", "--note", "参考重写")
        # 合法迭代：改写 target（保留大段重合）
        target.write_text(PEER_LONG + "\n\ndef extra():\n    return 42\n", encoding="utf-8")
        r = self.iso("scan", "--json", check=False)
        rep = json.loads(r.stdout)
        self.assertNotIn("HIGH", [f["severity"] for f in rep["findings"]],
                         f"登记后迭代不得被判 HIGH: {rep['findings']}")

    def test_threshold_out_of_range_rejected(self):
        """--threshold <=0 会把 0% 重合也判 HIGH，>1 会静默关闭检测——都必须拒绝。"""
        for th in ("0", "-0.5", "1.1"):
            r = self.iso("scan", "--json", "--threshold", th, check=False)
            self.assertNotEqual(r.returncode, 0, f"threshold={th} 应被拒绝")
            self.assertIn("(0, 1]", r.stderr)

    def test_binary_figures_not_text_compared(self):
        """.tif/.gif 等二进制不参与文本比对（读成乱码既浪费也无意义）。"""
        bin_dir = self.tmp / "bins"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "peer_fig.tif").write_bytes(bytes(range(256)) * 3)
        self.iso("add", str(bin_dir / "peer_fig.tif"))
        figs = self.project / "ResultFigures"
        figs.mkdir(exist_ok=True)
        (figs / "our_fig.tif").write_bytes(bytes(range(255, -1, -1)) * 3)
        (figs / "our_anim.gif").write_bytes(b"GIF89a" + bytes(range(256)) * 3)
        r = self.iso("scan", "--json")
        rep = json.loads(r.stdout)
        touched = [f for f in rep["findings"] if f["path"].endswith((".tif", ".gif"))]
        self.assertEqual(touched, [], f"二进制不应产生内容比对发现: {rep['findings']}")


class FailClosedScopeTest(unittest.TestCase):
    """fail-closed 只应在 refs 里确有外部资料时触发。

    init 自带的 README.md / .gitkeep / 空 papers、templates 子目录不是外部资料；
    把它们当成"已引入外部资料"会让零资料的项目在检测器缺失时被误拒。
    """

    def test_refs_has_material_ignores_scaffold(self):
        sys.path.insert(0, str(ROOT / "shared" / "state-engine"))
        import state_isolation as si
        tmp = Path(tempfile.mkdtemp(prefix="mm_fc_scope_"))
        try:
            refs = tmp / "External" / "refs"
            refs.mkdir(parents=True)
            self.assertFalse(si._refs_has_material(str(tmp)))
            (refs / "README.md").write_text("rules", encoding="utf-8")
            (refs / "papers").mkdir()
            (refs / "papers" / ".gitkeep").write_text("", encoding="utf-8")
            self.assertFalse(si._refs_has_material(str(tmp)),
                             "README/.gitkeep/空目录不算外部资料")
            (refs / "papers" / "peer.py").write_text("x = 1\n", encoding="utf-8")
            self.assertTrue(si._refs_has_material(str(tmp)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
