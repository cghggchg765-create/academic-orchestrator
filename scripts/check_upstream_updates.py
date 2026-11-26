#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游更新检查（/academic-update 的机器入口）。

读取 upstream-manifest.json，逐个上游检查：
  - git 源：git fetch 后比对本地 HEAD 与远端是否落后（只读，不 pull、不改工作区）
  - 插件源：读 installed_plugins.json 记录的版本，与 manifest 里的 installed_version 比对
  - 技能包：读 SKILL.md / manifest.yaml 里的 version 字段

默认只报告（dry-run）。加 --apply 才对 git 源执行 pull（仍不碰插件与用户级副本）。

用法:
  python scripts/check_upstream_updates.py                 # 全部检查（只读）
  python scripts/check_upstream_updates.py --json          # 机器可读
  python scripts/check_upstream_updates.py --id aris       # 只查一个
  python scripts/check_upstream_updates.py --apply --id aris   # 执行 git pull
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "upstream-manifest.json"


def _run(cmd, cwd=None, timeout=30):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return 1, "", str(exc)


def _read_version_from_skill(path: Path) -> str | None:
    """从 SKILL.md frontmatter 或 manifest.yaml 读 version。"""
    for name in ("manifest.yaml", "SKILL.md"):
        p = path / name if path.is_dir() else path
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r'^version:\s*"?([0-9][^"\s]*)"?', text, re.M)
        if m:
            return m.group(1)
    return None


def check_git_source(git_dir: str, timeout: int = 30) -> dict:
    """只读检查 git 源是否落后远端。不 pull。"""
    p = Path(git_dir)
    if not p.exists():
        return {"state": "MISSING", "detail": "git 源目录不存在"}
    if not (p / ".git").exists() and not (p / "HEAD").exists():
        return {"state": "NOT_GIT", "detail": "不是 git 仓库"}
    rc, head, _ = _run(["git", "-C", str(p), "rev-parse", "--short", "HEAD"], timeout=timeout)
    if rc != 0:
        return {"state": "ERROR", "detail": "无法读取 HEAD"}
    rc2, branch, _ = _run(["git", "-C", str(p), "rev-parse", "--abbrev-ref", "HEAD"], timeout=timeout)
    branch = branch or "main"
    # 只 fetch，不改工作区
    rc3, _, err3 = _run(["git", "-C", str(p), "fetch", "--quiet", "origin", branch], timeout=max(timeout, 60))
    if rc3 != 0:
        return {"state": "FETCH_FAILED", "head": head, "branch": branch, "detail": err3[:200]}
    rc4, behind, _ = _run(["git", "-C", str(p), "rev-list", "--count", f"HEAD..origin/{branch}"], timeout=timeout)
    rc5, ahead, _ = _run(["git", "-C", str(p), "rev-list", "--count", f"origin/{branch}..HEAD"], timeout=timeout)
    if rc4 != 0:
        return {"state": "ERROR", "head": head, "branch": branch, "detail": "无法计算落后提交数"}
    behind_n = int(behind or "0")
    ahead_n = int(ahead or "0")
    state = "UP_TO_DATE" if behind_n == 0 else "BEHIND"
    return {"state": state, "head": head, "branch": branch,
            "behind": behind_n, "ahead": ahead_n}


def check_plugin_source(entry: dict) -> dict:
    """插件源：读 installed_plugins.json 的实际版本。"""
    pid = entry.get("id")
    inst = Path.home() / ".zcode" / "cli" / "plugins" / "installed_plugins.json"
    if not inst.exists():
        return {"state": "UNKNOWN", "detail": "installed_plugins.json 不存在"}
    try:
        data = json.loads(inst.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": "UNKNOWN", "detail": f"读取失败: {exc}"}
    for pl in data.get("plugins", []):
        if pl.get("name") == pid or str(pl.get("id", "")).startswith(pid + "@"):
            ver = pl.get("version")
            declared = entry.get("installed_version")
            same = (str(ver) == str(declared))
            return {"state": "UP_TO_DATE" if same else "VERSION_DIFF",
                    "installed": ver, "declared": declared}
    return {"state": "NOT_INSTALLED", "detail": f"{pid} 未在 installed_plugins.json 中"}


def check_bundle_source(entry: dict) -> dict:
    """技能包：读本地 SKILL.md/manifest.yaml 版本。"""
    paths = entry.get("local_paths") or []
    found = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            found.append({"path": raw, "state": "MISSING"})
            continue
        ver = _read_version_from_skill(p)
        found.append({"path": raw, "version": ver, "state": "OK" if ver else "NO_VERSION"})
    ok = [f for f in found if f["state"] == "OK"]
    return {"state": "OK" if ok else "NO_VERSION_FOUND", "items": found}


def apply_git_pull(git_dir: str, branch: str) -> dict:
    """执行 git pull --ff-only。拒绝非 fast-forward，避免覆盖本地改动。"""
    p = Path(git_dir)
    rc, status, _ = _run(["git", "-C", str(p), "status", "--porcelain"], timeout=30)
    if status:
        return {"state": "DIRTY", "detail": "工作区有未提交改动，拒绝 pull（请先处理）"}
    rc2, out, err2 = _run(["git", "-C", str(p), "pull", "--ff-only", "origin", branch], timeout=180)
    if rc2 != 0:
        return {"state": "PULL_FAILED", "detail": (err2 or out)[:300]}
    return {"state": "PULLED", "detail": out[:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description="上游更新检查（默认只读）")
    ap.add_argument("--id", help="只检查指定上游 id")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--apply", action="store_true", help="对 git 源执行 pull --ff-only")
    ap.add_argument("--manifest", default=str(MANIFEST))
    args = ap.parse_args()

    mpath = Path(args.manifest)
    if not mpath.exists():
        print(f"上游清单不存在: {mpath}", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"上游清单 JSON 无效: {exc}", file=sys.stderr)
        return 2

    results = []
    for entry in manifest.get("upstreams", []):
        uid = entry.get("id")
        if args.id and uid != args.id:
            continue
        method = entry.get("update_method", "")
        rec = {"id": uid, "kind": entry.get("kind"), "method": method}
        if method == "git_pull" and entry.get("git_source"):
            rec["check"] = check_git_source(entry["git_source"])
            if args.apply and rec["check"].get("state") == "BEHIND":
                rec["apply"] = apply_git_pull(entry["git_source"], rec["check"].get("branch", "main"))
        elif method == "plugin_marketplace":
            rec["check"] = check_plugin_source(entry)
        else:
            rec["check"] = check_bundle_source(entry)
        results.append(rec)

    if args.json:
        print(json.dumps({"checked_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                          "results": results}, ensure_ascii=False, indent=2))
    else:
        print("上游更新检查（只读）")
        print("-" * 70)
        for r in results:
            c = r.get("check", {})
            st = c.get("state", "?")
            extra = ""
            if st == "BEHIND":
                extra = f" 落后 {c.get('behind')} 个提交（分支 {c.get('branch')}）"
            elif st == "VERSION_DIFF":
                extra = f" 已装 {c.get('installed')} / 声明 {c.get('declared')}"
            print(f"  [{st:14}] {r['id']:26} {extra}")
            if "apply" in r:
                print(f"      → apply: {r['apply']['state']}")
        print("-" * 70)
        print("提示：--apply 仅对 git 源执行 pull --ff-only；插件类更新请走 Plugin Management。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
