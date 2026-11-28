#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部资料隔离与污染检测。

要解决的问题
------------
开发过程中会引入同行代码、方案、论文等外部资料。这些资料应当**可读可用**，
但不能污染自有产物：不能悄悄变成"我们写的代码"，不能残留在交付物里，
也不能让子 Agent 把参考实现直接复制进来当成原创。

三层隔离
--------
1. **只读引用区** `External/refs/`：外部资料唯一允许落地的地方。
   入库即哈希锁定（`External/refs.lock.json`），此后任何改动都能检出。
   目录自带 `.readonly` 标记与 README，说明"只读、可引用、不可修改"。

2. **派生登记** `External/derived.jsonl`：把外部资料转成自有产物时
   （如"参考了 A 项目的算法，重写为 Code/problem_1/model.py"），
   必须登记一行来源映射。这样"哪段代码有外部来源"永远可追溯，
   而不是靠人记。

3. **污染检测**：扫描自有产物区（Code/ ReportPaper/ ModelDocs/ 等），
   与外部资料做内容比对。命中以下情况即报：
     · 自有文件里出现与外部文件高度重合的长片段（疑似直接复制）
     · 外部资料文件出现在自有产物目录内（位置污染）
     · 派生登记缺失：代码里有外部来源标记但没登记

判据口径
--------
"高度重合"用归一化后的 n-gram 重合率，阈值见 COPY_SIMILARITY_THRESHOLD。
只对长度超过 MIN_COMPARE_LINES 的文件比对（短片段如 import 语句必然相同）。

用法
----
    python scripts/external_isolation.py init      --root <项目>   # 建只读引用区
    python scripts/external_isolation.py add <文件> --root <项目>  # 纳入外部资料并锁定
    python scripts/external_isolation.py lock      --root <项目>   # 重建/校验锁定
    python scripts/external_isolation.py check     --root <项目>   # 校验只读区未被改动
    python scripts/external_isolation.py derive --ref <外部文件> --target <产物> --note "怎么用的"
    python scripts/external_isolation.py scan      --root <项目>   # 污染检测
    python scripts/external_isolation.py scan      --root <项目> --json

只读：check / scan 不修改任何文件。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTERNAL_DIR = "External"
REFS_DIR = "External/refs"
LOCK_FILE = "External/refs.lock.json"
DERIVED_FILE = "External/derived.jsonl"
READONLY_MARK = "External/.readonly"

# 自有产物区：这些目录里的文件必须是我们自己产生的，不允许外部资料混入
PRODUCT_DIRS = ("Code", "ReportPaper", "ModelDocs", "ResultFigures", "SubmissionPackage")

# 比对口径
# 门槛 8 行而非更高：竞赛/脚本类模块常见 10-20 行的单函数文件，
# 门槛定 12 会让"整份文件被复制"这种最严重的情况反而漏检。
# 代价是短文件可能误报——用双向重合 + 60% 阈值压住误报。
MIN_COMPARE_LINES = 8
COPY_SIMILARITY_THRESHOLD = 0.60  # n-gram 重合率超过此值判"疑似复制"
NGRAM_SIZE = 5                  # 5 行滑窗（比 6 更适配短文件）
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".pdf", ".zip", ".tar", ".gz", ".7z",
               ".xlsx", ".docx", ".pptx", ".pyc", ".so", ".dll",
               # 图像/排版二进制（ResultFigures / ReportPaper 常见）——按文本读只会得到乱码
               ".gif", ".tif", ".tiff", ".bmp", ".webp", ".ico", ".psd", ".ai",
               # 数据 / 模型二进制（Code/output 常见）
               ".npy", ".npz", ".pkl", ".pickle", ".h5", ".hdf5", ".mat", ".sav",
               ".parquet", ".feather", ".db", ".sqlite", ".sqlite3",
               ".pt", ".pth", ".ckpt", ".onnx", ".joblib",
               # 旧版 office 与其余压缩/分发格式
               ".xls", ".doc", ".ppt", ".rar", ".bz2", ".xz", ".lzma", ".whl", ".egg"}
SKIP_NAMES = {"readme.md", ".gitkeep", ".readonly"}
# 单文件读取上限：n-gram 比对只对文本有意义，超大文件几乎必然是二进制/数据转储，
# 整读进内存会让 scan 崩溃（在门禁里表现为"检测不可用"的假 fail-closed）。
MAX_SCAN_BYTES = 32 * 1024 * 1024


# ---------------------------------------------------------------- 基础工具

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iter_files(base: Path):
    """递归列出可比对的文本文件（跳过二进制、说明文件、隐藏目录）。"""
    if not base.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in sorted(filenames):
            if fn.lower() in SKIP_NAMES:
                continue
            p = Path(dirpath) / fn
            if p.suffix.lower() in SKIP_SUFFIX:
                continue
            yield p


def _normalized_lines(path: Path) -> list[str]:
    """读取并归一化：去空行、去行首尾空白、压多空格、忽略大小写。

    归一化是为了让"改几个空格/换行"这种伪原创能被识别出来。
    超过 MAX_SCAN_BYTES 的文件直接跳过（不比对、不误报）。
    """
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        s = re.sub(r"\s+", " ", line).strip().lower()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        out.append(s)
    return out


def _ngrams(lines: list[str], n: int = NGRAM_SIZE) -> set[tuple[str, ...]]:
    if len(lines) < n:
        return set()
    return {tuple(lines[i:i + n]) for i in range(len(lines) - n + 1)}


# ---------------------------------------------------------------- 1. 只读引用区

def cmd_init(root: Path) -> int:
    refs = root / REFS_DIR
    refs.mkdir(parents=True, exist_ok=True)
    mark = root / READONLY_MARK
    if not mark.exists():
        mark.write_text(
            "此目录（External/refs/）是只读引用区。\n"
            "\n"
            "规则：\n"
            "  1. 外部资料（同行代码/方案/论文/模板）只允许放在这里，不得放进 Code/ 等产物目录。\n"
            "  2. 文件入库后由 refs.lock.json 哈希锁定；需要更新请用 add 重新纳入，不要手改。\n"
            "  3. 把外部内容转成自有产物时，用 derive 命令登记来源映射。\n"
            "  4. 子 Agent 可以读这里，但不得写入；引用后在产物中标注来源。\n"
            "\n"
            "校验：python scripts/external_isolation.py check --root .\n"
            "扫描污染：python scripts/external_isolation.py scan --root .\n",
            encoding="utf-8")
    readme = refs / "README.md"
    if not readme.exists():
        readme.write_text(
            "# External/refs — 外部参考资料（只读）\n\n"
            "放同行的代码、方案、论文、模板等。这里的文件受哈希锁定保护，改动会被 check 检出。\n\n"
            "## 怎么用\n\n"
            "```bash\n"
            "# 纳入外部资料（自动锁定）\n"
            "python scripts/external_isolation.py add path/to/peer_solution.py --root . --note \"来源：XX 项目\"\n\n"
            "# 校验只读区没被改过\n"
            "python scripts/external_isolation.py check --root .\n\n"
            "# 把外部实现转成自有代码时登记来源\n"
            "python scripts/external_isolation.py derive \\\n"
            "  --ref External/refs/peer_solution.py \\\n"
            "  --target Code/problem_1/model.py \\\n"
            "  --note \"参考其目标函数构造，按本问约束重写\"\n\n"
            "# 扫描自有产物是否混入外部资料\n"
            "python scripts/external_isolation.py scan --root .\n"
            "```\n",
            encoding="utf-8")
    print(f"只读引用区就绪: {refs}")
    print(f"  标记文件: {mark}")
    return cmd_lock(root, quiet=False)


def _load_lock(root: Path) -> dict:
    path = root / LOCK_FILE
    if not path.is_file():
        return {"version": "1.0", "updated_at": None, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": "1.0", "updated_at": None, "files": {}, "_corrupt": True}
    if not isinstance(data, dict):
        return {"version": "1.0", "updated_at": None, "files": {}, "_corrupt": True}
    data.setdefault("files", {})
    return data


def _save_lock(root: Path, lock: dict) -> None:
    lock["updated_at"] = _now()
    path = root / LOCK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def cmd_add(root: Path, src: Path, note: str = "", force: bool = False) -> int:
    refs = root / REFS_DIR
    refs.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        print(f"[external] 源路径不存在: {src}", file=sys.stderr)
        return 1
    lock = _load_lock(root)
    files = lock.setdefault("files", {})

    targets = [src] if src.is_file() else list(_iter_files(src))
    added = 0
    for f in targets:
        if f.is_file():
            rel_in = f.name if src.is_file() else f.relative_to(src).as_posix()
            dst = refs / rel_in
        else:
            continue
        rel = dst.relative_to(root).as_posix()
        if dst.exists() and not force:
            print(f"[external] 已存在，跳过（--force 覆盖）: {rel}", file=sys.stderr)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(f.read_bytes())
        files[rel] = {"sha256": _sha256(dst), "size": dst.stat().st_size,
                      "origin": note or str(f), "added_at": _now()}
        added += 1
        print(f"  纳入: {rel}  ({files[rel]['sha256'][:12]}…)")
    _save_lock(root, lock)
    print(f"[external] 新增 {added} 个外部资料文件，已锁定")
    return 0


def cmd_lock(root: Path, quiet: bool = True) -> int:
    """重建锁定：以当前磁盘内容为准（用于首次锁定或显式更新）。"""
    refs = root / REFS_DIR
    if not refs.is_dir():
        print(f"[external] 引用区不存在: {refs}（先跑 init）", file=sys.stderr)
        return 1
    lock = _load_lock(root)
    files = {}
    for p in _iter_files(refs):
        if p.name == "README.md":
            continue
        rel = p.relative_to(root).as_posix()
        old = (lock.get("files") or {}).get(rel) or {}
        files[rel] = {"sha256": _sha256(p), "size": p.stat().st_size,
                      "origin": old.get("origin", ""), "added_at": old.get("added_at", _now())}
    lock["files"] = files
    _save_lock(root, lock)
    if not quiet:
        print(f"  已锁定 {len(files)} 个外部资料文件 → {LOCK_FILE}")
    return 0


def cmd_check(root: Path, as_json: bool = False) -> int:
    """校验只读区：任何增删改都报 TAMPERED。"""
    refs = root / REFS_DIR
    lock_path = root / LOCK_FILE
    problems: list[str] = []
    if not lock_path.is_file():
        result = {"status": "MISSING", "detail": f"锁定文件不存在: {LOCK_FILE}",
                  "problems": [f"未建立基线：{LOCK_FILE}"]}
        if as_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("[external] 只读区校验：MISSING（尚未建立锁定基线）")
        return 1 if refs.is_dir() else 0

    lock = _load_lock(root)
    if lock.get("_corrupt"):
        problems.append("锁定文件损坏，无法校验")
    recorded = lock.get("files") or {}

    current = {}
    if refs.is_dir():
        for p in _iter_files(refs):
            if p.name == "README.md":
                continue
            current[p.relative_to(root).as_posix()] = _sha256(p)

    for rel, meta in sorted(recorded.items()):
        if rel not in current:
            problems.append(f"外部资料被删除: {rel}")
        elif current[rel] != meta.get("sha256"):
            problems.append(f"外部资料被修改: {rel}（锁定 {str(meta.get('sha256'))[:12]}… "
                            f"实际 {current[rel][:12]}…）")
    for rel in sorted(set(current) - set(recorded)):
        problems.append(f"未经 add 就放进引用区: {rel}")

    status = "TAMPERED" if problems else "PASS"
    result = {"status": status, "checked": len(current), "recorded": len(recorded),
              "problems": problems}
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[external] 只读区校验：{status}（锁定 {len(recorded)} / 实际 {len(current)}）")
        for p in problems:
            print(f"  ✗ {p}")
    return 0 if status == "PASS" else 1


# ---------------------------------------------------------------- 2. 派生登记

def cmd_derive(root: Path, ref: str, target: str, note: str, node: str = "") -> int:
    refs = root / REFS_DIR
    ref_path = (root / ref) if not Path(ref).is_absolute() else Path(ref)
    if not ref_path.exists():
        print(f"[external] 外部资料不存在: {ref}", file=sys.stderr)
        return 1
    rel_ref = ref_path.relative_to(root).as_posix() if ref_path.is_relative_to(root) else str(ref_path)
    # 只允许登记引用区内的资料，避免把产物目录当外部来源
    if not rel_ref.startswith(REFS_DIR + "/"):
        print(f"[external] 只能登记 {REFS_DIR}/ 下的外部资料，实际: {rel_ref}", file=sys.stderr)
        return 1

    target_path = root / target
    record = {
        "ts": _now(),
        "ref": rel_ref,
        "ref_sha256": _sha256(ref_path) if ref_path.is_file() else None,
        "target": target.replace("\\", "/"),
        "target_exists": target_path.exists(),
        "target_sha256": _sha256(target_path) if target_path.is_file() else None,
        "node": node or None,
        "note": note,
    }
    path = root / DERIVED_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[external] 已登记派生来源: {rel_ref} → {record['target']}")
    return 0


def _load_derived(root: Path) -> list[dict]:
    path = root / DERIVED_FILE
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


# ---------------------------------------------------------------- 3. 污染检测

def cmd_scan(root: Path, as_json: bool = False, threshold: float = COPY_SIMILARITY_THRESHOLD) -> int:
    # 阈值必须在 (0, 1]：
    #   · <=0 会让"重合率 0%"也过线（best 初值 0.0 >= threshold），把所有 ≥8 行产物
    #     全部误判 HIGH（ref=None, similarity=0.0），门禁等于全拒；
    #   · >1 则任何重合率都不可能达到，内容复制检测被静默关闭。
    if not (threshold > 0 and threshold <= 1):
        print(f"[external] --threshold 必须在 (0, 1] 区间，实际: {threshold}", file=sys.stderr)
        return 2
    refs = root / REFS_DIR
    ref_lines: dict[str, list[str]] = {}
    # 全部外部文件名（不受行数门槛限制）：位置污染按名字判定，短文件同样要能检出
    ref_names: dict[str, str] = {}
    if refs.is_dir():
        for p in _iter_files(refs):
            if p.name == "README.md":
                continue
            rel_ref = p.relative_to(root).as_posix()
            ref_names[p.name] = rel_ref
            lines = _normalized_lines(p)
            if len(lines) >= MIN_COMPARE_LINES:
                ref_lines[rel_ref] = lines

    derived = _load_derived(root)
    # 登记豁免按 (target, ref) 配对：登记"A 派生出了 T"只豁免 T 与 A 的重合，
    # 不能让 T 从此对其它未登记的外部文件免疫（路径级豁免等于登记一次、终身全免）。
    derived_pairs = {(d.get("target"), d.get("ref"))
                     for d in derived if d.get("target") and d.get("ref")}

    findings: list[dict] = []

    # A. 位置污染：外部资料出现在自有产物目录内
    for prod in PRODUCT_DIRS:
        base = root / prod
        if not base.is_dir():
            continue
        for p in _iter_files(base):
            rel = p.relative_to(root).as_posix()
            # 与引用区同名的文件出现在产物区 → 高度可疑（按文件名，不看行数）
            name = p.name
            if name in ref_names:
                findings.append({
                    "kind": "location_contamination", "severity": "HIGH",
                    "path": rel,
                    "detail": f"产物目录内出现与外部资料同名的文件（外部: {ref_names[name]}）",
                })

    # B. 内容复制：产物与外部资料 n-gram 重合
    if ref_lines:
        ref_grams = {rel: _ngrams(lines) for rel, lines in ref_lines.items()}
        for prod in PRODUCT_DIRS:
            base = root / prod
            if not base.is_dir():
                continue
            for p in _iter_files(base):
                rel = p.relative_to(root).as_posix()
                lines = _normalized_lines(p)
                if len(lines) < MIN_COMPARE_LINES:
                    continue
                grams = _ngrams(lines)
                if not grams:
                    continue
                best = (0.0, None)
                for ref_rel, rg in ref_grams.items():
                    if not rg:
                        continue
                    # 双向重合取较大者：
                    #   · 产物套用外部（产物 ⊂ 外部）→ 用 overlap_of_product 会低估；
                    #   · 产物是外部超集（产物 ⊃ 外部）→ 用 overlap_of_ref 才是真实占比。
                    # 任一方向高度重合都说明存在未声明的大段挪用，取 max 更保守。
                    overlap_of_product = len(grams & rg) / len(grams)
                    overlap_of_ref = len(grams & rg) / len(rg)
                    overlap = max(overlap_of_product, overlap_of_ref)
                    if overlap > best[0]:
                        best = (overlap, ref_rel)
                if best[0] >= threshold:
                    registered = (rel, best[1]) in derived_pairs
                    findings.append({
                        "kind": "content_copy", "severity": "HIGH" if not registered else "INFO",
                        "path": rel, "ref": best[1],
                        "similarity": round(best[0], 3),
                        "detail": (f"与 {best[1]} 的 {NGRAM_SIZE} 行片段重合 {best[0]:.0%}"
                                   + ("（已登记派生来源，视为合规参考）" if registered
                                      else "（未登记派生来源，疑似直接复制）")),
                    })

    # C. 派生登记失效：登记过但目标已不存在
    for d in derived:
        tgt = d.get("target")
        if tgt and not (root / tgt).exists():
            findings.append({
                "kind": "stale_derivation", "severity": "LOW",
                "path": tgt, "ref": d.get("ref"),
                "detail": "派生登记指向的目标已不存在（可能被重命名或删除，需同步更新登记）",
            })

    status = "CONTAMINATED" if any(f["severity"] == "HIGH" for f in findings) else "CLEAN"
    result = {
        "status": status,
        "external_files": len(ref_lines),
        "derivations": len(derived),
        "threshold": threshold,
        "findings": findings,
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[external] 污染检测：{status}（外部资料 {len(ref_lines)} / 派生登记 {len(derived)}）")
        if not findings:
            print("  ✅ 未发现污染")
        for f in findings:
            print(f"  [{f['severity']}] {f['kind']}: {f['path']} — {f['detail']}")
    return 0 if status == "CLEAN" else 1


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description="外部资料隔离与污染检测")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="创建只读引用区并建立锁定")
    p.add_argument("--root", default=".")

    p = sub.add_parser("add", help="纳入外部资料并锁定")
    p.add_argument("src", help="外部文件或目录")
    p.add_argument("--root", default=".")
    p.add_argument("--note", default="", help="来源说明（写进锁定记录）")
    p.add_argument("--force", action="store_true", help="覆盖已存在的同名文件")

    p = sub.add_parser("lock", help="按当前磁盘内容重建锁定（显式更新基线）")
    p.add_argument("--root", default=".")

    p = sub.add_parser("check", help="校验只读区未被改动")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("derive", help="登记外部资料 → 自有产物的来源映射")
    p.add_argument("--ref", required=True, help="外部资料路径（须在 External/refs/ 下）")
    p.add_argument("--target", required=True, help="自有产物路径")
    p.add_argument("--note", required=True, help="怎么用的：参考了什么、怎么改写的")
    p.add_argument("--node", default="", help="关联节点（如 N4）")
    p.add_argument("--root", default=".")

    p = sub.add_parser("scan", help="扫描自有产物是否混入外部资料")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    p.add_argument("--threshold", type=float, default=COPY_SIMILARITY_THRESHOLD,
                   help=f"n-gram 重合率阈值（默认 {COPY_SIMILARITY_THRESHOLD}）")

    args = ap.parse_args()
    root = Path(args.root).resolve()

    if args.cmd == "init":
        return cmd_init(root)
    if args.cmd == "add":
        return cmd_add(root, Path(args.src).resolve(), args.note, args.force)
    if args.cmd == "lock":
        return cmd_lock(root)
    if args.cmd == "check":
        return cmd_check(root, args.json)
    if args.cmd == "derive":
        return cmd_derive(root, args.ref, args.target, args.note, args.node)
    if args.cmd == "scan":
        return cmd_scan(root, args.json, args.threshold)
    return 2


if __name__ == "__main__":
    sys.exit(main())
