#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill 内容解析器：把"加载 skill"从依赖 Skill 工具变成依赖文件系统。

为什么需要它
------------
门禁要求"审阅前加载配对 skill 并声明"，但宿主的**子 Agent 工具集可能不含 Skill**
（实测会遇到 "会话工具集无 Skill 工具"）。此时：
  · `skill("mm-self-review")` 无法执行；
  · 门禁只校验 `--skills` 声明字符串，无法分辨"真读了"还是"抄了个名字"；
  · Agent 被要求做一件做不到的事，只能人工按口径等价执行。

而**所有子 Agent 都有 Read**。所以正确做法是让 skill 内容可被读取：
主 Agent 用本脚本取出 skill 正文，直接注入派发 prompt；子 Agent 无需任何 Skill 工具。

用法
----
    # 取 skill 正文（用于注入派发 prompt）
    python scripts/skill_context.py --name mm-self-review

    # 只取解析到的路径（让子 Agent 自己 Read）
    python scripts/skill_context.py --name mm-self-review --path-only

    # 一次取多个（逗号分隔），拼成可直接粘贴的上下文块
    python scripts/skill_context.py --name mm-iteration-engine,code-review

    # 列出某个 skill 是否可解析、解析到哪份（排查遮蔽）
    python scripts/skill_context.py --name mm-self-review --resolve-only

    # 只输出正文（去掉 frontmatter），适合塞进 prompt
    python scripts/skill_context.py --name mm-self-review --body-only

解析顺序与宿主一致（先命中者胜）：显式根 → ~/.zcode/skills → ~/.agents/skills
→ ~/.zcode/skill-sources（clone 仓库）→ 项目 .zcode/skills → .agents/skills
→ 插件缓存。同名多处命中时报告全部候选，避免"改了不生效"。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
ZCODE_SKILLS = HOME / ".zcode" / "skills"
AGENTS_SKILLS = HOME / ".agents" / "skills"
SKILL_SOURCES = HOME / ".zcode" / "skill-sources"
PLUGIN_CACHE = HOME / ".zcode" / "cli" / "plugins" / "cache"

MAX_BODY_CHARS = 120_000  # 单份 skill 正文上限，防止把超大文档塞进 prompt


def _roots(project: Path | None) -> list[Path]:
    out: list[Path] = []
    env_roots = os.environ.get("MM_SKILL_ROOTS") or os.environ.get("PIPELINE_SKILLS_ROOTS")
    if env_roots:
        out.extend(Path(p) for p in env_roots.split(os.pathsep) if p.strip())
    out.extend([ZCODE_SKILLS, AGENTS_SKILLS, SKILL_SOURCES])
    plugin_root = os.environ.get("ZCODE_PLUGIN_ROOT")
    if plugin_root:
        out.append(Path(plugin_root) / "skills")
    if project:
        out.extend([project / ".zcode" / "skills", project / ".agents" / "skills"])
    if PLUGIN_CACHE.is_dir():
        # 插件缓存：<cache>/<marketplace>/<plugin>/<version>/skills/<name>
        out.extend(sorted(PLUGIN_CACHE.glob("*/*/*/skills")))
    return [r for r in out if r.is_dir()]


def _skill_entry(base: Path, name: str) -> Path | None:
    """在某个根下定位 skill 目录（兼容三种真实布局）。"""
    direct = base / name
    if (direct / "SKILL.md").is_file():
        return direct
    # clone 型仓库：<root>/<repo>/skills/<name>/SKILL.md
    if (base / "skills" / name / "SKILL.md").is_file():
        return base / "skills" / name
    return None


def resolve(name: str, project: Path | None = None) -> list[Path]:
    """返回全部命中该 skill 的目录（按解析优先级排序，第一个即生效的）。"""
    bare = name.split(":", 1)[-1]          # 去插件前缀
    hits: list[Path] = []
    for root in _roots(project):
        entry = _skill_entry(root, bare)
        if entry is not None:
            hits.append(entry)
    return hits


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="解析并输出 skill 正文（替代对 Skill 工具的依赖）")
    ap.add_argument("--name", required=True,
                    help="skill 名，可逗号分隔多个；支持 plugin:skill 形式")
    ap.add_argument("--path-only", action="store_true", help="只输出解析到的路径")
    ap.add_argument("--body-only", action="store_true", help="只输出正文（去 frontmatter）")
    ap.add_argument("--resolve-only", action="store_true",
                    help="只报告可解析性与全部候选（排查遮蔽）")
    ap.add_argument("--project", default=None, help="项目根（用于解析项目级 skill 根）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    project = Path(args.project).resolve() if args.project else None
    names = [n.strip() for n in args.name.split(",") if n.strip()]
    results = []
    exit_code = 0

    for name in names:
        hits = resolve(name, project)
        if not hits:
            results.append({"name": name, "found": False, "path": None,
                            "candidates": [], "body": None})
            if not args.json:
                print(f"[skill_context] ✗ 无法解析: {name}", file=sys.stderr)
                roots = _roots(project)
                print(f"  已搜索 {len(roots)} 个 skill 根（前 6 个）:", file=sys.stderr)
                for r in roots[:6]:
                    print(f"    - {r}", file=sys.stderr)
                if len(roots) > 6:
                    print(f"    …（另有 {len(roots) - 6} 个）", file=sys.stderr)
                print("  提示：用 --json 或 --resolve-only 查看完整候选", file=sys.stderr)
            exit_code = 1
            continue

        chosen = hits[0]
        skill_md = chosen / "SKILL.md"
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            results.append({"name": name, "found": False, "path": str(chosen),
                            "candidates": [str(h) for h in hits], "body": None,
                            "error": str(exc)})
            exit_code = 1
            continue

        meta, body = _split_frontmatter(text)
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + f"\n\n…（已截断，原文 {len(body)} 字符）"
        results.append({
            "name": name, "found": True, "path": str(skill_md),
            "candidates": [str(h / "SKILL.md") for h in hits],
            "shadowed": len(hits) > 1,
            "frontmatter_name": meta.get("name"),
            "body": body,
        })

    if args.json:
        import json
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return exit_code

    for r in results:
        if not r["found"]:
            continue
        if args.resolve_only:
            print(f"{r['name']}: {r['path']}")
            if r.get("shadowed"):
                print("  ⚠ 同名多处命中（后者被遮蔽）：")
                for c in r["candidates"][1:]:
                    print(f"    - {c}")
            continue
        if args.path_only:
            print(r["path"])
            continue
        if len(names) > 1:
            print(f"\n{'=' * 70}\n# [{r['name']}] {r['path']}\n{'=' * 70}")
        print(r["body"] if args.body_only else
              f"<!-- source: {r['path']} -->\n{r['body']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
