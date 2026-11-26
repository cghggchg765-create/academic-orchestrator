#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw_lock.py — 原始数据只读锁定（独立于 dataprep 的基线）。

问题：血缘台账里的 raw 哈希由 dataprep 自己登记，存在"先改数据再登记"的漏洞。
本工具在 **N0/N1（数据尚未被处理）** 建立独立基线 `Data/raw_lock.json`，
此后任何对 Data/raw 的改动都会在 D1 校验时暴露。

用法:
    python scripts/raw_lock.py --root .                # 建立/校验锁定（幂等，已锁则校验）
    python scripts/raw_lock.py --root . --force         # 强制重建基线（仅用户明确要求时）
    python scripts/raw_lock.py --root . --check         # 只校验，不创建
    python scripts/raw_lock.py --root . --json

退出码：0 = 已锁定或校验通过；1 = 检测到篡改；2 = 参数/环境问题
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LOCK_REL = os.path.join("Data", "raw_lock.json")
RAW_REL = os.path.join("Data", "raw")
SKIP_NAMES = {"readme.txt", ".gitkeep", ".gitignore"}
SKIP_SUFFIX = {".pyc", ".tmp", ".swp"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scan_raw(root: Path) -> dict[str, dict]:
    """扫描 Data/raw 下所有数据文件（跳过说明/占位文件）。"""
    raw_dir = root / RAW_REL
    out: dict[str, dict] = {}
    if not raw_dir.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(raw_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in sorted(filenames):
            if fn in SKIP_NAMES or Path(fn).suffix.lower() in SKIP_SUFFIX:
                continue
            full = Path(dirpath) / fn
            rel = full.relative_to(root).as_posix()
            out[rel] = {"sha256": _sha256(full), "size": full.stat().st_size}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="原始数据只读锁定")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--force", action="store_true", help="强制重建基线（覆盖已有锁定）")
    ap.add_argument("--check", action="store_true", help="只校验，不创建")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    lock_path = root / LOCK_REL
    current = scan_raw(root)

    if not current:
        msg = f"Data/raw 下没有可锁定的数据文件（{RAW_REL}）；若项目尚无原始数据请先放入"
        if args.json:
            print(json.dumps({"status": "EMPTY", "detail": msg}, ensure_ascii=False))
        else:
            print(msg, file=sys.stderr)
        return 0 if args.check else 2

    if lock_path.exists() and not args.force:
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"锁定文件损坏: {exc}", file=sys.stderr)
            return 2
        base = lock.get("files") or {}
        tampered, added, removed = [], [], []
        for rel, meta in current.items():
            if rel not in base:
                added.append(rel)
            elif base[rel].get("sha256") != meta["sha256"]:
                tampered.append({"path": rel, "locked": base[rel].get("sha256"),
                                 "actual": meta["sha256"]})
        for rel in base:
            if rel not in current:
                removed.append(rel)
        ok = not tampered and not added and not removed
        report = {
            "status": "PASS" if ok else "TAMPERED",
            "locked_at": lock.get("locked_at"),
            "file_count": len(base),
            "tampered": tampered,
            "added": added,
            "removed": removed,
            "hint": ("原始数据自锁定以来未被改动" if ok else
                     "原始数据发生变更。若属误操作请从备份恢复；确需变更须经用户确认后 --force 重建基线"),
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"raw 锁定校验：{report['status']}")
            for t in tampered:
                print(f"  ✗ 被修改: {t['path']}（锁定 {t['locked'][:12]}… 实际 {t['actual'][:12]}…）")
            for a in added:
                print(f"  + 新增未登记: {a}")
            for r in removed:
                print(f"  - 已删除: {r}")
            if ok:
                print(f"  ✓ {len(base)} 个原始数据文件与锁定一致")
        return 0 if ok else 1

    if args.check:
        print(f"尚未建立 raw 锁定基线: {LOCK_REL}（请在不带 --check 时运行一次）", file=sys.stderr)
        return 1

    lock = {
        "schema_version": "raw-lock/1.0",
        "locked_at": _now(),
        "locked_by": "main-agent (N0/N1 数据导入后、处理前)",
        "note": "原始数据只读基线。任何改动都会在 D1 血缘校验中被判为篡改。",
        "files": current,
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = {"status": "LOCKED", "lock_file": LOCK_REL, "file_count": len(current),
           "locked_at": lock["locked_at"]}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"已锁定 {len(current)} 个原始数据文件 → {LOCK_REL}")
        print("此后任何对 Data/raw 的修改都会被 D1 血缘校验判定为篡改。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
