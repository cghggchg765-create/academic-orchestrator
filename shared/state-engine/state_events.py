#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁事件流（append-only 审计日志）。

解决的问题（审计 P2-10/P2-10b）：
  - 门禁只有"当前值"，覆盖式 update → 无法回答"V1 从 FAIL 变 PASS 是谁、何时、凭什么"
  - --allow-missing-* 豁免只用于提前 return，不留任何机器可读痕迹 → 事后无法区分
    "真 PASS" 与 "豁免 PASS"，直接削弱门禁可信度

设计：每次门禁变更 append 一条到 state/reports/gate-events.jsonl，
字段含 from/to/actor/source_cmd/evidence/evidence_sha256/exemption/prev_hash（哈希链）。
只追加、不修改——历史不可篡改（改任一条则后续哈希链断裂）。

2.0.0 纠正留痕闭环（对应 academic-orchestration「运行中纠正」协议）：
  - 主 Agent 每次 SendMessage 纠正 → ``correction-add`` 写 state/reports/corrections.jsonl
  - 子 Agent 本人回执 → ``correction-ack`` 写 state/reports/correction-acks.jsonl
  - A3/B1 门禁 PASS 前校验「同一 node 的每条纠正都有同一 agent_id 的回执」，
    否则判 CORRECTION_UNACKED；事件流哈希链断裂判 CORRECTION_LEDGER_TAMPERED
  - 派发句柄 state/agents/<id>/dispatch.json：dispatch-start/close/heartbeat 维护生命周期，
    超过 ttl 仍 running 的记录判僵尸，由 project-audit 汇总暴露
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

from state_defs import (
    NODES, STATE_DIR, load_json, now_iso, save_json_atomic, save_text_atomic,
    sha256_of,
)

GATE_EVENTS = os.path.join(STATE_DIR, "reports", "gate-events.jsonl")
EXEMPTIONS = os.path.join(STATE_DIR, "reports", "exemptions.jsonl")

# 纠正留痕（主 Agent 写）+ 回执留痕（子 Agent 写）
CORRECTIONS = os.path.join(STATE_DIR, "reports", "corrections.jsonl")
CORRECTION_ACKS = os.path.join(STATE_DIR, "reports", "correction-acks.jsonl")
# 派发句柄目录：state/agents/<agentId>/dispatch.json
DISPATCH_ROOT = os.path.join(STATE_DIR, "agents")
DEFAULT_DISPATCH_TTL_S = 1800

# 纠正类型（与 academic-orchestration 协议一致；同时接受 ASCII code 便于脚本调用）
CORRECTION_TYPES = {
    "需求变更": "requirement_change",
    "前提失效": "prereq_invalidated",
    "范围纠正": "scope_correction",
    "门禁风险": "gate_risk",
    "冲突消解": "conflict_resolution",
}
CORRECTION_TYPE_LABELS = {code: label for label, code in CORRECTION_TYPES.items()}
DELIVERY_VALUES = ("steered", "queued", "resumed_background")
DISPATCH_CLOSED_STATUS = ("done", "failed", "timeout", "cancelled")


# ---------------------------------------------------------------- 底层：sha / 哈希链追加

def _sha_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _last_hash(path):
    """取事件流最后一行的 event_hash，作为新事件的 prev_hash（形成哈希链）。"""
    if not os.path.isfile(path):
        return None
    last = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.strip():
                    last = line.rstrip("\n")
    except OSError:
        return None
    if not last:
        return None
    return hashlib.sha256(last.encode("utf-8")).hexdigest()


def _read_jsonl(path):
    """读 JSONL，跳过损坏行并返回 (records, corrupt_count)。

    实现在 state_progress（checkpoint 同款容错读法），此处只做委托，避免两份实现漂移。
    """
    from state_progress import _read_jsonl as _impl
    return _impl(path)


def _append(path, record):
    """追加一行 JSONL（并发安全）。

    原实现是"读全量 → 拼接 → 整文件原子替换"，两个进程同时写时会互相覆盖
    （后写者用自己读到的旧快照盖掉前者刚追加的行），且 os.replace 在 Windows 上
    会因目标被占用抛 PermissionError，把整个门禁写入打崩。现在委托
    state_progress 的加锁追加实现（O_APPEND 单行写入 + 线程/跨进程锁 + fsync）。
    """
    from state_progress import _append_jsonl
    _append_jsonl(path, record)


def _append_chained(path, record):
    """追加一条带 prev_hash/event_hash 的记录（哈希链，防事后改写）。

    **取尾哈希、算 event_hash、写盘三步必须原子**：原实现先读 prev_hash 再单独写，
    并发时两个进程读到同一个 prev_hash → 链分叉，verify_chain 立刻判 line N
    prev_hash mismatch。这里把整段放进同一把文件锁内。
    """
    from state_progress import _JSONL_THREAD_LOCK, _file_lock

    record = dict(record)
    with _JSONL_THREAD_LOCK:
        with _file_lock(path):
            record["prev_hash"] = _last_hash(path)
            record["event_hash"] = hashlib.sha256(
                json.dumps({k: v for k, v in record.items() if k != "event_hash"},
                           ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            # 已持锁：直接追加，不能再调 _append（它会重复加锁导致死锁）
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
            fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_APPEND, 0o644)
            try:
                size = os.lseek(fd, 0, os.SEEK_END)
                if size:
                    os.lseek(fd, size - 1, os.SEEK_SET)
                    if os.read(fd, 1) != b"\n":
                        os.write(fd, b"\n")
                os.write(fd, data)
                os.fsync(fd)
            finally:
                os.close(fd)
    return record


def _verify_chain_file(path):
    """校验单个 JSONL 事件流的哈希链是否连续（供 N8 终检防篡改）。"""
    if not os.path.isfile(path):
        return {"intact": True, "count": 0, "broken_at": None}
    records = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.strip():
                    records.append(line.rstrip("\n"))
    except OSError:
        return {"intact": False, "count": 0, "broken_at": "read-error"}
    prev = None
    for i, raw in enumerate(records, 1):
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            return {"intact": False, "count": len(records), "broken_at": f"line {i} not json"}
        stored_hash = ev.pop("event_hash", None)
        stored_prev = ev.get("prev_hash")
        if stored_prev != prev:
            return {"intact": False, "count": len(records), "broken_at": f"line {i} prev_hash mismatch"}
        expect = hashlib.sha256(
            json.dumps(ev, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if stored_hash != expect:
            return {"intact": False, "count": len(records), "broken_at": f"line {i} hash mismatch"}
        prev = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return {"intact": True, "count": len(records), "broken_at": None}


def verify_chain(root):
    """校验 gate-events 的哈希链是否连续（用于 N8 终检防篡改）。"""
    return _verify_chain_file(os.path.join(root, GATE_EVENTS))


def verify_corrections_chain(root):
    """校验纠正留痕与回执留痕两份事件流的哈希链（任一断裂即不可信）。"""
    corrections = _verify_chain_file(os.path.join(root, CORRECTIONS))
    acks = _verify_chain_file(os.path.join(root, CORRECTION_ACKS))
    return {
        "intact": bool(corrections["intact"] and acks["intact"]),
        "corrections": corrections,
        "acks": acks,
    }


# ---------------------------------------------------------------- 门禁事件 / 豁免

def record_gate_change(root, gate, from_status, to_status, actor,
                       source_cmd="", evidence=None, exemption=None, note=""):
    """记录一次门禁变更（append-only + 哈希链）。"""
    path = os.path.join(root, GATE_EVENTS)
    return _append_chained(path, {
        "ts": now_iso(),
        "gate": gate,
        "from": from_status,
        "to": to_status,
        "actor": actor or "-",
        "source_cmd": source_cmd or "-",
        "evidence": evidence or None,
        "evidence_sha256": _sha_file(os.path.join(root, evidence)) if evidence else None,
        "exemption": exemption or None,
        "note": note or "",
    })


def record_exemption(root, kind, node, agent, detail=""):
    """记录一次门禁豁免（--allow-missing-mcp / --allow-missing-lineage /
    --allow-empty-artifacts / --allow-no-checkpoint）。"""
    path = os.path.join(root, EXEMPTIONS)
    return _append_chained(path, {
        "ts": now_iso(), "kind": kind, "node": node, "agent": agent or "-",
        "detail": detail or "",
    })


def summarize_exemptions(root):
    """汇总豁免次数（供 project-audit / N8 终检展示）。"""
    path = os.path.join(root, EXEMPTIONS)
    out = {"total": 0, "by_kind": {}, "by_node": {}, "events": []}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out["total"] += 1
                out["by_kind"][ev.get("kind", "?")] = out["by_kind"].get(ev.get("kind", "?"), 0) + 1
                out["by_node"][ev.get("node", "?")] = out["by_node"].get(ev.get("node", "?"), 0) + 1
                out["events"].append(ev)
    except OSError:
        pass
    return out


# ---------------------------------------------------------------- 纠正留痕（主 Agent 侧）

def _require_node(node):
    if node not in NODES:
        sys.exit(f"[state_utils] 非法节点 {node}。合法节点: {', '.join(NODES)}")


def _require_agent_id(agent_id, label="agent_id"):
    """agent_id 会拼进 state/agents/<id>/ 路径，必须防路径穿越（P0-8）与 Windows 名折叠。"""
    from state_guard import safe_component
    # 必须查**原始输入**：safe_component 内部会 strip，`"abc "` 会被静默转成 "abc"，
    # 于是两个不同 agent_id 落到同一目录却都不报错（Windows 尾空格/尾点同样折叠）。
    raw = str(agent_id if agent_id is not None else "")
    if raw != raw.strip():
        sys.exit(f"[state_utils] 非法 {label}: {agent_id!r}"
                 f"（首尾空白会被静默剥离并与 {raw.strip()!r} 折叠为同一路径）")
    value = safe_component(agent_id, label)
    # Windows 上 `abc.` 与 `abc` 是同一目录，CON/PRN/NUL/COM1 是设备名：
    # 允许它们会让两个不同 agent 共用同一份 dispatch.json/claim.json。
    text = str(value)
    stem = text.split(".", 1)[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} \
        | {f"LPT{i}" for i in range(1, 10)}
    if text.endswith(".") or stem in reserved:
        sys.exit(f"[state_utils] 非法 {label}: {agent_id!r}"
                 f"（Windows 上会与 {text.rstrip('.')!r} 折叠为同一路径，"
                 f"或为系统保留名 CON/PRN/NUL/COM1-9/LPT1-9）")
    return text


def _normalize_correction_type(value):
    raw = str(value or "").strip()
    if raw in CORRECTION_TYPES:
        return raw
    code = raw.lower()
    if code in CORRECTION_TYPE_LABELS:
        return CORRECTION_TYPE_LABELS[code]
    sys.exit("[state_utils] 非法纠正类型: "
             f"{value!r}；合法值: {', '.join(CORRECTION_TYPES)} 或 "
             f"{', '.join(CORRECTION_TYPES.values())}")


def load_corrections(root):
    return _read_jsonl(os.path.join(root, CORRECTIONS))


def load_correction_acks(root):
    return _read_jsonl(os.path.join(root, CORRECTION_ACKS))


def record_correction(root, *, node, agent_id, correction_type, finding,
                      requirement, impact="", round_no=None, delivery="queued",
                      by="main-agent", note=""):
    """记录一条运行中纠正（主 Agent 调用；append-only + 哈希链）。

    返回记录本身；``correction_id`` 用于子 Agent 回执时精确对齐（同一 node 可能有多条纠正，
    只有逐条回执才算闭环，不能拿一条回执抵多条）。
    """
    _require_node(node)
    agent_id = _require_agent_id(agent_id)
    label = _normalize_correction_type(correction_type)
    delivery = str(delivery or "queued").strip()
    if delivery not in DELIVERY_VALUES:
        sys.exit(f"[state_utils] 非法 delivery: {delivery!r}；合法值: {', '.join(DELIVERY_VALUES)}")
    finding = str(finding or "").strip()
    requirement = str(requirement or "").strip()
    if not finding:
        sys.exit("[state_utils] correction-add 必须提供 --finding（观察到的事实与证据路径）")
    if not requirement:
        sys.exit("[state_utils] correction-add 必须提供 --requirement（本次必须如何调整）")
    if round_no is not None:
        try:
            round_no = int(round_no)
            if round_no < 1:
                raise ValueError
        except (TypeError, ValueError):
            sys.exit(f"[state_utils] 非法 round: {round_no!r}（须为正整数）")
    path = os.path.join(root, CORRECTIONS)
    ts = now_iso()
    prev = _last_hash(path)
    corr_id = "corr_" + hashlib.sha256(
        json.dumps({"agent_id": agent_id, "node": node, "round": round_no, "type": label,
                    "finding": finding, "requirement": requirement, "ts": ts,
                    "prev_hash": prev}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    record = {
        "ts": ts,
        "correction_id": corr_id,
        "agent_id": agent_id,
        "node": node,
        "round": round_no,
        "type": label,
        "type_code": CORRECTION_TYPES[label],
        "finding": finding,
        "impact": str(impact or ""),
        "requirement": requirement,
        "delivery": delivery,
        "by": by or "main-agent",
        "note": str(note or ""),
    }
    record = _append_chained(path, record)
    # 若该 Agent 有 dispatch.json，把纠正挂到派发句柄上，主 Agent 一眼能看出还有几条待回执
    dispatch = _load_dispatch(root, agent_id)
    if dispatch:
        dispatch.setdefault("corrections", []).append(
            {"correction_id": corr_id, "type": label, "ts": ts, "delivery": delivery})
        dispatch["last_activity_at"] = ts
        _save_dispatch(root, agent_id, dispatch)
    return record


def find_correction(root, correction_id):
    """按 correction_id 查找一条纠正记录（找不到返回 None）。"""
    cid = str(correction_id or "").strip()
    if not cid:
        return None
    records, _ = load_corrections(root)
    hit = None
    for rec in records:
        if rec.get("correction_id") == cid:
            hit = rec
    return hit


def record_correction_ack(root, correction_id, agent_id, note="", by=None):
    """记录子 Agent 的回执（append-only + 哈希链）。

    防伪造：回执声明的 agent_id 必须与纠正记录里的 agent_id 完全一致；
    其他 Agent（含主 Agent 代签）的回执一律拒绝。
    """
    agent_id = _require_agent_id(agent_id)
    correction = find_correction(root, correction_id)
    if not correction:
        sys.exit(f"[state_utils] 纠正不存在: {correction_id!r}（先 correction-list 核对 correction_id）")
    if correction.get("agent_id") != agent_id:
        sys.exit(
            f"[state_utils] 拒绝回执：纠正 {correction['correction_id']} 发给 "
            f"{correction.get('agent_id')}，回执人却是 {agent_id}。\n"
            f"  回执必须由被纠正的 Agent 本人提交（agent_id 必须一致），否则视为未回执。"
        )
    path = os.path.join(root, CORRECTION_ACKS)
    for ack in load_correction_acks(root)[0]:
        if (ack.get("correction_id") == correction["correction_id"]
                and ack.get("agent_id") == agent_id):
            return dict(ack, duplicate=True)
    record = {
        "ts": now_iso(),
        "correction_id": correction["correction_id"],
        "agent_id": agent_id,
        "node": correction.get("node"),
        "round": correction.get("round"),
        "correction_type": correction.get("type"),
        "note": str(note or ""),
        "by": by or agent_id,
    }
    record = _append_chained(path, record)
    dispatch = _load_dispatch(root, agent_id)
    if dispatch:
        dispatch["last_activity_at"] = record["ts"]
        for item in dispatch.get("corrections") or []:
            if item.get("correction_id") == correction["correction_id"]:
                item["acked_at"] = record["ts"]
        _save_dispatch(root, agent_id, dispatch)
    return record


def _parse_ts(value):
    from datetime import datetime
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def ack_ledger(root):
    """回执索引：{(correction_id, agent_id): ack}，仅保留能解析时间且 node 一致的记录。

    同一纠正只认**同一 agent_id** 的回执；回执时间早于纠正时间的记录视为伪造，不采信。
    """
    corrections, _ = load_corrections(root)
    corr_by_id = {c.get("correction_id"): c for c in corrections if c.get("correction_id")}
    acks, _ = load_correction_acks(root)
    index = {}
    for ack in acks:
        cid = ack.get("correction_id")
        aid = ack.get("agent_id")
        if not cid or not aid or cid not in corr_by_id:
            continue
        corr = corr_by_id[cid]
        if corr.get("agent_id") != aid:
            continue  # 非本人回执，无效
        if ack.get("node") not in (None, corr.get("node")):
            continue  # 回执挂错节点，无效
        ack_ts, corr_ts = _parse_ts(ack.get("ts")), _parse_ts(corr.get("ts"))
        if ack_ts is None or corr_ts is None or ack_ts < corr_ts:
            continue  # 时间缺失或回执早于纠正 → 不采信
        index[(cid, aid)] = ack
    return index


def unacked_corrections(root, node=None):
    """返回未回执的纠正列表（node=None 表示全项目，A3 终检用；指定 node 时只查该节点，B1 用）。"""
    corrections, _ = load_corrections(root)
    acked = ack_ledger(root)
    out = []
    for corr in corrections:
        if not corr.get("correction_id"):
            continue
        if node is not None and corr.get("node") != node:
            continue
        key = (corr["correction_id"], corr.get("agent_id"))
        if key not in acked:
            out.append(corr)
    out.sort(key=lambda c: str(c.get("ts") or ""))
    return out


def summarize_corrections(root, node=None):
    """纠正留痕汇总（供 project-audit 消费；结构稳定，字段名不做改名）。"""
    corrections, corrupt = load_corrections(root)
    acks, acks_corrupt = load_correction_acks(root)
    if node is not None:
        corrections = [c for c in corrections if c.get("node") == node]
    acked = ack_ledger(root)
    unacked = unacked_corrections(root, node=node)
    by_node, by_type, by_delivery = {}, {}, {}
    for corr in corrections:
        by_node[corr.get("node", "?")] = by_node.get(corr.get("node", "?"), 0) + 1
        by_type[corr.get("type", "?")] = by_type.get(corr.get("type", "?"), 0) + 1
        by_delivery[corr.get("delivery", "?")] = by_delivery.get(corr.get("delivery", "?"), 0) + 1
    return {
        "ledger_exists": os.path.isfile(os.path.join(root, CORRECTIONS)),
        "acks_exists": os.path.isfile(os.path.join(root, CORRECTION_ACKS)),
        "node": node,
        "total": len(corrections),
        "acked": len(corrections) - len(unacked),
        "unacked": len(unacked),
        "unacked_details": [{
            "correction_id": c.get("correction_id"),
            "node": c.get("node"),
            "agent_id": c.get("agent_id"),
            "round": c.get("round"),
            "type": c.get("type"),
            "delivery": c.get("delivery"),
            "ts": c.get("ts"),
            "finding": str(c.get("finding") or "")[:160],
            "requirement": str(c.get("requirement") or "")[:160],
        } for c in unacked],
        "by_node": by_node,
        "by_type": by_type,
        "by_delivery": by_delivery,
        "acks_total": len(acks),
        "corrupt_lines": corrupt + acks_corrupt,
        "chain": verify_corrections_chain(root),
        "ack_rule": "回执必须由纠正记录里的同一 agent_id 提交，且回执时间不得早于纠正时间；"
                    "其他 Agent 的回执不计入闭环",
    }


def cmd_correction_add(args):
    root = os.path.abspath(args.dir)
    record = record_correction(
        root,
        node=args.node,
        agent_id=args.agent,
        correction_type=args.type,
        finding=args.finding,
        requirement=args.requirement,
        impact=args.impact or "",
        round_no=getattr(args, "round", None),
        delivery=args.delivery,
        by=getattr(args, "by", "") or "main-agent",
        note=getattr(args, "note", "") or "",
    )
    print(json.dumps({
        "recorded": True,
        "correction_id": record["correction_id"],
        "node": record["node"],
        "agent_id": record["agent_id"],
        "round": record["round"],
        "type": record["type"],
        "delivery": record["delivery"],
        "ledger": CORRECTIONS,
        "ack_command": (f"python state/state_utils.py correction-ack {record['correction_id']} "
                        f"--agent {record['agent_id']} --note \"<如何落实>\""),
        "note": "回执必须由该 agent_id 本人提交；纠正未回执时 A3 不得 PASS（CORRECTION_UNACKED）",
    }, ensure_ascii=False, indent=2))


def cmd_correction_ack(args):
    root = os.path.abspath(args.dir)
    record = record_correction_ack(root, args.correction_id, args.agent,
                                   note=args.note or "", by=getattr(args, "by", "") or None)
    if record.get("duplicate"):
        print(f"[state_utils] 该纠正已有 {args.agent} 的回执（{record.get('ts')}），未重复写入")
        return
    print(json.dumps({
        "acked": True,
        "correction_id": record["correction_id"],
        "agent_id": record["agent_id"],
        "node": record.get("node"),
        "round": record.get("round"),
        "ts": record["ts"],
        "ledger": CORRECTION_ACKS,
    }, ensure_ascii=False, indent=2))


def cmd_correction_list(args):
    root = os.path.abspath(args.dir)
    node = getattr(args, "node", None)
    summary = summarize_corrections(root, node=node)
    corrections, _ = load_corrections(root)
    if node is not None:
        corrections = [c for c in corrections if c.get("node") == node]
    acked = ack_ledger(root)
    rows = []
    for corr in corrections:
        ack = acked.get((corr.get("correction_id"), corr.get("agent_id")))
        row = dict(corr)
        row["acked"] = bool(ack)
        row["acked_at"] = (ack or {}).get("ts")
        row["ack_note"] = (ack or {}).get("note")
        rows.append(row)
    if getattr(args, "unacked", False):
        rows = [r for r in rows if not r["acked"]]
    if getattr(args, "json", False):
        print(json.dumps({"node": node, "count": len(rows), "corrections": rows,
                          "summary": summary}, ensure_ascii=False, indent=2))
        return
    print(f"# 纠正留痕（{CORRECTIONS}）" + (f" node={node}" if node else " 全项目"))
    if not rows:
        print("- 无记录")
        return
    for r in rows:
        mark = "✅ 已回执" if r["acked"] else "🔴 未回执"
        print(f"- [{r.get('ts')}] {r.get('correction_id')} node={r.get('node')} "
              f"agent={r.get('agent_id')} round={r.get('round') or '-'} "
              f"type={r.get('type')} delivery={r.get('delivery')} → {mark}")
        print(f"    发现: {r.get('finding')}")
        print(f"    要求: {r.get('requirement')}")
        if r["acked"]:
            print(f"    回执: {r.get('acked_at')} {r.get('ack_note') or ''}")
    if summary["unacked"]:
        print(f"\n⚠ 未回执 {summary['unacked']} 条：A3 终检将判 CORRECTION_UNACKED，不得 PASS。")


# ---------------------------------------------------------------- 派发句柄（dispatch.json）

def dispatch_file(root, agent_id):
    agent_id = _require_agent_id(agent_id)
    path = os.path.join(root, DISPATCH_ROOT, agent_id, "dispatch.json")
    from state_guard import assert_within
    return assert_within(root, path, "dispatch.json 路径")


def _load_dispatch(root, agent_id, strict=False):
    try:
        path = dispatch_file(root, agent_id)
    except SystemExit:
        if strict:
            raise
        return None
    return load_json(path)


def _save_dispatch(root, agent_id, record):
    path = dispatch_file(root, agent_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_json_atomic(path, record)


def _age_seconds(ts):
    from datetime import datetime, timezone
    parsed = _parse_ts(ts)
    if parsed is None:
        return None
    now = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, int((now - parsed).total_seconds()))


def close_dispatch(root, agent_id, status, note="", artifacts=None, source="dispatch-close"):
    """收尾一个派发句柄（不存在时返回 None，便于调用方 best-effort 调用）。"""
    if status not in DISPATCH_CLOSED_STATUS:
        sys.exit(f"[state_utils] 非法 dispatch 状态: {status!r}；合法值: {', '.join(DISPATCH_CLOSED_STATUS)}")
    record = _load_dispatch(root, agent_id, strict=True)
    if not record:
        return None
    record["status"] = status
    record["closed_at"] = now_iso()
    record["last_activity_at"] = record["closed_at"]
    record["close_source"] = source
    if note:
        record["close_note"] = str(note)
    if artifacts:
        record["artifacts"] = _artifact_digests(root, artifacts)
    _save_dispatch(root, agent_id, record)
    return record


def _artifact_digests(root, artifacts):
    out = []
    for rel in artifacts:
        text = str(rel or "").replace("\\", "/").strip()
        if not text:
            continue
        full = os.path.join(root, text)
        out.append({"path": text,
                    "sha256": sha256_of(full) if os.path.isfile(full) else None,
                    "state": "present" if os.path.isfile(full) else "missing"})
    return out


def touch_dispatch(root, agent_id, source, checkpoint=None):
    """刷新派发句柄活跃时间（checkpoint/heartbeat 调用），返回记录或 None。"""
    if not agent_id:
        return None
    record = _load_dispatch(root, agent_id)
    if not record:
        return None
    record["last_activity_at"] = now_iso()
    record["last_activity_source"] = source
    if checkpoint:
        record["last_checkpoint"] = checkpoint
    _save_dispatch(root, agent_id, record)
    return record


def dispatch_records(root):
    """读取全部派发句柄（state/agents/*/dispatch.json）。"""
    base = os.path.join(root, DISPATCH_ROOT)
    out = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name, "dispatch.json")
        if not os.path.isfile(path):
            continue
        record = load_json(path) or {}
        if not isinstance(record, dict):
            continue
        record.setdefault("agentId", name)
        out.append(record)
    return out


def record_correction_acks_from_result(root, result):
    """从子 Agent 的 result.json 采集回执（result-ingest 调用）。

    动机（审计 B-2）：``RespondToCoordinator`` 是宿主侧工具，插件无法强制；只靠
    "子 Agent 自觉回执"不可靠。``result.json`` 则是**必须交付**、且由 result-ingest
    机器校验（schema/产物哈希/agent_id 白名单）的载体，把回执挂进去等于把它纳入
    同一道机器校验，比"自觉回执"稳得多。

    防伪造与 CLI 回执同一套规则：
      - correction_id 必须存在；
      - 回执人 = result.json 的 agent_id（不能替别的 Agent 回执）；
      - correction 的 node 必须等于 result 的 node_id。
    返回 (accepted, errors)：accepted 为已写入的回执数；errors 为非空即调用方应拒绝整份结果。
    """
    raw = result.get("corrections_ack")
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["result.corrections_ack 必须是数组（每项 {correction_id, note?}）"]
    agent_id = str(result.get("agent_id") or "").strip()
    node = str(result.get("node_id") or "").strip()
    accepted, errors = [], []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            item = {"correction_id": item}
        if not isinstance(item, dict) or not str(item.get("correction_id") or "").strip():
            errors.append(f"corrections_ack[{i}] 缺少 correction_id")
            continue
        cid = str(item["correction_id"]).strip()
        correction = find_correction(root, cid)
        if not correction:
            errors.append(f"corrections_ack[{i}] 指向不存在的纠正 {cid}")
            continue
        if correction.get("agent_id") != agent_id:
            errors.append(f"corrections_ack[{i}] 纠正 {cid} 发给 {correction.get('agent_id')}，"
                          f"但本结果由 {agent_id} 提交（代签无效）")
            continue
        if node and correction.get("node") != node:
            errors.append(f"corrections_ack[{i}] 纠正 {cid} 属于 {correction.get('node')}，"
                          f"与本结果节点 {node} 不符")
            continue
        ack = record_correction_ack(root, cid, agent_id,
                                   note=str(item.get("note") or "") or "经 result.json 回执",
                                   by=f"{agent_id}(result.json)")
        accepted.append(ack)
    return accepted, errors


def write_conflicts(root):
    """并行写入冲突检测：同时 running 的两个派发声明了同一写入目标。

    依据（academic-orchestration「互斥规则」）：同一业务文件只允许一个写入者。
    派发时用 ``dispatch-start --writes <path>`` 声明该 Agent 的写入目标，此函数把
    running 句柄两两比对写入集合（目录写目标按前缀判定，文件目标按等值判定）。
    """
    records = [r for r in dispatch_records(root) if (r.get("status") or "running") == "running"]
    conflicts = []
    for i, first in enumerate(records):
        for second in records[i + 1:]:
            if first.get("node") == second.get("node"):
                # 同节点双写：由 claim 租约负责拦截；这里只报不同节点的文件重叠
                continue
            overlaps = []
            for a in (first.get("writes") or []):
                for b in (second.get("writes") or []):
                    if _write_targets_overlap(a, b):
                        overlaps.append({"first": a, "second": b})
            if overlaps:
                conflicts.append({
                    "agents": [first.get("agentId"), second.get("agentId")],
                    "nodes": [first.get("node"), second.get("node")],
                    "overlaps": overlaps,
                    "reason": "两个并行 Agent 声明了同一写入目标（违反「同一业务文件只允许一个写入者」）",
                })
    return conflicts


def _write_targets_overlap(a, b):
    """写入目标重叠判定：相等，或一方是另一方的上级目录（目录写 vs 文件写）。"""
    def norm(value):
        text = str(value or "").replace("\\", "/").strip().strip("/")
        return text
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    return a == b or b.startswith(a + "/") or a.startswith(b + "/")


def check_dispatch_artifact_consistency(root, result):
    """回收核对（对应 academic-orchestration 协议 E.2）：result 产物与 dispatch.json 记录的哈希是否一致。

    文档承诺「收到完成通知后校验产物哈希与 dispatch.json 记录一致（防空返回/伪完成）」，
    此前同样没有任何代码。这里在 result-ingest 时执行：
      - dispatch 在 dispatch-close 时记录了 artifacts → 逐个复核磁盘当前哈希；
      - result.artifacts 里同路径的条目必须与 dispatch 记录一致（不一致说明产物被换过）。

    返回错误列表（空=通过）。没有 dispatch 句柄时返回空——手工单节点执行不该被这条卡住。
    """
    agent_id = str(result.get("agent_id") or "").strip()
    if not agent_id:
        return []
    dispatch = _load_dispatch(root, agent_id)
    if not dispatch:
        return []
    recorded = dispatch.get("artifacts") or []
    if not recorded:
        return []
    result_hashes = {}
    for item in result.get("validated_artifacts") or []:
        if isinstance(item, dict) and item.get("path"):
            result_hashes[str(item["path"]).replace("\\", "/")] = item.get("sha256")
    errors = []
    for entry in recorded:
        rel = str(entry.get("path") or "").replace("\\", "/").strip()
        if not rel:
            continue
        full = os.path.join(root, rel)
        current = sha256_of(full) if os.path.isfile(full) else None
        if current is None:
            errors.append(f"dispatch 记录的产物已不存在: {rel}（疑似空返回/伪完成）")
            continue
        if entry.get("sha256") and entry["sha256"] != current:
            errors.append(f"产物在 dispatch 记录后已被改动: {rel}"
                          f"（记录 {str(entry['sha256'])[:12]}… / 实际 {str(current)[:12]}…）")
            continue
        if rel in result_hashes and result_hashes[rel] != current:
            errors.append(f"result 与磁盘产物哈希不一致: {rel}")
    return errors


def close_dispatch_from_result(root, result):
    """result-ingest 成功即视为回收完成：把仍 running 的句柄收尾为 done（幂等）。

    这样 dispatch.json 的生命周期有明确的责任人（主 Agent 的回收入口），
    不会因为"忘了 dispatch-close"而永久停在 running 被误判僵尸。
    """
    agent_id = str(result.get("agent_id") or "").strip()
    if not agent_id:
        return None
    dispatch = _load_dispatch(root, agent_id)
    if not dispatch or dispatch.get("status") != "running":
        return None
    artifacts = [a.get("path") for a in (result.get("validated_artifacts") or [])
                 if isinstance(a, dict) and a.get("path")]
    return close_dispatch(root, agent_id, "done",
                          note=f"result-ingest 回收（run_id={result.get('run_id')}）",
                          artifacts=artifacts, source="result-ingest")


def dispatch_summary(root):
    """派发句柄汇总：running/已收尾/僵尸（超 ttl 仍 running）。供 project-audit 消费。"""
    records = dispatch_records(root)
    by_status = {}
    zombies, running = [], []
    for record in records:
        status = record.get("status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        activity = record.get("last_activity_at") or record.get("started_at")
        age = _age_seconds(activity)
        ttl = record.get("ttl_s")
        try:
            ttl = int(ttl) if ttl is not None else DEFAULT_DISPATCH_TTL_S
        except (TypeError, ValueError):
            ttl = DEFAULT_DISPATCH_TTL_S
        item = {
            "agentId": record.get("agentId"),
            "node": record.get("node"),
            "round": record.get("round"),
            "status": status,
            "started_at": record.get("started_at"),
            "last_activity_at": activity,
            "last_activity_source": record.get("last_activity_source"),
            "age_s": age,
            "ttl_s": ttl,
            "corrections": len(record.get("corrections") or []),
            "unacked_corrections": sum(1 for c in (record.get("corrections") or [])
                                       if not c.get("acked_at")),
            "last_checkpoint": record.get("last_checkpoint"),
            "zombie": bool(status == "running" and age is not None and age > ttl),
        }
        if item["zombie"]:
            zombies.append(item)
        elif status == "running":
            running.append(item)
    return {
        "total": len(records),
        "by_status": by_status,
        "running": running,
        "zombies": zombies,
        "conflicts": write_conflicts(root),
        "zombie_rule": f"status=running 且距最后一次活动（heartbeat/checkpoint/correction）超过 ttl_s"
                       f"（默认 {DEFAULT_DISPATCH_TTL_S}s）即判僵尸",
        "conflict_rule": "两个 running 句柄（不同节点）声明的 writes 目标相同或互为上下级 → 写入冲突",
        "dispatches": sorted(
            [{
                "agentId": r.get("agentId"), "node": r.get("node"), "round": r.get("round"),
                "status": r.get("status"), "started_at": r.get("started_at"),
                "closed_at": r.get("closed_at"),
            } for r in records],
            key=lambda r: str(r.get("started_at") or "")),
    }


def cmd_dispatch_start(args):
    root = os.path.abspath(args.dir)
    _require_node(args.node)
    agent_id = _require_agent_id(args.agent_id)
    existing = _load_dispatch(root, agent_id)
    ts = now_iso()
    ttl = int(getattr(args, "ttl", DEFAULT_DISPATCH_TTL_S) or DEFAULT_DISPATCH_TTL_S)
    if existing and existing.get("status") == "running" and not getattr(args, "force", False):
        age = _age_seconds(existing.get("last_activity_at") or existing.get("started_at"))
        if age is None or age <= (existing.get("ttl_s") or DEFAULT_DISPATCH_TTL_S):
            sys.exit(f"[state_utils] 派发句柄已存在且仍在 running（{existing.get('node')}，"
                     f"{existing.get('started_at')}）。如确认原 Agent 已失联，用 --force 接管。")
    must_load = [s.strip() for s in str(getattr(args, "must_load", "") or "").split(",") if s.strip()]
    writes = [s.strip().replace("\\", "/") for s in str(getattr(args, "writes", "") or "").split(",") if s.strip()]
    record = {
        "agentId": agent_id,
        "node": args.node,
        "round": getattr(args, "round", None),
        "started_at": ts,
        "last_activity_at": ts,
        "last_activity_source": "dispatch-start",
        "must_load": must_load,
        "writes": writes,
        "task": getattr(args, "task", "") or "",
        "status": "running",
        "ttl_s": ttl,
        "closed_at": None,
        "corrections": [],
        "last_checkpoint": None,
    }
    if existing:
        record["previous_dispatch"] = {
            "status": existing.get("status"),
            "started_at": existing.get("started_at"),
            "closed_at": existing.get("closed_at"),
        }
    _save_dispatch(root, agent_id, record)
    other_conflicts = [c for c in write_conflicts(root) if agent_id in (c.get("agents") or [])]
    print(json.dumps({
        "dispatch_recorded": True,
        "agentId": agent_id,
        "node": record["node"],
        "round": record["round"],
        "status": record["status"],
        "must_load": must_load,
        "writes": writes,
        "ttl_s": ttl,
        "path": os.path.relpath(dispatch_file(root, agent_id), root).replace("\\", "/"),
        "write_conflicts": other_conflicts,
        "hint": "子 Agent 完成时调用 dispatch-close <agentId> --status done --artifact <产物路径>；"
                "主 Agent 回收时据此核对产物哈希",
    }, ensure_ascii=False, indent=2))


def cmd_dispatch_heartbeat(args):
    root = os.path.abspath(args.dir)
    record = touch_dispatch(root, args.agent_id, "heartbeat")
    if not record:
        sys.exit(f"[state_utils] 找不到派发句柄: {args.agent_id}（先 dispatch-start）")
    print(f"[state_utils] dispatch heartbeat: {args.agent_id} @ {record['last_activity_at']}")


def cmd_dispatch_close(args):
    root = os.path.abspath(args.dir)
    record = close_dispatch(root, args.agent_id, args.status, note=args.note or "",
                            artifacts=args.artifact or [])
    if not record:
        sys.exit(f"[state_utils] 找不到派发句柄: {args.agent_id}（先 dispatch-start）")
    print(json.dumps({
        "closed": True,
        "agentId": record["agentId"],
        "node": record.get("node"),
        "status": record["status"],
        "closed_at": record["closed_at"],
        "artifacts": record.get("artifacts") or [],
    }, ensure_ascii=False, indent=2))


def cmd_dispatch_list(args):
    root = os.path.abspath(args.dir)
    print(json.dumps(dispatch_summary(root), ensure_ascii=False, indent=2))
