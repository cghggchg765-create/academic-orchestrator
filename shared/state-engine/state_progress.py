#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进度快照 / 产物入库 / 孤儿扫描（2.0.0 新增，供子 Agent 分阶段归档与入库记录强制）。

设计目标（对应用户要求）：
  1. 子 Agent 长任务分阶段归档 —— checkpoint 把"做到哪、产出了什么、还差什么"结构化落盘，
     中断后读最后一条即可续跑，不必从头重来。
  2. 文件不乱放且必有入库记录 —— register-artifact 强制产物只能落在本节点声明目录内；
     orphan-scan 找出落在任何节点产物目录之外的散落文件。

落盘位置：
  state/checkpoints/<节点>.jsonl          进度快照（append-only，最新在末尾）
  state/reports/artifacts-registry.json   产物入库台账（path → sha256/大小/登记人/时间）
  state/reports/orphan-files.json         孤儿文件扫描结果
"""
from __future__ import annotations

import json
import os
import sys

from state_defs import (
    NODES, STATE_DIR, now_iso, save_json_atomic, save_text_atomic, sha256_of,
)

CHECKPOINT_DIR = os.path.join(STATE_DIR, "checkpoints")
ARTIFACT_REGISTRY = os.path.join(STATE_DIR, "reports", "artifacts-registry.json")
ORPHAN_REPORT = os.path.join(STATE_DIR, "reports", "orphan-files.json")

# 孤儿扫描时忽略的顶层目录（非产物区：状态区/版本控制/依赖/构建缓存）
IGNORE_TOP = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules",
    "state", "Material", "BackupArchive", ".zcode", ".agents", ".github",
}
IGNORE_SUFFIX = {".pyc", ".pyo", ".aux", ".log", ".out", ".toc", ".bbl", ".blg",
                 ".synctex.gz", ".fls", ".fdb_latexmk", ".xdv", ".lof", ".lot"}
# 版本控制/占位/系统文件：不是内容产物，不参与孤儿判定
IGNORE_NAMES = {".gitignore", ".gitattributes", ".gitkeep", ".DS_Store", "Thumbs.db",
                "desktop.ini", "README.md", "AGENTS.md"}
# 项目预建即存在的基础设施目录：属于脚手架而非产出，不参与孤儿判定
SCAFFOLD_DIRS = {"DefenseMaterial", "Literature", "Material", "BackupArchive", "LogRecord"}


def _artifact_roots(node: str) -> list[str]:
    """节点声明的产物路径（可能是文件或目录，逗号分隔）。"""
    raw = NODES[node].get("artifact", "") or ""
    return [p.strip().rstrip("/\\") for p in raw.split(",") if p.strip()]


def _all_artifact_roots() -> list[str]:
    roots = []
    for nid in NODES:
        roots.extend(_artifact_roots(nid))
    # 去重、去掉被其它根包含的子路径（保留最上层）
    uniq = sorted(set(roots), key=len)
    out = []
    for r in uniq:
        if not any(r == o or r.startswith(o + os.sep) or r.startswith(o + "/") for o in out):
            out.append(r)
    return out


def _under(path: str, root: str) -> bool:
    """路径包含判定（归一化 + relpath，防 `Data/../../x` 绕过）。
    用 relpath 判定是否上跳，避免纯字符串前缀比较被 `..` 欺骗。"""
    p = os.path.abspath(path)
    r = os.path.abspath(root)
    try:
        rel = os.path.relpath(p, r)
    except ValueError:
        return False
    return not (rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel))


def _read_jsonl(path):
    """读 JSONL，跳过损坏行并返回 (records, corrupt_count)。

    原来直接 json.loads 每行，一行半截就让整个节点快照不可读、续跑能力归零。
    现在坏行被跳过并计数，调用方可提示用户。
    """
    records, corrupt = [], 0
    if not os.path.isfile(path):
        return records, corrupt
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                corrupt += 1
    return records, corrupt


def _append_jsonl(path, record):
    """原子追加一行 JSON。先读全量 + 追加 + 原子替换，避免中断留下半行。"""
    records, corrupt = _read_jsonl(path)
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    body += json.dumps(record, ensure_ascii=False) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_text_atomic(path, body)
    return corrupt


def cmd_checkpoint(args):
    root = os.path.abspath(args.dir)
    node = args.node
    if not os.path.exists(os.path.join(root, STATE_DIR, "decision_log.json")):
        sys.exit(f"[state_utils] 项目未初始化：{root}；请先运行 init")
    by = (args.by or NODES[node]["executor"]).strip()
    ckpt_dir = os.path.join(root, CHECKPOINT_DIR)
    os.makedirs(ckpt_dir, exist_ok=True)
    path = os.path.join(ckpt_dir, f"{node}.jsonl")

    # 序号：接着已有的往下排
    seq = 1
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            seq = sum(1 for line in fh if line.strip()) + 1

    # 产物快照：存在才算哈希，缺失记 null 并标 missing（供续跑时发现半成品）
    artifacts = []
    for rel in args.artifact or []:
        full = os.path.join(root, rel)
        if os.path.isfile(full):
            artifacts.append({"path": rel.replace("\\", "/"), "sha256": sha256_of(full),
                              "size": os.path.getsize(full), "state": "present"})
        elif os.path.isdir(full):
            entries = []
            for dp, dn, fn in os.walk(full):
                if ".git" in dp.split(os.sep):
                    dn[:] = []
                    continue
                for f in sorted(fn):
                    entries.append(os.path.relpath(os.path.join(dp, f), root).replace("\\", "/"))
            artifacts.append({"path": rel.replace("\\", "/"), "files": entries, "state": "present"})
        else:
            artifacts.append({"path": rel.replace("\\", "/"), "sha256": None,
                              "state": "missing"})

    record = {
        "seq": seq,
        "node": node,
        "phase": args.phase,
        "by": by,
        "ts": now_iso(),
        "done": list(args.done or []),
        "pending": list(args.pending or []),
        "artifacts": artifacts,
        "note": args.note or "",
    }
    _append_jsonl(path, record)

    # 同步写一份人类可读摘要，便于中断后直接看
    md = os.path.join(ckpt_dir, f"{node}.md")
    records, corrupt = _read_jsonl(path)
    lines = [f"# {node} {NODES[node]['name']} 进度快照", ""]
    if corrupt:
        lines.append(f"> ⚠ 检测到 {corrupt} 行损坏记录（已跳过；完整数据见 {node}.jsonl）")
        lines.append("")
    for r in records:
        lines.append(f"## #{r.get('seq')} {r.get('phase')} · {r.get('ts')} · by {r.get('by')}")
        if r.get("done"):
            lines.append("已完成: " + "; ".join(r["done"]))
        if r.get("pending"):
            lines.append("待完成: " + "; ".join(r["pending"]))
        if r.get("artifacts"):
            got = ", ".join(f"{a.get('path')}({a.get('state')})" for a in r["artifacts"])
            lines.append("产物: " + got)
        if r.get("note"):
            lines.append("备注: " + r["note"])
        lines.append("")
    save_text_atomic(md, "\n".join(lines))
    print(f"[state_utils] checkpoint #{seq} 已落盘: {CHECKPOINT_DIR}/{node}.jsonl（阶段: {args.phase}）")


def cmd_checkpoint_list(args):
    root = os.path.abspath(args.dir)
    path = os.path.join(root, CHECKPOINT_DIR, f"{args.node}.jsonl")
    if not os.path.exists(path):
        print(json.dumps({"node": args.node, "checkpoints": [], "resume_hint": "无快照，从头开始"},
                         ensure_ascii=False, indent=2))
        return
    records, corrupt = _read_jsonl(path)
    if args.latest:
        records = records[-1:]
    last = records[-1] if records else {}
    # P1-9：空壳快照（无 done/pending/artifact）允许落盘（保持"快速记一笔"的用法），
    # 但必须明确告警——它不是可续跑的归档，续跑时需要人工回溯。
    empty_shell = bool(last) and not (last.get("done") or last.get("pending")
                                      or last.get("artifacts"))
    if last:
        hint = (f"从 {last.get('phase')} 之后续跑；已完成 {len(last.get('done') or [])} 项，"
                f"待完成 {len(last.get('pending') or [])} 项")
        if empty_shell:
            hint = (f"⚠ 最近一次快照（{last.get('phase')}）是空壳：无已完成/待完成项、无产物记录，"
                    f"不构成可续跑的归档。续跑前请人工确认实际进度，或重发一条含 "
                    f"--done/--pending/--artifact 的快照。")
    else:
        hint = "无快照，从头开始"
    out = {
        "node": args.node,
        "count": len(records),
        "corrupt_lines": corrupt,
        "resumable": (not empty_shell) if last else False,
        "checkpoints": records,
        "resume_hint": hint,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_register_artifact(args):
    root = os.path.abspath(args.dir)
    node = args.node
    rel = args.path.replace("\\", "/").strip()
    full = os.path.join(root, rel)
    if not os.path.exists(full):
        sys.exit(f"[state_utils] 产物不存在，无法登记: {rel}")

    # 强制落位：必须位于本节点声明的产物目录之下
    roots = _artifact_roots(node)
    if roots and not any(_under(full, os.path.join(root, r)) for r in roots):
        sys.exit(f"[state_utils] 产物落位违规: {rel} 不在节点 {node} 的产物目录 "
                 f"{roots} 之下（禁止乱放；若确需新增落点，先改 state_defs 的 artifact 声明）")

    by = (args.by or NODES[node]["executor"]).strip()
    reg_path = os.path.join(root, ARTIFACT_REGISTRY)
    reg = {"schema_version": "artifacts-registry/1.0", "artifacts": []}
    if os.path.exists(reg_path):
        try:
            reg = json.loads(open(reg_path, encoding="utf-8").read())
        except json.JSONDecodeError:
            reg = {"schema_version": "artifacts-registry/1.0", "artifacts": []}
    items = reg.setdefault("artifacts", [])

    exists = os.path.isfile(full)
    entry = {
        "path": rel,
        "node": node,
        "kind": args.kind or "",
        "sha256": sha256_of(full) if exists else None,
        "size": os.path.getsize(full) if exists else None,
        "is_dir": not exists,
        "registered_by": by,
        "registered_at": now_iso(),
        "note": args.note or "",
    }
    # 幂等：同路径覆盖为新记录（保留历史在 note 里可追溯）
    prev = [a for a in items if a.get("path") == rel]
    if prev:
        entry["previous_sha256"] = prev[-1].get("sha256")
        items[:] = [a for a in items if a.get("path") != rel]
    items.append(entry)
    os.makedirs(os.path.dirname(reg_path), exist_ok=True)
    save_json_atomic(reg_path, reg)
    print(json.dumps({"registered": True, "path": rel, "sha256": entry["sha256"],
                      "node": node, "total_registered": len(items)}, ensure_ascii=False, indent=2))


def _scan_orphans(root):
    """孤儿文件扫描（供 cmd_orphan_scan 与 project-audit 复用），返回相对路径列表。"""
    roots = _all_artifact_roots()
    # 已登记产物
    registered = set()
    reg_path = os.path.join(root, ARTIFACT_REGISTRY)
    if os.path.exists(reg_path):
        try:
            for a in json.loads(open(reg_path, encoding="utf-8").read()).get("artifacts", []):
                registered.add(a.get("path", ""))
        except json.JSONDecodeError:
            pass
    orphans = []
    for dp, dns, fns in os.walk(root):
        rel_dir = os.path.relpath(dp, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        if parts and (parts[0] in IGNORE_TOP or parts[0] in SCAFFOLD_DIRS):
            dns[:] = []
            continue
        dns[:] = [d for d in dns if d not in IGNORE_TOP and d != ".git"]
        for f in fns:
            if f in IGNORE_NAMES:
                continue
            rel = os.path.relpath(os.path.join(dp, f), root).replace("\\", "/")
            if any(rel.endswith(s) for s in IGNORE_SUFFIX):
                continue
            if any(_under(os.path.join(root, rel), os.path.join(root, r)) for r in roots):
                continue  # 在某个节点产物目录内，合法
            if rel in registered:
                continue
            orphans.append(rel)
    return sorted(orphans)


def cmd_orphan_scan(args):
    root = os.path.abspath(args.dir)
    roots = _all_artifact_roots()
    # 已登记产物（目录形态的登记展开为其子文件）
    registered = set()
    reg_path = os.path.join(root, ARTIFACT_REGISTRY)
    if os.path.exists(reg_path):
        try:
            for a in json.loads(open(reg_path, encoding="utf-8").read()).get("artifacts", []):
                registered.add(a.get("path", ""))
        except json.JSONDecodeError:
            pass
    orphans = _scan_orphans(root)

    report = {
        "scanned_at": now_iso(),
        "artifact_roots": roots,
        "orphan_count": len(orphans),
        "orphans": sorted(orphans),
        "hint": ("orphans 非空说明有文件既不在任何节点产物目录下、也未登记入库。"
                 "处理：移到对应节点产物目录并 register-artifact，或确认属于源码/配置后忽略。"),
    }
    if args.apply:
        os.makedirs(os.path.dirname(os.path.join(root, ORPHAN_REPORT)), exist_ok=True)
        save_json_atomic(os.path.join(root, ORPHAN_REPORT), report)
        print(f"[state_utils] 孤儿扫描结果已落盘: {ORPHAN_REPORT}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
