#!/usr/bin/env python3
"""插件注册链路一致性检查。

检查仓库、插件缓存以及用户级注册元数据是否指向同一份组件树。所有路径
均可通过命令行参数指定，便于在测试环境或不同 ZCode 安装中复用。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

REPO = Path(__file__).resolve().parents[1]
CACHE_ROOT = Path.home() / ".zcode" / "cli" / "plugins" / "cache" / "academic-orchestrator"
PLUGIN_DIR = CACHE_ROOT / "academic-orchestrator"
INSTALLED = CACHE_ROOT / "installed_plugins.json"
KNOWN_MARKETPLACES = CACHE_ROOT / "known_marketplaces.json"

AGENT_COUNT, SKILL_COUNT, COMMAND_COUNT = 24, 34, 22
HOSTILE_NAMES = ("math", "modeling", "mm-", "academic-", "humaniz", "latex", "mathematical-")
PLUGIN_ID = "academic-orchestrator@academic-orchestrator"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
IGNORED_PARTS = {".git", "__pycache__"}
IGNORED_SUFFIXES = {".pyc"}


@dataclass(frozen=True)
class RegistryPaths:
    """Paths participating in the plugin registry check."""

    repo: Path
    cache_root: Path
    plugin_dir: Path
    installed: Path
    known_marketplaces: Path

    @classmethod
    def from_args(cls, repo_root: Path | str | None = None,
                  cache_root: Path | str | None = None) -> "RegistryPaths":
        repo = Path(repo_root) if repo_root is not None else REPO
        cache = Path(cache_root) if cache_root is not None else CACHE_ROOT
        # Explicit test/CI cache roots own their registry metadata. The default
        # ZCode cache keeps metadata beside the cache directory, so preserve that
        # legacy layout only when no explicit root was supplied.
        if cache_root is not None:
            registry_root = cache
        else:
            registry_root = cache.parent.parent if cache.parent.name == "cache" else cache.parent
        return cls(repo, cache, cache / "academic-orchestrator",
                   registry_root / "installed_plugins.json", registry_root / "known_marketplaces.json")


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_junction(path: Path) -> bool:
    """Return whether a path is a junction without requiring Python 3.12 APIs."""
    checker = getattr(path, "is_junction", None)
    if checker is None:
        return False
    try:
        return bool(checker())
    except OSError:
        return True


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts) or path.suffix in IGNORED_SUFFIXES


def file_tree(root: Path) -> dict[str, str]:
    """Return every non-runtime file below *root*, keyed by POSIX relative path."""
    if not root.is_dir():
        return {}
    result: dict[str, str] = {}
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs
                   if not _is_ignored(Path(name)) and not _is_junction(current_path / name)]
        for name in files:
            path = current_path / name
            if _is_ignored(path):
                continue
            try:
                result[path.relative_to(root).as_posix()] = md5(path)
            except OSError:
                continue
    return result


def skill_map(base: Path) -> dict[str, str]:
    """Compatibility wrapper returning the complete tree of each skill."""
    return {name: digest for name, digest in file_tree(base).items() if name.endswith("/SKILL.md")}


def dir_map(base: Path, suffix: str = ".md") -> dict[str, str]:
    """Compatibility wrapper for flat component directories."""
    return {name: digest for name, digest in file_tree(base).items() if name.endswith(suffix)}


def _version_dirs(paths: RegistryPaths) -> list[str]:
    if not paths.plugin_dir.is_dir():
        return []
    return sorted(item.name for item in paths.plugin_dir.iterdir()
                  if item.is_dir() and VERSION_RE.fullmatch(item.name))


def _read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _installed_plugin(paths: RegistryPaths) -> dict[str, object] | None:
    payload = _read_json(paths.installed)
    if not isinstance(payload, dict):
        return None
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return None
    return next((item for item in plugins
                 if isinstance(item, dict) and item.get("id") == PLUGIN_ID), None)


def _same_path(actual: object, expected: Path) -> bool:
    if not isinstance(actual, str):
        return False
    try:
        return Path(actual).resolve() == expected.resolve()
    except OSError:
        return Path(actual) == expected


def check_version_consistency(issues: list[str], paths: RegistryPaths | None = None) -> dict[str, str]:
    """Check package versions while using only paths derived from ``paths``."""
    paths = paths or RegistryPaths.from_args()
    versions: dict[str, str] = {}
    try:
        text = (paths.repo / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        versions["pyproject"] = match.group(1) if match else "?"
    except OSError:
        versions["pyproject"] = "?"
    for manifest in (".zcode-plugin", ".claude-plugin", ".codex-plugin"):
        payload = _read_json(paths.repo / manifest / "plugin.json")
        versions[manifest] = str(payload.get("version", "?")) if isinstance(payload, dict) else "?"
    try:
        text = (paths.repo / "skills" / "mathematical-modeling" / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r'version:\s*"([^"]+)"', text)
        versions["skill"] = match.group(1) if match else "?"
    except OSError:
        versions["skill"] = "?"
    marketplace = _read_json(paths.cache_root / "marketplace.json")
    if marketplace is None:
        marketplace = _read_json(paths.plugin_dir / "marketplace.json")
    plugins = marketplace.get("plugins", []) if isinstance(marketplace, dict) else []
    first = plugins[0] if isinstance(plugins, list) and plugins and isinstance(plugins[0], dict) else {}
    versions["marketplace"] = str(first.get("version", "?"))
    installed = _installed_plugin(paths)
    versions["installed"] = str(installed.get("version", "?")) if installed else "?"
    versions["cache_dirs"] = ",".join(_version_dirs(paths))
    comparable = {value for key, value in versions.items() if key != "cache_dirs" and value != "?"}
    if len(comparable) > 1:
        issues.append(f"版本不一致：{versions}")
    return versions


def check_installed_metadata(issues: list[str], version_dirs: list[str],
                             paths: RegistryPaths | None = None) -> None:
    """Validate installed source/install paths and manifests when those files exist."""
    paths = paths or RegistryPaths.from_args()
    installed = _installed_plugin(paths)
    if installed is None:
        if paths.installed.exists():
            issues.append(f"{paths.installed} 缺少 {PLUGIN_ID} 注册项或不可解析")
        return
    version = str(installed.get("version", "?"))
    expected_install = paths.plugin_dir / version
    if version not in version_dirs:
        issues.append(f"installed version {version} 没有对应缓存版本目录")
    source = installed.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if source_path is not None and not _same_path(source_path, expected_install):
        issues.append(f"installed source.path 不匹配：期望 {expected_install}")
    install_path = installed.get("installPath")
    if install_path is not None and not _same_path(install_path, expected_install):
        issues.append(f"installed installPath 不匹配：期望 {expected_install}")
    for ver in version_dirs:
        version_root = paths.plugin_dir / ver
        manifests = [version_root / "manifest.json", version_root / "marketplace.json"]
        manifests.extend(version_root / name / "plugin.json"
                         for name in (".zcode-plugin", ".claude-plugin", ".codex-plugin"))
        for manifest in manifests:
            if not manifest.is_file():
                continue
            payload = _read_json(manifest)
            if not isinstance(payload, dict):
                issues.append(f"{manifest.relative_to(paths.plugin_dir)} 不可解析")
                continue
            manifest_version = payload.get("version")
            if manifest_version is not None and str(manifest_version) != ver:
                issues.append(f"{manifest.relative_to(paths.plugin_dir)} version 不匹配：{manifest_version}")


def _component_tree(root: Path, component: str) -> dict[str, str]:
    return file_tree(root / component)


def _format_tree_diff(repo_map: dict[str, str], cache_map: dict[str, str]) -> str:
    missing = sorted(set(repo_map) - set(cache_map))
    extras = sorted(set(cache_map) - set(repo_map))
    diff = sorted(name for name in set(repo_map) & set(cache_map) if repo_map[name] != cache_map[name])
    return f"missing={missing[:8]} extras={extras[:8]} diff={diff[:8]}"


def check_cache_content(issues: list[str], version_dirs: list[str],
                        paths: RegistryPaths | None = None) -> None:
    """Compare complete agents/commands/skills trees, including nested files and extras."""
    paths = paths or RegistryPaths.from_args()
    for ver in version_dirs:
        version_root = paths.plugin_dir / ver
        for component, expected in (("agents", AGENT_COUNT), ("commands", COMMAND_COUNT), ("skills", SKILL_COUNT)):
            repo_map = _component_tree(paths.repo, component)
            cache_map = _component_tree(version_root, component)
            if component == "agents" and len([name for name in repo_map if "/" not in name]) != expected:
                issues.append(f"仓库 {component} 数量 {len(repo_map)} != 期望 {expected}")
            if component == "commands" and len([name for name in repo_map if "/" not in name]) != expected:
                issues.append(f"仓库 {component} 数量 {len(repo_map)} != 期望 {expected}")
            if component == "skills" and len([name for name in repo_map if name.endswith("/SKILL.md")]) != expected:
                issues.append(f"仓库 {component} 数量 {len([name for name in repo_map if name.endswith('/SKILL.md')])} != 期望 {expected}")
            if repo_map != cache_map:
                issues.append(f"{ver}/{component}: 与仓库完整树不一致 {_format_tree_diff(repo_map, cache_map)}")


def check_nested_dirs(issues: list[str], version_dirs: list[str], paths: RegistryPaths | None = None) -> None:
    """Detect nested semantic-version directories."""
    paths = paths or RegistryPaths.from_args()
    for ver in version_dirs:
        for item in (paths.plugin_dir / ver).iterdir():
            if item.is_dir() and VERSION_RE.fullmatch(item.name):
                issues.append(f"嵌套版本目录：{ver}/{item.name}（应删除，只保留顶层版本目录）")


def check_agent_frontmatter(issues: list[str], version_dirs: list[str],
                            paths: RegistryPaths | None = None) -> None:
    """Validate agent frontmatter."""
    paths = paths or RegistryPaths.from_args()
    for ver in version_dirs:
        agents_dir = paths.plugin_dir / ver / "agents"
        if not agents_dir.is_dir():
            issues.append(f"{ver}/agents 目录缺失")
            continue
        bad = []
        for path in sorted(agents_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                bad.append(f"{path.name}(不可读)")
                continue
            match = re.match(r"^---\n(.*?)\n---", text, re.S)
            frontmatter = match.group(1) if match else ""
            if not re.search(r"^name:\s*\S", frontmatter, re.M):
                bad.append(f"{path.name}(缺 name)")
            elif not (re.search(r"^mode:\s*\S", frontmatter, re.M)
                      or re.search(r"^model:\s*\S", frontmatter, re.M)
                      or re.search(r"^tools:", frontmatter, re.M)):
                bad.append(f"{path.name}(缺 mode/model/tools 声明)")
        if bad:
            issues.append(f"{ver}/agents frontmatter 非法：{bad}")


def _repo_inventory(repo_root: Path) -> dict[str, set[str]]:
    inventory: dict[str, set[str]] = {}
    for component in ("agents", "skills", "commands"):
        directory = repo_root / component
        if component == "skills":
            names = {item.name for item in directory.iterdir() if item.is_dir()} if directory.is_dir() else set()
        else:
            names = {item.name for item in directory.glob("*.md")} if directory.is_dir() else set()
        inventory[component] = names
    return inventory


def _residue_names(root: Path, inventory: dict[str, set[str]]) -> list[str]:
    result: list[str] = []
    for component, names in inventory.items():
        directory = root / component
        if not directory.is_dir():
            continue
        for item in directory.iterdir():
            if item.name in names:
                result.append(f"{component}/{item.name}")
    return result


def user_level_residue(user_roots: Iterable[Path] | None = None,
                       repo_root: Path | None = None) -> list[str]:
    roots = tuple(user_roots or (Path.home() / ".zcode", Path.home() / ".agents"))
    inventory = _repo_inventory(repo_root or REPO)
    return [f"{root}: {name}" for root in roots for name in _residue_names(root, inventory)]


def check_user_level_residue(issues: list[str], user_roots: Iterable[Path] | None = None,
                             repo_root: Path | None = None) -> list[str]:
    """Report exact repository components left in both supported user roots."""
    residue = user_level_residue(user_roots, repo_root)
    if residue:
        issues.append(f"用户级目录存在本仓库组件残留（插件独占模式下应无）：{residue}")
    return residue


def check_clean_package(issues: list[str], repo: Path) -> None:
    """Fail closed when the dirty worktree cannot reproduce its components."""
    try:
        result = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        issues.append("clean-package 无法读取 git tracked inventory")
        return
    def is_gitignored(rel: str) -> bool:
        try:
            r = subprocess.run(["git", "check-ignore", "-q", "--", rel],
                               cwd=repo, capture_output=True, text=True)
            return r.returncode == 0
        except (OSError, subprocess.CalledProcessError):
            return False

    def is_tracked_in_head(rel: str) -> bool:
        # Resolve HEAD:rel directly so CJK filenames are not compared across
        # different bytes/encoding-normalization surfaces.
        try:
            r = subprocess.run(["git", "cat-file", "-e", f"HEAD:{rel}"],
                               cwd=repo, capture_output=True, text=True)
            return r.returncode == 0
        except (OSError, subprocess.CalledProcessError):
            return False

    required = set()
    for component in ("agents", "commands", "skills"):
        base = repo / component
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            rel = path.relative_to(repo).as_posix()
            if path.is_file() and not _is_ignored(path) and not is_gitignored(rel):
                required.add(rel)
    for base in ("hooks", "scripts", "mcp"):
        directory = repo / base
        if directory.is_dir():
            for path in directory.rglob("*"):
                rel = path.relative_to(repo).as_posix()
                if path.is_file() and not _is_ignored(path) and not is_gitignored(rel):
                    required.add(rel)
    required.update({".plugin-only", ".mcp.json.template"})
    missing = sorted(rel for rel in required if not is_tracked_in_head(rel))
    if missing:
        issues.append(f"clean-package 缺少 git tracked 组件/资产 {len(missing)} 项: {missing[:12]}")


def check_mcp_keys(issues: list[str], repo: Path | None = None, runtime: bool = False) -> None:
    """Check MCP declarations without printing secret values.

    A clean source package is valid with only .mcp.json.template.  The
    runtime flag is required when a local session wants to assert credentials.
    """
    root = repo or REPO
    mcp = root / ".mcp.json"
    template = root / ".mcp.json.template"
    if not mcp.is_file():
        if not template.is_file():
            issues.append("MCP 配置模板缺失（.mcp.json.template）")
        elif runtime:
            issues.append("运行时 .mcp.json 缺失（请从模板配置外部环境变量；不提交真实密钥）")
        return
    payload = _read_json(mcp)
    servers = payload.get("mcpServers", {}) if isinstance(payload, dict) else {}
    if not isinstance(servers, dict):
        issues.append(".mcp.json 不可解析")
        return
    for name in ("paper-mcp", "context7", "github", "tavily-mcp", "tokenhub-tools"):
        if name not in servers:
            issues.append(f".mcp.json 缺 {name} 声明")
            continue
        joined = json.dumps(servers[name], ensure_ascii=False)
        if "${" in joined:
            issues.append(f".mcp.json {name} 为占位符配置（真实密钥未写入）")
            continue
        if name in ("github", "tavily-mcp", "tokenhub-tools"):
            keys = ("GITHUB_PERSONAL_ACCESS_TOKEN", "tavilyApiKey", "TOKENHUB_API_KEY")
            if not any(key in joined for key in keys):
                issues.append(f".mcp.json {name} 缺少密钥")


def main() -> int:
    parser = argparse.ArgumentParser(description="插件注册链路一致性检查")
    parser.add_argument("--repo-root", "--repo", dest="repo_root", default=str(REPO), help="仓库根目录")
    parser.add_argument("--cache-root", default=None, help="插件缓存根目录（显式传入时 registry 元数据位于该目录；缺省使用 ZCode 标准布局）")
    parser.add_argument("--runtime", action="store_true", help="额外检查本机 .mcp.json/运行时密钥是否就绪")
    parser.add_argument("--strict-git", action="store_true", help="检查 clean checkout 是否能复现当前组件树")
    parser.add_argument("--quiet", action="store_true", help="仅输出结论")
    args = parser.parse_args()
    paths = RegistryPaths.from_args(args.repo_root, args.cache_root)
    issues: list[str] = []
    versions = check_version_consistency(issues, paths)
    version_dirs = _version_dirs(paths)
    if not paths.plugin_dir.is_dir():
        issues.append(f"插件缓存目录缺失：{paths.plugin_dir}")
    elif not version_dirs:
        issues.append("插件缓存无版本目录")
    else:
        check_installed_metadata(issues, version_dirs, paths)
        check_cache_content(issues, version_dirs, paths)
        check_nested_dirs(issues, version_dirs, paths)
        check_agent_frontmatter(issues, version_dirs, paths)
    marketplaces = _read_json(paths.known_marketplaces)
    if isinstance(marketplaces, dict):
        ids = {item.get("id") for item in marketplaces.get("marketplaces", []) if isinstance(item, dict)}
        if "math-modeling" not in ids:
            issues.append("known_marketplaces.json 未收录 math-modeling")
    else:
        issues.append("known_marketplaces.json 缺失或不可解析")
    residue = check_user_level_residue(issues)
    if args.strict_git:
        check_clean_package(issues, paths.repo)
    check_mcp_keys(issues, paths.repo, runtime=args.runtime)
    if not args.quiet:
        print("版本：", json.dumps(versions, ensure_ascii=False))
        print("缓存版本目录：", version_dirs)
        print("用户级残留：", "无" if not residue else residue)
    if issues:
        print(f"FAIL：{len(issues)} 项问题")
        for issue in issues:
            print("  -", issue)
        return 1
    print("PASS：插件注册链路一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
