#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游更新检查（/academic-update 的机器入口）。

读取 upstream-manifest.json，逐个上游检查：
  - git 源：读取本地 HEAD sha，与 manifest 的 installed_commit 比对；
    能连远端时顺带报告 behind / ahead（只读，不 pull、不改工作区）
  - 插件源：读 installed_plugins.json 记录的实际版本
  - 技能包：读 SKILL.md / manifest.yaml 里的 version 字段（只报告，不判定）

默认只报告（dry-run）。加 --apply 才对 git 源执行 pull --ff-only：
tracked=false 的条目跳过；用 <git_dir>/.mm-upstream.lock 串行化，防止并发
更新与中断残留；git status 返回码非 0 时不继续。

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
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "upstream-manifest.json"

LOCK_NAME = ".mm-upstream.lock"
MERGE_HINT = ("若出现冲突请手动处理：git status 查看，"
              "git merge --abort 可回到 pull 前状态")


def _run(cmd, cwd=None, timeout=30):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return 1, "", str(exc)


SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def _is_sha(text: str) -> bool:
    return bool(SHA_RE.match((text or "").strip().lower()))


def _sha_matches(recorded: str, head_sha: str) -> bool:
    """登记值可以是完整 sha 或 short sha（至少 7 位）。"""
    rec = (recorded or "").strip().lower()
    cur = (head_sha or "").strip().lower()
    if not rec or not cur:
        return False
    if rec == cur:
        return True
    short, full = (rec, cur) if len(rec) <= len(cur) else (cur, rec)
    return len(short) >= 7 and full.startswith(short)


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


def check_git_source(git_dir: str, installed_commit: str | None = None,
                     timeout: int = 30) -> dict:
    """只读检查 git 源。不 pull。

    状态由本地 HEAD sha 与 manifest 的 installed_commit 比对决定：
    UP_TO_DATE / DRIFT / UNTRACKED_COMMIT；远端 behind 数仅作参考。
    """
    p = Path(git_dir)
    if not p.exists():
        return {"state": "MISSING", "detail": "git 源目录不存在"}
    if not (p / ".git").exists() and not (p / "HEAD").exists():
        return {"state": "NOT_GIT", "detail": "不是 git 仓库"}
    rc, head_sha, err = _run(["git", "-C", str(p), "rev-parse", "HEAD"], timeout=timeout)
    if rc != 0 or not head_sha:
        return {"state": "ERROR", "detail": f"无法读取 HEAD: {err[:200]}"}
    rc_s, head_short, _ = _run(["git", "-C", str(p), "rev-parse", "--short", "HEAD"],
                               timeout=timeout)
    head_short = head_short or head_sha[:7]
    rc2, branch, _ = _run(["git", "-C", str(p), "rev-parse", "--abbrev-ref", "HEAD"],
                          timeout=timeout)
    branch = branch or "main"

    recorded = (installed_commit or "").strip()
    res = {"head_sha": head_sha, "head_short": head_short, "branch": branch,
           "installed_commit": recorded or None}
    if not recorded:
        res["state"] = "UNTRACKED_COMMIT"
        res["detail"] = (f"manifest 未登记 installed_commit（当前 HEAD {head_short}），"
                         "请补登记")
    elif not _is_sha(recorded):
        res["state"] = "UNTRACKED_COMMIT"
        res["detail"] = (f"installed_commit 不是合法 sha（{recorded}），"
                         f"当前 HEAD 为 {head_short}；请改为登记 sha")
    elif _sha_matches(recorded, head_sha):
        res["state"] = "UP_TO_DATE"
        res["detail"] = f"本地 HEAD {head_short} 与登记 commit 一致"
    else:
        res["state"] = "DRIFT"
        res["detail"] = (f"本地 HEAD {head_short} 与登记 commit {recorded} 不一致，"
                         "可能被手动改动过；确认后回填实际 HEAD")

    # 只 fetch，不改工作区；失败不影响上面的本地比对结论
    rc3, _, err3 = _run(["git", "-C", str(p), "fetch", "--quiet", "origin", branch],
                        timeout=max(timeout, 60))
    if rc3 != 0:
        res["remote_state"] = "FETCH_FAILED"
        res["fetch_error"] = err3[:200]
        res["behind"] = None
        res["ahead"] = None
        return res
    rc4, behind, _ = _run(["git", "-C", str(p), "rev-list", "--count",
                           f"HEAD..origin/{branch}"], timeout=timeout)
    rc5, ahead, _ = _run(["git", "-C", str(p), "rev-list", "--count",
                          f"origin/{branch}..HEAD"], timeout=timeout)
    if rc4 != 0:
        res["remote_state"] = "ERROR"
        res["fetch_error"] = "无法计算落后提交数"
        res["behind"] = None
        res["ahead"] = None
        return res
    res["remote_state"] = "OK"
    try:
        res["behind"] = int(behind or "0")
    except ValueError:
        res["behind"] = 0
    try:
        res["ahead"] = int(ahead or "0")
    except ValueError:
        res["ahead"] = 0
    return res


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
            if declared in (None, ""):
                return {"state": "REPORTED", "installed": ver,
                        "detail": "清单未声明可校验版本，仅报告实际版本"}
            same = (str(ver) == str(declared))
            return {"state": "UP_TO_DATE" if same else "VERSION_DIFF",
                    "installed": ver, "declared": declared}
    return {"state": "NOT_INSTALLED", "detail": f"{pid} 未在 installed_plugins.json 中"}


def check_bundle_source(entry: dict) -> dict:
    """技能包：读本地 SKILL.md/manifest.yaml 版本，只报告不判定。"""
    paths = entry.get("local_paths") or []
    found = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            found.append({"path": raw, "state": "MISSING"})
            continue
        ver = _read_version_from_skill(p)
        found.append({"path": raw, "version": ver, "state": "OK" if ver else "NO_VERSION"})
    return {"state": "REPORTED", "items": found,
            "detail": "仅报告实际找到的版本，不判定一致/不一致"}


def apply_git_pull(entry: dict, branch: str) -> dict:
    """执行 git pull --ff-only（仅限 tracked 的 git 源）。

    保护顺序：tracked=false 跳过 → 建锁（O_CREAT|O_EXCL）→ git status 返回码
    必须为 0 → 工作区有改动拒绝 → 只允许 fast-forward。锁文件在所有路径上
    由 finally 删除。
    """
    if entry.get("tracked") is False:
        return {"state": "SKIPPED", "detail": "tracked=false，不自动更新"}

    git_dir = entry.get("git_source")
    p = Path(git_dir) if git_dir else None
    if p is None or not p.exists():
        return {"state": "MISSING", "detail": "git 源目录不存在"}

    lock = p / LOCK_NAME
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"state": "LOCKED",
                "detail": f"锁文件已存在：{lock}（另一个进程正在更新；"
                          "确认无进程后可手动删除）"}
    except OSError as exc:
        return {"state": "LOCK_FAILED", "detail": f"无法创建锁文件：{exc}"}

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"pid={os.getpid()}\n")

        rc, status, err = _run(["git", "-C", str(p), "status", "--porcelain"], timeout=30)
        if rc != 0:
            return {"state": "STATUS_FAILED",
                    "detail": (err or status or f"git status 返回码 {rc}")[:300]}
        # 锁文件是本次操作自己建的，不算用户改动
        dirty = [ln for ln in status.splitlines()
                 if ln.strip() and not ln.rstrip().endswith(LOCK_NAME)]
        if dirty:
            return {"state": "DIRTY",
                    "detail": "工作区有未提交改动，拒绝 pull（请先处理）"}

        rc2, out, err2 = _run(["git", "-C", str(p), "pull", "--ff-only", "origin", branch],
                              timeout=180)
        if rc2 != 0:
            detail = (err2 or out)[:300]
            return {"state": "PULL_FAILED",
                    "detail": f"{detail} | {MERGE_HINT}" if detail else MERGE_HINT}

        _, new_head, _ = _run(["git", "-C", str(p), "rev-parse", "--short", "HEAD"],
                              timeout=30)
        detail = out[:200]
        if new_head:
            note = f"新 HEAD {new_head}，请回填 installed_commit"
            detail = f"{detail} | {note}" if detail else note
        return {"state": "PULLED", "detail": detail}
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _reported_summary(check: dict) -> str:
    if "installed" in check:
        return f"实际版本 {check.get('installed')}（仅报告）"
    items = check.get("items") or []
    parts = [f"{Path(i.get('path', '')).name}={i.get('version') or 'N/A'}"
             for i in items]
    if len(parts) > 4:
        parts = parts[:4] + ["…"]
    if not parts:
        return "无可读版本"
    return "实际版本 " + ", ".join(parts)


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
        rec = {"id": uid, "kind": entry.get("kind"), "method": method,
               "tracked": entry.get("tracked")}
        if method == "git_pull" and entry.get("git_source"):
            check = check_git_source(entry["git_source"], entry.get("installed_commit"))
            rec["check"] = check
            if args.apply:
                behind = check.get("behind")
                if entry.get("tracked") is False:
                    rec["apply"] = {"state": "SKIPPED",
                                    "detail": "tracked=false，不自动更新"}
                elif check.get("state") in ("MISSING", "NOT_GIT", "ERROR"):
                    rec["apply"] = {"state": "SKIPPED",
                                    "detail": f"检查状态 {check.get('state')}，无法更新"}
                elif behind is None:
                    rec["apply"] = {"state": "SKIPPED",
                                    "detail": "远端提交数未知（fetch 失败），未执行 pull"}
                elif behind <= 0:
                    rec["apply"] = {"state": "SKIPPED", "detail": "远端无新提交，无需 pull"}
                else:
                    rec["apply"] = apply_git_pull(entry, check.get("branch") or "main")
        elif method == "plugin_marketplace":
            rec["check"] = check_plugin_source(entry)
        else:
            rec["check"] = check_bundle_source(entry)
        results.append(rec)

    if args.json:
        print(json.dumps({"checked_at": datetime.now().isoformat(timespec="seconds"),
                          "results": results}, ensure_ascii=False, indent=2))
        return 0

    print("上游更新检查" + ("（--apply）" if args.apply else "（只读）"))
    print("-" * 70)
    for r in results:
        c = r.get("check", {})
        st = c.get("state", "?")
        extra = ""
        if st == "VERSION_DIFF":
            extra = f" 已装 {c.get('installed')} / 声明 {c.get('declared')}"
        elif st == "REPORTED":
            extra = " " + _reported_summary(c)
        elif st in ("DRIFT", "UNTRACKED_COMMIT"):
            extra = " " + (c.get("detail") or "")
        behind = c.get("behind")
        if isinstance(behind, int) and behind > 0:
            extra += f"；落后 {behind} 个提交（分支 {c.get('branch')}）"
        if c.get("remote_state") == "FETCH_FAILED":
            extra += "；远端检查失败 FETCH_FAILED"
        print(f"  [{st:16}] {r['id']:26}{extra}")
        if "apply" in r:
            ap = r["apply"]
            print(f"      → apply: {ap['state']}")
            if ap["state"] != "PULLED":
                print(f"        {ap.get('detail', '')}")
    print("-" * 70)
    print("提示：--apply 仅对 tracked=true 的 git 源执行 pull --ff-only；"
          "插件类更新请走 Plugin Management。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
