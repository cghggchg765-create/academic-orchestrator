#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部资料污染检测的门禁接入层。

为什么单独成模块
----------------
scripts/external_isolation.py 是唯一实现（CLI 全功能），但 state-engine 的门禁
不能直接 import 它：项目内它位于 state/tools/（垫片转发 scripts/），仓库内位于
scripts/。门禁需要的是"加载唯一实现 → 跑检测 → HIGH 即拒绝"这一件事，
按 raw_lock 的既有模式（_load_raw_lock_scan）用文件路径动态加载。

门禁接入点
----------
  · node-finish   收工时：External/refs 非空 → 必须 scan 无 HIGH
  · round-score   每轮评分前：同上

设计原则
--------
  · External/refs 为空（没引入外部资料）→ 不检测、不报错（不引入无关负担）
  · HIGH（未登记的雷同/位置污染）→ sys.exit 拒绝，附修复指引
  · 加载失败 → fail-closed：有外部资料却无法检测时拒绝收工（宁拦勿漏）
"""
from __future__ import annotations

import os
import sys

ISO_SCRIPT = "external_isolation.py"


def _iso_script_path(root: str) -> str:
    """定位 external_isolation.py **真实实现**（仓库 scripts/ 或项目 state/tools/）。

    注意候选必须是真实实现而非转发垫片：项目 scripts/<tool>.py 是 runpy 转发壳，
    没有 cmd_scan 等函数，误加载会让检测"永远不可用"→ 门禁永远 fail-closed，
    有外部资料的项目从此无法收工。用"含 cmd_scan 定义"作为实现标志。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        # 仓库内运行：<repo>/shared/state-engine → <repo>/scripts/
        os.path.join(here, "..", "..", "scripts", ISO_SCRIPT),
        # 项目内运行：init 已分发到 state/tools/
        os.path.join(root, "state", "tools", ISO_SCRIPT),
    ]
    for c in candidates:
        if os.path.isfile(c):
            try:
                with open(c, encoding="utf-8", errors="replace") as fh:
                    if "def cmd_scan" in fh.read():
                        return c
            except OSError:
                continue
    return ""


def load_iso_module(root: str):
    """动态加载 external_isolation 模块（按文件路径，不走包导入）。"""
    import importlib.util
    path = _iso_script_path(root)
    if not path:
        return None
    spec = importlib.util.spec_from_file_location("_external_isolation_gate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collect_findings(root: str):
    """跑污染扫描，返回 (findings, 外部资料文件数)。

    返回 None 表示无法检测（脚本缺失或扫描崩溃）——调用方据此 fail-closed。
    """
    mod = load_iso_module(root)
    if mod is None:
        return None, None
    try:
        refs = root if os.path.isabs(root) else os.path.abspath(root)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.cmd_scan(__import__("pathlib").Path(refs), True,
                              mod.COPY_SIMILARITY_THRESHOLD)
        import json
        report = json.loads(buf.getvalue())
        return report.get("findings", []), report.get("external_files", 0)
    except SystemExit:
        return None, None
    except Exception:
        return None, None


def _refs_has_material(root: str) -> bool:
    """External/refs/ 里是否存在真实外部资料。

    init 会让 refs/ 自带 README.md、.gitkeep 与空的 papers/ templates/ 子目录——
    这些是脚手架，不是外部资料。判空必须与 scan 的口径一致（scan 也会跳过它们），
    否则"零外部资料"的项目在检测器缺失时被误判 fail-closed，
    违反"无外部资料 → 不检测不报错"的设计。
    """
    refs_dir = os.path.join(root, "External", "refs")
    if not os.path.isdir(refs_dir):
        return False
    ignore = {"readme.md", ".gitkeep", ".readonly"}
    for dirpath, dirnames, filenames in os.walk(refs_dir):
        for fn in filenames:
            if fn.lower() not in ignore:
                return True
    return False


def require_clean_products(root: str, node: str = "", context: str = "收工"):
    """门禁入口：项目引入了外部资料时，自有产物必须通过污染检测。

    HIGH 发现（未登记的内容雷同 / 外部文件混进产物区）→ 拒绝。
    检测本身不可用（脚本缺失）→ 也拒绝（fail-closed，宁拦勿漏）。
    """
    findings, n_external = collect_findings(root)
    if findings is None:
        if _refs_has_material(root):
            sys.exit(
                f"[state_utils] 拒绝{context}：项目引入了外部资料（External/refs/），"
                f"但污染检测不可用（找不到 external_isolation.py）。\n"
                f"  宁拦勿漏：无法证明未照搬就不得交付。\n"
                f"  修复：python state/state_utils.py init --sync-runtime（补齐工具）"
                f"或从插件仓库复制 scripts/external_isolation.py 到 state/tools/"
            )
        return  # 没有外部资料，无需检测

    highs = [f for f in findings if f.get("severity") == "HIGH"]
    if not highs:
        return

    node_note = f"节点 {node} " if node else ""
    lines = "\n  - ".join(
        f"{f.get('path')}: {f.get('detail')}" for f in highs[:8])
    sys.exit(
        f"[state_utils] 拒绝{context}（防照搬门禁）：{node_note}检出 "
        f"{len(highs)} 项高置信污染。\n  - {lines}\n"
        f"\n  取长补短而不是照搬。两条合规路径：\n"
        f"    ① 确属参考后重写 → 登记来源：\n"
        f"       python scripts/external_isolation.py derive \\\n"
        f"         --ref <外部文件> --target <产物> --note \"参考了什么、怎么改写的\"\n"
        f"    ② 确属照搬 → 重写该产物，用自己的思路与表达\n"
        f"  详见：python scripts/external_isolation.py scan --root ."
    )
