#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径根解析（voice-pipeline 的可移植层）。

原实现把 `C:\\Users\\11352\\.zcode\\skills\\xxx` 与豆包路径硬编码进 registry.json
和 doctor.py，换台机器全断。本模块把"技能装在哪"变成运行时解析。

解析优先级（先命中先用）：
  1. 环境变量 PIPELINE_SKILLS_ROOTS —— 分号/逗号分隔的多个根（覆盖语义，测试友好）
  2. $ZCODE_PLUGIN_ROOT / $CLAUDE_PLUGIN_ROOT 下的 skills/（插件内分发场景）
  3. <pipeline skill 自己所在目录> 的同级（同仓分发：pipeline 与子技能并列）
  4. ~/.zcode/skills
  5. ~/.agents/skills
  6. 项目内 <cwd>/.zcode/skills、<cwd>/.agents/skills

registry.json 里的 path/entry 允许三种写法：
  · "$SKILLS_ROOT/<技能名>"        → 在所有根下找
  · "./<相对动线>"                → 相对 pipeline 自己
  · 绝对路径                      → 原样使用（向后兼容旧 registry）
"""
from __future__ import annotations

import os
from pathlib import Path

SELF_DIR = Path(__file__).resolve().parents[1]   # <pipeline>/


def skill_roots() -> list[Path]:
    """返回候选技能根目录列表（去重、保序、只保留存在的）。"""
    roots: list[Path] = []

    env = os.environ.get("PIPELINE_SKILLS_ROOTS", "")
    for part in env.replace(";", os.pathsep).replace(",", os.pathsep).split(os.pathsep):
        part = part.strip()
        if part:
            roots.append(Path(part))

    for var in ("ZCODE_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        plugin_root = os.environ.get(var)
        if plugin_root:
            cand = Path(plugin_root) / "skills"
            if cand.is_dir():
                roots.append(cand)
            roots.append(Path(plugin_root))

    roots.append(SELF_DIR)
    roots.append(SELF_DIR.parent)

    home = Path.home()
    roots.append(home / ".zcode" / "skills")
    roots.append(home / ".agents" / "skills")

    cwd = Path.cwd()
    roots.append(cwd / ".zcode" / "skills")
    roots.append(cwd / ".agents" / "skills")

    seen, out = set(), []
    for r in roots:
        try:
            key = str(r.resolve()).lower()
        except OSError:
            key = str(r).lower()
        if key in seen:
            continue
        seen.add(key)
        if r.is_dir():
            out.append(r)
    return out


def resolve_entry(raw: str | None) -> Path | None:
    """把 registry 的一条 path/entry 解析成真实存在的 Path；解析不到返回 None。"""
    if not raw:
        return None
    s = str(raw).strip()

    for token in ("$SKILLS_ROOT", "${SKILLS_ROOT}", "%SKILLS_ROOT%"):
        if s.startswith(token):
            rest = s[len(token):].lstrip("/\\")
            for root in skill_roots():
                cand = root / rest if rest else root
                if cand.exists():
                    return cand
            return None

    p = Path(os.path.expanduser(os.path.expandvars(s)))

    if not p.is_absolute():
        cand = (SELF_DIR / p).resolve()
        return cand if cand.exists() else None

    if p.exists():
        return p
    name = p.name
    for root in skill_roots():
        cand = root / name
        if cand.exists():
            return cand
    return None


def skill_path_by_name(name: str) -> Path | None:
    """按技能名在所有根下查找。"""
    for root in skill_roots():
        cand = root / name
        if cand.exists():
            return cand
    return None


if __name__ == "__main__":
    print("skill roots:")
    for r in skill_roots():
        print("  -", r)
