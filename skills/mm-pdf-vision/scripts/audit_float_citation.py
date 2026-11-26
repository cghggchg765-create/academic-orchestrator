"""Audit whether each figure/table is cited before it appears.

Reading order rule: a float must be referenced *before* the reader meets it.
The float's position is taken from its caption block ("图 N" / "表 N") actually
rendered in the PDF; each reference's position comes from the hyperref link
rectangle.  A float is flagged when its earliest reference lies below it on the
same page, or on a later page.

Usage: python audit_float_citation.py <pdf>
"""
# Bundled with mm-pdf-vision (latex layout QA toolkit). Originally written for the CUMCM 2026 C-problem layout review.
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    raise SystemExit(
        "本脚本需要 PyMuPDF（读取 PDF 文字块与内部链接）。\n"
        "  安装：pip install pymupdf\n"
        "  提示：项目 venv 常未安装，可改用装有 PyMuPDF 的解释器运行；\n"
        "        若解释器已换但仍报错，请确认未在缺依赖的环境里调用。"
    )


def label_map(aux: Path) -> dict[str, tuple[str, str, int]]:
    """hyperref destination -> (label, printed number, float page)"""
    out = {}
    pat = re.compile(
        r"\\newlabel\{((?:fig|tab):[^}]+)\}\{\{([^}]*)\}\{(\d+)\}\{[^}]*\}\{"
        r"((?:figure|table)\.caption\.\d+)\}")
    for m in pat.finditer(aux.read_text(encoding="utf-8")):
        out[m.group(4)] = (m.group(1), m.group(2), int(m.group(3)))
    return out


def caption_y(page: "fitz.Page", kind: str, number: str) -> float | None:
    """Top y of the caption block for 图/表 <number> on this page."""
    want = f"{'图' if kind == 'fig' else '表'}{number}"
    for block in page.get_text("blocks"):
        text = block[4].strip()
        head = text.splitlines()[0].replace(" ", "") if text else ""
        if head.startswith(want):
            return block[1]
    return None


def main() -> None:
    pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "main.pdf")
    aux = pdf.with_suffix(".aux")
    lmap = label_map(aux)
    doc = fitz.open(pdf)

    refs: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for pno in range(doc.page_count):
        for link in doc[pno].get_links():
            dest = link.get("nameddest") or ""
            if dest not in lmap:
                continue
            label = lmap[dest][0]
            rect = link.get("from")
            if rect:
                refs[label].append((pno + 1, round(rect[1], 1)))

    print(f"{'label':26s} {'float @':>14s} {'first ref @':>14s}  status")
    print("-" * 74)
    bad = []
    for dest, (label, number, fpage) in sorted(lmap.items(), key=lambda kv: kv[1][2]):
        kind = "fig" if label.startswith("fig:") else "tab"
        cy = caption_y(doc[fpage - 1], kind, number)
        if cy is None:
            cy = 0.0
        hits = refs.get(label, [])
        if not hits:
            print(f"{label:26s} p{fpage} y={cy:6.1f} {'-':>14s}  *** 无引用 ***")
            bad.append(label)
            continue
        first = min(hits)
        ok = first < (fpage, cy)      # reference strictly above the caption / earlier page
        status = "OK（引用在图之前）" if ok else "*** 图先于首次引用 ***"
        if not ok:
            bad.append(label)
        print(f"{label:26s} p{fpage} y={cy:6.1f} p{first[0]} y={first[1]:6.1f}  {status}")
    print("-" * 74)
    print(f"检查 {len(lmap)} 个图表；图先于首次引用/无引用的: {len(bad)}")
    for b in bad:
        print("   -", b)


if __name__ == "__main__":
    main()
