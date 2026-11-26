"""Render every page of a PDF to PNG and write a manifest.

This is the entry point the CUMCM workflow expects from mm-pdf-vision —
latex_linter / reviewer / orchestrator / mm-viz-reviewer / mm-latex-writing all
invoke it as `python scripts/pdf_render_pages.py <pdf> --out <dir> --dpi 150` —
so the CLI signature and the manifest field names are a contract.

Implementation note: rendering is done entirely with PyMuPDF, so this script
never spawns an external process. Earlier revisions shelled out to
pdftoppm/mutool/gs; that was dropped deliberately so the tool has a single,
auditable code path and no argv-building surface at all. If PyMuPDF is missing
the script exits non-zero with TOOL_BLOCKED instead of silently producing a
partial manifest.

Usage:
    python pdf_render_pages.py <pdf> [--out DIR] [--dpi 150] [--first N] [--last N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DPI = 150

try:
    import fitz  # PyMuPDF
except ImportError:
    print("TOOL_BLOCKED: 本脚本需要 PyMuPDF。", file=sys.stderr)
    print("  安装：pip install pymupdf", file=sys.stderr)
    print("  提示：项目 venv 常未安装；可改用装有 PyMuPDF 的解释器运行本脚本，", file=sys.stderr)
    print("        例如 <python-with-pymupdf> scripts/pdf_render_pages.py <pdf> --out <dir>", file=sys.stderr)
    raise SystemExit(3)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a PDF to per-page PNGs + manifest.json")
    ap.add_argument("pdf", help="PDF 路径")
    ap.add_argument("--out", default="state/reports/pdf-pages/pdf",
                    help="输出目录（默认 state/reports/pdf-pages/pdf）")
    ap.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"渲染 DPI（默认 {DEFAULT_DPI}）")
    ap.add_argument("--first", type=int, default=1, help="起始页（默认 1）")
    ap.add_argument("--last", type=int, default=0, help="结束页（默认到末页）")
    args = ap.parse_args()

    pdf = Path(args.pdf).expanduser()
    if not pdf.is_file():
        print(f"PDF_NOT_FOUND: {pdf}", file=sys.stderr)
        return 2
    pdf = pdf.resolve()
    dpi = max(36, min(int(args.dpi), 600))

    try:
        doc = fitz.open(str(pdf))
    except Exception as exc:  # noqa: BLE001
        print(f"PDF_UNREADABLE: 无法打开 {pdf}：{exc}", file=sys.stderr)
        return 2

    total = doc.page_count
    first = max(1, min(int(args.first), total))
    last = total if not args.last else max(first, min(int(args.last), total))

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    pages: list[Path] = []
    for pno in range(first - 1, last):
        target = out / f"page-{pno + 1:04d}.png"
        doc[pno].get_pixmap(matrix=matrix).save(str(target))
        pages.append(target)

    if not pages:
        print("RENDER_EMPTY: 未产出任何页面图片，请检查页范围参数。", file=sys.stderr)
        return 3

    manifest = {
        "source_pdf": str(pdf),
        "source_sha256": sha256(pdf),
        "page_count": total,
        "rendered_pages": len(pages),
        "first_page": first,
        "last_page": last,
        "dpi": dpi,
        "engine": "pymupdf",
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "pages": [str(p.resolve()) for p in pages],
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    print(f"引擎=pymupdf  渲染 {len(pages)}/{total} 页  dpi={dpi}")
    print(f"输出目录: {out.resolve()}")
    print(f"manifest: {manifest_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
