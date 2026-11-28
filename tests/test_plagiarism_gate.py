#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""防照搬门禁的回归测试。

用户场景：引入外部资料（External/refs/）学习参考后，子 Agent 可能直接照搬。
此前 scan 只是文档软性要求，没有任何门禁强制 —— 照搬产物可以顺利评分收工。

现在：
  · round-score 评分前强制跑污染检测，HIGH（未登记雷同）→ 拒绝评分
  · node-finish 收工时同样强制（非迭代节点路径）
  · derive 登记来源后放行（合规参考不是抄袭）
  · 检测不可用但有外部资料 → fail-closed 拒绝（宁拦勿漏）
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
GUARD = ROOT / "shared" / "state-engine" / "problem_guard.py"

PEER = "\n".join([
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
MAIN_SKILLS = "mm-iteration-engine,mm-algorithm-dev,code-review"


class PlagiarismGateTest(unittest.TestCase):
    """防照搬：评分/收工前检测，登记后放行，检测缺失时 fail-closed。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_plagiar_"))
        self.proj = self.tmp / "P"
        sr = self.tmp / "skills"
        sr.mkdir()
        for n in ("mm-iteration-engine", "mm-algorithm-dev", "code-review", "mm-self-review"):
            d = sr / n
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {n}\ndescription: {n} fx\n---\n", encoding="utf-8")
        self.env = dict(os.environ)
        self.env["MM_SKILL_ROOTS"] = str(sr)
        run = lambda *a: subprocess.run(  # noqa: E731
            [sys.executable, str(STATE), *a, "--dir", str(self.proj)],
            capture_output=True, text=True, env=self.env)
        run("init", "--name", "T")
        run("init", "--sync-runtime", "--name", "T")
        # 后续统一用**项目内**入口：隔离门禁的模块 here 必须指向项目内，
        # 才能验证生产语义（删 state/tools 副本 → fail-closed）；
        # 用仓库入口会让 state_isolation 解析到仓库脚本，测不到该分支。
        proj_state = self.proj / "state" / "state_utils.py"
        self.assertTrue(proj_state.is_file())
        run = lambda *a: subprocess.run(  # noqa: E731
            [sys.executable, str(proj_state), *a, "--dir", str(self.proj)],
            capture_output=True, text=True, env=self.env)
        problem = self.tmp / "problem.md"
        problem.write_text("# Problem\nobjectives\n", encoding="utf-8")
        subprocess.run([sys.executable, str(GUARD), "create",
                        "--project", str(self.proj), "--source", str(problem),
                        "--figure-mode", "none",
                        "--objectives", '["o"]', "--constraints", '["c"]',
                        "--preconditions", '["p"]', "--data-requirements", '["d"]',
                        "--evaluation-metrics", '["m"]'],
                       capture_output=True, text=True, env=self.env)
        # 引入外部资料并照搬
        peer = self.tmp / "peer.py"
        peer.write_text(PEER, encoding="utf-8")
        self.shim = self.proj / "scripts" / "external_isolation.py"
        subprocess.run([sys.executable, str(self.shim), "add", str(peer),
                        "--root", str(self.proj)], capture_output=True, text=True)
        code = self.proj / "Code" / "problem_1"
        code.mkdir(parents=True, exist_ok=True)
        (code / "model.py").write_text(PEER, encoding="utf-8")
        (self.proj / "Code" / "main.py").write_text("print(1)\n", encoding="utf-8")
        reports = self.proj / "state" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "mcp-calls.jsonl").write_text(
            json.dumps({"node": "N4", "round": 1, "mcp": "context7, github",
                        "query": "q", "ts": "t", "result": "r", "card": "c"}) + "\n",
            encoding="utf-8")
        self.run_state = run
        run("node-start", "N4")
        run("round-start", "N4", "--skip-prereq")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_round_score_blocks_copied_product(self):
        """评分给照搬产物背书 → 拒绝，报出文件与重合率。"""
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8",
                           "--dims", '{"correctness":8,"efficiency":8,"readability":8,'
                                     '"robustness":8,"innovation":7}',
                           "--judge", "mm-code-reviewer", "--skills-read", MAIN_SKILLS,
                           "--evidence", "Code/main.py", "--allow-missing-mcp")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("防照搬", r.stderr, r.stderr[:300])
        self.assertIn("Code/problem_1/model.py", r.stderr)
        self.assertIn("derive", r.stderr, "拒绝信息必须给合规出路")

    def test_derive_registration_unblocks(self):
        """登记派生来源后放行（取长补短是合规的）。"""
        subprocess.run([sys.executable, str(self.shim), "derive",
                        "--ref", "External/refs/peer.py",
                        "--target", "Code/problem_1/model.py",
                        "--note", "参考目标函数构造并重写", "--root", str(self.proj)],
                       capture_output=True, text=True)
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8",
                           "--dims", '{"correctness":8,"efficiency":8,"readability":8,'
                                     '"robustness":8,"innovation":7}',
                           "--judge", "mm-code-reviewer", "--skills-read", MAIN_SKILLS,
                           "--evidence", "Code/main.py", "--allow-missing-mcp")
        self.assertEqual(r.returncode, 0, r.stderr[:400])

    def test_no_external_refs_no_check(self):
        """没引入外部资料时不检测（不引入无关负担）。"""
        # 删掉外部资料目录内容 → 门禁应直接放行
        refs = self.proj / "External" / "refs"
        for p in refs.iterdir():
            if p.name != "README.md":
                if p.is_file():
                    p.unlink()
                else:
                    shutil.rmtree(p)
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8",
                           "--dims", '{"correctness":8,"efficiency":8,"readability":8,'
                                     '"robustness":8,"innovation":7}',
                           "--judge", "mm-code-reviewer", "--skills-read", MAIN_SKILLS,
                           "--evidence", "Code/main.py", "--allow-missing-mcp")
        self.assertEqual(r.returncode, 0, r.stderr[:400])

    def test_fail_closed_when_detector_missing(self):
        """有外部资料但检测脚本缺失 → 拒绝（宁拦勿漏，项目自包含）。

        项目内运行只找项目内实现（state/tools/），不依赖插件仓库兜底——
        这是有意的：无法证明未照搬就不得交付，且项目必须能独立检测。
        删除 tools 副本后应明确报"检测不可用"，而不是放行或误报"污染"。
        """
        tools = self.proj / "state" / "tools" / "external_isolation.py"
        self.assertTrue(tools.is_file(), "前置：init 应分发检测脚本到 state/tools/")
        tools.unlink()
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8",
                           "--dims", '{"correctness":8,"efficiency":8,"readability":8,'
                                     '"robustness":8,"innovation":7}',
                           "--judge", "mm-code-reviewer", "--skills-read", MAIN_SKILLS,
                           "--evidence", "Code/main.py", "--allow-missing-mcp")
        self.assertNotEqual(r.returncode, 0, "检测缺失时不得放行（宁拦勿漏）")
        self.assertIn("污染检测不可用", r.stderr, r.stderr[:300])
        self.assertIn("sync-runtime", r.stderr, "必须给出补齐工具的命令")


class IsoPathResolutionTest(unittest.TestCase):
    """state_isolation 的脚本定位：仓库运行与项目内运行都能找到唯一实现。"""

    def test_repo_run_finds_script(self):
        sys.path.insert(0, str(ROOT / "shared" / "state-engine"))
        import state_isolation as si
        p = si._iso_script_path(str(ROOT))
        self.assertTrue(p, "仓库运行应能定位 scripts/external_isolation.py")
        self.assertTrue(Path(p).is_file())

    def test_project_run_finds_distributed_copy(self):
        tmp = Path(tempfile.mkdtemp(prefix="mm_iso_path_"))
        try:
            proj = tmp / "P"
            subprocess.run([sys.executable, str(STATE), "init", "--name", "T",
                            "--dir", str(proj)], capture_output=True, text=True)
            sys.path.insert(0, str(proj / "state"))
            try:
                import state_isolation as si
                p = si._iso_script_path(str(proj))
                self.assertTrue(p, "项目内运行应能定位 state/tools/external_isolation.py")
            finally:
                sys.path.pop(0)
                for k in [k for k in list(sys.modules) if k == "state_isolation"]:
                    del sys.modules[k]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
