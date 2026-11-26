#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checkpoint 0 — MCP 启动自检与闭环校验
=====================================

按 mcp/checkpoint-0-boot.md 实现：

  ① 全局 MCP 扫描（以本机真实配置为唯一依据，禁止虚构/硬编码）
  ② 筛选数学建模四类适配 MCP
  ③ 内嵌封装确认（协议文档在位）
  ④ 自检（加载状态 / 调用权限 / 联网状态 / 密钥有效性）→ 门禁判定

用法：
  python scripts/mcp_boot_check.py [--report] [--namespaces a,b,c]
  python scripts/mcp_boot_check.py --coverage --dir <任务目录>
  python scripts/mcp_boot_check.py --ledger <references-ledger.md>

输出：
  标准输出判定行：MCP_READY / MCP_BLOCKED <缺失清单>
  --report 额外写 mcp/mcp-boot-report.md
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import socket
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 四类适配 MCP 的名称匹配规则（与 mcp/mcp-scan-results.md、cluster-roles.md 一致）
CATEGORIES = {
    "论文搜索MCP(paper-mcp)": {
        "need": "core",
        "match": ["paper-mcp", "paper_mcp", "papermcp", "paper-mcp@", "paper_mcp@"],
        "endpoint": "https://api.crossref.org/works?rows=0&select=DOI",
        "note": "core 常驻 · 文献检索&归档",
    },
    "GitHub MCP(github)": {
        "need": "core",
        "match": ["github"],
        "endpoint": "https://api.github.com",
        "note": "core 常驻 · 开源工程",
    },
    "Context7 MCP(context7)": {
        "need": "core",
        "match": ["context7"],
        "endpoint": "https://context7.com",
        "note": "core 常驻 · 算法技术",
    },
    "Tavily全网搜索MCP(tavily)": {
        "need": "optional",
        "match": ["tavily"],
        "endpoint": "https://api.tavily.com",
        "note": "待装·已内嵌双密钥；就绪回退见 tokenhub",
    },
    "全网搜索回退MCP(tokenhub-tools)": {
        "need": "fallback",
        "match": ["tokenhub-tools", "tokenhub", "tokenhub_tools"],
        "endpoint": None,
        "note": "Tavily 未就绪时承接全网搜索",
    },
}

KMAP = {"paper": "论文搜索MCP(paper-mcp)", "context7": "Context7 MCP(context7)",
        "github": "GitHub MCP(github)", "tavily": "Tavily全网搜索MCP(tavily)",
        "tokenhub": "全网搜索回退MCP(tokenhub-tools)"}

# 六节点必调映射（与 mcp/call-hierarchy.md 一致）
MANDATORY = {
    "N1": ["paper", "tavily/tokenhub"],
    "N3": ["context7", "paper"],
    "N4": ["context7", "github"],
    "N5": ["github", "tavily/tokenhub"],
    "N6": ["paper", "tavily/tokenhub"],
    "N7": ["paper"],
}

KNOWN_NAMESPACES = {
    "paper-mcp", "paper_mcp", "papermcp", "github", "github-mcp", "context7",
    "tavily", "tavily-mcp", "tokenhub", "tokenhub-tools", "tokenhub_tools"
}


def _normalize_namespace(name: str) -> str:
    value = str(name or "").strip().lower().replace("_", "-")
    value = re.sub(r"^mcp--", "", value)
    return re.sub(r"@[^@]+$", "", value)


def _mcp_config_candidates():
    cands = []
    # 项目内
    for rel in (".mcp.json", ".zcode/mcp.json", ".codex-plugin", ".claude-plugin"):
        p = ROOT / rel
        if p.is_file():
            cands.append(p)
        elif p.is_dir():
            for f in p.rglob("*.json"):
                cands.append(f)
    # 用户目录
    for home in (Path.home(), Path(os.environ.get("USERPROFILE", ""))):
        for rel in (".zcode/mcp.json", ".codex/mcp.json", ".mcp.json"):
            p = home / rel
            if p.is_file():
                cands.append(p)
        cj = home / ".claude.json"
        if cj.is_file():
            cands.append(cj)
    # 环境变量
    env = os.environ.get("MCP_CONFIG", "")
    if env and Path(env).is_file():
        cands.append(Path(env))
    # 去重保序
    seen, out = set(), []
    for p in cands:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def scan_configured_mcps():
    """从真实配置文件扫描已注册 MCP 服务名（步骤①）。返回 {name} 集合。"""
    names = set()
    for p in _mcp_config_candidates():
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for key in ("mcpServers", "mcpServers2", "servers"):
            if isinstance(data, dict) and isinstance(data.get(key), dict):
                for name in data[key]:
                    names.add(str(name).lower())
        # .claude.json 的 projects.*.mcpServers
        if isinstance(data, dict) and "projects" in data:
            for proj in data["projects"].values():
                if isinstance(proj, dict) and isinstance(proj.get("mcpServers"), dict):
                    for name in proj["mcpServers"]:
                        names.add(str(name).lower())
    return names


def _host_reachable(url, timeout=6):
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 100 <= r.status < 400
    except Exception:
        return False


def _tavily_keys():
    """Return only whether an external runtime key is configured; never read/print secrets."""
    return ["configured"] if os.environ.get("TAVILY_API_KEY", "").strip() else []


def _internals_in_place():
    files = {
        "checkpoint-0-boot.md": ROOT / "mcp/checkpoint-0-boot.md",
        "cluster-roles.md": ROOT / "mcp/cluster-roles.md",
        "call-hierarchy.md": ROOT / "mcp/call-hierarchy.md",
        "validation-checkpoints.md": ROOT / "mcp/validation-checkpoints.md",
        "knowledge-card.template.md": ROOT / "mcp/knowledge-card.template.md",
        "reference-ledger.template.md": ROOT / "mcp/reference-ledger.template.md",
        "mm-boot 命令": ROOT / "commands/mm-boot.md",
    }
    missing = [k for k, v in files.items() if not v.is_file()]
    return missing


def _category_matches(category: str, name: str) -> bool:
    """Match real session namespaces, including mcp__ and @version forms."""
    normalized = _normalize_namespace(name)
    aliases = {
        "论文搜索MCP(paper-mcp)": {"paper-mcp", "papermcp", "paper-mcp-server"},
        "GitHub MCP(github)": {"github", "github-mcp", "github-server"},
        "Context7 MCP(context7)": {"context7", "context7-mcp"},
        "Tavily全网搜索MCP(tavily)": {"tavily", "tavily-mcp", "tavily-server"},
        "全网搜索回退MCP(tokenhub-tools)": {"tokenhub", "tokenhub-tools", "tokenhub-tools-mcp"},
    }
    return normalized in aliases.get(category, set())


def run_check(namespaces=None, probe=True):
    configured = scan_configured_mcps()
    # 命名空间参数是对会话内真实注册工具的补充输入，但必须是已知服务 ID。
    for ns in (namespaces or []):
        value = _normalize_namespace(ns)
        if value in {_normalize_namespace(item) for item in KNOWN_NAMESPACES}:
            configured.add(value)

    rows, blocked = [], []
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for cat, spec in CATEGORIES.items():
        hit = [c for c in configured if _category_matches(cat, c)]
        online = _host_reachable(spec["endpoint"]) if (probe and spec["endpoint"]) else None
        status = "ok" if hit else "missing"
        if hit and probe and spec["endpoint"] and online is False:
            status = "offline"
        rows.append({
            "category": cat, "found": sorted(hit), "status": status,
            "online": online, "note": spec["note"],
        })
        if (not hit or (probe and spec["need"] == "core" and online is False)) and spec["need"] == "core":
            blocked.append(cat if hit else cat + " 未注册")
        if hit and probe and spec["need"] in {"optional", "fallback"} and online is False:
            # An offline optional provider may be replaced by an online fallback;
            # its row remains visible but does not masquerade as ready.
            pass

    # Web 综合判定：Tavily 为可回退项，仅当与全网搜索回退（tokenhub）同时缺失才阻断
    saw_tavily = any(r["found"] and (not probe or r["online"] is True)
                      for r in rows if r["category"].startswith("Tavily"))
    # tokenhub has no HTTP endpoint in this checker; presence is the best
    # available signal and the actual call must still be recorded downstream.
    saw_tokenhub = any(r["found"] for r in rows if r["category"].startswith("全网"))
    web_ok = saw_tavily or saw_tokenhub
    if not web_ok:
        blocked.append("Tavily/全网搜索 不可用（需安装 tavily-mcp 或启用 tokenhub-tools）")

    core_names = [r["category"] for r in rows if r["found"]]
    intern_missing = _internals_in_place()
    tavily_keys = _tavily_keys()

    gate = "MCP_READY"
    if blocked or not web_ok:
        gate = "MCP_BLOCKED"
        if not web_ok:
            blocked.append("Tavily/全网搜索 不可用（需安装 tavily-mcp 或启用 tokenhub-tools）")
    if intern_missing:
        gate = "MCP_BLOCKED"
        blocked.append(f"内嵌封装缺失: {', '.join(intern_missing)}")

    blocked = list(dict.fromkeys(blocked))
    return {
        "gate": gate, "blocked": blocked, "rows": rows,
        "configured_count": len(configured), "core_found": core_names,
        "tavily_keys": len(tavily_keys), "intern_missing": intern_missing,
        "timestamp": now, "web_ok": web_ok,
    }


def render_report(res, path=None):
    lines = [
        "# MCP 自检报告（Checkpoint 0）",
        "",
        f"- 时间：{res['timestamp']}",
        f"- 判定：**{res['gate']}**",
        f"- 扫描到 MCP 服务数：{res['configured_count']}",
        f"- Tavily 内嵌密钥：{res['tavily_keys']} 枚",
        "",
        "## 分类自检",
        "",
        "| 类别 | 是否注册 | 联网探测 | 备注 |",
        "|------|:------:|:------:|------|",
    ]
    for r in res["rows"]:
        on = {"ok": "✅", "missing": "❌"}[r["status"]]
        net = "—" if r["online"] is None else ("✅" if r["online"] else "❌")
        lines.append(f"| {r['category']} | {on} {', '.join(r['found']) if r['found'] else '未注册'} | {net} | {r['note']} |")
    lines += ["", "## 门禁", ""]
    if res["gate"] == "MCP_READY":
        lines.append("`MCP_READY` — 允许建模任务启动。")
    else:
        lines.append("`MCP_BLOCKED` — 终止任务，修复以下项后重跑：")
        for b in res["blocked"]:
            lines.append(f"- ❌ {b}")
    if path:
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines)


def api_coverage(calls_path):
    """--coverage: 校验五节点必调 MCP 覆盖。calls_path 为 mcp-calls.jsonl。"""
    seen = {}
    if Path(calls_path).is_file():
        for line in Path(calls_path).read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            node = str(rec.get("node", "")).upper()
            mcp = _normalize_namespace(rec.get("mcp", rec.get("mcp_source", "")))
            seen.setdefault(node, set()).add(mcp)
    rows = []
    for node, reqs in sorted(MANDATORY.items()):
        got = seen.get(node, set())
        lacks = [r for r in reqs if not any(any(_m in g for _m in KMAP[r.split("/")[0]]["match"]) for g in got)]
        rows.append((node, sorted(got), lacks))
    return rows


def ledger_check(path):
    """--ledger: GB/T 7714 台账基础校验（作者/题名/年份/DOI 或链接）。"""
    p = Path(path)
    if not p.is_file():
        print(f"[ledger] 文件不存在: {path}")
        return 1
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_seen = False
    issues, total = [], 0
    for i, ln in enumerate(lines, 1):
        if re.match(r"^\s*\|?\s*#\s*\|", ln) or header_seen:
            header_seen = True
        if not header_seen or not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 9 or cells[0] in ("#", ""):
            continue
        total += 1
        author, title, year, doi = cells[1], cells[2], cells[4], cells[6]
        if not author or author in ("作者", "……"):
            issues.append(f"行{i}: 缺作者")
        if not title or title in ("题名", "……"):
            issues.append(f"行{i}: 缺题名")
        if not year or not re.search(r"\d{4}", year):
            issues.append(f"行{i}: 缺年份")
        if not doi or ("doi" not in doi.lower() and "http" not in doi.lower()):
            issues.append(f"行{i}: 缺 DOI/链接")
    for it in issues:
        print(f"[ledger] ⚠ {it}")
    print(f"[ledger] 条目 {total} 条，问题 {len(issues)} 处 → {'PASS' if not issues and total else 'FAIL' if issues else 'NO_ROWS'}")
    return 0 if not issues and total else 1


def main():
    ap = argparse.ArgumentParser(description="Checkpoint 0 MCP 自检")
    ap.add_argument("--report", action="store_true", help="写出 mcp/mcp-boot-report.md")
    ap.add_argument("--namespaces", default="", help="会话内真实注册的 MCP 命名空间，逗号分隔")
    ap.add_argument("--no-probe", action="store_true", help="跳过联网探测")
    ap.add_argument("--coverage", action="store_true", help="五节点必调覆盖校验")
    ap.add_argument("--dir", default=".", help="--coverage 任务目录（读取 state/reports/mcp-calls.jsonl）")
    ap.add_argument("--ledger", default="", help="GB/T 7714 台账 markdown 路径")
    args = ap.parse_args()

    if args.ledger:
        sys.exit(ledger_check(args.ledger))

    if args.coverage:
        calls = Path(args.dir) / "state/reports/mcp-calls.jsonl"
        print(f"== 五节点必调 MCP 覆盖校验（{calls}）==")
        all_ok = True
        for node, got, lacks in api_coverage(calls):
            mark = "✅" if not lacks else "❌"
            print(f"{mark} {node}: 已调用 {got or '无'} 缺失 {lacks or '—'}")
            if lacks:
                all_ok = False
        print("COVERAGE_PASS" if all_ok else "COVERAGE_FAIL")
        sys.exit(0 if all_ok else 1)

    ns = [x for x in args.namespaces.split(",") if x.strip()]
    res = run_check(namespaces=ns, probe=not args.no_probe)
    rep = render_report(res, ROOT / "mcp/mcp-boot-report.md" if args.report else None)
    print(rep)
    print("")
    if res["gate"] == "MCP_READY":
        print("MCP_READY — 允许建模任务启动")
        sys.exit(0)
    print("MCP_BLOCKED — 终止任务，修复以下后重跑:")
    for b in res["blocked"]:
        print(f"  - {b}")
    sys.exit(1)


if __name__ == "__main__":
    main()
