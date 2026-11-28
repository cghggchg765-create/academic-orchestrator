#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径根解析（fig/voice pipeline 的可移植层）。

原实现把 `C:\\Users\\11352\\.zcode\\skills\\xxx` 与豆包路径硬编码进 registry.json
和 doctor.py，换台机器全断。本模块把"技能装在哪"变成运行时解析：

解析优先级（先命中先用）：
  1. 环境变量 PIPELINE_SKILLS_ROOTS —— 分号/逗号分隔的多个根（覆盖语义，测试友好）
  2. $ZCODE_PLUGIN_ROOT / $CLAUDE_PLUGIN_ROOT 下的 skills/（插件内分发场景）
  3. <pipeline skill 自己所在目录> 的同级（同仓分发：pipeline 与子技能并列）
  4. ~/.zcode/skills
  5. ~/.agents/skills
  6. 项目内 <cwd>/.zcode/skills、<cwd>/.agents/skills

registry.json 里的 path/entry 允许三种写法，本模块统一处理：
  · "$SKILLS_ROOT/<技能名>"        → 在所有根下找
  · "./<相对动线>"                → 相对 pipeline 自己
  · 绝对路径                      → 原样使用（向后兼容旧 registry）

用法（doctor.py / update.py 里）：
    from _roots import resolve_entry, skill_roots
    p = resolve_entry(item["path"])     # -> Path | None
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

    # 同仓分发：pipeline 与子技能并列
    roots.append(SELF_DIR)
    roots.append(SELF_DIR.parent)

    home = Path.home()
    roots.append(home / ".zcode" / "skills")
    roots.append(home / ".agents" / "skills")
    # 上游克隆目录：有些仓库把技能放在 <repo>/skills/<name>/，
    # 用户级入口是指向该子目录的 junction。搜索 cloned repo 根以便 _probe 能下探一层。

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
    """把 registry 的一条 path/entry 解析成真实存在的 Path；解析不到返回 None。

    额外兜底：有些仓库把技能放在 `<repo>/skills/<name>/`，用户级入口可能是
    那个子目录或指向上级的 junction。若 `<root>/<name>` 不存在，再到
    `<root>/<name>/skills/<name>` 里找一层。
    """
    if not raw:
        return None
    s = str(raw).strip()

    def _probe(base: Path) -> Path | None:
        if base.exists():
            return base
        # 仓库布局下探：<repo>/skills/<name>/ （base 是目录）
        nested = base / "skills" / base.name
        if nested.exists():
            return nested
        # base 指向具体文件（如 .../<name>/SKILL.md）时，父目录同样需要下探
        if base.suffix:
            parent = base.parent
            alt = parent / "skills" / parent.name / base.name
            if alt.exists():
                return alt
        return None

    # $SKILLS_ROOT 占位：在所有根下按剩余相对部分查找
    for token in ("$SKILLS_ROOT", "${SKILLS_ROOT}", "%SKILLS_ROOT%"):
        if s.startswith(token):
            rest = s[len(token):].lstrip("/\\")
            for root in skill_roots():
                got = _probe(root / rest if rest else root)
                if got:
                    return got
            return None

    p = Path(os.path.expanduser(os.path.expandvars(s)))

    # 相对路径：相对 pipeline 目录
    if not p.is_absolute():
        return _probe((SELF_DIR / p).resolve())

    # 绝对路径：原样（兼容旧 registry），不存在则尝试用同名技能在新根下找
    got = _probe(p)
    if got:
        return got
    name = p.name
    for root in skill_roots():
        got = _probe(root / name)
        if got:
            return got
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
