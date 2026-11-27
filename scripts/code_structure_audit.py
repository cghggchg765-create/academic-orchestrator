#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码结构审计：把"单文件 ≤300 行 / 单函数 ≤50 行 / 禁止空壳与版本副本"变成可测判据。

为什么需要这个脚本
------------------
`mm-algorithm-dev` 规定"超 300 行必须拆分"，但此前全仓没有任何机器检查，
规范只是纸面要求——结果是 solver 文件实际膨胀到上千行也没人拦。
本脚本给 `mm-code-reviewer` 的"可读性"维度提供客观锚点，也给 N4/N5 收工
提供一个可执行的"结构是否合格"证据。

用法
----
    python scripts/code_structure_audit.py --root <项目根>
    python scripts/code_structure_audit.py --root . --json
    python scripts/code_structure_audit.py --root . --strict   # 有 FAIL 时退出码 1

判据（与 mm-algorithm-dev 一致）
--------------------------------
FAIL  单文件 > 300 行（不含空行与纯注释行）
FAIL  单函数 > 50 行（同上口径）
FAIL  空壳文件：只有 docstring/import/raise NotImplementedError/pass，无任何实质逻辑
FAIL  版本副本：文件名含 _v2/_old/_new/_copy/_backup/_final 或 "copy"/"(1)" 等
WARN  版本副本目录（_backup/、archive/、_old/ 等）
WARN  同一 problem_N 内职责重叠（多个文件都定义 solve/main 入口）

只读：本脚本不修改任何文件。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

MAX_FILE_LINES = 300
MAX_FUNC_LINES = 50

# 版本副本：文件名里出现这些东西，基本可以确定是"改之前保一份"的残留
VERSION_SUFFIX = re.compile(
    r"(_v\d+|_old|_new|_copy|_backup|_final|_bak|_orig|_deprecated|_new2|copy\s*\(\d+\)|_\(\d+\))(\.py)?$",
    re.IGNORECASE,
)
VERSION_DIRS = {"_backup", "backup", "_old", "old", "_archive", "archive",
                "_deprecated", "deprecated", "_bak", ".bak", "_copy"}

# 空壳判据：整份文件去掉注释与 docstring 后，剩下的"实质语句"不超过这些形态
SHELL_STATEMENT_TYPES = (ast.Import, ast.ImportFrom, ast.Pass, ast.Expr)


def _is_comment_or_blank(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("#")


def count_code_lines(text: str) -> int:
    """物理行数扣除空行与整行注释（保留行内代码与 docstring —— 保守口径）。"""
    return sum(1 for line in text.splitlines() if not _is_comment_or_blank(line))


def _function_span(node: ast.AST) -> int:
    """函数体行数：end_lineno - lineno + 1（含签名与 docstring）。"""
    end = getattr(node, "end_lineno", None) or getattr(node, "lineno", 0)
    return end - node.lineno + 1


def _is_shell(tree: ast.Module) -> bool:
    """判断文件是否为空壳：除 import / pass / docstring 外没有任何逻辑。

    raise NotImplementedError 也算空壳（那是占位模板的标志）。
    """
    for node in tree.body:
        if isinstance(node, SHELL_STATEMENT_TYPES):
            # 顶层 docstring / import / pass
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            if isinstance(node, ast.Pass):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            return False
        if isinstance(node, ast.Raise):
            # raise NotImplementedError(...) 单独出现 = 占位
            exc = node.exc
            name = ""
            if isinstance(exc, ast.Call):
                exc = exc.func
            if isinstance(exc, ast.Name):
                name = exc.id
            elif isinstance(exc, ast.Attribute):
                name = exc.attr
            if name == "NotImplementedError":
                continue
            return False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # 只有"整体 raise NotImplementedError"的函数才算空壳
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = [b for b in node.body
                        if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
                if body and all(isinstance(b, ast.Raise) for b in body):
                    continue
            return False
        return False
    return True


def _defined_entrypoints(tree: ast.Module) -> set[str]:
    """本文件定义的顶层可执行入口（用于识别职责重叠）。"""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
    return names


def audit_code_dir(code_dir: Path) -> dict:
    """审计一个 Code/ 目录，返回结构化报告。"""
    fails: list[dict] = []
    warns: list[dict] = []
    stats = {"files": 0, "code_lines": 0, "largest_file": None,
             "largest_file_lines": 0, "largest_function": None, "largest_function_lines": 0}

    if not code_dir.is_dir():
        return {"ok": False, "reason": f"代码目录不存在: {code_dir}",
                "fails": [], "warns": [], "stats": stats}

    entry_by_dir: dict[str, dict[str, set[str]]] = {}

    for path in sorted(code_dir.rglob("*.py")):
        rel = path.relative_to(code_dir).as_posix()
        # 版本副本目录
        if any(part.lower() in VERSION_DIRS for part in path.parts):
            warns.append({"kind": "version_dir", "path": rel,
                          "detail": "版本/备份目录残留，按单一版本纪律应删除或合并"})
            continue
        if VERSION_SUFFIX.search(path.name):
            fails.append({"kind": "version_copy", "path": rel,
                          "detail": "文件名含版本后缀（_v2/_old/_new/_backup…），应就地修改而非留副本"})
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warns.append({"kind": "unreadable", "path": rel, "detail": str(exc)})
            continue

        stats["files"] += 1
        nlines = count_code_lines(text)
        stats["code_lines"] += nlines
        if nlines > stats["largest_file_lines"]:
            stats["largest_file"] = rel
            stats["largest_file_lines"] = nlines
        if nlines > MAX_FILE_LINES:
            fails.append({"kind": "file_too_long", "path": rel,
                          "detail": f"{nlines} 行代码（> {MAX_FILE_LINES}），须按职责拆分"})

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            fails.append({"kind": "syntax_error", "path": rel,
                          "detail": f"无法解析（第 {exc.lineno} 行）：{exc.msg}"})
            continue

        if _is_shell(tree):
            # __init__.py 的空是合法的（Python 包标记），不算"占位空壳"
            if path.name == "__init__.py":
                continue
            fails.append({"kind": "empty_shell", "path": rel,
                          "detail": "空壳文件（只有 docstring/import/NotImplementedError），应删除"})

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                span = _function_span(node)
                qual = f"{rel}::{node.name}"
                if span > stats["largest_function_lines"]:
                    stats["largest_function"] = qual
                    stats["largest_function_lines"] = span
                if span > MAX_FUNC_LINES:
                    fails.append({"kind": "function_too_long", "path": rel,
                                  "detail": f"{node.name}() 跨 {span} 行（> {MAX_FUNC_LINES}），须拆分"})

        # 职责重叠：同一 problem_N 目录下多个文件都定义公开顶层函数入口
        m = re.search(r"problem_(\d+)", rel)
        if m:
            entries = _defined_entrypoints(tree)
            if entries:
                entry_by_dir.setdefault(m.group(1), {})[rel] = entries

    for q, files in entry_by_dir.items():
        if len(files) < 2:
            continue
        # 只提示"同一题下多个文件都暴露同名入口"，这是职责边界不清的典型信号
        seen: dict[str, list[str]] = {}
        for rel, entries in files.items():
            for name in entries:
                seen.setdefault(name, []).append(rel)
        for name, owners in seen.items():
            if len(owners) > 1:
                warns.append({"kind": "role_overlap",
                              "path": ", ".join(sorted(owners)),
                              "detail": f"第 {q} 问多个文件都定义 {name}()，职责边界不清"})

    return {"ok": not fails, "fails": fails, "warns": warns, "stats": stats,
            "thresholds": {"max_file_lines": MAX_FILE_LINES,
                           "max_function_lines": MAX_FUNC_LINES}}


def main() -> int:
    ap = argparse.ArgumentParser(description="代码结构审计（体积阈值 / 空壳 / 版本副本）")
    ap.add_argument("--root", default=".", help="项目根目录（含 Code/）")
    ap.add_argument("--code-dir", default=None, help="直接指定代码目录（默认 <root>/Code）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有 FAIL 时退出码 1")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    code_dir = Path(args.code_dir).resolve() if args.code_dir else root / "Code"
    report = audit_code_dir(code_dir)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["stats"]
        print(f"代码结构审计: {code_dir}")
        print(f"  文件 {s['files']} 个 / 代码行 {s['code_lines']}")
        if s["largest_file"]:
            print(f"  最大文件: {s['largest_file']}（{s['largest_file_lines']} 行，上限 {MAX_FILE_LINES}）")
        if s["largest_function"]:
            print(f"  最长函数: {s['largest_function']}（{s['largest_function_lines']} 行，上限 {MAX_FUNC_LINES}）")
        for f in report["fails"]:
            print(f"  [FAIL] {f['path']}: {f['detail']}")
        for w in report["warns"]:
            print(f"  [WARN] {w['path']}: {w['detail']}")
        if not report["fails"] and not report["warns"]:
            print("  ✅ 结构合格")
        elif not report["fails"]:
            print("  ⚠ 有告警，无阻断")
        else:
            print(f"  ❌ {len(report['fails'])} 项结构不合格，须修复后重跑")

    return 1 if (args.strict and report["fails"]) else 0


if __name__ == "__main__":
    sys.exit(main())
