"""Measure bottom whitespace on rendered page images.

Reads PGM (P5) files produced by `pdftoppm -gray`, finds the lowest row that
contains body ink (ignoring the page-number footer band), and reports the
leftover gap in PDF points, so pages can be compared before/after a layout
change.

Usage:
    python measure_whitespace.py <glob> <dpi> [footer_band_pt]
"""
# Bundled with mm-pdf-vision (latex layout QA toolkit). Originally written for the CUMCM 2026 C-problem layout review.
from __future__ import annotations

import glob
import sys

A4_H_PT = 841.89
TOP_MARGIN_PT = 71.0
BOTTOM_MARGIN_PT = 71.0


def read_pgm(path: str) -> tuple[bytes, int, int]:
    with open(path, "rb") as fh:
        data = fh.read()
    # header: P5 <ws> width <ws> height <ws> maxval <single ws> then raster
    fields, pos = [], 2
    while len(fields) < 3:
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            while pos < len(data) and data[pos] != 0x0A:
                pos += 1
            continue
        start = pos
        while pos < len(data) and not data[pos:pos + 1].isspace():
            pos += 1
        fields.append(int(data[start:pos]))
    pos += 1  # single whitespace after maxval
    width, height, _maxval = fields
    return data[pos:pos + width * height], width, height


def page_whitespace(path: str, footer_band_pt: float = 45.0) -> float:
    raster, width, height = read_pgm(path)
    scale = A4_H_PT / height
    # scan rows from the bottom up, stop before the footer band
    text_bottom_pt = A4_H_PT - BOTTOM_MARGIN_PT
    footer_limit_px = int((A4_H_PT - BOTTOM_MARGIN_PT + 6.0) / scale)
    last_ink_px = None
    for row in range(min(footer_limit_px, height) - 1, -1, -1):
        line = raster[row * width:(row + 1) * width]
        if min(line) < 200:
            last_ink_px = row
            break
    if last_ink_px is None:
        return text_bottom_pt
    return max(0.0, text_bottom_pt - last_ink_px * scale)


def main() -> int:
    pattern, dpi = sys.argv[1], float(sys.argv[2])
    footer_band = float(sys.argv[3]) if len(sys.argv) > 3 else 45.0
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"no files match {pattern}")
        return 1
    text_h = A4_H_PT - TOP_MARGIN_PT - BOTTOM_MARGIN_PT
    gaps = []
    print(f"{'page':>16s} {'bottom gap/pt':>14s} {'% text height':>14s}")
    print("-" * 48)
    for path in files:
        gap = page_whitespace(path, footer_band)
        gaps.append(gap)
        flag = "  <== large" if gap > 120 else ""
        print(f"{path.split('/')[-1]:>16s} {gap:14.1f} {gap / text_h * 100:13.1f}%{flag}")
    mean = sum(gaps) / len(gaps)
    srt = sorted(gaps)
    median = srt[len(srt) // 2]
    print("-" * 48)
    print(f"pages={len(gaps)}  mean={mean:.1f}pt  median={median:.1f}pt  "
          f"max={max(gaps):.1f}pt  pages>120pt={sum(1 for g in gaps if g > 120)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
