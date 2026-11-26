"""能力匹配层：把「阶段/任务需要什么能力」映射到「本机哪个 skill 最匹配」。

架构纪律：
- 输入只有两样：`capability_taxonomy.json`（协调层知识）与 `skill_discovery.discover()`
  的运行时结果（专业 skill 自报的 description）。
- 输出是排序后的候选清单 + 打分依据，不缓存、不记忆任何具体 skill 名称。
- 换 skill、升级 skill、新增 skill 之后重新跑一次即可得到新结果，插件无需改动。

打分（可调，见 taxonomy.selection_policy）：
    name_hits        * name_weight          # skill 名或目录名命中关键词（强信号）
    description_hits * description_weight   # description 命中关键词（弱信号）
    stage_bonus      * stage_weight         # 该 skill 已被本阶段其他能力选中（协同加权）
硬约束：必须至少命中 name 或 description 一次；disabled skill 默认排除。
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

TAXONOMY_PATH = Path(__file__).with_name("capability_taxonomy.json")

_ASCII_KW = re.compile(r"^[a-z0-9][a-z0-9 ._/+&-]*$")


def _keyword_hit(keyword: str, haystack: str) -> bool:
    """关键词命中判定。

    纯 ASCII 关键词按词边界匹配——否则 `tex` 会命中 `contextual`、`pad` 会命中
    `padding`，产生大量假匹配；含中文的关键词用子串匹配（中文无空格分词）。
    """
    key = keyword.strip().casefold()
    if not key:
        return False
    if _ASCII_KW.match(key):
        pattern = r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])"
        return re.search(pattern, haystack) is not None
    return key in haystack


def load_taxonomy(path: Path | None = None) -> dict:
    with open(path or TAXONOMY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _policy(taxonomy: dict) -> dict:
    policy = taxonomy.get("selection_policy") or {}
    return {
        "max_primary": int(policy.get("max_primary", 3)),
        "max_supporting": int(policy.get("max_supporting", 4)),
        "max_stage_primary": int(policy.get("max_stage_primary", 4)),
        "per_capability_primary": int(policy.get("per_capability_primary", 1)),
        "min_score": float(policy.get("min_score", 3.0)),
        "name_weight": float(policy.get("name_weight", 3.0)),
        "description_weight": float(policy.get("description_weight", 1.0)),
        "stage_weight": float(policy.get("stage_weight", 1.5)),
        "require_name_or_description_hit": bool(policy.get("require_name_or_description_hit", True)),
        "exclude_disabled_skills": bool(policy.get("exclude_disabled_skills", True)),
        "routing_skills": list(policy.get("routing_skills") or []),
    }


def _haystack(skill: dict) -> tuple[str, str]:
    name = f"{skill.get('skill_id', '')} {skill.get('dir_name', '')}".casefold()
    desc = str(skill.get("description", "")).casefold()
    return name, desc


def _count_hits(keywords: list[str], name: str, desc: str) -> tuple[int, int, list[str]]:
    """统计关键词命中：返回 (name 命中数, desc 命中数, 命中关键词列表)。

    关键词按子串匹配——技能描述多为自然语言短语，子串匹配比词切分更稳，
    且对中文（无空格分词）友好。命中数按"不同关键词"计，避免同一词反复加权。
    """
    name_hits = 0
    desc_hits = 0
    matched: list[str] = []
    for kw in keywords:
        key = str(kw).strip()
        if not key:
            continue
        in_name = _keyword_hit(key, name)
        in_desc = _keyword_hit(key, desc)
        if in_name:
            name_hits += 1
        if in_desc:
            desc_hits += 1
        if in_name or in_desc:
            matched.append(key)
    return name_hits, desc_hits, matched


def score_skill(skill: dict, keywords: list[str], policy: dict) -> dict:
    name, desc = _haystack(skill)
    name_hits, desc_hits, matched = _count_hits(keywords, name, desc)
    score = name_hits * policy["name_weight"] + desc_hits * policy["description_weight"]
    # 命中不同关键词越多，说明能力覆盖越广，轻微加权（对数抑制，防止长描述刷分）
    if matched:
        score += math.log2(1 + len(set(matched)))
    return {
        "skill_id": skill["skill_id"],
        "score": round(score, 3),
        "name_hits": name_hits,
        "description_hits": desc_hits,
        "matched_keywords": sorted(set(matched)),
        "scope": skill.get("scope", ""),
        "plugin": skill.get("plugin", ""),
        "path": skill.get("path", ""),
    }


def match_capability(capability_id: str, taxonomy: dict, skills: list[dict],
                     exclude_skills: set[str] | None = None) -> list[dict]:
    """为单个能力挑选候选 skill，按分数降序（同分按名称稳定排序）。"""
    policy = _policy(taxonomy)
    capability = next((c for c in taxonomy.get("capabilities", []) if c["id"] == capability_id), None)
    if capability is None:
        raise KeyError(f"未定义的能力: {capability_id}")
    excluded = {s.casefold() for s in (exclude_skills or set())}
    # 纯编排入口不是专业执行者：加载它们等于把流程再套一层，故不参与匹配
    excluded |= {s.casefold() for s in policy["routing_skills"]}
    results: list[dict] = []
    for skill in skills:
        if policy["exclude_disabled_skills"] and skill.get("disabled"):
            continue
        if skill["skill_id"].casefold() in excluded:
            continue
        scored = score_skill(skill, capability.get("keywords", []), policy)
        if policy["require_name_or_description_hit"] and not scored["matched_keywords"]:
            continue
        if scored["score"] < policy["min_score"]:
            continue
        scored["capability"] = capability_id
        results.append(scored)
    results.sort(key=lambda r: (-r["score"], r["skill_id"].casefold()))
    return results


def plan_for_stage(stage: str, taxonomy: dict, skills: list[dict],
                   exclude_skills: set[str] | None = None,
                   extra_capabilities: list[str] | None = None) -> dict:
    """生成某阶段的能力→skill 派发计划。

    返回结构：
      capabilities: [{capability, label, primary: [...], supporting: [...]}]
      primary_skills: 去重后的"必须加载"清单（硬门禁用）
      supporting_skills: 建议加载
      unresolved: 有该能力需求但本机找不到合适 skill（如实报告，不硬凑）
    """
    policy = _policy(taxonomy)
    stage_map = taxonomy.get("stage_capabilities", {})
    cap_ids = list(stage_map.get(stage) or [])
    for extra in extra_capabilities or []:
        if extra not in cap_ids:
            cap_ids.append(extra)

    chosen_primary: list[str] = []
    capability_rows: list[dict] = []
    unresolved: list[str] = []
    stage_cap = policy["max_stage_primary"]

    for cap_id in cap_ids:
        try:
            ranked = match_capability(cap_id, taxonomy, skills, exclude_skills)
        except KeyError:
            unresolved.append(f"{cap_id}（能力未在词表中定义）")
            continue
        if not ranked:
            unresolved.append(f"{cap_id}（本机未找到匹配 skill）")
            capability_rows.append({
                "capability": cap_id,
                "label": _label(taxonomy, cap_id),
                "primary": [], "supporting": [], "status": "unresolved",
            })
            continue
        # 已在本阶段 primary 中的候选跳过，避免同一 skill 占多个能力位
        fresh = [r for r in ranked if r["skill_id"] not in chosen_primary]
        # 一个能力只取最强的 per_capability_primary 个，其余降为 supporting——
        # 同质技能并列 primary 会让子 Agent 同时加载多份互相覆盖的规范
        quota = min(policy["per_capability_primary"], max(0, stage_cap - len(chosen_primary)))
        primary = fresh[:quota]
        rest = fresh[quota: quota + policy["max_supporting"]]
        chosen_primary.extend(r["skill_id"] for r in primary)
        capability_rows.append({
            "capability": cap_id,
            "label": _label(taxonomy, cap_id),
            "primary": primary,
            "supporting": rest,
            "status": "matched" if primary else ("deferred" if fresh else "supporting-only"),
        })

    supporting_skills: list[str] = []
    for row in capability_rows:
        for item in row["supporting"]:
            if item["skill_id"] not in chosen_primary and item["skill_id"] not in supporting_skills:
                supporting_skills.append(item["skill_id"])

    return {
        "stage": stage,
        "capabilities": capability_rows,
        "primary_skills": chosen_primary,
        "supporting_skills": supporting_skills,
        "unresolved": unresolved,
        "policy": {k: policy[k] for k in ("max_primary", "max_supporting", "max_stage_primary", "min_score")},
    }


def _label(taxonomy: dict, capability_id: str) -> str:
    for cap in taxonomy.get("capabilities", []):
        if cap["id"] == capability_id:
            return cap.get("label", capability_id)
    return capability_id


def plan_for_task(task_text: str, taxonomy: dict, skills: list[dict],
                  exclude_skills: set[str] | None = None) -> dict:
    """按自由文本任务描述推断能力（用于非阶段场景：单点请求、聊天直呼）。

    只做能力识别，不绑定阶段——识别出的能力再走 match_capability。
    """
    text = (task_text or "").casefold()
    matched_caps: list[dict] = []
    for cap in taxonomy.get("capabilities", []):
        keywords = cap.get("keywords", [])
        name_hits, _, matched = _count_hits(keywords, "", text)
        if name_hits:
            matched_caps.append({
                "capability": cap["id"],
                "label": cap.get("label", cap["id"]),
                "matched_keywords": sorted(set(matched)),
                "hits": name_hits,
            })
    matched_caps.sort(key=lambda r: (-r["hits"], r["capability"]))
    rows: list[dict] = []
    unresolved: list[str] = []
    primary_skills: list[str] = []
    supporting_skills: list[str] = []
    policy = _policy(taxonomy)
    for cap in matched_caps:
        ranked = match_capability(cap["capability"], taxonomy, skills, exclude_skills)
        fresh = [r for r in ranked if r["skill_id"] not in primary_skills]
        if not fresh:
            unresolved.append(f"{cap['capability']}（本机未找到匹配 skill）")
            continue
        primary = fresh[: policy["max_primary"]]
        rest = fresh[len(primary): len(primary) + policy["max_supporting"]]
        primary_skills.extend(r["skill_id"] for r in primary)
        for item in rest:
            if item["skill_id"] not in primary_skills and item["skill_id"] not in supporting_skills:
                supporting_skills.append(item["skill_id"])
        rows.append({**cap, "primary": primary, "supporting": rest})
    return {
        "task": task_text,
        "capabilities": rows,
        "primary_skills": primary_skills,
        "supporting_skills": supporting_skills,
        "unresolved": unresolved,
        "policy": {k: policy[k] for k in ("max_primary", "max_supporting", "min_score")},
    }
