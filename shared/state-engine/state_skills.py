"""技能编排 CLI 命令（skill-plan / skill-list / skill-audit）。

这是"协调层 → 专业 skill"的接线点：
1. `skill-plan`  为某节点/某任务生成本次派发必须加载的专业 skill 清单，
                 落盘 `state/skill-routing/<node>.json`（runtime manifest）。
2. `skill-list`  列出本机发现到的 skill 与其来源（排障用，也可人工核对匹配结果）。
3. `skill-audit` 校验"节点声明的 skill 是否真的被加载"（硬门禁调用）。

设计要点：
- manifest 只记录**本次实际匹配结果**（含打分依据与来源路径），不写死任何 skill 名。
- manifest 落盘后 node-start / node-finish 才有据可查；专业 skill 升级后重跑
  `skill-plan` 即刷新，无需改动本插件代码。
"""
from __future__ import annotations

import json
import os
import sys

from state_defs import (
    NODES, STATE_DIR, load_state, now_iso, save_json_atomic, save_state,
    skill_basename, normalized_skill_set,
)

ROUTING_DIR = os.path.join(STATE_DIR, "skill-routing")


def _routing_dir(root: str) -> str:
    return os.path.join(root, ROUTING_DIR)


def _manifest_path(root: str, node: str) -> str:
    return os.path.join(_routing_dir(root), f"{node}.json")


def _import_router():
    """按需导入路由模块（shared/skill-routing 不在 sys.path 时临时补入）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "skill-routing"),
        os.path.join(here, "..", "..", "shared", "skill-routing"),
        os.path.join(here, "skill-routing"),
    ]
    for cand in candidates:
        cand = os.path.abspath(cand)
        if os.path.isfile(os.path.join(cand, "skill_matcher.py")):
            if cand not in sys.path:
                sys.path.insert(0, cand)
            import skill_discovery
            import skill_matcher
            return skill_discovery, skill_matcher
    raise RuntimeError(
        "未找到 skill-routing 模块（期望 shared/skill-routing/{skill_discovery,skill_matcher}.py）。"
        "请确认插件完整安装，或在项目 state/ 中重跑 init --sync-runtime。"
    )


def build_manifest(root: str, node: str, task: str = "", extra_capabilities: list[str] | None = None,
                   extra_roots: list[str] | None = None) -> dict:
    """生成一个节点的 skill 派发清单（含能力→skill 的匹配依据）。"""
    discovery, matcher = _import_router()
    taxonomy = matcher.load_taxonomy()
    skills = discovery.discover(root, extra=extra_roots)

    if task:
        plan = matcher.plan_for_task(task, taxonomy, skills)
        plan["stage"] = node
        plan["mode"] = "task"
    else:
        plan = matcher.plan_for_stage(node, taxonomy, skills,
                                      extra_capabilities=extra_capabilities)
        plan["mode"] = "stage"

    # 节点固有 required_skills 始终是硬要求，与动态匹配结果合并
    required = [skill_basename(s) for s in NODES.get(node, {}).get("skills", [])]
    dynamic = [s for s in plan["primary_skills"] if s not in required]

    manifest = {
        "schema_version": "1.0",
        "node": node,
        "node_name": NODES.get(node, {}).get("name", node),
        "generated_at": now_iso(),
        "mode": plan["mode"],
        "task": task or "",
        "required_skills": required,
        "dynamic_skills": dynamic,
        "supporting_skills": [s for s in plan["supporting_skills"] if s not in required and s not in dynamic],
        "capabilities": plan["capabilities"],
        "unresolved": plan["unresolved"],
        "policy": plan.get("policy", {}),
        "skill_index_size": len(skills),
        "taxonomy_version": taxonomy.get("version", ""),
    }
    manifest["must_load"] = sorted(set(required) | set(dynamic))
    return manifest


def cmd_skill_plan(args):
    root = os.path.abspath(args.dir)
    node = args.node
    if node not in NODES:
        sys.exit(f"[state_utils] 未知节点: {node}（可选: {', '.join(NODES)}）")
    extra_caps = [c.strip() for c in (args.capability or "").split(",") if c.strip()]
    extra_roots = [r for r in (args.skill_root or []) if r]
    manifest = build_manifest(root, node, task=args.task, extra_capabilities=extra_caps,
                             extra_roots=extra_roots)
    if args.apply:
        os.makedirs(_routing_dir(root), exist_ok=True)
        save_json_atomic(_manifest_path(root, node), manifest)
        print(f"[state_utils] skill 派发清单已落盘: {os.path.relpath(_manifest_path(root, node), root)}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest["unresolved"] and not args.allow_unresolved:
        print("[state_utils] ⚠ 存在未解决的能力需求（本机无匹配 skill）："
              + "；".join(manifest["unresolved"]), file=sys.stderr)


def cmd_skill_list(args):
    discovery, matcher = _import_router()
    root = os.path.abspath(args.dir)
    skills = discovery.discover(root)
    if args.capability:
        taxonomy = matcher.load_taxonomy()
        ranked = matcher.match_capability(args.capability, taxonomy, skills)
        payload = {"capability": args.capability, "candidates": ranked}
    else:
        rows = [{
            "skill_id": s["skill_id"],
            "scope": s.get("scope", ""),
            "plugin": s.get("plugin", ""),
            "disabled": bool(s.get("disabled")),
            "description": s["description"][:160],
            "path": s["path"],
        } for s in skills]
        if args.scope:
            rows = [r for r in rows if r["scope"] == args.scope]
        payload = {"total": len(rows), "skills": rows}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_skill_audit(args):
    """硬门禁：节点声明的 --skills 必须覆盖 manifest 的 must_load。"""
    root = os.path.abspath(args.dir)
    node = args.node
    path = _manifest_path(root, node)
    if not os.path.isfile(path):
        if args.require_manifest:
            sys.exit(f"[state_utils] 节点 {node} 缺少 skill 派发清单（先运行 skill-plan {node} --apply）")
        print(json.dumps({"node": node, "manifest": "missing", "ok": True,
                          "note": "未启用 skill 路由（缺少 manifest，按未启用处理）"}, ensure_ascii=False))
        return
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    declared = normalized_skill_set((args.skills or "").split(","))
    must = normalized_skill_set(manifest.get("must_load", []))
    missing = must - declared
    extra = declared - must
    result = {
        "node": node,
        "manifest": "present",
        "generated_at": manifest.get("generated_at"),
        "must_load": sorted(must),
        "declared": sorted(declared),
        "missing": sorted(missing),
        "extra": sorted(extra),
        "ok": not missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if missing:
        sys.exit(f"[state_utils] 节点 {node} 未加载派发清单要求的专业 skill: {', '.join(sorted(missing))}")


def require_skill_manifest(root: str, node: str) -> dict | None:
    """node-start 用：返回 manifest（存在时），供门禁检查与派发提示。"""
    path = _manifest_path(root, node)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
