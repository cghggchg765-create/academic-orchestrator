#!/usr/bin/env python3
"""latex_compile_check.py — LaTeX 编译产物复用（哈希判重，避免每轮全量重编译）。

背景：N7 写作链路中 latex_linter / typesetting / 反向复核每轮都会重新编译同一份
LaTeX 源。当源文件（main.tex/preamble.tex/ref.bib/sections/*.tex 等）自上次编译
后字节不变时，重编译结果必然相同——本工具用源集哈希决定是否跳过，把"每轮重编译"
收敛为"源变更才编译"，且门禁语义不变（源任何变化都会触发重编译）。

用法：
  python latex_compile_check.py --tex-dir <目录> [--build-dir <目录>] [--force]
  python latex_compile_check.py --tex-dir <目录> --check          # 仅判重，不执行编译

判重规则：源集 sha256 与上次编译留存一致 且 目标 PDF 存在 且 PDF 不旧于任一源 → NO_RECOMPILE；
否则 NEEDS_RECOMPILE（默认模式会继续执行 standard 编译：xelatex ×2 + bibtex + xelatex ×1，
写回最新哈希戳）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

STAMP_NAME = ".latex-compile-stamp.json"
LATEX_MAIN_CANDIDATES = ("main.tex", "Main.tex", "paper.tex", "Thesis.tex")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect_inputs(tex_dir: Path) -> list[Path]:
    """源集：目录下全部 .tex/.bib（含子目录），按相对路径排序保证哈希稳定。"""
    files = [p for p in tex_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".tex", ".bib")]
    return sorted(files, key=lambda p: p.relative_to(tex_dir).as_posix())


def compute_source_hash(tex_dir: Path) -> str:
    blobs = []
    for path in collect_inputs(tex_dir):
        rel = path.relative_to(tex_dir).as_posix()
        try:
            content = path.read_bytes()
        except OSError:
            content = b""
        blobs.append(f"{rel}:{len(content)}:{_sha256_bytes(content)}")
    return _sha256_bytes("\n".join(blobs).encode("utf-8"))


def find_main(tex_dir: Path) -> Path | None:
    for name in LATEX_MAIN_CANDIDATES:
        candidate = tex_dir / name
        if candidate.is_file():
            return candidate
    # 兜底：目录中存在唯一一个在 preamble 之前有 \documentclass 的 .tex
    for path in sorted(tex_dir.glob("*.tex")):
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
        except OSError:
            continue
        if "\\documentclass" in head:
            return path
    return None


def read_stamp(build_dir: Path) -> dict | None:
    stamp = build_dir / STAMP_NAME
    if not stamp.is_file():
        return None
    try:
        return json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_stamp(build_dir: Path, source_hash: str, pdf_path: Path | None) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / STAMP_NAME).write_text(
        json.dumps({"source_sha256": source_hash,
                    "pdf": pdf_path.name if pdf_path else None,
                    "compiled_epoch_ms": int(__import__("time").time() * 1000)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def needs_recompile(tex_dir: Path, build_dir: Path, source_hash: str) -> tuple[bool, dict]:
    stamp = read_stamp(build_dir)
    if not stamp or stamp.get("source_sha256") != source_hash:
        return True, {"reason": "hash_mismatch_or_no_stamp"}
    pdf_name = stamp.get("pdf")
    pdf = (build_dir / pdf_name) if pdf_name else None
    if pdf is None or not pdf.is_file():
        return True, {"reason": "pdf_missing"}
    newest_source = max((p.stat().st_mtime_ns for p in collect_inputs(tex_dir)), default=0)
    if pdf.stat().st_mtime_ns < newest_source:
        return True, {"reason": "pdf_older_than_sources"}
    return False, {"reason": "unchanged", "pdf": str(pdf)}


def run_compile(tex_dir: Path, build_dir: Path, main_file: Path) -> tuple[bool, str]:
    """标准编译：xelatex ×2 → bibtex → xelatex ×1，输出到 build_dir。"""
    build_dir.mkdir(parents=True, exist_ok=True)
    latex = shutil.which("xelatex") or shutil.which("pdflatex")
    if latex is None:
        return False, "LATEX_UNAVAILABLE: 未找到 xelatex/pdflatex，无法执行编译"
    bibtex = shutil.which("bibtex")
    base_args = [latex, "-interaction=nonstopmode", "-halt-on-error",
                 f"-output-directory={build_dir}", str(main_file)]
    for _ in range(2):
        r = subprocess.run(base_args, cwd=tex_dir, capture_output=True, text=True)
        if r.returncode != 0:
            return False, r.stdout[-1500:] or r.stderr[-500:]
    if bibtex:
        aux = build_dir / (main_file.stem + ".aux")
        if aux.is_file():
            subprocess.run([bibtex, str(aux)], cwd=build_dir, capture_output=True, text=True)
            subprocess.run(base_args, cwd=tex_dir, capture_output=True, text=True)
    pdf = build_dir / (main_file.stem + ".pdf")
    if not pdf.is_file():
        return False, "LATEX_MAYBE_ERROR: 编译结束但未生成 PDF"
    return True, f"RECOMPILED: {pdf}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tex-dir", required=True, type=Path, help="LaTeX 源目录")
    parser.add_argument("--build-dir", type=Path, default=None, help="编译输出目录（默认 tex-dir/.build）")
    parser.add_argument("--check", action="store_true", help="仅判重，不执行编译")
    parser.add_argument("--force", action="store_true", help="忽略哈希戳强制重编译")
    args = parser.parse_args(argv)

    tex_dir = args.tex_dir.resolve()
    if not tex_dir.is_dir():
        print(f"ERROR: 目录不存在: {tex_dir}")
        return 2
    build_dir = (args.build_dir or tex_dir / ".build").resolve()
    main_file = find_main(tex_dir)
    if main_file is None and not args.check:
        print("ERROR: 未找到主 .tex（main.tex/paper.tex/Thesis.tex 或含 \\documentclass 的 .tex）")
        return 2

    source_hash = compute_source_hash(tex_dir)
    if args.force:
        needed, info = True, {"reason": "forced"}
    else:
        needed, info = needs_recompile(tex_dir, build_dir, source_hash)

    if args.check or main_file is None:
        print(("NEEDS_RECOMPILE" if needed else "NO_RECOMPILE") +
              f" {json.dumps(info, ensure_ascii=False)}")
        return 0 if not needed and not args.check else 0

    if not needed:
        print(f"NO_RECOMPILE {json.dumps(info, ensure_ascii=False)}")
        return 0

    ok, message = run_compile(tex_dir, build_dir, main_file)
    if ok:
        write_stamp(build_dir, source_hash, build_dir / (main_file.stem + ".pdf"))
        print(message)
        return 0
    print(message)
    return 1


if __name__ == "__main__":
    sys.exit(main())