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
           "gates": ["P2", "A1", "H2"], "artifact": "Code/", "stage": "4_solving",
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
           "gates": ["W1", "A2", "W2", "H3", "B1"], "artifact": "ReportPaper/", "stage": "7_writing",
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
    """节点的全部合法审阅者：主 reviewer + secondary_reviewers（2.0.0）。

    secondary 用于「同一节点需要多个独立视角」的场景，例如 N6/N7/N8 除常规审阅外
    还要由 mm-figure-table-benchmarker 出 B1（图表/表格文献对标）结论。
    """
    info = NODES[node]
    out = []
    if info.get("reviewer"):
        out.append(info["reviewer"])
    out.extend(info.get("secondary_reviewers") or [])
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


def reviewer_required_skills(node, agent=None):
    """某审阅者在本节点必须声明的 skill 清单。

    2.0.0：同一节点可能有多个审阅视角——
      - 主 reviewer：沿用节点 required_skills（它要核对执行产物与规范）；
      - secondary reviewer（如 mm-figure-table-benchmarker）：只需它自己的专项规范，
        不应被强制声明执行方规范（mm-visualization 等），否则角色边界混乱。
    """
    info = NODES[node]
    secondaries = info.get("secondary_reviewers") or []
    if agent and agent in secondaries and agent != info.get("reviewer"):
        return SECONDARY_REVIEWER_SKILLS.get(agent, [])
    return info.get("skills", [])


def require_review_skills(node, skills, agent=None):
    declared = normalized_skill_set(skills.split(","))
    required_list = reviewer_required_skills(node, agent)
    missing_keys = normalized_skill_set(required_list) - declared
    if missing_keys:
        # 报告原始注册名（带插件前缀），便于直接复制到 --skills
        missing = [s for s in required_list if skill_basename(s) in missing_keys]
        sys.exit(f"[state_utils] 审阅前必读 Skill 未声明: {', '.join(missing)}")


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
    """节点产物快照哈希：文件→sha256；目录→递归文件清单哈希（相对路径排序拼接，64KB 分块）。"""
    paths = [p.strip() for p in NODES[node].get("artifact", "").split(",") if p.strip()]
    snapshot = {}
    for p in paths:
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
MCP_MANDATORY_NODES = {
    "N1": "论文搜索 MCP + Tavily/tokenhub 全网搜索 MCP",
    "N3": "Context7 MCP + 论文搜索 MCP",
    "N4": "Context7 MCP + GitHub MCP",
    "N5": "GitHub MCP + Tavily/tokenhub 全网搜索 MCP",
    "N6": "论文搜索 MCP + Tavily/WebSearch（必要时 Context7）",
    "N7": "论文搜索 MCP",
}
MCP_CALLS_FILE = os.path.join(STATE_DIR, "reports", "mcp-calls.jsonl")
# Deep Research 介入留痕（dr-note 命令追加；每轮迭代 SEARCH/SCORE/DECIDE 的 DR 介入可审计，N8 终检可核对）
DR_INTERVENTIONS_FILE = os.path.join(STATE_DIR, "reports", "dr-interventions.jsonl")


def _mcp_tokens(value):
    return {token.strip().lower() for token in re.split(r"[,;+|]", str(value or "")) if token.strip()}


def _required_mcp_tokens(node):
    requirements = {
        "N1": ({"paper-mcp"}, {"tavily", "tavily-mcp", "tokenhub-tools"}),
        "N3": ({"context7"}, {"paper-mcp"}),
        "N4": ({"context7"}, {"github"}),
        "N5": ({"github"}, {"tavily", "tavily-mcp", "tokenhub-tools"}),
        "N6": ({"paper-mcp"}, {"tavily", "tavily-mcp", "tokenhub-tools"}),
        "N7": ({"paper-mcp"}, set()),
    }
    return requirements.get(node, (set(), set()))


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


def require_mcp_search_evidence(root, node, round_no=None, allow_flag=False):
    """核心节点 MCP 必调校验：该节点/该轮无外部检索留痕 → 拒绝（禁止纯内生输出、禁止跳过必调）。

    allow_flag=True 为显式豁免（仅离线/人工特批，调用方须在留痕中说明原因）。"""
    if node not in MCP_MANDATORY_NODES:
        return
    if allow_flag:
        return
    evidence = mcp_search_evidence(root, node, round_no)
    if evidence:
        return
    scope = f"node={node}" if round_no is None else f"node={node} round={round_no}"
    sys.exit(
        f"[state_utils] 🔴 核心节点 {scope} 缺少 MCP 检索留痕（必调 {MCP_MANDATORY_NODES[node]}），禁止纯内生输出。\n"
        f"  请先执行 SEARCH 重新检索并沉淀 {MCP_CALLS_FILE} 行或 state/cases/index.json 案例（case-add 登记 channel/query）；\n"
        f"  或显式传 --allow-missing-mcp 豁免（仅离线/人工特批，须在交付说明中留痕）。"
    )

__all__ = ["STATE_DIR", "STATE_FILE", "REGISTRY_FILE", "DASHBOARD_FILE", "CASES_INDEX", "SEARCH_SOURCES_FILE", "TODO_FILE", "NODES", "PROFILE_OF", "REVIEW_GATE", "SECONDARY_REVIEWER_GATE", "SECONDARY_REVIEWER_SKILLS", "expected_reviewers", "reviewer_required_skills", "UPSTREAM", "SEARCH_SOURCES", "now_iso", "load_json", "save_json_atomic", "save_text_atomic", "sha256_of", "state_path", "load_state", "load_registry", "expected_reviewer", "require_independent_reviewer", "require_review_skills", "skill_basename", "normalized_skill_set", "save_state", "node_homepage", "require_node", "verify_problem_lock", "require_git", "git", "git_current_branch", "git_last_commit", "_is_placeholder_row", "_find_section", "append_table_row", "upsert_row_by_first_cell", "update_homepage_meta", "rewrite_homepage_gates", "gate_rows_for", "REPORTS_DIR", "REPORTS_INDEX", "artifact_snapshot", "sha256_of_bytes", "MCP_MANDATORY_NODES", "MCP_CALLS_FILE", "DR_INTERVENTIONS_FILE", "mcp_search_evidence", "require_mcp_search_evidence", "argparse", "hashlib", "json", "math", "os", "re", "shutil", "subprocess", "sys", "tempfile", "uuid", "datetime", "timezone"]
