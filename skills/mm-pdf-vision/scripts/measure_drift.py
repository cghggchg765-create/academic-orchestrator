"""Quantify how far each figure/table drifts from the text that references it.

hyperref turns every \\ref{fig:x} into an internal link whose source rectangle
sits on the page holding the reference text, and whose destination is the page
holding the float.  The auto-generated destination names (figure.caption.N /
table.caption.N) are mapped back to the author labels via main.aux.
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
        "本脚本需要 PyMuPDF（读取 PDF 内部链接与页码）。\n"
        "  安装：pip install pymupdf\n"
        "  提示：项目 venv 常未安装，可改用装有 PyMuPDF 的解释器运行。\n"
        "  另注意：本脚本依赖 main.aux 与 PDF 同源，两者不一致会读出错误页码。"
    )

PDF = Path(sys.argv[1] if len(sys.argv) > 1 else "main.pdf")
AUX = PDF.with_suffix(".aux")


def label_map(aux: Path) -> dict[str, tuple[str, int]]:
    """figure.caption.N -> (label, float page)"""
    out: dict[str, tuple[str, int]] = {}
    pattern = re.compile(
        r"\\newlabel\{((?:fig|tab):[^}]+)\}\{\{([^}]*)\}\{(\d+)\}\{[^}]*\}\{((?:figure|table)\.caption\.\d+)\}")
    for m in pattern.finditer(aux.read_text(encoding="utf-8")):
        label, page, dest = m.group(1), int(m.group(3)), m.group(4)
        out[dest] = (label, page)
    return out


def main() -> None:
    lmap = label_map(AUX)
    doc = fitz.open(PDF)

    refs: dict[str, list[tuple[int, float]]] = defaultdict(list)   # label -> [(ref page, y)]
    for pno in range(doc.page_count):
        for link in doc[pno].get_links():
            dest = link.get("nameddest") or ""
            if dest not in lmap:
                continue
            label, _ = lmap[dest]
            rect = link.get("from")
            y = rect[1] if rect else 0.0
            refs[label].append((pno + 1, round(y, 1)))

    rows = []
    for dest, (label, fpage) in lmap.items():
        hits = sorted(refs.get(label, []))
        if not hits:
            rows.append((fpage, label, fpage, [], None, "NO LINK"))
            continue
        dist = min(abs(rp - fpage) for rp, _ in hits)
        rows.append((fpage, label, fpage, hits, dist, ""))

    print(f"{'label':26s} {'float p':>7s} {'first ref p':>11s} {'dist':>5s}  note")
    print("-" * 84)
    problems = []
    for fpage, label, _, hits, dist, note in sorted(rows):
        first_ref = min((p for p, _ in hits), default=None)
        flag = ""
        if first_ref is not None and first_ref > fpage:
            flag = "  <== FIGURE PRECEDES ITS FIRST REFERENCE"
            problems.append((label, fpage, first_ref))
        elif dist is not None and dist >= 2:
            flag = "  <== DRIFT"
            problems.append((label, fpage, first_ref))
        print(f"{label:26s} {fpage:7d} {str(first_ref) if first_ref else '-':>11s} "
              f"{str(dist) if dist is not None else '-':>5s}{flag}")
    print("-" * 84)
    print(f"floats: {len(rows)}   same-page: {sum(1 for r in rows if r[4] == 0)}"
          f"   adjacent(1): {sum(1 for r in rows if r[4] == 1)}"
          f"   drifted(>=2): {sum(1 for r in rows if r[4] is not None and r[4] >= 2)}")
    if problems:
        print("\n需要修图前引用的图表:")
        for label, fpage, rpage in problems:
            print(f"   {label}: 图在第{fpage}页, 首次引用在第{rpage}页")
    drifted = [r for r in rows if r[4] is not None and r[4] >= 2]
    print("-" * 70)
    print(f"floats: {len(rows)}   same-page: {sum(1 for r in rows if r[4] == 0)}"
          f"   adjacent(1): {sum(1 for r in rows if r[4] == 1)}   drifted(>=2): {len(drifted)}")


if __name__ == "__main__":
    main()
