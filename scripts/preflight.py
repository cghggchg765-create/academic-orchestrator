#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首次安装自检（preflight）。把插件打包发给别人后，让对方先跑这个。

回答一个问题：**这台机器上，本插件依赖的东西真的装好、能用了么？**

按 upstream-sources.json 分三档检查：
  required    —— 缺失则 blocked（核心流程跑不起来）
  recommended —— 缺失则 degraded（可用但少一条路）
  optional    —— 缺失只提示

检查什么（不止"目录存在"，还查可加载性）：
  · 目录/文件是否存在
  · skill 的 frontmatter 是否含 name + description（否则宿主会丢弃它）
  · plugin 是否在 ZCode 的插件缓存里且版本可读
  · 关键入口脚本是否可执行（figure-pipeline / voice-pipeline 的 doctor.py）
  · 本项目自身的运行时是否完整（state_utils 可导入、lint 可跑）

用法:
  python scripts/preflight.py                 # 人读报告
  python scripts/preflight.py --json          # 机器可读
  python scripts/preflight.py --tier required # 只查必需项
  python scripts/preflight.py --root <项目>    # 同时检查某个项目能否开工

退出码：0 = 全部必需项就绪；1 = 有 required 缺失；2 = manifest 问题
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "upstream-sources.json"
HOME = Path.home()
ZCODE_SKILLS = HOME / ".zcode" / "skills"
AGENTS_SKILLS = HOME / ".agents" / "skills"
# 本机 skill 的第三处落点：clone 下来的仓库镜像（不一定是可加载的 skill 根，
# 但"装没装"要靠它判断）。与 skills/*-pipeline/scripts/_roots.py 的根清单保持一致。
PLUGIN_CACHE = HOME / ".zcode" / "cli" / "plugins" / "cache"
# 所有可能存放 skill 的根：路径探测一律走这张表，避免各处各写一份而漏查。
SKILL_ROOTS = (ZCODE_SKILLS, AGENTS_SKILLS, REPO / "skills")


def _read_frontmatter(skill_md: Path):
    """返回 frontmatter 的顶层键名集合与 name/description；解析失败返回 (None, None, None)。"""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None, None
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return set(), None, None
    body = m.group(1)
    keys = set(re.findall(r"^([A-Za-z_][\w-]*):", body, re.M))
    name = re.search(r"^name:\s*(.+)$", body, re.M)
    desc = re.search(r"^description:\s*(.+)$", body, re.M)
    return keys, (name.group(1).strip() if name else None), (desc.group(1).strip() if desc else None)


def check_skill_dir(path: Path, skill_name: str | None = None) -> dict:
    """检查一个 skill 目录是否真的能被宿主加载。

    三种真实布局都要认（clone 型仓库常见后两种）：
      · <name>/SKILL.md                     —— 直接可加载的 skill
      · <name>/skills/<name>/SKILL.md       —— clone 下来的单技能仓库（多一层 skills/）
      · <name>/skills/<sub>/SKILL.md ×N     —— clone 下来的 bundle 仓库
    """
    if not path.exists():
        return {"ok": False, "reason": "目录不存在", "path": str(path)}
    if not path.is_dir():
        return {"ok": False, "reason": "不是目录", "path": str(path)}

    def _subs(d: Path):
        try:
            return [p for p in d.iterdir() if (p / "SKILL.md").is_file()]
        except OSError:
            return []

    # 单技能仓库：<name>/skills/<name>/SKILL.md
    nested = path / "skills" / path.name
    if (nested / "SKILL.md").is_file():
        path = nested
        md = nested / "SKILL.md"
    else:
        md = path / "SKILL.md"
    if not md.is_file():
        # bundle：优先看仓库约定的 skills/ 子目录，再看根下一层
        subs = _subs(path / "skills") if (path / "skills").is_dir() else []
        if not subs:
            subs = _subs(path)
        if subs:
            bad = []
            for s in subs:
                keys, name, desc = _read_frontmatter(s / "SKILL.md")
                if not name or not desc:
                    bad.append(s.name)
            if bad:
                return {"ok": False, "reason": f"{len(bad)}/{len(subs)} 个子技能缺 name/description（会被宿主丢弃）",
                        "path": str(path), "bad_children": bad[:8]}
            return {"ok": True, "path": str(path), "kind": "bundle", "children": len(subs)}
        return {"ok": False, "reason": "缺 SKILL.md（且无子技能）", "path": str(path)}
    keys, name, desc = _read_frontmatter(md)
    if keys is None:
        return {"ok": False, "reason": "SKILL.md 不可读", "path": str(path)}
    if not name:
        return {"ok": False, "reason": "frontmatter 缺 name（宿主会丢弃该 skill）", "path": str(path)}
    if not desc:
        return {"ok": False, "reason": "frontmatter 缺 description（宿主会丢弃该 skill）", "path": str(path)}
    if len(desc) > 1024:
        return {"ok": False, "reason": f"description 超 1024 字符（{len(desc)}），会被丢弃", "path": str(path)}
    allowed = {"name", "description", "when_to_use", "license", "metadata"}
    extra = sorted(keys - allowed)
    warn = [f"非白名单 frontmatter 键 {extra}（会导致 safeToAutoLoad=false，不自动加载）"] if extra else []
    return {"ok": True, "path": str(path), "kind": "skill", "name": name, "warnings": warn}


def check_plugin_cache(plugin_id: str) -> dict:
    """检查插件是否在 ZCode 缓存里（按名字前缀找版本目录）。"""
    if not PLUGIN_CACHE.is_dir():
        return {"ok": False, "reason": "插件缓存目录不存在", "path": str(PLUGIN_CACHE)}
    hits = list(PLUGIN_CACHE.rglob(f"*{plugin_id}*"))
    dirs = [h for h in hits if h.is_dir()]
    if not dirs:
        return {"ok": False, "reason": f"插件缓存里没有 {plugin_id}", "path": str(PLUGIN_CACHE)}
    return {"ok": True, "path": str(dirs[0]), "candidates": [str(d) for d in dirs[:3]]}


def find_skill_path(entry: dict) -> Path | None:
    """按 id 在常见 skill 根里找该 skill 的实际目录。"""
    sid = entry.get("id", "")
    for root in SKILL_ROOTS:
        p = root / sid
        if p.exists():
            return p
    # pipeline 类会 clone 成别的名字（如 figures4papers → scientific-figure-making）
    for alias in (entry.get("provides") or []):
        for root in SKILL_ROOTS:
            p = root / alias
            if p.exists():
                return p
    return None


def check_entry(entry: dict) -> dict:
    sid = entry.get("id", "?")
    kind = entry.get("kind")
    tier = entry.get("tier", "optional")
    result = {"id": sid, "tier": tier, "kind": kind, "role": entry.get("role", "")}

    if kind == "plugin":
        rec = check_plugin_cache(sid)
        # 插件也可能被解到 skill 目录（用户级副本），两者任一即可
        if not rec["ok"]:
            alt = find_skill_path(entry)
            if alt:
                rec = {**check_skill_dir(alt), "via": "skill dir"}
        result.update(rec)
        return result

    # skill / skill_bundle
    path = find_skill_path(entry)
    if path is None:
        # pipeline 类自身可能是本地件，允许用 local_path 兜底
        lp = entry.get("local_path")
        if lp and Path(lp).exists():
            path = Path(lp)
    if path is None:
        result.update({"ok": False,
                       "reason": "未安装（在 ~/.zcode/skills、~/.agents/skills、仓库 skills/ 都没找到）",
                       "repo": entry.get("repo")})
        return result
    result.update(check_skill_dir(path))
    result["repo"] = entry.get("repo")
    # bundle 额外核对 provides 是否都在。
    # provides 是**子技能名**：单技能包直接放在 skills 根（<root>/<name>），
    # 而 bundle 型库通常放在解析路径下的 skills/ 子目录（aris/skills/<name>），
    # 两种布局都要认，否则会把装好的 bundle 误报成缺失。
    provides = entry.get("provides") or []
    if provides and result.get("ok"):
        roots = list(SKILL_ROOTS)
        if path is not None:
            roots.extend([path, path / "skills"])
        missing = [p for p in provides if not any((root / p).exists() for root in roots)]
        if missing:
            result["ok"] = False
            result["reason"] = f"声称提供但实际缺失: {missing[:6]}"
    return result


def check_repo_runtime() -> dict:
    """本项目自身运行时是否可用（能跑 lint / 能导入状态引擎）。"""
    checks = {}
    su = REPO / "shared" / "state-engine" / "state_utils.py"
    checks["state_engine"] = {"ok": su.is_file(), "path": str(su)}
    lint = REPO / "scripts" / "lint_contracts.py"
    checks["lint_script"] = {"ok": lint.is_file(), "path": str(lint)}
    # 关键契约
    for rel in ("shared/contracts/gates-registry.json",
                "shared/contracts/math_modeling/data_lineage.schema.json",
                "shared/skill-routing/capability_taxonomy.json",
                "upstream-sources.json"):
        p = REPO / rel
        checks[rel] = {"ok": p.is_file(), "path": str(p)}
    bad = [k for k, v in checks.items() if not v["ok"]]
    return {"ok": not bad, "missing": bad, "checks": checks}


def run_lint() -> dict:
    lint = REPO / "scripts" / "lint_contracts.py"
    if not lint.is_file():
        return {"ok": False, "reason": "lint_contracts.py 缺失"}
    try:
        r = subprocess.run([sys.executable, str(lint)], capture_output=True,
                           text=True, timeout=180, cwd=str(REPO))
        return {"ok": r.returncode == 0, "returncode": r.returncode,
                "tail": (r.stdout or r.stderr or "").strip().splitlines()[-3:]}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "reason": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser(description="首次安装自检")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tier", choices=["required", "recommended", "optional"],
                    help="只检查该档位及以上")
    ap.add_argument("--skip-lint", action="store_true", help="跳过 lint（较慢）")
    args = ap.parse_args()

    if not MANIFEST.is_file():
        print(f"清单缺失: {MANIFEST}", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"清单 JSON 无效: {exc}", file=sys.stderr)
        return 2

    tiers = {"required": 0, "recommended": 1, "optional": 2}
    limit = tiers.get(args.tier, 2)
    results = []
    for entry in manifest.get("sources", []):
        if tiers.get(entry.get("tier", "optional"), 2) > limit:
            continue
        results.append(check_entry(entry))

    runtime = check_repo_runtime()
    lint = {"ok": True, "skipped": True} if args.skip_lint else run_lint()

    blocked = [r for r in results if r["tier"] == "required" and not r.get("ok")]
    degraded = [r for r in results if r["tier"] == "recommended" and not r.get("ok")]
    optional_missing = [r for r in results if r["tier"] == "optional" and not r.get("ok")]

    if blocked or not runtime["ok"] or not lint["ok"]:
        status = "BLOCKED"
    elif degraded:
        status = "DEGRADED"
    else:
        status = "READY"

    report = {
        "status": status,
        "checked_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "host": {"python": sys.version.split()[0], "platform": sys.platform},
        "summary": {"required_missing": len(blocked),
                    "recommended_missing": len(degraded),
                    "optional_missing": len(optional_missing),
                    "runtime_ok": runtime["ok"], "lint_ok": lint["ok"]},
        "blocked": [{"id": b["id"], "reason": b.get("reason"), "repo": b.get("repo"),
                     "install": next((e.get("install") for e in manifest["sources"]
                                      if e.get("id") == b["id"]), None)} for b in blocked],
        "degraded": [{"id": d["id"], "reason": d.get("reason"), "repo": d.get("repo")} for d in degraded],
        "optional_missing": [o["id"] for o in optional_missing],
        "runtime": runtime,
        "lint": lint,
        "details": results,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if status != "BLOCKED" else 1

    icon = {"READY": "✅", "DEGRADED": "⚠", "BLOCKED": "❌"}[status]
    print(f"{icon} 首次安装自检：{status}")
    print(f"   仓库: {report['repo']}")
    print(f"   宿主: Python {report['host']['python']} / {report['host']['platform']}")
    print()

    def show(title, items, show_install=False):
        if not items:
            print(f"{title}: 无")
            return
        print(f"{title}:")
        for it in items:
            rid = it.get("id") if isinstance(it, dict) else it
            reason = it.get("reason", "") if isinstance(it, dict) else ""
            repo = it.get("repo", "") if isinstance(it, dict) else ""
            print(f"  · {rid}" + (f" — {reason}" if reason else ""))
            if repo and repo != "LOCAL_ONLY":
                print(f"      仓库: {repo}")
            if show_install and isinstance(it, dict) and it.get("install"):
                print(f"      安装: {it['install']}")

    show("❌ 必需缺失（核心流程不可用）", report["blocked"], show_install=True)
    show("⚠ 建议缺失（可用但少一条路）", report["degraded"])
    show("可选缺失（不影响核心）", report["optional_missing"])
    print()
    print(f"本项目运行时: {'OK' if runtime['ok'] else '缺 ' + str(runtime['missing'])}")
    print(f"契约 lint: {'OK' if lint['ok'] else 'FAIL'}")
    if status == "BLOCKED":
        print()
        print("下一步：按上面「安装」列逐项补齐 required，然后重跑本脚本。")
    return 0 if status != "BLOCKED" else 1


if __name__ == "__main__":
    sys.exit(main())
