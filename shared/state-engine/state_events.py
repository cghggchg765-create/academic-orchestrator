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
"""
from __future__ import annotations

import hashlib
import json
import os

from state_defs import STATE_DIR, now_iso, save_text_atomic

GATE_EVENTS = os.path.join(STATE_DIR, "reports", "gate-events.jsonl")
EXEMPTIONS = os.path.join(STATE_DIR, "reports", "exemptions.jsonl")


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


def _append(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = ""
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            body = ""
    body += json.dumps(record, ensure_ascii=False) + "\n"
    save_text_atomic(path, body)


def record_gate_change(root, gate, from_status, to_status, actor,
                       source_cmd="", evidence=None, exemption=None, note=""):
    """记录一次门禁变更（append-only + 哈希链）。"""
    path = os.path.join(root, GATE_EVENTS)
    prev = _last_hash(path)
    ev = {
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
        "prev_hash": prev,
    }
    ev["event_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in ev.items() if k != "event_hash"},
                   ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    _append(path, ev)
    return ev


def record_exemption(root, kind, node, agent, detail=""):
    """记录一次门禁豁免（--allow-missing-mcp / --allow-missing-lineage /
    --allow-empty-artifacts / --allow-no-checkpoint）。"""
    path = os.path.join(root, EXEMPTIONS)
    prev = _last_hash(path)
    ev = {"ts": now_iso(), "kind": kind, "node": node, "agent": agent or "-",
          "detail": detail or "", "prev_hash": prev}
    ev["event_hash"] = hashlib.sha256(
        json.dumps(ev, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    _append(path, ev)
    return ev


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


def verify_chain(root):
    """校验 gate-events 的哈希链是否连续（用于 N8 终检防篡改）。"""
    path = os.path.join(root, GATE_EVENTS)
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
