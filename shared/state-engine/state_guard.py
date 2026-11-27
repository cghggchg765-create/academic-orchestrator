#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""节点完成守卫（单一收口）。

P0 审计的核心发现：同一套门禁存在**多条互不校验的写入旁路**——
  ① node-finish        （有校验，但可跳过 node-start 绕过）
  ② round-decide       （有 deliverables 校验，但不查上游/本节点门禁）
  ③ scope-promote      （直接写 completed）
  ④ result-ingest      （直接写 completed，无任何校验）

本模块提供 `require_completion_allowed(root, node, ...)`，上述四条路径**必须**调用它。
这样"能否标完成"只有一个判定点，新增路径不可能再忘。

守卫做五件事：
  1. 必须曾经 node-start（存在 start_artifact_hash）——否则技能清单/上游校验都会被跳过
  2. 上游节点全部 completed，且上游声明的全部门禁 PASS/auto_passed/confirmed
  3. 上游产物哈希未漂移（防"审阅后偷偷改产物"）
  4. 本节点必读 skill 已声明（若传了 skills）
  5. 交付物齐备（checkpoint + 真实产物）
"""
from __future__ import annotations

import os

from state_defs import (
    NODES, UPSTREAM, REVIEW_GATE, artifact_snapshot, load_state,
    skill_basename, normalized_skill_set,
)

PASS_STATES = {"PASS", "auto_passed", "confirmed"}


def _upstream_gates(node):
    """上游节点参与推进判定的全部门禁（H 类人工门禁为 advisory，不阻塞）。"""
    out = []
    for up_node, _ in UPSTREAM.get(node, []):
        gates = list(NODES.get(up_node, {}).get("gates") or [])
        rg = REVIEW_GATE.get(up_node)
        if rg and rg not in gates:
            gates.append(rg)
        out.append((up_node, [g for g in gates if not g.startswith("H")]))
    return out


def check_not_started(root, node, state=None):
    """P0-3：非 N0 节点若从未 node-start，返回错误信息；否则 None。"""
    if node == "N0":
        return None
    st = state or load_state(root)
    if not (st.get("nodes", {}).get(node) or {}).get("start_artifact_hash"):
        return (f"[state_utils] 拒绝：节点 {node} 从未 node-start（无 start_artifact_hash）。\n"
                f"  必须先 node-start 以登记开工快照并生成 skill 派发清单，再执行/收工。\n"
                f"  否则技能清单校验与上游前置校验都会被跳过。")
    return None


def check_upstream(root, node, state=None, require_artifact_present=False):
    """上游 completed + 门禁 PASS + 产物哈希未漂移。返回错误列表。

    `require_artifact_present` 额外要求上游声明的产物路径在磁盘上存在
    （node-start 用它拦"上游产物被删了还继续开工"）。

    这是"上游能否推进"的唯一实现：node-start / node-finish / round-start /
    round-decide / result-ingest / scope-promote 全部调用本函数，不得各写一套。
    """
    st = state or load_state(root)
    errs = []
    for up_node, gates in _upstream_gates(node):
        up = st.get("nodes", {}).get(up_node) or {}
        if up.get("status") != "completed":
            errs.append(f"上游 {up_node} 状态为 {up.get('status', 'pending')}，需 completed")
        for g in gates:
            gs = (st.get("gates", {}).get(g) or {}).get("status", "pending")
            if gs not in PASS_STATES:
                errs.append(f"上游 {up_node} 门禁 {g}={gs}（未通过）——须先走完"
                            f"「审阅→修改→再审阅」并 PASS")
        # 产物漂移：审阅后改了上游产物 → 下游不得开工
        recorded = up.get("artifact_hash") or {}
        if recorded:
            current = artifact_snapshot(root, up_node)
            changed = [k for k, v in current.items() if recorded.get(k) != v]
            if changed:
                errs.append(f"上游 {up_node} 产物在登记后已变更（{', '.join(changed)}）"
                            f"——须重审后再推进")
        if require_artifact_present:
            for art_path in str(NODES.get(up_node, {}).get("artifact") or "").split(","):
                art_path = art_path.strip()
                if art_path and not os.path.exists(os.path.join(root, art_path)):
                    errs.append(f"上游 {up_node} 的产物 {art_path} 不存在")
    return errs


def check_own_gates(node, state):
    """P0-2：本节点除迭代动态门禁（S<n>-*）与 H 类外的全部门禁须 PASS。"""
    errs = []
    for g in (NODES.get(node, {}).get("gates") or []):
        if g.startswith("S") or g.startswith("H"):
            continue
        gs = (state.get("gates", {}).get(g) or {}).get("status", "pending")
        if gs not in PASS_STATES:
            errs.append(f"本节点门禁 {g}={gs}（未通过）")
    return errs


# 模块级别名：require_completion_allowed 的关键字参数也叫 check_own_gates，
# 在函数体内会遮蔽同名函数，故内部一律通过该别名调用。
_own_gate_errors = check_own_gates


def check_skills(node, skills):
    """本节点 required_skills 是否全部声明。"""
    required = NODES.get(node, {}).get("skills") or []
    if not required:
        return []
    declared = normalized_skill_set(str(skills or "").split(","))
    missing = normalized_skill_set(required) - declared
    if not missing:
        return []
    # 报原始注册名（带插件前缀），可直接复制进 --skills
    originals = [s for s in required if skill_basename(s) in missing]
    return [f"必读 skill 未声明: {', '.join(originals)}"
            f"（把这些名字填进 --skills，逗号分隔）"]


def require_completion_allowed(root, node, *, skills=None, allow_no_start=False,
                               allow_empty=False, allow_no_checkpoint=False,
                               check_own_gates=True):
    """统一完成守卫：不满足则以 SystemExit 拒绝。所有写 completed 的路径都必须调用。"""
    state = load_state(root)
    errs = []

    if not allow_no_start:
        msg = check_not_started(root, node, state)
        if msg:
            raise SystemExit(msg)

    errs.extend(check_upstream(root, node, state))
    # 参数名 check_own_gates 与模块级同名函数冲突，参数会遮蔽函数：
    # 直接写 check_own_gates(node, state) 实际调用的是 bool，必然 TypeError
    # （True→'bool' object is not callable，False→分支根本不进）。
    # 用模块级别名避开遮蔽，同时保留参数名不破坏调用方 API。
    if check_own_gates:
        errs.extend(_own_gate_errors(node, state))
    if skills is not None:
        errs.extend(check_skills(node, skills))
    if errs:
        raise SystemExit(
            f"[state_utils] 拒绝：节点 {node} 不满足完成条件（{len(errs)} 项）：\n  - "
            + "\n  - ".join(errs)
            + "\n  逐条修完后重跑本命令；全绿才会写 completed。"
        )

    # 交付物（checkpoint + 真实产物）——复用 node 模块，避免逻辑重复
    from state_nodes import require_node_deliverables
    require_node_deliverables(root, node, allow_empty=allow_empty,
                              allow_no_checkpoint=allow_no_checkpoint)


# ------------------------------------------------------------------ 路径安全

def safe_component(value, label="name"):
    """校验单段标识符，防路径穿越（P0-8）。"""
    import re as _re
    s = str(value or "").strip()
    if not _re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", s):
        raise SystemExit(f"[state_utils] 非法 {label}: {value!r}"
                         f"（只允许字母数字开头，含 . _ -，长度 1-64）")
    return s


def assert_within(root, path, label="路径"):
    """断言 path 位于 root 之内（P0-8）。"""
    root_abs = os.path.abspath(root)
    p = os.path.abspath(path)
    try:
        rel = os.path.relpath(p, root_abs)
    except ValueError:
        raise SystemExit(f"[state_utils] {label} 越界: {path}")
    if os.path.isabs(rel) or rel == os.pardir or rel.startswith(os.pardir + os.sep):
        raise SystemExit(f"[state_utils] {label} 越界（必须在项目根内）: {path}")
    return p
