"""Small dependency-free language routing helpers."""
from __future__ import annotations

import re

_CJK = re.compile(r"[\u3400-\u9fff]")


def detect_language(text: str) -> str:
    cjk = len(_CJK.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk and cjk >= latin:
        return "zh"
    return "en"
