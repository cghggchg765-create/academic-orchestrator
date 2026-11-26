#!/usr/bin/env python3
"""Render a PDF into per-page PNG images for vision-capable reading and
layout/format verification (mm-pdf-vision workflow).

This script is deliberately read-only and engine-adaptive.  When a vision-capable
model must verify the compiled PDF (page numbering, footer centering, figure/table
placement relative to their citation paragraphs, page-count rules, CJK rendering,
identity information), it renders every page and reads the images one by one.

Engine resolution order (auto):
  1. pdfinfo/pdftoppm (poppler)      — most portable on Linux/CI
  2. mutool (MuPDF)                  — available wherever mupdf-tools is installed
  3. PyMuPDF (fitz, optional package)
  4. ghostscript (gs)

The script never embeds secrets and never calls a model.  Outputs are written to a
fresh directory under --out; a manifest JSON describes the page set so downstream
agents/humans can attach evidence to concrete page numbers.

Usage:
  python scripts/pdf_render_pages.py <pdf>
      [--out <dir>] [--dpi 150] [--engine auto|pdftoppm|mutool|pymupdf|gs|fake]
      [--fake-pages N] [--manifest <path>] [--quiet]

Exit codes: 0 success; 2 blocked (no rendering engine found); 1 usage/IO error.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


RENDERER_VERSION = "pdf-render-pages/1"
MANIFEST_SCHEMA = "pdf-render/1.1"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_engine(requested: str) -> str | None:
    if requested != "auto":
        return requested if requested in {"pdftoppm", "mutool", "pymupdf", "gs", "fake"} else None
    if shutil.which("pdftoppm"):
        return "pdftoppm"
    if shutil.which("mutool"):
        return "mutool"
    try:
        import fitz  # noqa: F401
        return "pymupdf"
    except Exception:
        pass
    if shutil.which("gs"):
        return "gs"
    return None


def page_count_pdfinfo(pdf: Path) -> int | None:
    exe = shutil.which("pdfinfo")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, str(pdf)], capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    match = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    return int(match.group(1)) if match else None


def render_with_engine(pdf: Path, out_dir: Path, dpi: int, engine: str, fake_pages: int) -> tuple[int, list[Path], str]:
    """Render every page; return (page_count, image_paths, engine_note)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / "page"
    if engine == "fake":
        images = [_touch_image(prefix, n) for n in range(1, fake_pages + 1)]
        return fake_pages, images, "fake"
    if engine == "pdftoppm":
        exe = shutil.which("pdftoppm")
        r = subprocess.run([exe, "-png", "-r", str(dpi), str(pdf), str(prefix)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"pdftoppm failed: {r.stderr[:400]}")
        images = sorted(glob.glob(str(out_dir / "page-*.png")))
        return len(images), [Path(p) for p in images], "pdftoppm"
    if engine == "mutool":
        exe = shutil.which("mutool")
        r = subprocess.run([exe, "draw", "-o", str(out_dir / "page-%d.png"), "-r", str(dpi), str(pdf)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"mutool failed: {r.stderr[:400]}")
        images = sorted(glob.glob(str(out_dir / "page-*.png")))
        return len(images), [Path(p) for p in images], "mutool"
    if engine == "gs":
        exe = shutil.which("gs")
        r = subprocess.run([exe, "-sDEVICE=pngalpha", "-r", str(dpi), "-o", str(out_dir / "page-%d.png"), str(pdf)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"gs failed: {r.stderr[:400]}")
        images = sorted(glob.glob(str(out_dir / "page-*.png")))
        return len(images), [Path(p) for p in images], "gs"
    if engine == "pymupdf":
        import fitz
        doc = fitz.open(str(pdf))
        images = []
        for page_no in range(doc.page_count):
            pix = doc.load_page(page_no).get_pixmap(dpi=dpi)
            target = out_dir / f"page-{page_no + 1:04d}.png"
            pix.save(str(target))
            images.append(target)
        count = doc.page_count
        doc.close()
        return count, images, "pymupdf"
    raise RuntimeError(f"unsupported engine: {engine}")


def _touch_image(path: Path, page_no: int) -> Path:
    target = path.parent / f"page-{page_no:04d}.png"
    if not target.exists():
        target.write_bytes(b"")
    return target


def _cache_manifest_path(out_dir: Path, manifest_path: Path | None) -> Path:
    return manifest_path or (out_dir / "manifest.json")


def _cache_hit(pdf: Path, out_dir: Path, manifest_path: Path | None,
               engine: str, dpi: int, fake_pages: int) -> dict[str, object] | None:
    """Return a prior manifest only when its complete render key still matches."""
    path = _cache_manifest_path(out_dir, manifest_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        source = payload.get("source") or {}
        expected_count = fake_pages if engine == "fake" else int(payload.get("page_count", 0))
        if payload.get("schema_version") != MANIFEST_SCHEMA:
            return None
        if payload.get("renderer_version") != RENDERER_VERSION:
            return None
        if source.get("sha256") != sha256_file(pdf) or source.get("size_bytes") != pdf.stat().st_size:
            return None
        if payload.get("engine") != engine or int(payload.get("dpi", -1)) != dpi:
            return None
        if engine == "fake" and int(payload.get("fake_pages", -1)) != fake_pages:
            return None
        pages = payload.get("pages") or []
        if int(payload.get("page_count", -1)) != expected_count or len(pages) != expected_count:
            return None
        for item in pages:
            image = Path(str(item.get("image", "")))
            candidate = image if image.is_absolute() else out_dir.parent / image
            if not candidate.is_file():
                candidate = out_dir / image.name
            if not candidate.is_file():
                return None
        payload["cache_hit"] = True
        return payload
    except (OSError, ValueError, TypeError, KeyError):
        return None


def build_manifest(pdf: Path, out_dir: Path, count: int, images: list[Path], engine: str,
                   dpi: int, manifest_path: Path | None, fake_pages: int = 0) -> dict[str, object]:
    rel_images = [str(p.relative_to(out_dir.parent)) if out_dir.parent in p.parents else str(p)
                  for p in images]
    payload = {
        "schema_version": MANIFEST_SCHEMA,
        "renderer_version": RENDERER_VERSION,
        "source": {"path": str(pdf), "sha256": sha256_file(pdf), "size_bytes": pdf.stat().st_size},
        "rendered_at": utc_now(),
        "engine": engine,
        "dpi": dpi,
        "fake_pages": fake_pages if engine == "fake" else 0,
        "cache_hit": False,
        "page_count": count,
        "pages": [
            {"page": idx + 1, "image": rel}
            for idx, rel in enumerate(rel_images)
        ],
        "out_dir": str(out_dir),
        "visual_notice": ("视觉/像素级检查（页码居中、图表位置、乱码、身份信息、页序）"
                          "由视觉能力模型读图完成；文本层检查另走 pdf_read_preflight/日志。"),
    }
    manifest_path = manifest_path or (out_dir / "manifest.json")
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, manifest_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PDF 分页渲染（供视觉逐页阅读/格式核查）")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=None,
                        help="输出目录（默认 state/reports/pdf-pages/<stem>-<时间戳>）")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--engine", default="auto",
                        choices=["auto", "pdftoppm", "mutool", "pymupdf", "gs", "fake"])
    parser.add_argument("--fake-pages", type=int, default=3, help="fake 引擎页数（仅测试）")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        print(f"PDF 不存在: {pdf}", file=sys.stderr)
        return 1
    engine = find_engine(args.engine)
    if engine is None:
        print("VENV/TOOL_BLOCKED: 无可用的 PDF 渲染引擎（需要 pdftoppm/mutool/PyMuPDF/gs 之一）", file=sys.stderr)
        print("安装其一后重试：poppler-utils、mupdf-tools、pymupdf、ghostscript", file=sys.stderr)
        return 2
    out_dir = args.out
    if out_dir is None:
        stem = pdf.stem
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = Path("state/reports/pdf-pages") / f"{stem}-{stamp}"
    out_dir = out_dir.resolve()
    manifest_path = args.manifest.resolve() if args.manifest else None
    cached = _cache_hit(pdf, out_dir, manifest_path, engine, args.dpi, args.fake_pages)
    if cached is not None:
        if not args.quiet:
            print("RENDER_CACHE_HIT")
            print(f"engine={cached['engine']} pages={cached['page_count']} dpi={cached['dpi']}")
            print(f"out={out_dir}")
            print(f"manifest={_cache_manifest_path(out_dir, manifest_path)}")
        return 0
    try:
        count, images, engine_note = render_with_engine(pdf, out_dir, args.dpi, engine, args.fake_pages)
    except Exception as exc:  # engine/runtime failure
        print(f"RENDER_FAILED: {exc}", file=sys.stderr)
        return 1
    payload = build_manifest(pdf, out_dir, count, images, engine_note, args.dpi, manifest_path, args.fake_pages)
    if not args.quiet:
        print("RENDER_READY")
        print(f"engine={engine_note} pages={count} dpi={args.dpi}")
        print(f"out={out_dir}")
        print(f"manifest={manifest_path or (out_dir / 'manifest.json')}")
        print("下一步：具备视觉能力时逐页读取 page-*.png 并按 mm-pdf-vision 检查清单核查；")
        print("无视觉能力时生成人工核查请求单（检查清单 + 图片路径），门禁标记 PENDING 而非 PASS。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())