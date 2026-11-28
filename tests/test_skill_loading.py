#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能加载与审阅分工的回归测试。

覆盖用户实测遇到的两类问题：
  ① "Skill 未加载：会话工具集无 Skill 工具" —— 子 Agent 拿不到 Skill 时的正规解法
     必须是"内容可读"而非"必须调工具"：skill_context.py 能取正文/路径，
     门禁校验 skill 内容是否真能解析到磁盘（声明即通过的时代结束）。
  ② "5 维审阅只派一个 Agent" —— 维度分工：readability/innovation 由独立审阅者评，
     但不得越界评别人的维度，也不得接管整体分。
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
SKILL_CONTEXT = ROOT / "scripts" / "skill_context.py"

sys.path.insert(0, str(ROOT / "shared" / "state-engine"))


class SkillContextResolverTest(unittest.TestCase):
    """skill_context.py：让 skill 内容经由文件系统可达，不依赖 Skill 工具。"""

    def run_ctx(self, *args):
        return subprocess.run([sys.executable, str(SKILL_CONTEXT), *args],
                              capture_output=True, text=True)

    def test_resolves_installed_skill(self):
        """已安装的 skill 必须能解析到路径（用户报错里提到 mm-self-review）。"""
        r = self.run_ctx("--name", "mm-self-review", "--path-only")
        self.assertEqual(r.returncode, 0, f"应能解析: {r.stderr}")
        path = Path(r.stdout.strip())
        self.assertTrue(path.is_file(), f"解析到的路径应存在: {path}")
        self.assertEqual(path.name, "SKILL.md")

    def test_body_only_strips_frontmatter(self):
        """--body-only 用于注入 prompt：不能带 frontmatter，且要有实质正文。"""
        r = self.run_ctx("--name", "mm-self-review", "--body-only")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = r.stdout
        self.assertFalse(body.lstrip().startswith("---"), "正文不应以 frontmatter 开头")
        self.assertGreater(len(body), 500, "正文应包含实质规范内容")

    def test_multiple_names(self):
        """一次取多个 skill（派发时常用）。"""
        r = self.run_ctx("--name", "mm-self-review,code-review", "--path-only")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 2)

    def test_unknown_skill_exits_nonzero(self):
        """解析不到必须失败（否则门禁无法据此拦截）。"""
        r = self.run_ctx("--name", "definitely-not-a-skill-xyz", "--path-only")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("无法解析", r.stderr)

    def test_resolve_only_reports_shadowing(self):
        """同名多处命中时要报遮蔽，避免"改了不生效"。"""
        r = self.run_ctx("--name", "code-review", "--resolve-only")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SKILL.md", r.stdout)


class SkillGateContentTest(unittest.TestCase):
    """门禁从"声明的字符串"升级为"内容可达"（skill_is_resolvable）。"""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "shared" / "state-engine"))
        import state_defs
        self.d = state_defs

    def test_known_skill_resolvable(self):
        ok, path = self.d.skill_is_resolvable("academic-orchestrator:mm-self-review")
        self.assertTrue(ok, "已安装 skill 应可解析")
        self.assertTrue(path and path.endswith("SKILL.md"))

    def test_unknown_skill_not_resolvable(self):
        ok, path = self.d.skill_is_resolvable("no-such-skill-abc123")
        self.assertFalse(ok)
        self.assertIsNone(path)

    def test_split_reviewer_has_lighter_skill_requirement(self):
        """分工审阅者只读"判断"规范，不继承主审阅者的执行规范。"""
        main_req = self.d.reviewer_required_skills("N4", "mm-code-reviewer")
        split_req = self.d.reviewer_required_skills("N4", "reviewer")
        self.assertIn("academic-orchestrator:code-review", main_req)
        self.assertNotIn("academic-orchestrator:code-review", split_req,
                         "分工审阅者不应被要求读代码审阅规范")
        self.assertIn("academic-orchestrator:mm-self-review", split_req)

    def test_split_agent_is_legal_reviewer(self):
        """维度分工 agent 必须被认作该节点的合法审阅者。"""
        self.assertIn("reviewer", self.d.expected_reviewers("N4"))


class DimensionSplitTest(unittest.TestCase):
    """维度分工的端到端行为：越界拒绝、本维度记录、主审阅者仍可整体评分。"""

    MAIN_SKILLS = "mm-iteration-engine,mm-algorithm-dev,code-review"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_dimsplit_"))
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
        self.run_state("init", "--name", "T")
        self.run_state("init", "--sync-runtime", "--name", "T")
        problem = self.tmp / "problem.md"
        problem.write_text("# Problem\nobjectives\n", encoding="utf-8")
        subprocess.run([sys.executable, str(GUARD), "create",
                        "--project", str(self.proj), "--source", str(problem),
                        "--figure-mode", "none",
                        "--objectives", '["o"]', "--constraints", '["c"]',
                        "--preconditions", '["p"]', "--data-requirements", '["d"]',
                        "--evaluation-metrics", '["m"]'],
                       capture_output=True, text=True, env=self.env)
        (self.proj / "Code").mkdir(exist_ok=True)
        (self.proj / "Code" / "main.py").write_text("print(1)\n", encoding="utf-8")
        reports = self.proj / "state" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "mcp-calls.jsonl").write_text(
            json.dumps({"node": "N4", "round": 1, "mcp": "context7, github",
                        "query": "q", "ts": "t", "result": "r", "card": "c"}) + "\n",
            encoding="utf-8")
        self.run_state("node-start", "N4") if False else None
        # 直接构造"N4 已开工 + 上游齐备"的状态：本用例只验证维度分工，
        # 上游门禁链由 test_workflow_contracts 的分阶段用例覆盖。
        doc_path = self.proj / "state" / "decision_log.json"
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        for n in ("N1", "N2", "N3"):
            doc["nodes"][n]["status"] = "completed"
        for g in ("M1", "D1", "P1"):
            doc["gates"].setdefault(g, {})["status"] = "PASS"
        doc["nodes"]["N4"]["status"] = "in_progress"
        # node-start 的快照字段是收工校验用的；此处只需开工标记
        doc["nodes"]["N4"]["start_artifact_hash"] = {"Code/": "snapshot"}
        doc_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.run_state("round-start", "N4", "--skip-prereq")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_state(self, *args, check=True):
        r = subprocess.run([sys.executable, str(STATE), *args, "--dir", str(self.proj)],
                           capture_output=True, text=True, env=self.env)
        if check and r.returncode != 0:
            self.fail(f"命令失败 {args}: {r.stderr}")
        return r

    def test_main_reviewer_requires_total(self):
        """整体分必须由主审阅者给出，不能只交维度分。"""
        r = self.run_state("round-score", "N4", "--round", "1",
                           "--dims", '{"correctness":8}',
                           "--judge", "mm-code-reviewer", "--skills-read", self.MAIN_SKILLS,
                           "--evidence", "Code/main.py", "--allow-missing-mcp", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--total", r.stderr)

    def test_split_reviewer_cannot_score_out_of_scope(self):
        """分工审阅者不能评不属于自己的维度（防越界）。"""
        r = self.run_state("round-score", "N4", "--round", "1",
                           "--dims", '{"correctness":9}',
                           "--judge", "reviewer", "--skills-read", "mm-self-review",
                           "--evidence", "Code/main.py", "--allow-missing-mcp", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue("只负责维度" in r.stderr or "不能评" in r.stderr, r.stderr[:200])

    def test_split_reviewer_records_own_dimensions(self):
        """分工维度分数应落盘，供主审阅者汇总。"""
        r = self.run_state("round-score", "N4", "--round", "1",
                           "--dims", '{"readability":8,"innovation":7}',
                           "--judge", "reviewer", "--skills-read", "mm-self-review",
                           "--evidence", "Code/main.py", "--allow-missing-mcp")
        self.assertIn("recorded", r.stdout)
        doc = json.loads((self.proj / "state" / "decision_log.json").read_text(encoding="utf-8"))
        rnd = next(x for x in doc["rounds"] if x.get("node") == "N4")
        contrib = rnd.get("dimension_contributions") or {}
        self.assertIn("reviewer", contrib)
        self.assertEqual(contrib["reviewer"]["dimensions"]["readability"], 8)

    def test_split_reviewer_rejects_invalid_dims(self):
        """分工提交的 dims 必须是非空对象、键在分工内、值为 0-10 的数。"""
        for dims in ("{}", '["readability"]', '{"readability": "good"}', '{"readability": 99}'):
            r = self.run_state("round-score", "N4", "--round", "1", "--dims", dims,
                               "--judge", "reviewer", "--skills-read", "mm-self-review",
                               "--evidence", "Code/main.py", "--allow-missing-mcp", check=False)
            self.assertNotEqual(r.returncode, 0, f"dims={dims} 应被拒绝，实际被记录")

    def test_split_agent_cannot_write_node_gate(self):
        """分工审阅者不得通过 node-review 写主门禁（P2 归主审阅者落盘）。"""
        r = self.run_state("node-review", "N4", "--agent", "reviewer", "--result", "PASS",
                           "--skills", "mm-self-review", "--evidence", "Code/main.py",
                           check=False)
        self.assertNotEqual(r.returncode, 0, "分工审阅者做 node-review 应被拒绝")
        self.assertIn("维度分工审阅者", r.stderr)
        doc = json.loads((self.proj / "state" / "decision_log.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["gates"].get("P2") or {}).get("status"), "pending",
                         "P2 不得被分工审阅者写掉")

    def test_round_decide_warns_missing_split_dims(self):
        """主审阅者漏掉分工维度且无 contribution 时，round-decide 必须提示。"""
        self.run_state("round-score", "N4", "--round", "1", "--total", "7",
                       "--dims", '{"correctness":8,"efficiency":7,"robustness":7}',
                       "--judge", "mm-code-reviewer", "--skills-read", self.MAIN_SKILLS,
                       "--evidence", "Code/main.py", "--allow-missing-mcp")
        r = self.run_state("round-decide", "N4", "--round", "1", check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("维度分工", r.stderr, "应在 stderr 提示分工维度未评分")

    def test_main_reviewer_can_still_score_whole(self):
        """分工不阻塞主审阅者的整体评分路径。"""
        r = self.run_state("round-score", "N4", "--round", "1", "--total", "8",
                           "--dims",
                           '{"correctness":8,"efficiency":8,"readability":8,'
                           '"robustness":8,"innovation":7}',
                           "--judge", "mm-code-reviewer", "--skills-read", self.MAIN_SKILLS,
                           "--evidence", "Code/main.py", "--allow-missing-mcp")
        self.assertEqual(r.returncode, 0, r.stderr)


class CapabilityKeywordCoverageTest(unittest.TestCase):
    """能力词表必须覆盖英文表达，否则英文 description 的 skill 永远匹配不上。"""

    def setUp(self):
        self.tax = json.loads(
            (ROOT / "shared" / "skill-routing" / "capability_taxonomy.json")
            .read_text(encoding="utf-8"))

    def keywords(self, cid):
        for c in self.tax["capabilities"]:
            if c["id"] == cid:
                return [k.casefold() for k in c.get("keywords") or []]
        return []

    def test_writing_keywords_cover_english(self):
        """回归用：原词表几乎只有中文词，nature-writing 只得 2 分被 min_score 过滤。"""
        kws = self.keywords("paper.writing")
        for word in ("manuscript", "draft", "writing"):
            self.assertIn(word, kws, f"paper.writing 应含英文词 {word}")

    def test_style_and_search_keywords_cover_english(self):
        self.assertIn("polishing", self.keywords("paper.style"))
        self.assertIn("search", self.keywords("literature.search"))

    def test_nature_skill_scores_above_threshold(self):
        """nature-writing 必须能通过 min_score 阈值（用户装了它却从不被选中）。"""
        sys.path.insert(0, str(ROOT / "shared" / "skill-routing"))
        import skill_discovery as sd
        import skill_matcher as sm
        skills = sd.discover(str(ROOT))
        ids = {s["skill_id"]: s for s in skills}
        target = ids.get("nature-writing")
        if not target:
            self.skipTest("本机未安装 nature-writing")
        tax = sm.load_taxonomy()
        policy = sm._policy(tax)
        caps = {c["id"]: c for c in tax["capabilities"]}
        score = sm.score_skill(target, caps["paper.writing"]["keywords"], policy)
        self.assertGreaterEqual(score["score"], policy["min_score"],
                                f"nature-writing 得分 {score['score']} 低于阈值 "
                                f"{policy['min_score']}，会被过滤")


class PluginCacheVersionOrderTest(unittest.TestCase):
    """插件缓存多版本共存时必须解析语义版本最高的副本。

    纯字典序会把 1.10.0 排在 2.0.0 之前（'1' < '2'）：插件跨大版本升级后，
    旧缓存副本会把新版"遮蔽"——用户改新版 skill 永远不生效。
    """

    def test_newest_version_wins(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "skill_context_probe", ROOT / "scripts" / "skill_context.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tmp = Path(tempfile.mkdtemp(prefix="mm_cache_"))
        try:
            cache = tmp / "cache"
            for ver in ("1.10.0", "1.9.0", "2.0.0"):
                sk = cache / "mk" / "plug" / ver / "skills" / "some-skill"
                sk.mkdir(parents=True)
                (sk / "SKILL.md").write_text(
                    f"---\nname: some-skill\ndescription: v{ver}\n---\n\nbody\n",
                    encoding="utf-8")
            mod.PLUGIN_CACHE = cache
            cache_roots = mod._plugin_cache_roots()
            self.assertEqual(len(cache_roots), 1, f"同一插件多版本只应取最高版: {cache_roots}")
            self.assertEqual(cache_roots[0], cache / "mk" / "plug" / "2.0.0" / "skills",
                             f"应选语义版本最高的 2.0.0，实际: {cache_roots[0]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TaxonomyStalenessTest(unittest.TestCase):
    """项目内词表副本过期时必须告警（否则改了词表老项目不生效）。"""

    def test_stale_version_warns(self):
        tmp = Path(tempfile.mkdtemp(prefix="mm_tax_"))
        try:
            proj = tmp / "P"
            env = dict(os.environ)
            subprocess.run([sys.executable, str(STATE), "init", "--name", "T",
                            "--dir", str(proj)], capture_output=True, text=True, env=env)
            tax = proj / "state" / "skill-routing" / "capability_taxonomy.json"
            self.assertTrue(tax.is_file(), "init 应复制能力词表到项目内")
            data = json.loads(tax.read_text(encoding="utf-8"))
            data["version"] = "0.0.1"   # 模拟插件升级后老项目未刷新
            tax.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            # 确认写入生效（避免被其它步骤覆盖）
            self.assertEqual(
                json.loads(tax.read_text(encoding="utf-8"))["version"], "0.0.1",
                "测试前置：项目内词表应已降级")
            # 必须用**项目内**脚本跑：仓库脚本会读仓库词表（那是对的），
            # 只有项目内运行才会用到项目副本，过期检测才有意义。
            proj_state = proj / "state" / "state_utils.py"
            self.assertTrue(proj_state.is_file(), "init 应复制 state_utils.py 到项目内")
            r = subprocess.run([sys.executable, str(proj_state), "skill-plan", "N7",
                                "--dir", str(proj)],
                               capture_output=True, text=True, env=env)
            combined = r.stdout + r.stderr
            self.assertIn("落后于插件", combined,
                          f"应提示词表过期，实际 stderr: {r.stderr[:300]}")
            # 同时确认它确实用了旧版词表（否则告警与行为不一致）
            doc = json.loads(r.stdout)
            self.assertEqual(doc.get("taxonomy_version"), "0.0.1",
                             "告警与所用词表版本必须一致")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
