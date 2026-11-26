"""MM case-search —— 优秀论文案例库结构化检索核心（纯函数，无副作用）。

移植自 math-modeling-skill-pro 仓库 scripts/search_cases.py（作者授权融合）。
检索对象：skills/mathematical-modeling/assets/case-library/ 下的 139 张案例卡索引
（2012—2025 CUMCM 优秀论文决策记忆，非论文原文库）。

用法（经 state_utils.py case-search 子命令暴露）：
    python state/state_utils.py case-search "小样本 多指标 综合评价 稳健性" --top 6
    python state/state_utils.py case-search "多目标 约束 调度" --type 优化 --year 2020

定位规则（fail-closed）：
    1. --skill-root <技能安装根> 显式传入（推荐：指向包含 skills/ 的目录）；
    2. 环境变量 MM_SKILL_ROOT；
    3. 从本模块 __file__ 向上探测包含 skills/mathematical-modeling/assets/case-library 的祖先目录。
    均未找到时抛 FileNotFoundError，调用方应报错并提示传 --skill-root，不静默降级。
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

# 中文术语 → 别名（英文/近义），用于查询词扩展；tag: 前缀进入加权检索
ALIASES: dict[str, list[str]] = {
    "预测": ["prediction", "forecast", "回归", "时间序列"],
    "评价": ["evaluation", "ranking", "综合评价", "决策"],
    "优化": ["optimization", "最优", "调度", "规划", "分配"],
    "分类": ["classification", "判别", "识别"],
    "聚类": ["clustering", "分群"],
    "网络": ["network", "graph", "路径", "节点", "运输"],
    "机理": ["mechanism", "ode", "pde", "动力学", "微分方程"],
    "仿真": ["simulation", "monte carlo", "蒙特卡洛", "随机模拟"],
    "小样本": ["small sample", "灰色预测", "bootstrap"],
    "多目标": ["multi-objective", "pareto", "nsga", "epsilon constraint"],
    "不确定性": ["uncertainty", "robust", "稳健", "敏感性", "scenario"],
}

CASE_LIB_REL = os.path.join("skills", "mathematical-modeling", "assets", "case-library", "index.json")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower().replace("＋", "+")).strip()


def tokens(text: str) -> list[str]:
    """查询/文档分词：英文词 + 数字 + 中文二字片段 + 别名术语 + tag:规范术语。"""
    text = normalize(text)
    words = re.findall(r"[a-z][a-z0-9+.-]{1,}|\d+(?:\.\d+)?", text)
    chunks = re.findall(r"[\u3400-\u9fff]+", text)
    chinese: list[str] = []
    for chunk in chunks:
        chinese.extend(chunk[index:index + 2] for index in range(max(1, len(chunk) - 1)))
        chinese.extend(term for term in ALIASES if term in chunk)
    expanded = words + chinese
    for canonical, variants in ALIASES.items():
        if canonical in text or any(variant in text for variant in variants):
            expanded.append(f"tag:{canonical}")
    return expanded


def field_text(case: dict[str, Any]) -> str:
    return " ".join([
        str(case.get("title") or ""),
        str(case.get("core_problem") or ""),
        str(case.get("data_features") or ""),
        " ".join(case.get("problem_types") or []),
        " ".join(case.get("models") or []),
        " ".join(case.get("keywords") or []),
        " ".join(case.get("validation_methods") or []),
        " ".join(case.get("transferable_patterns") or []),
        str(case.get("search_text") or ""),
    ])


def score_cases(query: str, cases: list[dict[str, Any]]) -> list[tuple[float, dict[str, Any], list[str]]]:
    """TF-IDF 风格加权：tag: 术语权重更高；查询中显式出现的类型/模型名额外加分。

    返回 [(score, case, matched_tokens)]，按分数降序、年份降序、case_id 升序。"""
    query_tokens = tokens(query)
    if not query_tokens:
        return []
    documents = [Counter(tokens(field_text(case))) for case in cases]
    document_frequency = Counter()
    for document in documents:
        document_frequency.update(document.keys())
    query_counts = Counter(query_tokens)
    count = len(cases)
    ranked: list[tuple[float, dict[str, Any], list[str]]] = []
    for case, document in zip(cases, documents):
        score = 0.0
        matched: list[str] = []
        for token, query_weight in query_counts.items():
            frequency = document.get(token, 0)
            if not frequency:
                continue
            inverse = math.log((count + 1) / (document_frequency[token] + 0.5)) + 1
            boost = 3.5 if token.startswith("tag:") else 1.0
            score += query_weight * inverse * boost * (1 + math.log(frequency))
            matched.append(token.removeprefix("tag:"))
        normalized_query = normalize(query)
        for value in (case.get("problem_types") or []) + (case.get("models") or []):
            if normalize(str(value)) and normalize(str(value)) in normalized_query:
                score += 4.0
        if score > 0:
            ranked.append((score, case, sorted(set(matched))))
    ranked.sort(key=lambda item: (-item[0], -int(item[1]["year"]), item[1]["case_id"]))
    return ranked


def locate_skill_root(skill_root: str | os.PathLike | None = None) -> Path:
    """定位技能安装根（包含 skills/ 的目录）。

    顺序与权威性（fail-closed，禁止静默降级）：
        1. 显式 --skill-root：权威参数。若该目录下无案例库索引，立即报错，
           不回退到其他候选（避免用户指定错误却悄悄用了别的库）。
        2. 环境变量 MM_SKILL_ROOT：同样权威，指定即校验，不符即报错。
        3. 未提供任何显式根时，从本模块 __file__ 向上探测包含案例库的祖先目录。
    """
    if skill_root:
        candidate = Path(skill_root)
        index = candidate / CASE_LIB_REL
        if index.is_file():
            return candidate
        raise FileNotFoundError(
            f"--skill-root {str(candidate)!r} 下未找到案例库索引"
            f"（期望 {CASE_LIB_REL}）。请检查参数是否指向包含 skills/ 的技能安装根。"
        )
    env_root = os.environ.get("MM_SKILL_ROOT")
    if env_root:
        candidate = Path(env_root)
        index = candidate / CASE_LIB_REL
        if index.is_file():
            return candidate
        raise FileNotFoundError(
            f"环境变量 MM_SKILL_ROOT={env_root!r} 下未找到案例库索引"
            f"（期望 {CASE_LIB_REL}）。请修正环境变量或改用 --skill-root。"
        )
    current = Path(__file__).resolve()
    for parent in (current, *current.parents):
        if (parent / CASE_LIB_REL).is_file():
            return parent
    raise FileNotFoundError(
        "未定位到案例库索引（skills/mathematical-modeling/assets/case-library/index.json）。"
        "请通过 --skill-root 传入技能安装根目录（包含 skills/ 的目录），或设置环境变量 MM_SKILL_ROOT。"
    )


def load_cases(index_path: str | os.PathLike) -> list[dict[str, Any]]:
    """读取案例库 index.json 并返回 cases 列表。"""
    import json
    payload = json.loads(Path(index_path).read_text(encoding="utf-8"))
    return list(payload.get("cases") or [])


def filter_cases(cases: list[dict[str, Any]], year: int | None = None,
                 problem_type: str | None = None, model: str | None = None) -> list[dict[str, Any]]:
    """按年份/问题类型/模型过滤；问题类型与模型使用归一化子串匹配。"""
    out = cases
    if year is not None:
        out = [case for case in out if int(case["year"]) == year]
    if problem_type:
        needle = normalize(problem_type)
        out = [case for case in out if needle in normalize(" ".join(case.get("problem_types") or []))]
    if model:
        needle = normalize(model)
        out = [case for case in out if needle in normalize(" ".join(case.get("models") or []))]
    return out
