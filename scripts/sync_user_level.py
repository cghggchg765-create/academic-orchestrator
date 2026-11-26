#!/usr/bin/env python3
"""同步/清理仓库组件与 ZCode 用户级目录。"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[1]
USER = Path.home() / ".zcode"
# Both compatibility roots can shadow plugin components; inspect both by default.
USER_ROOTS: tuple[Path, ...] = (USER, Path.home() / ".agents")
IGNORED_PARTS = {".git", "__pycache__"}
IGNORED_SUFFIXES = {".pyc"}


def _is_junction(path: Path) -> bool:
    """Return whether a path is a junction on runtimes that expose the API."""
    checker = getattr(path, "is_junction", None)
    if checker is None:
        return False
    try:
        return bool(checker())
    except OSError:
        # A broken junction must still be treated as a directory link so that
        # cleanup removes the link itself rather than traversing its target.
        return True


def _name_set(values: Iterable[str]) -> set[str]:
    """Normalize component names for Windows' case-insensitive filesystem."""
    return {str(value).casefold() for value in values}


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts) or path.suffix in IGNORED_SUFFIXES


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def tree(root: Path, rel: str) -> dict[str, tuple[int, str]]:
    """Return the complete non-runtime file tree as ``relative -> (size, hash)``."""
    base = root / rel
    if not base.is_dir():
        return {}
    result: dict[str, tuple[int, str]] = {}
    for current, dirs, files in os.walk(base, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs
                   if not _is_ignored(Path(name)) and not _is_junction(current_path / name)]
        for name in files:
            path = current_path / name
            if _is_ignored(path):
                continue
            try:
                result[path.relative_to(base).as_posix()] = (path.stat().st_size, sha256_of(path))
            except OSError:
                continue
    return result


def components(repo: Path | None = None) -> tuple[list[str], list[str], list[str]]:
    """Return the exact repository inventory for skills, agents, and commands."""
    root = repo or REPO
    skills_dir, agents_dir, commands_dir = root / "skills", root / "agents", root / "commands"
    skills = sorted(path.name for path in skills_dir.iterdir() if path.is_dir()) if skills_dir.is_dir() else []
    agents = sorted(path.name for path in agents_dir.glob("*.md")) if agents_dir.is_dir() else []
    commands = sorted(path.name for path in commands_dir.glob("*.md")) if commands_dir.is_dir() else []
    return skills, agents, commands


def _roots(user_roots: Iterable[Path] | None = None) -> tuple[Path, ...]:
    return tuple(user_roots or USER_ROOTS)


def _tree_differences(repo_root: Path, user_root: Path) -> list[str]:
    """Compare a package tree and report missing, extra, size, and content differences."""
    repo_map = tree(repo_root.parent, repo_root.name)
    user_map = tree(user_root.parent, user_root.name)
    issues: list[str] = []
    # Windows resolves paths case-insensitively; compare canonicalized keys so
    # a casing-only rename does not create a false missing/extra pair.
    repo_keys = {name.casefold(): name for name in repo_map}
    user_keys = {name.casefold(): name for name in user_map}
    missing = sorted(repo_keys[key] for key in repo_keys.keys() - user_keys.keys())
    extras = sorted(user_keys[key] for key in user_keys.keys() - repo_keys.keys())
    common = repo_keys.keys() & user_keys.keys()
    size_diffs = sorted(repo_keys[key] for key in common
                        if repo_map[repo_keys[key]][0] != user_map[user_keys[key]][0])
    content_diffs = sorted(repo_keys[key] for key in common
                           if repo_map[repo_keys[key]][0] == user_map[user_keys[key]][0]
                           and repo_map[repo_keys[key]][1] != user_map[user_keys[key]][1])
    if missing:
        issues.append(f"仅仓库={missing[:8]}")
    if extras:
        issues.append(f"仅用户级={extras[:8]}")
    if size_diffs:
        issues.append(f"大小不同={size_diffs[:8]}")
    if content_diffs:
        issues.append(f"内容不同={content_diffs[:8]}")
    return issues


def _file_differences(repo_file: Path, user_file: Path) -> list[str]:
    if not user_file.exists():
        return ["仅仓库=[%s]" % repo_file.name]
    repo_size, repo_hash = repo_file.stat().st_size, sha256_of(repo_file)
    user_size, user_hash = user_file.stat().st_size, sha256_of(user_file)
    differences = []
    if repo_size != user_size:
        differences.append(f"大小不同=[{repo_file.name}]")
    elif repo_hash != user_hash:
        differences.append(f"内容不同=[{repo_file.name}]")
    return differences


def diff_report(user_roots: Iterable[Path] | None = None) -> list[str]:
    """Compare complete repository component trees across every supported user root."""
    roots = _roots(user_roots)
    skills, agents, commands = components()
    issues: list[str] = []
    for user_root in roots:
        for skill in skills:
            differences = _tree_differences(REPO / "skills" / skill, user_root / "skills" / skill)
            if differences:
                issues.append(f"[{user_root.name}:skill:{skill}] " + " ".join(differences))
        for agent in agents:
            differences = _file_differences(REPO / "agents" / agent, user_root / "agents" / agent)
            if differences:
                issues.append(f"[{user_root.name}:agent:{agent}] " + " ".join(differences))
        for command in commands:
            differences = _file_differences(REPO / "commands" / command, user_root / "commands" / command)
            if differences:
                issues.append(f"[{user_root.name}:command:{command}] " + " ".join(differences))
    return issues


def _ensure_component_dirs(root: Path) -> None:
    for component in ("skills", "agents", "commands"):
        (root / component).mkdir(parents=True, exist_ok=True)


def _backup_path(root: Path, name: str) -> Path:
    return root / f".{name}-{time.strftime('%Y%m%d-%H%M%S')}"


def _copy_skill(repo_skill: Path, user_skill: Path, backup: Path) -> None:
    if user_skill.exists():
        shutil.copytree(user_skill, backup, dirs_exist_ok=True)
        shutil.rmtree(user_skill)
    user_skill.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_skill, user_skill)


def _copy_file(repo_file: Path, user_file: Path, backup: Path) -> None:
    if user_file.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(user_file, backup)
    user_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_file, user_file)


def sync(dry_run: bool, check_only: bool = False) -> int:
    """Align all supported user-level roots with the repository."""
    if (REPO / ".plugin-only").exists():
        print("插件独占模式已启用，请改用 --plugin-only")
        return 1
    roots = _roots()
    issues = diff_report(roots)
    if not issues:
        print("用户级副本与仓库（插件同源）已一致")
        return 0
    print(f"发现 {len(issues)} 处差异（check_only={check_only}）：")
    for issue in issues[:20]:
        print(f"  {issue}")
    if check_only or dry_run:
        return 1
    skills, agents, commands = components()
    for root in roots:
        _ensure_component_dirs(root)
        backup = _backup_path(root, "mm-sync-backup")
        for skill in skills:
            _copy_skill(REPO / "skills" / skill, root / "skills" / skill, backup / "skills" / skill)
        for agent in agents:
            _copy_file(REPO / "agents" / agent, root / "agents" / agent, backup / "agents" / agent)
        for command in commands:
            _copy_file(REPO / "commands" / command, root / "commands" / command, backup / "commands" / command)
        print(f"已同步 {root}: skills={len(skills)} agents={len(agents)} commands={len(commands)}")
    remain = diff_report(roots)
    print("复检:", "全部一致" if not remain else f"仍不一致 {len(remain)} 处")
    return 0 if not remain else 1


def _inventory_paths(root: Path, skills: list[str], agents: list[str], commands: list[str]) -> list[tuple[str, Path]]:
    """Find component paths case-insensitively without following links."""
    result: list[tuple[str, Path]] = []
    for kind, names, directory in (
        ("skills", skills, root / "skills"),
        ("agents", agents, root / "agents"),
        ("commands", commands, root / "commands"),
    ):
        if not directory.is_dir():
            continue
        by_name = {p.name.casefold(): p for p in directory.iterdir()}
        for name in names:
            path = by_name.get(name.casefold())
            if path is not None:
                result.append((kind, path))
    return result


def _remove_path(path: Path) -> None:
    """Remove a file, directory, symlink, or junction without traversing links."""
    if _is_junction(path) or path.is_symlink() or path.is_file():
        try:
            path.unlink()
        except (PermissionError, OSError):
            # Windows junctions can require rmdir even when unlink is rejected.
            os.rmdir(path)
        return
    if path.is_dir():
        shutil.rmtree(path)


def plugin_only(dry_run: bool) -> int:
    """Remove repository components from both ~/.zcode and ~/.agents."""
    roots = _roots()
    skills, agents, commands = components()
    targets = [(root, kind, path) for root in roots
               for kind, path in _inventory_paths(root, skills, agents, commands)]
    if not targets:
        for root in roots:
            _ensure_component_dirs(root)
        print("插件独占模式：用户级目录已无本仓库组件副本")
        return 0
    print(f"发现用户级本仓库组件副本 {len(targets)} 个（dry_run={dry_run}）")
    if dry_run:
        return 1
    for root in roots:
        _ensure_component_dirs(root)
    backups = {root: _backup_path(root, "mm-plugin-only-backup") for root in roots}
    for root, kind, path in targets:
        backup = backups[root] / kind / path.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir() and not _is_junction(path) and not path.is_symlink():
            shutil.copytree(path, backup, dirs_exist_ok=True)
        else:
            if path.is_file() and not path.is_symlink():
                shutil.copy2(path, backup)
        _remove_path(path)
    print("已清理用户级副本（两套用户级根目录）")
    return 0


def main() -> int:
    global REPO, USER_ROOTS
    parser = argparse.ArgumentParser(description="同步/清理数学建模组件与 ZCode 用户级目录")
    parser.add_argument("--repo", "--repo-root", dest="repo", default=str(REPO))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plugin-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    REPO = Path(args.repo)
    USER_ROOTS = (Path.home() / ".zcode", Path.home() / ".agents")
    if args.plugin_only:
        return plugin_only(args.dry_run)
    return sync(args.dry_run, check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
