"""模块独立调用契约（B1/B2 回归）：每个阶段模块可独立解析、独立调用。

- 状态引擎在共享层 `shared/state-engine/`，旧路径垫片必须解析到同一 NODES 定义；
- registry（shared/state-engine/registry.json）与 state_defs.NODES 双份一致；
- N1-N8 每个节点的 executor/reviewer/required_skills/门禁均可解析到实际文件；
- 曾耦合 mm-iteration-engine/scripts 私有路径的 5 个技能经上移后不再引用旧内部路径。
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "shared" / "state-engine"
REGISTRY_FILE = ENGINE_DIR / "registry.json"
SHIM_FILE = ROOT / "skills" / "mm-iteration-engine" / "scripts" / "state_utils.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"无法解析模块: {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RegistryResolvabilityTest(unittest.TestCase):
    """N1-N8 每个节点可独立解析：executor/reviewer/技能/门禁全部落到实际文件。"""

    def setUp(self):
        self.registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        self.engine = _load_module("mm_engine_standalone", ENGINE_DIR / "state_utils.py")
        self.agent_files = {p.stem for p in (ROOT / "agents").glob("*.md")}
        self.skill_dirs = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}

    def test_registry_covers_eight_nodes(self):
        node_ids = sorted(entry.get("id", "") for entry in self.registry.get("nodes", []))
        self.assertEqual(node_ids, ["N%d" % i for i in range(1, 9)])

    def test_each_node_resolves_executor_reviewer_skills_gates(self):
        for entry in self.registry.get("nodes", []):
            node_id = entry.get("id")
            with self.subTest(node=node_id):
                self.assertIn(entry.get("executor"), self.agent_files, f"{node_id} executor")
                self.assertIn(entry.get("reviewer"), self.agent_files, f"{node_id} reviewer")
                for skill in entry.get("required_skills", []):
                    short = skill.split(":", 1)[-1]  # 去掉 math-modeling-agent-system: 前缀
                    self.assertIn(short, self.skill_dirs, f"{node_id} required_skills 缺 {short}")
                self.assertTrue(entry.get("gates"), f"{node_id} 门禁为空")

    def test_nodedefs_match_registry(self):
        """共享 registry 与 state_defs.NODES 双份一致（executor/reviewer/skills/gates/artifact）。"""
        by_id = {entry.get("id"): entry for entry in self.registry.get("nodes", [])}
        for node_id, entry in by_id.items():
            info = self.engine.NODES.get(node_id)
            self.assertIsNotNone(info, f"registry 节点 {node_id} 在 NODES 中不存在")
            self.assertEqual(entry.get("executor"), info.get("executor"), f"{node_id} executor")
            self.assertEqual(entry.get("reviewer"), info.get("reviewer"), f"{node_id} reviewer")
            self.assertEqual(self.engine.normalized_skill_set(entry.get("required_skills", [])),
                             self.engine.normalized_skill_set(info.get("skills", [])), f"{node_id} skills")
            self.assertEqual(sorted(entry.get("gates", [])), sorted(info.get("gates", [])),
                             f"{node_id} gates")

    def test_state_engine_standalone(self):
        """状态引擎可在不含 mm-iteration-engine 技能的前提下独立加载（模块独立化核心）。"""
        self.assertEqual(sorted(self.engine.NODES.keys()),
                         ["N%d" % i for i in range(9)])
        self.assertTrue(hasattr(self.engine, "UPSTREAM"))
        self.assertTrue(hasattr(self.engine, "state_utils_help") or hasattr(self.engine, "main"))


class ShimCompatibilityTest(unittest.TestCase):
    """旧路径垫片必须解析到与共享层相同的状态引擎（CLI 与 import 双模式）。"""

    def test_shim_resolves_same_nodes(self):
        shim = _load_module("mm_shim_sh", SHIM_FILE)
        canonical = _load_module("mm_engine_sh", ENGINE_DIR / "state_utils.py")
        self.assertEqual(sorted(shim.NODES.keys()), sorted(canonical.NODES.keys()))
        self.assertEqual(shim.NODES.get("N7"), canonical.NODES.get("N7"))
        # 垫片对 NODES/UPSTREAM 常量的转发不引入额外前缀符号
        self.assertTrue(hasattr(shim, "UPSTREAM"))


class SkillSelfContainmentTest(unittest.TestCase):
    """曾硬耦合 mm-iteration-engine/scripts 私有路径的 5 个技能，语法上不再引用旧内部路径。"""

    FORMER_COUPLED_SKILLS = (
        "mathematical-modeling",
        "mm-algorithm-dev",
        "mm-problem-analysis",
        "sync-and-compatibility",
        "mm-iteration-engine",
    )

    def test_no_private_engine_dir_reference(self):
        for skill in self.FORMER_COUPLED_SKILLS:
            text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("mm-iteration-engine/scripts", text, f"{skill} 仍引用私有引擎目录")
            # 显式声明依赖：引用共享层或项目 state/ 产物均合法
            self.assertTrue(
                re.search(
                    r"shared/state-engine|state_utils\.py|"
                    r"state/(registry|agents|nodes|decision_log|problem_lock|cases|reports)",
                    text,
                ),
                f"{skill} 未声明状态引擎依赖（shared/state-engine 或项目 state/）",
            )


if __name__ == "__main__":
    unittest.main()