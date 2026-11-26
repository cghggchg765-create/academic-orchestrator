"""Print every figure/table label with the page it landed on, sorted by page."""
# Bundled with mm-pdf-vision (latex layout QA toolkit). Originally written for the CUMCM 2026 C-problem layout review.
from __future__ import annotations

import re
import sys
from pathlib import Path

aux = Path(sys.argv[1] if len(sys.argv) > 1 else "main.aux").read_text(encoding="utf-8")
pattern = re.compile(r"\\newlabel\{((?:fig|tab):[^}]+)\}\{\{([^}]*)\}\{(\d+)\}")
rows = [(int(m.group(3)), m.group(1), m.group(2)) for m in pattern.finditer(aux)]
for page, label, number in sorted(rows):
    kind = "图" if label.startswith("fig:") else "表"
    print(f"p{page:3d}  {kind}{number:>3s}  {label}")
print(f"\ntotal floats: {len(rows)}")
