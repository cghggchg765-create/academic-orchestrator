"""Measure the natural aspect ratio of every figure used by the paper.

Prints: file, media size in pt (or px for bitmaps), aspect ratio h/w,
and the rendered height at a given \\textwidth fraction.
"""
# Bundled with mm-pdf-vision (latex layout QA toolkit). Originally written for the CUMCM 2026 C-problem layout review.
from __future__ import annotations

import re
import sys
from pathlib import Path

FIGDIR = Path(r"F:\deskop\r\latex\figures")
TEXTWIDTH_PT = 418.25  # cumcmthesis A4 text width, measured from main.log

USED = [
    ("fig:technical-route", "four_problem_framework_cn.png"),
    ("fig:loadpv", "data_load_pv.pdf"),
    ("fig:seasonnet", "seasonal_netload.pdf"),
    ("fig:q1price", "q1_price_netload.pdf"),
    ("fig:system", "energy_flow_mechanism_cn.png"),
    ("fig:q1dispatch", "q1_dispatch.pdf"),
    ("fig:q1compare", "q1_method_compare.pdf"),
    ("fig:q2scores", "q2_scenario_scores.pdf"),
    ("fig:q2scenario", "two_stage_decision_cn.png"),
    ("fig:q2daily", "q2_daily_profile.pdf"),
    ("fig:rolling", "rolling_flow_academic_cn.png"),
    ("fig:q3cost", "q3_cost_breakdown_cn.jpg"),
    ("fig:q3month", "q3_monthly_risk.pdf"),
    ("fig:q3case", "q3_case_0923.pdf"),
    ("fig:priceprofile", "q4_price_framework_cn.png"),
    ("fig:q4case", "q4_forecast_case_0621.pdf"),
    ("fig:q4total", "q4_total_cost.pdf"),
    ("fig:ablation", "q3_ablation.pdf"),
]


def pdf_size(path: Path) -> tuple[float, float]:
    raw = path.read_bytes()
    m = re.search(rb"/MediaBox\s*\[\s*([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)", raw)
    if not m:
        raise ValueError(f"no MediaBox in {path.name}")
    x0, y0, x1, y1 = (float(v) for v in m.groups())
    w, h = abs(x1 - x0), abs(y1 - y0)
    rot = re.search(rb"/Rotate\s+(-?\d+)", raw)
    if rot and abs(int(rot.group(1))) == 90:
        w, h = h, w
    return w, h


def raster_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
    except ImportError:
        import struct
        with path.open("rb") as fh:
            head = fh.read(32)
        if head.startswith(b"\x89PNG"):
            w, h = struct.unpack(">II", head[16:24])
            return w, h
        if head[:2] == b"\xff\xd8":
            with path.open("rb") as fh:
                data = fh.read()
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg
        raise ValueError(f"unknown raster format {path.name}")
    else:
        with Image.open(path) as im:
            return im.size


def main() -> None:
    print(f"{'label':22s} {'file':34s} {'w':>7s} {'h':>7s} {'h/w':>6s}  "
          f"{'h@0.72tw':>9s} {'h@0.60tw':>9s}")
    print("-" * 104)
    rows = []
    for label, name in USED:
        path = FIGDIR / name
        if not path.exists():
            print(f"{label:22s} {name:34s}  MISSING")
            continue
        if name.lower().endswith(".pdf"):
            w, h = pdf_size(path)
        else:
            w, h = raster_size(path)
        ratio = h / w
        rows.append((label, name, w, h, ratio))
        print(f"{label:22s} {name:34s} {w:7.1f} {h:7.1f} {ratio:6.3f}  "
              f"{ratio * 0.72 * TEXTWIDTH_PT:9.1f} {ratio * 0.60 * TEXTWIDTH_PT:9.1f}")
    print()
    print("h@Xtw = rendered height in pt if width is set to X * textwidth "
          f"(textwidth={TEXTWIDTH_PT} pt, A4 text height ~ 690 pt)")


if __name__ == "__main__":
    sys.exit(main())
