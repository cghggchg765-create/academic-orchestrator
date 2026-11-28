#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""state_utils.py — 状态统一节点命令行助手（schema 2.0）

数学建模迭代引擎的外部状态统一节点工具。所有写操作：UTF-8、原子替换、meta.seq 自增。
宿主: Codex CLI / ZCode CLI（纯标准库，无第三方依赖，Python 3.8+）。
初始化后本脚本会复制一份到项目的 state/state_utils.py（项目自包含，随仓库提交）。

用法（项目目录内执行）:
  python state/state_utils.py init --dir <项目目录> --name <竞赛> [--year YYYY] [--problem X] [--language zh] [--git] [--force]
  python state/state_utils.py dump [--dir .]
  python state/state_utils.py stage-set <key> <status> [--artifact p] [--decision d] [--dir .]
  python state/state_utils.py gate-set <GATE> <PASS|FAIL|BLOCKED> [--agent A] [--result R] [--dir .]
  python state/state_utils.py node-start <N4> [--goal G] [--dir .]
  python state/state_utils.py node-finish <N4> [--artifact p ...] [--dir .]
  python state/state_utils.py node-review <N4> --agent <id> --result <PASS|FAIL> --skills s1,s2 [--summary S] [--dir .]
  python state/state_utils.py round-start <N4|N5|N7|N8> [--goal G] [--branch B] [--git] [--dir .]
  python state/state_utils.py round-score <N4|N5|N7|N8> --round N --total 7.8 --dims '{"correctness":8.0,...}' [--judge A] [--git] [--dir .]
  python state/state_utils.py round-decide <N4|N5|N7|N8> --round N [--feedback F] [--git] [--dir .]
  python state/state_utils.py case-add --title T --source S [--url U] [--summary X] [--score n] [--source-type github-code] [--query Q] [--dir .]
  python state/state_utils.py search-source add --id <id> --type <类型> --name <名> --address <URL> --tool <工具> [--query-template T] [--apply-when a,b] [--priority n] [--dir .]
  python state/state_utils.py dashboard-refresh [--dir .]
  python state/state_utils.py claim <agent-id> --node N4 [--dir .]
  python state/state_utils.py node-log <N4> --step <小步骤描述> [--by <执行者>] [--dir .]
  python state/state_utils.py todo add <待办> [--node N4] [--dir .]
  python state/state_utils.py todo done <匹配文本> [--dir .]
  python state/state_utils.py todo plan [--dir .]
  python state/state_utils.py todo list [--dir .]
  python state/state_utils.py cascade-invalidate [--node N3] [--apply] [--dir .]
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

# 使同目录模块（legacy_names 等）在脚本与 importlib 两种加载方式下均可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 物理目录不携带流程序号；N0-N8 仅作为逻辑节点 ID 保留在状态数据中。
STATE_DIR = "state"
STATE_FILE = os.path.join(STATE_DIR, "decision_log.json")
REGISTRY_FILE = os.path.join(STATE_DIR, "registry.json")
DASHBOARD_FILE = os.path.join(STATE_DIR, "dashboard.md")
CASES_INDEX = os.path.join(STATE_DIR, "cases", "index.json")
SEARCH_SOURCES_FILE = os.path.join(STATE_DIR, "search_sources.json")
TODO_FILE = os.path.join(STATE_DIR, "todo.md")

# ---------------------------------------------------------------- 节点定义（与 registry.json / SKILL §6.1 双份一致）

NODES = {
    "N0": {"dir": "需求确认", "name": "需求确认", "executor": "main-agent", "reviewer": None, "skills": [],
           "gates": [], "artifact": "README-项目总说明.md, ProblemInfo/TeamInfo.txt, ProblemInfo/TimePlan.md, state/",
           "stage": "0_init", "review_mode": None, "phrases": []},
    "N1": {"dir": "选题拆解", "name": "选题拆解", "executor": "selector", "reviewer": "reviewer",
           "skills": ["academic-orchestrator:mm-problem-analysis", "academic-orchestrator:mm-self-review"],
           "gates": ["M1", "H1"], "artifact": "ProblemInfo/", "stage": "1_analysis",
           "review_mode": "node-review", "phrases": ["分析这道题", "选哪道", "题目拆解", "审题"]},
    "N2": {"dir": "数据处理", "name": "数据处理", "executor": "dataprep", "reviewer": "reviewer",
           "skills": ["academic-orchestrator:mm-data-preprocessing"],
           "gates": ["D1"], "artifact": "Data/", "stage": "2_data",
           "review_mode": "node-review", "phrases": ["处理数据", "数据清洗", "预处理", "特征工程"]},
    "N3": {"dir": "建模", "name": "建模", "executor": "modeler", "reviewer": "reviewer",
           "skills": ["academic-orchestrator:mm-model-library"],
           "gates": ["P1"], "artifact": "ModelDocs/", "stage": "3_modeling",
           "review_mode": "node-review", "phrases": ["选模型", "怎么建模", "建模方案", "公式推导"]},
    "N4": {"dir": "代码", "name": "代码/代码迭代", "executor": "coder", "reviewer": "mm-code-reviewer",
           "skills": ["academic-orchestrator:mm-iteration-engine", "academic-orchestrator:mm-algorithm-dev", "academic-orchestrator:code-review"],
           "gates": ["P2", "H2"], "artifact": "Code/", "stage": "4_solving",
           "review_mode": "code-score", "phrases": ["写代码", "实现算法", "代码迭代", "修代码", "算法开发"]},
    "N5": {"dir": "调优", "name": "调优", "executor": "tuner", "reviewer": "mm-code-reviewer",
           "skills": ["academic-orchestrator:mm-model-tuning", "academic-orchestrator:mm-iteration-engine"],
           "gates": ["T1"], "artifact": "ModelDocs/", "stage": "5_tuning",
           "review_mode": "tune-check", "phrases": ["调参", "调优", "优化模型", "敏感性分析"]},
    "N6": {"dir": "图表", "name": "图表", "executor": "visualization", "reviewer": "mm-viz-reviewer",
           "secondary_reviewers": ["mm-figure-table-benchmarker"],
           "skills": ["academic-orchestrator:mm-visualization", "academic-orchestrator:mm-iteration-engine",
                      "academic-orchestrator:figure-table-benchmark"],
           "gates": ["V1", "B1"], "artifact": "Code/output/figures, ResultFigures/", "stage": "6_visualization",
           "review_mode": "viz-check", "phrases": ["画图", "生成图表", "可视化", "图表对标"]},
    "N7": {"dir": "论文", "name": "论文/论文修改", "executor": "writing", "reviewer": "reviewer",
           "secondary_reviewers": ["mm-figure-table-benchmarker"],
           "skills": ["academic-orchestrator:mm-iteration-engine", "academic-orchestrator:mm-latex-writing",
                      "academic-orchestrator:mm-self-review", "academic-orchestrator:figure-table-benchmark"],
           "gates": ["W1", "W2", "H3", "B1"], "artifact": "ReportPaper/", "stage": "7_writing",
           "review_mode": "paper-review", "phrases": ["写论文", "论文初稿", "论文修改", "改论文"]},
    "N8": {"dir": "评审", "name": "评审", "executor": "reviewer", "reviewer": "reviewer",
           "secondary_reviewers": ["mm-figure-table-benchmarker"],
           "skills": ["academic-orchestrator:mm-self-review", "academic-orchestrator:figure-table-benchmark"],
           "gates": ["A3", "B1"], "artifact": "SubmissionPackage/", "stage": "8_review",
           "review_mode": "final-review", "phrases": ["检查论文", "评审", "终审", "自检"]},
}

# 迭代环节点 → termination profile
PROFILE_OF = {"N4": "code", "N5": "code", "N7": "paper", "N8": "paper"}

# 节点审阅 → 主门禁映射（node-review PASS/FAIL 时写入该门禁）
REVIEW_GATE = {"N1": "M1", "N2": "D1", "N3": "P1", "N4": "P2", "N5": "T1", "N6": "V1", "N7": "W2", "N8": "A3"}

# 次要审阅者 → 其专属门禁（2.0.0）。B1 = 图表/表格文献对标门禁。
SECONDARY_REVIEWER_GATE = {"mm-figure-table-benchmarker": "B1"}

# 维度级审阅分工（防"同一 Agent 自评全部五维"造成的单一视角与相互污染）。
#
# 原则：**只在维度确实需要不同证据来源时才拆**，不做无差别多派（避免工程冗余）。
#   · correctness / efficiency / robustness：要跑代码、看实测 → 留主审阅者
#   · readability / innovation：看设计与新颖性，与实现者视角冲突最大
#     → 由独立第二审阅者评，避免"自己写的代码自己说结构清晰、方法有创新"
#
# 只有声明了 DIMENSION_SPLIT 的节点才要求第二审阅者；其余保持单人审阅。
DIMENSION_SPLIT = {
    "N4": {
        "agent": "reviewer",
        "dimensions": ["readability", "innovation"],
        "rationale": ("readability/innovation 属设计与判断类，与实现者视角冲突最大；"
                      "correctness/efficiency/robustness 需实测运行证据，留在 mm-code-reviewer。"),
    },
    "N5": {
        "agent": "reviewer",
        "dimensions": ["innovation"],
        "rationale": ("调优节点的创新性（方法改进是否有依据）应由非算法实现方判断；"
                      "其余维度依赖调优实测数据。"),
    },
}

UPSTREAM = {
    "N1": [("N0", "需求确认")], "N2": [("N1", "选题拆解")], "N3": [("N1", "选题拆解"), ("N2", "数据处理")],
    "N4": [("N3", "建模")], "N5": [("N4", "代码")], "N6": [("N4", "代码"), ("N5", "调优")],
    "N7": [("N6", "图表")], "N8": [("N7", "论文")],
}

# ---------------------------------------------------------------- 搜索源注册表（SEARCH 检索地址清单）

SEARCH_SOURCES = {
    "version": "1.0",
    "_comment": "=== 迭代 SEARCH 步骤的检索地址注册表 === 按实际需求选源（需求→渠道映射见 SKILL §12），init 生成，可手工扩充（search-source add）。",
    "sources": [
        {"id": "github-code", "type": "开源项目/代码", "name": "GitHub Code Search",
         "address": "https://github.com/search?q=<QUERY>&type=code / gitee.com / gitlab.com",
         "tool": "gh_grep searchGitHub + WebSearch",
         "query_template": "<题型关键词> <算法名> python",
         "apply_when": ["需要参考实现", "需要开源代码"], "priority": 1},
        {"id": "paper-academic", "type": "论文/算法", "name": "arXiv / OpenAlex / Semantic Scholar",
         "address": "https://arxiv.org / https://api.openalex.org/works?search=<QUERY> / https://api.semanticscholar.org",
         "tool": "paper-mcp paper_search + WebSearch",
         "query_template": "<方法名> <问题域>",
         "apply_when": ["需要方法论论文", "需要算法原理"], "priority": 2},
        {"id": "paperswithcode", "type": "论文+代码对照", "name": "Papers with Code",
         "address": "https://paperswithcode.com",
         "tool": "WebSearch / WebFetch",
         "query_template": "<任务名> state of the art",
         "apply_when": ["需要论文+官方实现成对证据"], "priority": 3},
        {"id": "contest-papers", "type": "竞赛优秀论文", "name": "数学中国 / CUMCM 优秀论文库 / GitHub 数模仓库",
         "address": "http://www.madio.net / CUMCM 官网历年优秀论文 / github.com（MathModel-with-python 等数模仓库）",
         "tool": "WebSearch / WebFetch",
         "query_template": "CUMCM <年份> <题号> 优秀论文 <方法>",
         "apply_when": ["需要获奖论文参照", "评分点对齐"], "priority": 2},
        {"id": "lib-docs", "type": "库/框架文档", "name": "Context7",
         "address": "https://context7.com/<lib>",
         "tool": "context7 resolve-library-id + query-docs",
         "query_template": "<库名> <API/用法>",
         "apply_when": ["不确定库 API", "报错排查"], "priority": 4},
        {"id": "model-zoo", "type": "预训练模型/数据", "name": "HuggingFace",
         "address": "https://huggingface.co/models / https://huggingface.co/datasets",
         "tool": "WebSearch / WebFetch",
         "query_template": "<任务> <数据形态> dataset/model",
         "apply_when": ["需要数据集", "需要预训练模型"], "priority": 5},
        {"id": "zh-knowledge", "type": "中文方法线索（非权威源）", "name": "知乎 / CSDN / 博客园",
         "address": "zhihu.com / csdn.net / cnblogs.com",
         "tool": "WebSearch",
         "query_template": "<题型> 数学建模 <方法>",
         "apply_when": ["仅作线索，落地前回源头验证"], "priority": 6},
    ],
}

# ---------------------------------------------------------------- 基础工具


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def save_text_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def state_path(root):
    return os.path.join(root, STATE_FILE)


def load_state(root):
    path = state_path(root)
    if not os.path.exists(path):
        sys.exit(f"[state_utils] 未找到 {path}。请先执行: python state/state_utils.py init --dir {root}")
    state = load_json(path)
    if not isinstance(state, dict) or state.get("_schema") != "2.0":
        sys.exit(f"[state_utils] 状态文件 schema 无效: {path}（需要 2.0）")
    for key in ("stages", "nodes", "gates", "rounds", "decisions", "termination", "meta"):
        if key not in state:
            sys.exit(f"[state_utils] 状态文件缺少必需字段: {key}")
    return state


def load_registry(root):
    path = os.path.join(root, REGISTRY_FILE)
    registry = load_json(path)
    if not isinstance(registry, dict):
        sys.exit(f"[state_utils] 注册表无效: {path}")
    return {entry.get("id"): entry for entry in registry.get("nodes", []) if entry.get("id")}


def expected_reviewers(node):
    """节点的全部合法审阅者：主 reviewer + secondary_reviewers + 维度分工 agent。

    · secondary 用于「同一节点需要多个独立视角」（如 N6/N7/N8 的 B1 对标）；
    · DIMENSION_SPLIT 里的 agent 是"只评指定维度"的第二审阅者
      （如 N4 的 readability/innovation 由 reviewer 独立评，避免实现方自评结构优劣）。
    """
    info = NODES[node]
    out = []
    if info.get("reviewer"):
        out.append(info["reviewer"])
    out.extend(info.get("secondary_reviewers") or [])
    split_agent = (DIMENSION_SPLIT.get(node) or {}).get("agent")
    if split_agent and split_agent not in out:
        out.append(split_agent)
    return out


def expected_reviewer(node):
    return NODES[node].get("reviewer")


def require_independent_reviewer(node, agent):
    expected = expected_reviewer(node)
    allowed = expected_reviewers(node)
    if not agent:
        sys.exit("[state_utils] 必须指定独立审阅 Agent")
    if node != "N8" and agent == NODES[node].get("executor"):
        sys.exit(f"[state_utils] 拒绝自评: {agent} 不能审阅自身执行的 {node}")
    if expected and agent not in allowed:
        sys.exit(f"[state_utils] 审阅 Agent 不匹配: {node} 需要 {expected}"
                 + (f" 或 {', '.join(allowed[1:])}" if len(allowed) > 1 else "")
                 + f"，实际为 {agent}")


def skill_basename(skill):
    """技能名归一化：去掉插件命名空间前缀（`academic-orchestrator:mm-x` → `mm-x`）。

    宿主允许两种写法——插件注册名带前缀，流程文档与代理内文按裸名引用——
    两种写法必须视为同一技能，否则 `--skills` 校验会因写法不同而误判缺失。
    """
    return str(skill).split(":", 1)[-1].strip()


def normalized_skill_set(skills):
    return {skill_basename(s) for s in skills if str(s).strip()}


# 次要审阅者的专项必读 skill（2.0.0）。不继承执行方规范，避免角色边界混乱。
SECONDARY_REVIEWER_SKILLS = {
    "mm-figure-table-benchmarker": [
        "academic-orchestrator:figure-table-benchmark",
        "academic-orchestrator:mm-iteration-engine",
    ],
}


# 主审阅者的专项必读 skill（P0-10）。与执行方 required_skills 分离：
# 执行方要读"怎么做"的规范（mm-visualization/mm-latex-writing…），
# 审阅方要读"怎么判"的规范。
# 单一事实源：本表必须与各审阅 Agent 文档里 `--skills` 命令示例逐字一致
# （reviewer.md / mm-code-reviewer.md / mm-viz-reviewer.md），
# 否则按文档操作会被自己的门禁拒绝。
REVIEWER_SKILLS = {
    "N1": ["academic-orchestrator:mm-problem-analysis", "academic-orchestrator:mm-self-review"],
    "N2": ["academic-orchestrator:mm-data-preprocessing"],
    "N3": ["academic-orchestrator:mm-model-library"],
    "N4": ["academic-orchestrator:mm-iteration-engine", "academic-orchestrator:mm-algorithm-dev",
           "academic-orchestrator:code-review"],
    "N5": ["academic-orchestrator:mm-iteration-engine", "academic-orchestrator:mm-algorithm-dev",
           "academic-orchestrator:code-review", "academic-orchestrator:mm-model-tuning"],
    "N6": ["academic-orchestrator:mm-visualization", "academic-orchestrator:mm-iteration-engine"],
    "N7": ["academic-orchestrator:mm-iteration-engine", "academic-orchestrator:mm-latex-writing",
           "academic-orchestrator:mm-self-review"],
    "N8": ["academic-orchestrator:mm-iteration-engine", "academic-orchestrator:mm-latex-writing",
           "academic-orchestrator:mm-self-review"],
}


# 维度分工审阅者需要的规范（只判设计与创新，不判代码实现细节）。
# 未列出的节点回退到 mm-self-review。
DIMENSION_SPLIT_SKILLS = {
    "N4": ["academic-orchestrator:mm-self-review"],
    "N5": ["academic-orchestrator:mm-self-review"],
}


def reviewer_required_skills(node, agent=None):
    """某审阅者在本节点必须声明的 skill 清单。

    2.0.0：同一节点可能有多个审阅视角——
      - 主 reviewer：用 REVIEWER_SKILLS（"怎么判"的规范），**不再**沿用执行方 required_skills；
      - secondary reviewer（如 mm-figure-table-benchmarker）：只需它自己的专项规范；
      - **维度分工审阅者**（DIMENSION_SPLIT，如 N4 由 reviewer 评 readability/innovation）：
        只需"判断设计与创新"的规范（mm-self-review），不需要代码审阅的执行规范——
        否则分工就退化为主审阅者复读。
    P0-10：原实现对主 reviewer 返回 info["skills"]（执行方技能集），
    导致审阅者被要求声明 mm-visualization/mm-latex-writing 等执行规范，
    而 agent 文档里没写，按文档操作会被自己拒绝。
    """
    info = NODES[node]
    main_reviewer = info.get("reviewer")
    secondaries = info.get("secondary_reviewers") or []
    split_agent = (DIMENSION_SPLIT.get(node) or {}).get("agent")

    if agent and agent == split_agent and agent != main_reviewer:
        # 维度分工：只要求"审阅判断"规范，不要求执行/代码审阅规范
        return DIMENSION_SPLIT_SKILLS.get(node) or ["academic-orchestrator:mm-self-review"]
    if agent and agent in secondaries and agent != main_reviewer:
        return SECONDARY_REVIEWER_SKILLS.get(agent, [])
    return REVIEWER_SKILLS.get(node, info.get("skills", []))


def _version_sort_key(text):
    """版本号排序键（语义比较）：数字段按数值，非数字段按字符串。

    纯字典序会把 1.10.0 排在 2.0.0 前（'1' < '2'），插件缓存多版本共存时
    会解析到陈旧副本——这里统一按语义版本比较。
    """
    parts = []
    for tok in re.split(r"[._\-+]", str(text).strip()):
        if tok.isdigit():
            parts.append((0, int(tok), ""))
        elif tok:
            parts.append((1, 0, tok.casefold()))
    return parts


def skill_is_resolvable(skill, project=None):
    """该 skill 能否在磁盘上找到（与宿主解析顺序一致：先命中者胜）。

    返回 (bool, 路径或 None)。用于替代"依赖 Skill 工具"的可行性判断：
    子 Agent 工具集可能不含 Skill（实测会报"会话工具集无 Skill 工具"），
    但所有子 Agent 都有 Read，所以"内容可达"才是可靠判据。
    """
    bare = skill_basename(skill)
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, ".zcode", "skills"),
        os.path.join(home, ".agents", "skills"),
        os.path.join(home, ".zcode", "skill-sources"),
    ]
    env_roots = os.environ.get("MM_SKILL_ROOTS")
    if env_roots:
        roots = [p for p in env_roots.split(os.pathsep) if p.strip()] + roots
    plugin_root = os.environ.get("ZCODE_PLUGIN_ROOT")
    if plugin_root:
        roots.append(os.path.join(plugin_root, "skills"))
    if project:
        roots.extend([os.path.join(project, ".zcode", "skills"),
                      os.path.join(project, ".agents", "skills")])
    # 插件缓存：<cache>/<marketplace>/<plugin>/<version>/skills
    # 同一插件多版本共存时取语义版本最高的副本（字典序会在跨大版本时选到旧版）
    cache = os.path.join(home, ".zcode", "cli", "plugins", "cache")
    if os.path.isdir(cache):
        for market in sorted(os.listdir(cache)):
            mdir = os.path.join(cache, market)
            if not os.path.isdir(mdir):
                continue
            for plugin in sorted(os.listdir(mdir)):
                pdir = os.path.join(mdir, plugin)
                if not os.path.isdir(pdir):
                    continue
                for ver in sorted(os.listdir(pdir), key=_version_sort_key, reverse=True):
                    sk = os.path.join(pdir, ver, "skills")
                    if os.path.isdir(sk):
                        roots.append(sk)
    for root in roots:
        for cand in (os.path.join(root, bare, "SKILL.md"),
                     os.path.join(root, "skills", bare, "SKILL.md")):
            if os.path.isfile(cand):
                return True, cand
    return False, None


def require_review_skills(node, skills, agent=None, project=None):
    """审阅前必读 skill 校验。

    两件事分开做，不能混为"声明了字符串就放行"：
      ① 声明齐备：--skills 必须覆盖 reviewer_required_skills 的清单；
      ② **内容可达**：每个必读 skill 必须能在磁盘上解析到 SKILL.md。

    ② 是针对真实故障加的：子 Agent 工具集可能不含 Skill，
    `skill("mm-self-review")` 根本执行不了，此前门禁只查 ①，
    于是"抄了个名字"就能过——门禁形同虚设。
    现在补 ②：解析不到就拒绝，并按可用方式给出修复指引。
    """
    declared = normalized_skill_set(skills.split(","))
    required_list = reviewer_required_skills(node, agent)
    missing_keys = normalized_skill_set(required_list) - declared
    if missing_keys:
        # 报告原始注册名（带插件前缀），便于直接复制到 --skills
        missing = [s for s in required_list if skill_basename(s) in missing_keys]
        sys.exit(f"[state_utils] 审阅前必读 Skill 未声明: {', '.join(missing)}")

    # ② 内容可达性：声明了但磁盘上找不到 → 拒绝（防止"声明即通过"）
    unresolved = []
    for s in required_list:
        ok, _ = skill_is_resolvable(s, project)
        if not ok:
            unresolved.append(s)
    if unresolved:
        sys.exit(
            "[state_utils] 拒绝：以下必读 skill 声明了，但磁盘上解析不到 SKILL.md：\n  - "
            + "\n  - ".join(unresolved)
            + "\n  这说明 skill 未安装或被遮蔽（同名更高优先级副本覆盖）。\n"
            "  排查：python scripts/skill_context.py --name <skill> --resolve-only\n"
            "  若子 Agent 无 Skill 工具：改用内容注入\n"
            "    python scripts/skill_context.py --name <skill> --body-only > 上下文.txt\n"
            "    （主 Agent 把正文注入派发 prompt，子 Agent 只需 Read，无需 Skill 工具）"
        )


def save_state(root, state, bump=True):
    if bump:
        state.setdefault("meta", {})["seq"] = state.get("meta", {}).get("seq", 0) + 1
    state["meta"]["updated_at"] = now_iso()
    save_json_atomic(state_path(root), state)


def node_homepage(root, node):
    info = NODES[node]
    return os.path.join(root, STATE_DIR, "nodes", info["dir"], "dashboard.md")


def require_node(node, allowed=None):
    if node not in NODES:
        sys.exit(f"[state_utils] 非法节点 {node}。合法节点: {', '.join(NODES)}")
    if allowed is not None and node not in allowed:
        sys.exit(f"[state_utils] 节点 {node} 不支持该操作。仅支持: {', '.join(allowed)}")


def verify_problem_lock(root, required=True):
    path = os.path.join(root, STATE_DIR, "problem_lock.json")
    if not os.path.exists(path):
        if required:
            sys.exit(f"[state_utils] 缺少 {path}；请先阅读题目并创建 problem_lock.json")
        return None
    lock = load_json(path)
    required_fields = ("objectives", "constraints", "preconditions", "data_requirements", "evaluation_metrics")
    missing = [key for key in required_fields if not isinstance(lock.get(key), list) or not lock[key]]
    source = lock.get("source_path", "")
    if source:
        source = source if os.path.isabs(source) else os.path.join(root, source)
        if not os.path.isfile(source):
            missing.append("source_path")
        elif lock.get("source_sha256") != sha256_of(source):
            sys.exit("[state_utils] 题目原文 SHA-256 已变化；必须重新阅读题目并更新 problem_lock.json")
    if lock.get("status") != "verified" or missing:
        sys.exit(f"[state_utils] 题目事实锁定未通过: status={lock.get('status')}, missing={missing}")
    return lock


def require_git(root):
    if not os.path.exists(os.path.join(root, ".git")):
        sys.exit("[state_utils] 当前项目不是 git 仓库。请先 git init（或 init --git），再使用 --git 参数")


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def git_current_branch(root):
    r = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    return r.stdout.strip() if r.returncode == 0 else "-"


def git_last_commit(root):
    r = git(["log", "-1", "--oneline"], cwd=root)
    return r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else "-"


def _is_placeholder_row(line):
    """表格占位行（所有单元格均为 '-'）"""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(c == "-" for c in cells)


def _find_section(lines, section_keyword):
    """返回 (小节标题行下标, 小节结束下标)"""
    for i, ln in enumerate(lines):
        if ln.startswith("## ") and section_keyword in ln:
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    end = j
                    break
            return i, end
    return None, None


def append_table_row(md_path, section_keyword, row_text):
    """在 Markdown 文件指定小节（## 标题含 keyword）的表格末尾追加一行。"""
    if not os.path.exists(md_path):
        return
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    idx, end = _find_section(lines, section_keyword)
    if idx is None:
        return
    last = None
    for j in range(idx + 1, end):
        if lines[j].startswith("|"):
            last = j
    if last is not None and _is_placeholder_row(lines[last]):
        lines[last] = row_text + "\n"
    elif last is not None:
        lines.insert(last + 1, row_text + "\n")
    else:
        lines.insert(idx + 1, row_text + "\n")
    save_text_atomic(md_path, "".join(lines))


def upsert_row_by_first_cell(md_path, section_keyword, first_cell, row_text):
    """按首列定位更新表格行（存在则替换，否则追加）——避免重复行。"""
    if not os.path.exists(md_path):
        return
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    idx, end = _find_section(lines, section_keyword)
    if idx is None:
        return
    key = str(first_cell)
    for j in range(idx + 1, end):
        if lines[j].startswith("|") and not _is_placeholder_row(lines[j]):
            cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
            if cells and cells[0] == key:
                lines[j] = row_text + "\n"
                save_text_atomic(md_path, "".join(lines))
                return
    append_table_row(md_path, section_keyword, row_text)


def update_homepage_meta(md_path, status, updated=None):
    """更新节点首页 §1 的 状态/最近更新 两行。"""
    if not os.path.exists(md_path):
        return
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    for line in text.splitlines():
        if line.startswith("| 状态 |"):
            text = text.replace(line, f"| 状态 | {status} |", 1)
        elif line.startswith("| 最近更新 |"):
            text = text.replace(line, f"| 最近更新 | {updated or now_iso()} |", 1)
    save_text_atomic(md_path, text)


def rewrite_homepage_gates(md_path, gate_rows):
    """重写节点首页 §6 门禁状态表。"""
    if not os.path.exists(md_path):
        return
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    idx, end = _find_section(lines, "6. 门禁状态")
    if idx is None:
        return
    header = ["## 6. 门禁状态\n", "\n", "| 门禁 | 状态 | 结果 |\n", "|------|------|------|\n"]
    block = header + [g + "\n" for g in gate_rows]
    lines = lines[:idx] + block + lines[end:]
    save_text_atomic(md_path, "".join(lines))


def gate_rows_for(state, node):
    rows = []
    for gid in NODES[node]["gates"]:
        g = state["gates"].get(gid, {"status": "pending"})
        rows.append(f"| {gid} | {g.get('status', 'pending')} | {g.get('result') or '-'} |")
    for gid in sorted(state["gates"]):
        if gid.endswith(f"-{node}") and gid.startswith("S"):
            g = state["gates"][gid]
            rows.append(f"| {gid} | {g.get('status', 'pending')} | {g.get('result') or '-'} |")
    return rows


# ---------------------------------------------------------------- 模板文本

REPORTS_DIR = os.path.join(STATE_DIR, "reports")
REPORTS_INDEX = os.path.join(REPORTS_DIR, "index.json")


def artifact_snapshot(root, node):
    """节点产物快照哈希：文件→sha256；目录→递归文件清单哈希（相对路径排序拼接，64KB 分块）。

    活账本目录（state/）不参与哈希：它是工作流自身的状态存储，每次 save_state 都会变，
    若纳入快照会让"上游产物漂移"判定恒为真（N0 声明的 artifact 就含 state/）。
    这类路径只记存在性（"present"/None），用途是校验"该目录确实建立过"。
    """
    paths = [p.strip() for p in NODES[node].get("artifact", "").split(",") if p.strip()]
    state_prefix = STATE_DIR + "/"
    snapshot = {}
    for p in paths:
        norm = p.replace("\\", "/").strip("/")
        if norm == STATE_DIR or norm.startswith(state_prefix):
            snapshot[p] = "present" if os.path.exists(os.path.join(root, p)) else None
            continue
        full = os.path.join(root, p)
        if os.path.isfile(full):
            snapshot[p] = sha256_of(full)
        elif os.path.isdir(full):
            entries = []
            for dirpath, dirnames, filenames in os.walk(full):
                if ".git" in dirpath.split(os.sep):
                    dirnames[:] = []
                    continue
                for fn in sorted(filenames):
                    rel = os.path.relpath(os.path.join(dirpath, fn), root)
                    entries.append(f"{rel}:{sha256_of(os.path.join(dirpath, fn))}")
            snapshot[p] = sha256_of_bytes(str("\n").join(sorted(entries)).encode("utf-8"))
        else:
            snapshot[p] = None
    return snapshot


def sha256_of_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- 核心节点 MCP 必调（MCP 集成，见 mcp/call-hierarchy.md 六节点强制）
# 核心节点（N1/N3/N4/N5/N6/N7）必须调用对应 MCP 获取外部资料支撑；迭代每轮必须重新检索、禁止纯内生输出。
# 检索留痕（state/reports/mcp-calls.jsonl 行 · state/cases/index.json 案例/轮次引用）为审阅 PASS / 轮次评分的前置机器校验。
#
# 单一事实源：每个节点一条 (人类可读说明, 必含 token 组, 至少命中一组的 token 组)。
# 说明文字只用于报错，机器判定只读两套 token 组——此前说明表与 token 表分开维护，
# 加节点/改必调源时会只改一处，于是"报错说要 paper-mcp，实际校验查的是别的"。
MCP_MANDATORY_NODES = {
    "N1": {
        "desc": "论文搜索 MCP + Tavily/tokenhub 全网搜索 MCP",
        "all": ("paper-mcp",), "any": ("tavily", "tavily-mcp", "tokenhub-tools"),
    },
    "N3": {
        "desc": "Context7 MCP + 论文搜索 MCP",
        "all": ("context7",), "any": ("paper-mcp",),
    },
    "N4": {
        "desc": "Context7 MCP + GitHub MCP",
        "all": ("context7",), "any": ("github",),
    },
    "N5": {
        "desc": "GitHub MCP + Tavily/tokenhub 全网搜索 MCP",
        "all": ("github",), "any": ("tavily", "tavily-mcp", "tokenhub-tools"),
    },
    "N6": {
        "desc": "论文搜索 MCP + Tavily/WebSearch（必要时 Context7）",
        "all": ("paper-mcp",), "any": ("tavily", "tavily-mcp", "tokenhub-tools"),
    },
    "N7": {
        "desc": "论文搜索 MCP",
        "all": ("paper-mcp",), "any": (),
    },
}
MCP_CALLS_FILE = os.path.join(STATE_DIR, "reports", "mcp-calls.jsonl")
# Deep Research 介入留痕（dr-note 命令追加；每轮迭代 SEARCH/SCORE/DECIDE 的 DR 介入可审计，N8 终检可核对）
DR_INTERVENTIONS_FILE = os.path.join(STATE_DIR, "reports", "dr-interventions.jsonl")


def _mcp_tokens(value):
    return {token.strip().lower() for token in re.split(r"[,;+|]", str(value or "")) if token.strip()}


def mcp_requirement_text(node):
    """节点必调 MCP 的可读说明（用于报错与派发清单）。"""
    entry = MCP_MANDATORY_NODES.get(node)
    return entry["desc"] if isinstance(entry, dict) else str(entry or "")


def _required_mcp_tokens(node):
    entry = MCP_MANDATORY_NODES.get(node)
    if not isinstance(entry, dict):
        return set(), set()
    return set(entry["all"]), set(entry["any"])


def mcp_search_evidence(root, node, round_no=None):
    """Validate node/round-owned MCP records against mandatory categories.

    A generic case or an arbitrary ``mcp`` string is not enough: each required
    category must appear in a record carrying node, query, timestamp and result
    or card evidence. This keeps unrelated searches from satisfying a gate.
    """
    evidence = []
    required_a, required_b = _required_mcp_tokens(node)
    observed = set()
    calls_path = os.path.join(root, MCP_CALLS_FILE)
    if os.path.exists(calls_path):
        try:
            with open(calls_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if str(rec.get("node") or "") != node:
                        continue
                    rec_round = rec.get("round")
                    if round_no is not None and str(rec_round) != str(round_no):
                        continue
                    if not rec.get("query") or not (rec.get("ts") or rec.get("timestamp")):
                        continue
                    if not (rec.get("result") or rec.get("summary") or rec.get("card") or rec.get("card_path") or rec.get("output")):
                        continue
                    tokens = _mcp_tokens(rec.get("mcp"))
                    observed.update(tokens)
                    evidence.append(f"mcp-calls#{node}&round={rec_round if rec_round is not None else '-'}")
        except Exception:
            pass
    # Case index is a secondary evidence channel. It is valid only when the
    # case itself carries node/category/query/timestamp/result/card metadata;
    # legacy unscoped cases cannot satisfy a modern mandatory gate.
    cases = load_json(os.path.join(root, CASES_INDEX), {"version": "1.0", "cases": []})
    if isinstance(cases, dict):
        for case in cases.get("cases", []):
            if str(case.get("node") or "") != node:
                continue
            used = {str(item) for item in (case.get("used_in_rounds") or [])}
            if round_no is not None and str(round_no) not in used:
                continue
            if not case.get("query") or not (case.get("timestamp") or case.get("ts")):
                continue
            if not (case.get("result") or case.get("summary")) or not (case.get("card") or case.get("card_path")):
                continue
            observed.update(_mcp_tokens(case.get("mcp")))
            evidence.append(f"case#{case.get('id', '-')}&round={round_no if round_no is not None else '-'}")
    if required_a.issubset(observed) and (not required_b or required_b & observed):
        return sorted(set(evidence))
    return []


DATA_LINEAGE_FILE = os.path.join("Data", "data-lineage.json")


def _log_exemption(root, kind, node, agent="-", detail=""):
    """豁免留痕（P2-10b）：--allow-* 不再只是提前 return，而是写一条可审计记录。

    留痕失败不阻断主流程，但**必须可见**：静默 pass 会让"豁免 0 条"
    与"留痕功能坏了"无法区分，审计时看起来像从未豁免过。
    """
    try:
        from state_events import record_exemption
        record_exemption(root, kind, node, agent, detail)
    except Exception as exc:  # noqa: BLE001 - 留痕是旁路，任何失败都不该阻断业务
        print(f"[state_utils] ⚠ 豁免留痕写入失败（不阻断）：{kind} node={node} — {exc}",
              file=sys.stderr)


def require_data_lineage(root, node, allow_flag=False):
    """N2 数据血缘强制校验（D1 门禁机器执行者）。

    三件事必须可交叉检验：
      1. 处理了什么 —— raw 文件 sha256 与登记一致（未被篡改）
      2. 怎么处理   —— 每级 transform 脚本存在、哈希匹配、有参数与种子
      3. 产出什么   —— 每级 outputs 哈希一致，且下一级 inputs 匹配上一级 outputs（链不断裂）

    缺台账 / 校验不 PASS → 拒绝 D1 审阅落盘。allow_flag=True 为显式豁免（离线/人工特批）。
    """
    if node != "N2":
        return
    if allow_flag:
        _log_exemption(root, "allow-missing-lineage", node)
        return
    ledger = os.path.join(root, DATA_LINEAGE_FILE)
    if not os.path.isfile(ledger):
        sys.exit(
            f"[state_utils] 🔴 N2 缺少数据血缘台账 {DATA_LINEAGE_FILE}，D1 无法判定"
            f"「处理内容/过程/结果是否可交叉检验」。\n"
            f"  请先产出血缘台账（结构见 shared/contracts/math_modeling/data_lineage.schema.json），"
            f"并执行:\n"
            f"    python scripts/validate_data_lineage.py {DATA_LINEAGE_FILE} --root .\n"
            f"  或显式传 --allow-missing-lineage 豁免（仅离线/人工特批，须在交付说明中留痕）。"
        )
    # 定位校验器。三种运行形态都要覆盖：
    #   1) 插件根内运行： state_defs 在 <plugin>/shared/state-engine/ → 上两级即插件根
    #   2) 项目内副本运行：state_defs 被复制到 <project>/state/ → 项目内通常无 scripts，需回退
    #   3) 显式指定：ACADEMIC_ORCHESTRATOR_ROOT 环境变量
    _here = os.path.dirname(os.path.abspath(__file__))
    _cands = []
    env_root = os.environ.get("ACADEMIC_ORCHESTRATOR_ROOT")
    if env_root:
        _cands.append(os.path.join(env_root, "scripts", "validate_data_lineage.py"))
    _cands.append(os.path.join(os.path.dirname(os.path.dirname(_here)), "scripts", "validate_data_lineage.py"))
    _cands.append(os.path.join(_here, "..", "..", "scripts", "validate_data_lineage.py"))
    _cands.append(os.path.join(root, "scripts", "validate_data_lineage.py"))
    script = next((os.path.abspath(c) for c in _cands if os.path.isfile(c)), None)
    if not script:
        sys.exit(
            "[state_utils] 数据血缘校验器缺失: scripts/validate_data_lineage.py\n"
            "  项目内 state/ 副本找不到插件根。请在插件根目录运行，或设置环境变量\n"
            "    ACADEMIC_ORCHESTRATOR_ROOT=<插件根目录>\n"
            "  或传 --allow-missing-lineage 豁免（仅离线/人工特批）。"
        )
    try:
        proc = subprocess.run([sys.executable, script, ledger, "--root", root, "--json"],
                              capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError) as exc:
        sys.exit(f"[state_utils] 血缘校验执行失败: {exc}")
    try:
        report = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        sys.exit(f"[state_utils] 血缘校验输出无法解析: {(proc.stdout or proc.stderr)[:300]}")
    if report.get("status") == "PASS":
        return
    errs = report.get("errors") or [f"校验器退出码 {proc.returncode}"]
    detail = "\n".join(f"    - {e}" for e in errs[:10])
    sys.exit(
        f"[state_utils] 🔴 N2 数据血缘校验未通过（D1 拒绝放行）：\n{detail}\n"
        f"  修复方向：补齐缺失哈希/脚本记录、恢复 raw 原状、或让每级 inputs 与上一级 outputs 对齐。\n"
        f"  或显式传 --allow-missing-lineage 豁免（仅离线/人工特批，须在交付说明中留痕）。"
    )


def require_mcp_search_evidence(root, node, round_no=None, allow_flag=False):
    """核心节点 MCP 必调校验：该节点/该轮无外部检索留痕 → 拒绝（禁止纯内生输出、禁止跳过必调）。

    allow_flag=True 为显式豁免（仅离线/人工特批，调用方须在留痕中说明原因）。"""
    if node not in MCP_MANDATORY_NODES:
        return
    if allow_flag:
        _log_exemption(root, "allow-missing-mcp", node, detail=f"round={round_no}")
        return
    evidence = mcp_search_evidence(root, node, round_no)
    if evidence:
        return
    scope = f"node={node}" if round_no is None else f"node={node} round={round_no}"
    sys.exit(
        f"[state_utils] 🔴 核心节点 {scope} 缺少 MCP 检索留痕（必调 {mcp_requirement_text(node)}），禁止纯内生输出。\n"
        f"  请先执行 SEARCH 重新检索并沉淀 {MCP_CALLS_FILE} 行或 state/cases/index.json 案例（case-add 登记 channel/query）；\n"
        f"  或显式传 --allow-missing-mcp 豁免（仅离线/人工特批，须在交付说明中留痕）。"
    )

__all__ = ["STATE_DIR", "STATE_FILE", "REGISTRY_FILE", "DASHBOARD_FILE", "CASES_INDEX", "SEARCH_SOURCES_FILE", "TODO_FILE", "NODES", "PROFILE_OF", "REVIEW_GATE", "SECONDARY_REVIEWER_GATE", "SECONDARY_REVIEWER_SKILLS", "DIMENSION_SPLIT", "DIMENSION_SPLIT_SKILLS", "expected_reviewers", "reviewer_required_skills", "UPSTREAM", "SEARCH_SOURCES", "now_iso", "load_json", "save_json_atomic", "save_text_atomic", "sha256_of", "state_path", "load_state", "load_registry", "expected_reviewer", "require_independent_reviewer", "require_review_skills", "skill_is_resolvable", "skill_basename", "normalized_skill_set", "_version_sort_key", "save_state", "node_homepage", "require_node", "verify_problem_lock", "require_git", "git", "git_current_branch", "git_last_commit", "_is_placeholder_row", "_find_section", "append_table_row", "upsert_row_by_first_cell", "update_homepage_meta", "rewrite_homepage_gates", "gate_rows_for", "REPORTS_DIR", "REPORTS_INDEX", "artifact_snapshot", "sha256_of_bytes", "MCP_MANDATORY_NODES", "MCP_CALLS_FILE", "DR_INTERVENTIONS_FILE", "mcp_search_evidence", "require_mcp_search_evidence", "require_data_lineage", "DATA_LINEAGE_FILE", "argparse", "hashlib", "json", "math", "os", "re", "shutil", "subprocess", "sys", "tempfile", "uuid", "datetime", "timezone"]
