#!/usr/bin/env python3
"""state_utils.py — 状态统一节点命令行助手（兼容转发垫片）。

状态引擎已在 1.8.0 迁至共享层 `shared/state-engine/`（模块独立化：任何阶段模块
不再受 mm-iteration-engine 单一技能内部私有脚本约束）。本文件保留在旧路径作为
转发垫片，保证既有调用（`python skills/mm-iteration-engine/scripts/state_utils.py
<命令>` 与 `from state_utils import *`）零破坏；新文档请直接指向
`python shared/state-engine/state_utils.py <命令>`。
"""
from __future__ import annotations

import importlib.util
import os
import runpy

_CANON_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "..", "shared", "state-engine")
)
# 以别名加载规范模块，避免与垫片自身“同名自引用”造成 sys.modules 冲突
# （垫片常以 `state_utils` 之名被 import；规范模块必须挂在独立名字下）。
_spec = importlib.util.spec_from_file_location(
    "_mm_state_engine", os.path.join(_CANON_DIR, "state_utils.py")
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

__all__ = getattr(_module, "__all__", None) or [
    n for n in dir(_module) if not n.startswith("_")
]


def __getattr__(name):
    return getattr(_module, name)


if __name__ == "__main__":
    runpy.run_path(
        os.path.join(_CANON_DIR, "state_utils.py"), run_name="__main__"
    )