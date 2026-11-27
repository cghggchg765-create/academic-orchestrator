#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""voice-pipeline 自检：registry 契约、入口、Junction、关键文件与环境。

用法：
    python doctor.py            # 常规检查
    python doctor.py --json     # 机器可读
    python doctor.py --strict   # WARN 也返回非零
退出码：0 = 无 FAIL；1 = 有 FAIL（--strict 时含 WARN）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REGISTRY = SKILL_DIR / "registry.json"

# 可移植路径解析：registry 里写 $SKILLS_ROOT/<name>，运行时在多根下解析。
# 不再内置任何特定平台的绝对路径——技能装在一处（用户级/插件内/同仓并列）即可工作。
sys.path.insert(0, str(SKILL_DIR / "scripts"))
try:
    from _roots import resolve_entry, skill_roots as _skill_roots  # noqa: E402
except ImportError:  # 单独拷贝脚本时降级
    def resolve_entry(raw):
        p = Path(os.path.expanduser(os.path.expandvars(str(raw or ""))))
        return p if p.exists() else None

    def _skill_roots():
        return [Path.home() / ".zcode" / "skills", Path.home() / ".agents" / "skills"]


def _optional_mirror_roots() -> list[Path]:
    """可选镜像根：环境变量 PIPELINE_MIRROR_ROOTS，或默认 ~/.agents/skills。
    仅用于"若存在则抽查一致性"，镜像缺失不算失败。"""
    env = os.environ.get("PIPELINE_MIRROR_ROOTS", "")
    if env:
        return [Path(p) for p in env.replace(";", os.pathsep).replace(",", os.pathsep).split(os.pathsep)
                if p.strip()]
    cand = Path.home() / ".agents" / "skills"
    return [cand] if cand.is_dir() else []

STAGE_ORDER = ["V0", "V0e", "V1", "V2"]
ROLES = {"narrative", "diagnose", "edit", "rewrite"}
SKILL_FIELDS = [
    "slot", "stage", "name", "path", "entry", "repo", "stars", "maturity",
    "role", "roots", "best_at", "inputs", "outputs", "not_for", "done_when",
    "requires_files", "depends", "fallback",
]


def add(rows: list[dict], level: str, item: str, detail: str) -> None:
    rows.append({"level": level, "item": item, "detail": detail})


def read_frontmatter_name(skill_md: Path) -> str:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception:
        return ""
    match = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def check_registry_schema(registry: dict, rows: list[dict]) -> bool:
    ok = True
    if not isinstance(registry.get("stage_order"), list):
        add(rows, "FAIL", "schema", "缺少 stage_order")
        ok = False
    elif registry["stage_order"] != STAGE_ORDER:
        add(rows, "FAIL", "schema", f"stage_order={registry['stage_order']}，应为 {STAGE_ORDER}")
        ok = False

    skills = registry.get("skills", [])
    if not isinstance(skills, list) or not skills:
        add(rows, "FAIL", "schema", "skills 为空")
        return False

    names: set[str] = set()
    slots: set[str] = set()
    for item in skills:
        for field in SKILL_FIELDS:
            if field not in item:
                add(rows, "FAIL", "schema", f"{item.get('name', '?')} 缺少字段 {field}")
                ok = False
        name = item.get("name", "")
        if name in names:
            add(rows, "FAIL", "schema", f"技能名重复: {name}")
            ok = False
        names.add(name)
        if item.get("stage") not in STAGE_ORDER:
            add(rows, "FAIL", "schema", f"{name} stage={item.get('stage')} 不在允许值")
            ok = False
        if item.get("role") not in ROLES:
            add(rows, "FAIL", "schema", f"{name} role={item.get('role')!r} 不在 {sorted(ROLES)}")
            ok = False
        if item.get("slot") != item.get("stage"):
            add(rows, "FAIL", "schema", f"{name} slot={item.get('slot')} 与 stage={item.get('stage')} 不一致")
            ok = False
        if item.get("slot") in slots:
            add(rows, "FAIL", "schema", f"stage 重复: {item.get('slot')}")
            ok = False
        slots.add(item.get("slot"))
        roots = item.get("roots")
        if roots is not None and (not isinstance(roots, list) or not roots):
            add(rows, "WARN", "schema", f"{name} roots 为空（可省略该字段）")

    if ok:
        add(rows, "PASS", "schema", f"{len(skills)} 个技能，stage 唯一，字段齐全")
    return ok


def check_presets(registry: dict, rows: list[dict]) -> None:
    presets = registry.get("presets", [])
    if not isinstance(presets, list) or not presets:
        add(rows, "FAIL", "presets", "presets 为空")
        return
    stages = {item.get("stage") for item in registry.get("skills", [])}
    names: set[str] = set()
    ok = True
    for preset in presets:
        name = preset.get("name", "")
        if not name:
            add(rows, "FAIL", "presets", "存在无名 preset")
            ok = False
        elif name in names:
            add(rows, "FAIL", "presets", f"preset 重复: {name}")
            ok = False
        names.add(name)
        sequence = preset.get("sequence", [])
        if not isinstance(sequence, list) or not sequence:
            add(rows, "FAIL", "presets", f"{name} sequence 为空")
            ok = False
            continue
        for step in sequence:
            stage = step.get("stage")
            if stage not in stages:
                add(rows, "FAIL", "presets", f"{name} 引用未知 stage: {stage}")
                ok = False
    if ok:
        add(rows, "PASS", "presets", f"{len(presets)} 个预设有名、stage 可解析")


def check_skill(item: dict, rows: list[dict]) -> None:
    name = item["name"]
    # 可移植解析：$SKILLS_ROOT/<name> 在多根下解析（用户级 / 插件内 / 同仓并列 / skill-sources）
    path = resolve_entry(item.get("path")) or resolve_entry(f"$SKILLS_ROOT/{name}")
    entry = resolve_entry(item.get("entry")) if item.get("entry") else None
    if (entry is None or not entry.exists()) and path is not None:
        entry = path / "SKILL.md"

    if path is None:
        # optional 技能（如特定宿主内置件）缺失不计失败
        if item.get("optional"):
            add(rows, "INFO", name, "可选技能未安装（不影响本机使用）")
        else:
            add(rows, "FAIL", name,
                f"入口不存在（查找根: {', '.join(str(r) for r in _skill_roots()[:3])}…）")
        return
    if entry is None or not entry.exists():
        add(rows, "FAIL", name, f"entry 不存在: {item.get('entry')}")
        return

    actual = read_frontmatter_name(entry)
    if actual != name:
        add(rows, "FAIL", name, f"entry name={actual!r} 与注册名不一致")
    else:
        add(rows, "PASS", name, "入口与 name 一致")

    # requires_files 相对**技能目录**（SKILL.md 所在目录），不是仓库根。
    skill_dir = entry.parent if entry is not None else path
    missing = [rel for rel in item.get("requires_files", []) if not (skill_dir / rel).exists()]
    if missing:
        add(rows, "FAIL", name, "requires_files 缺失: " + ", ".join(missing))
    else:
        add(rows, "PASS", f"{name}:files", f"{len(item.get('requires_files', []))} 个关键文件齐全")

    # 技能本体已可解析即为就位。roots 只做"若声明了某个镜像根且该根确实存在，
    # 则抽查一致性"——单一来源即可工作，镜像缺失不算失败。
    expected = path.resolve()
    for extra_root in _optional_mirror_roots():
        link = extra_root / name
        if not link.exists():
            continue
        try:
            target = link.resolve()
        except Exception as exc:
            add(rows, "WARN", f"{name}@mirror", f"镜像解析失败: {exc}")
            continue
        if target != expected:
            add(rows, "WARN", f"{name}@mirror", f"镜像指向 {target}，与该技能实际位置 {expected} 不一致")
        else:
            add(rows, "PASS", f"{name}@mirror", "镜像指向一致")


def check_env(rows: list[dict]) -> None:
    add(rows, "INFO", "python", f"{sys.version.split()[0]} ({sys.executable})")
    git = shutil.which("git")
    if git:
        add(rows, "PASS", "git", git)
    else:
        add(rows, "WARN", "git", "未找到 git；update.py 只能做自检")


def finish(rows: list[dict], as_json: bool, strict: bool) -> int:
    fails = [r for r in rows if r["level"] == "FAIL"]
    warns = [r for r in rows if r["level"] == "WARN"]
    if as_json:
        print(json.dumps({"rows": rows, "fail": len(fails), "warn": len(warns)}, ensure_ascii=False, indent=2))
    else:
        width = max((len(r["item"]) for r in rows), default=10) + 2
        for r in rows:
            print(f"[{r['level']}] {r['item']:<{width}} {r['detail']}")
        print(
            f"\nSUMMARY: PASS={sum(1 for r in rows if r['level']=='PASS')} "
            f"WARN={len(warns)} FAIL={len(fails)} INFO={sum(1 for r in rows if r['level']=='INFO')}"
        )
    if fails or (strict and warns):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    rows: list[dict] = []
    if not REGISTRY.exists():
        add(rows, "FAIL", "registry", "registry.json 缺失")
        return finish(rows, args.json, args.strict)
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception as exc:
        add(rows, "FAIL", "registry", f"JSON 解析失败: {exc}")
        return finish(rows, args.json, args.strict)

    check_registry_schema(registry, rows)
    check_presets(registry, rows)
    for item in registry.get("skills", []):
        check_skill(item, rows)
    check_env(rows)
    return finish(rows, args.json, args.strict)


if __name__ == "__main__":
    sys.exit(main())
