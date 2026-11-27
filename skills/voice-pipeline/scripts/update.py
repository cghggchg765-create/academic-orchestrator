#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""voice-pipeline 一键更新：对 registry 里所有 git-backed 子技能执行 git pull，再跑 doctor。

用法：
    python update.py              # 更新并自检
    python update.py --check-only # 只自检，不拉取
    python update.py --dry-run    # 只显示将更新哪些仓库
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REGISTRY = SKILL_DIR / "registry.json"

# 可移植路径解析（与 doctor.py 共用）
sys.path.insert(0, str(SKILL_DIR / "scripts"))
try:
    from _roots import resolve_entry  # noqa: E402
except ImportError:
    def resolve_entry(raw):
        p = Path(str(raw or ""))
        return p if p.exists() else None
DOCTOR = SKILL_DIR / "scripts" / "doctor.py"


def run(args: list[str], cwd: Path | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=str(cwd) if cwd else None, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def repo_root(path: Path) -> Path | None:
    out = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], timeout=30)
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip())
    cur = path.resolve()
    while cur.parent != cur:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    return None


def head(repo: Path) -> str:
    out = run(["git", "-C", str(repo), "log", "-1", "--format=%h %ad %s", "--date=short"], timeout=30)
    return out.stdout.strip() if out.returncode == 0 else "?"


def head_hash(repo: Path) -> str:
    out = run(["git", "-C", str(repo), "rev-parse", "HEAD"], timeout=30)
    return out.stdout.strip() if out.returncode == 0 else ""


def diff_files(repo: Path, before: str, after: str) -> list[str]:
    if not before or not after or before == after:
        return []
    out = run(["git", "-C", str(repo), "diff", "--name-only", f"{before}..{after}"], timeout=60)
    return [line for line in out.stdout.splitlines() if line.strip()]


def is_dirty(repo: Path) -> bool:
    out = run(["git", "-C", str(repo), "status", "--porcelain"], timeout=30)
    return bool(out.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    repos: dict[Path, list[str]] = {}
    non_git: list[str] = []
    for item in registry.get("skills", []):
        # 可移植解析：$SKILLS_ROOT/<name> 运行时在多根下解析
        path = resolve_entry(item.get("path")) or resolve_entry(f"$SKILLS_ROOT/{item.get('name','')}")
        if path is None:
            if item.get("optional"):
                continue
            non_git.append(item.get("name", "") + "(未安装)")
            continue
        root = repo_root(path)
        if root:
            repos.setdefault(root, []).append(item.get("name", ""))
        else:
            non_git.append(item.get("name", ""))

    for name in non_git:
        print(f"[SKIP] {name}: 非 git 目录，手动更新；总控下次会重读其 SKILL.md")

    failures: list[str] = []
    changed = 0
    for repo, names in sorted(repos.items()):
        print(f"\n== {repo.name} ==  ({', '.join(names)})")
        print(f"   before: {head(repo)}")
        if args.check_only or args.dry_run:
            print("   skip pull")
            continue
        if is_dirty(repo):
            print("   WARN: 工作区有未提交改动，跳过 pull（先处理 git status）")
            failures.append(repo.name + " (dirty)")
            continue
        before = head_hash(repo)
        out = run(
            ["git", "-C", str(repo), "-c", "http.proxy=", "-c", "https.proxy=", "pull", "--ff-only"]
        )
        if out.returncode != 0:
            print(f"   FAIL: {out.stderr.strip()[:300]}")
            failures.append(repo.name)
            continue
        after = head_hash(repo)
        print(f"   after : {head(repo)}")
        if before and after and before != after:
            changed += 1
            files = diff_files(repo, before, after)
            if files:
                print("   changed files:")
                for file in files[:12]:
                    print(f"     - {file}")
                if len(files) > 12:
                    print(f"     ... 另有 {len(files) - 12} 个文件")
                if any(Path(f).name == "SKILL.md" for f in files):
                    print("   NOTE: SKILL.md 有变更——总控下次会读新流程；若能力边界/入口变化，请复核 registry。")
        else:
            print("   already up to date")

    print(f"\nrepos pulled: {changed}/{len(repos)}; non-git: {len(non_git)}")
    if DOCTOR.exists():
        print("\n== doctor ==")
        out = run([sys.executable, str(DOCTOR)], timeout=300)
        print(out.stdout)
        if out.returncode != 0:
            print(out.stderr)
            return out.returncode
    if failures:
        print("pull failures: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
