"""Detect pages where a float interrupts a running paragraph.

A float interrupts the flow when the page begins with a figure/table and the
previous page's last text line does not end a sentence, i.e. the paragraph is
split across the page break with the float wedged in between.

Also reports, per page, the bottom whitespace so layout quality can be tracked.
"""
# Bundled with mm-pdf-vision (latex layout QA toolkit). Originally written for the CUMCM 2026 C-problem layout review.
from __future__ import annotations

import re
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    raise SystemExit(
        "本脚本需要 PyMuPDF（直接读取 PDF 文字块位置）。\n"
        "  安装：pip install pymupdf\n"
        "  提示：项目 venv 常未安装，可改用装有 PyMuPDF 的解释器运行。\n"
        "  用法：check_interruptions.py <pdf> [统计页数]"
    )

PDF = sys.argv[1] if len(sys.argv) > 1 else "main.pdf"
A4_H = 841.89
BOTTOM_MARGIN = 71.0
SENTENCE_END = "。！？；：)”』"  # sentence-ending punctuation (plus closing marks)


def page_lines(page: "fitz.Page") -> list[tuple[float, float, str]]:
    """Body text lines with their block's top and bottom y (footer excluded)."""
    out = []
    footer_top = A4_H - 55.0
    for block in page.get_text("blocks"):
        y0, y1, text = block[1], block[3], block[4]
        if y0 > footer_top:          # page number / footer area
            continue
        text = text.strip()
        if not text:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line:
                out.append((y0, y1, line))
    out.sort()
    return out


def main() -> None:
    doc = fitz.open(PDF)
    float_re = re.compile(r"^(图|表)\s*\d+")
    info = []
    for pno in range(doc.page_count):
        lines = page_lines(doc[pno])
        if not lines:
            info.append((pno + 1, None, None, 0.0))
            continue
        first = lines[0][2]
        last = lines[-1][2]
        # bottom whitespace: from the last body block's bottom to the bottom margin
        last_y = max(y1 for _, y1, _ in lines)
        gap = max(0.0, (A4_H - BOTTOM_MARGIN) - last_y)
        info.append((pno + 1, first, last, gap))

    # 第二参数可限制统计页数（默认全篇；封面/摘要页同样计入，按需自行过滤）
    limit = doc.page_count
    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        limit = int(sys.argv[2])
    info = info[:limit]

    print(f"{'page':>5s} {'starts with float':>18s} {'prev ends sentence':>19s} {'gap/pt':>7s}")
    print("-" * 56)
    problems = []
    for pno, first, last, gap in info:
        starts_float = bool(first and float_re.match(first))
        prev_last = info[pno - 2][2] if pno >= 2 else None
        prev_ok = True if prev_last is None else prev_last.endswith(tuple(SENTENCE_END))
        flag = ""
        if starts_float and not prev_ok:
            flag = "  <== INTERRUPTS"
            problems.append(pno)
        print(f"{pno:5d} {str(starts_float):>18s} {str(prev_ok):>19s} {gap:7.1f}{flag}")

    gaps = [g for _, _, _, g in info]
    print("-" * 56)
    print(f"pages 1-{len(info)}: mean gap {sum(gaps) / len(gaps):.1f}pt  "
          f"max {max(gaps):.1f}pt  >120pt: {sum(1 for g in gaps if g > 120)}")
    worst = sorted(((g, p) for p, _, _, g in info), reverse=True)[:5]
    worst_txt = "  ".join(f"p{p}={g:.0f}pt" for g, p in worst if g > 60)
    if worst_txt:
        print(f"留白最大的几页: {worst_txt}")
    print(f"paragraph-interrupting pages: {problems or 'none'}")


if __name__ == "__main__":
    main()
