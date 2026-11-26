#!/usr/bin/env python3
"""插件升级自检：仓库契约 + 用户级同步滞后 + 组件完整性；--fix 自动重新同步。

用途：插件/系统更新后运行一次，自动检查哪些部分因旧版出现漂移（版本落后、
组件缺失、命名残留），并可自动纠正修复（重新同步用户级目录）。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()


def check_repo_contract() -> list[str]:
    """仓库契约检查（lint_contracts），返回问题列表（重定向其 stdout，避免混入报告输出）。"""
    import contextlib
    import importlib.util
    import io
    spec = importlib.util.spec_from_file_location("lint_contracts", ROOT / "scripts" / "lint_contracts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with contextlib.redirect_stdout(io.StringIO()):
        mod.main()
    return list(mod.ERRORS)


def user_sync_status() -> dict:
    """对比仓库与用户级目录：版本滞后、组件缺失（同步模式）/ 残留检查（插件独占模式）。"""
    issues: list[str] = []
    repo_ver = _repo_version()
    repo_components = {
        "skills": sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()),
        "agents": sorted(p.stem for p in (ROOT / "agents").glob("*.md")),
        "commands": sorted(p.stem for p in (ROOT / "commands").glob("*.md")),
    }
    targets = {"skills": HOME / ".zcode" / "skills", "agents": HOME / ".zcode" / "agents", "commands": HOME / ".zcode" / "commands"}
    plugin_only = (ROOT / ".plugin-only").exists()
    if plugin_only:
        # 插件独占模式需检查两套可能遮蔽插件的用户根目录，并按 Windows
        # 大小写不敏感规则匹配组件名，保持与 sync_user_level 一致。
        for user_root in (HOME / ".zcode", HOME / ".agents"):
            for comp, names in repo_components.items():
                d = user_root / comp
                if not d.is_dir():
                    continue
                installed = {p.name.casefold() if comp == "skills" else p.stem.casefold()
                             for p in d.iterdir()
                             if comp == "skills" or p.suffix.casefold() == ".md"}
                stray = [n for n in names if n.casefold() in installed]
                if stray:
                    issues.append(f"插件独占模式：{user_root.name}/{comp}/ 残留本仓库组件 {len(stray)} 项: {stray[:5]}（运行 python scripts/sync_user_level.py --plugin-only 清理）")
    else:
        for scope in (HOME / ".zcode", HOME / ".agents"):
            target = scope / "skills" / "mm-iteration-engine" / "SKILL.md"
            if target.exists():
                text = target.read_text(encoding="utf-8")
                ver = next((ln.split('"')[1] for ln in text.splitlines() if ln.strip().startswith("version:")), None)
                if ver != repo_ver:
                    issues.append(f"{scope}/skills mm-iteration-engine 版本 {ver} != 仓库 {repo_ver}")
                if "00_State" in text:
                    issues.append(f"{scope}/skills 仍含旧命名 00_State")
            else:
                issues.append(f"{scope}/skills/mm-iteration-engine 缺失")
        # 组件完整性
        for comp, names in repo_components.items():
            d = targets[comp]
            if not d.is_dir():
                issues.append(f"用户级 {comp}/ 缺失（{d}）")
                continue
            if comp == "skills":
                installed = {p.name for p in d.iterdir()}
            else:
                installed = {p.stem for p in d.iterdir() if p.suffix == ".md"}
            missing = [n for n in names if n not in installed]
            if missing:
                issues.append(f"用户级 {comp}/ 缺 {len(missing)} 项: {missing[:5]}")
    # 插件缓存（版本动态，随仓库版本走）
    plug = HOME / ".zcode" / "cli" / "plugins" / "cache" / "math-modeling" / "math-modeling-agent-system" / repo_ver
    if not (plug / ".zcode-plugin" / "plugin.json").exists():
        issues.append(f"插件缓存缺失: {plug}")
    return {"repo_version": repo_ver, "issues": issues}


def _repo_version() -> str:
    """仓库版本：SKILL.md 为准；缺失时回退到 pyproject.toml，避免陈旧硬编码。"""
    sk = ROOT / "skills" / "mm-iteration-engine" / "SKILL.md"
    try:
        for line in sk.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version:"):
                return line.split('"')[1]
    except OSError:
        pass
    try:
        match = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


def sync_user_dirs() -> list[str]:
    """重新同步用户级 skills/agents/commands（自动纠正）。"""
    synced = []

    def remove_any(t: Path):
        if t.is_junction():
            import os
            os.rmdir(t)
        elif t.is_symlink() or t.is_file():
            t.unlink(missing_ok=True)
        elif t.is_dir():
            shutil.rmtree(t, ignore_errors=True)

    for src_name, dst_name in (("skills", "skills"), ("agents", "agents"), ("commands", "commands")):
        src, dst = ROOT / src_name, HOME / ".zcode" / dst_name
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        if src_name == "skills":
            for item in src.iterdir():
                if not item.is_dir():
                    continue
                t = dst / item.name
                remove_any(t)
                shutil.copytree(item, t, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.bak"))
                n += 1
        else:
            for item in sorted(src.glob("*.md")):
                t = dst / item.name
                remove_any(t)
                shutil.copy2(item, t)
                n += 1
        synced.append(f"{dst_name}/ -> {n} 项")
    # .agents 兼容副本（skills）
    dst2 = HOME / ".agents" / "skills"
    dst2.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in (ROOT / "skills").iterdir():
        if not item.is_dir():
            continue
        t = dst2 / item.name
        remove_any(t)
        shutil.copytree(item, t, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.bak"))
        n += 1
    synced.append(f".agents/skills/ -> {n} 项")
    return synced


def run_plugin_only_cleanup() -> list[str]:
    """调用 sync_user_level.py --plugin-only 清除用户级副本（先备份后删除）。"""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_user_level.py"), "--plugin-only"],
        capture_output=True, text=True,
    )
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if proc.returncode != 0:
        lines.append(f"清理失败(rc={proc.returncode})")
    return lines


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="插件升级自检：契约 + 用户级同步 + 组件完整性；--fix 自动纠正")
    parser.add_argument("--fix", action="store_true", help="自动重新同步用户级目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    contract_issues = check_repo_contract()
    sync = user_sync_status()
    all_issues = contract_issues + sync["issues"]
    report = {
        "repo_version": sync["repo_version"],
        "contract_ok": not contract_issues,
        "user_sync_ok": not sync["issues"],
        "healthy": not all_issues,
        "issues": all_issues,
    }
    if args.fix and sync["issues"]:
        if (ROOT / ".plugin-only").exists():
            # 插件独占模式：修复方向是清除用户级副本（含备份），而不是再同步一份。
            report["fixed"] = run_plugin_only_cleanup()
        else:
            report["fixed"] = sync_user_dirs()
        # 修复后复检
        sync2 = user_sync_status()
        report["still_issues"] = sync2["issues"]
        report["healthy"] = not contract_issues and not sync2["issues"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"仓库版本: {report['repo_version']}")
        print(f"契约检查: {'通过' if report['contract_ok'] else '失败'}")
        print(f"用户级同步: {'一致' if report['user_sync_ok'] else '滞后'}")
        for issue in all_issues:
            print(f"  - {issue}")
        if args.fix and report.get("fixed"):
            print("已自动纠正:", "; ".join(report["fixed"]))
        print("结果:", "全部健康 ✓" if report["healthy"] else "存在待处理问题")
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
