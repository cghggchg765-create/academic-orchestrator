from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


registry = load_script("plugin_registry_check_phase1", "scripts/plugin_registry_check.py")
sync = load_script("sync_user_level_phase1", "scripts/sync_user_level.py")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_tree(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def seed_components(root: Path, *, nested: bool = False) -> None:
    write_tree(root, "agents/a.md", "agent")
    write_tree(root, "commands/c.md", "command")
    write_tree(root, "skills/s/SKILL.md", "skill")
    if nested:
        write_tree(root, "skills/s/examples/nested.txt", "nested")


def test_registry_paths_are_derived_from_arguments(tmp_path: Path):
    repo = tmp_path / "repo"
    cache_root = tmp_path / "cache"
    plugin_dir = cache_root / "math-modeling-agent-system"
    version_dir = plugin_dir / "1.2.3"
    seed_components(repo)
    seed_components(version_dir)
    args = registry.RegistryPaths.from_args(repo, cache_root)

    assert args.repo == repo
    assert args.cache_root == cache_root
    assert args.plugin_dir == plugin_dir
    assert args.installed == cache_root / "installed_plugins.json"
    assert args.known_marketplaces == cache_root / "known_marketplaces.json"


def test_registry_validates_complete_component_trees_and_extras(tmp_path: Path):
    repo = tmp_path / "repo"
    cache_root = tmp_path / "cache"
    version_dir = cache_root / "math-modeling-agent-system" / "1.2.3"
    seed_components(repo, nested=True)
    seed_components(version_dir, nested=True)
    write_tree(version_dir, "skills/s/extra.txt", "extra")
    issues: list[str] = []

    registry.check_cache_content(issues, ["1.2.3"], registry.RegistryPaths.from_args(repo, cache_root))

    assert any("extra" in issue for issue in issues)


def test_registry_validates_installed_source_install_path_and_cache_manifest(tmp_path: Path):
    repo = tmp_path / "repo"
    cache_root = tmp_path / "cache"
    version_dir = cache_root / "math-modeling-agent-system" / "1.2.3"
    seed_components(repo)
    seed_components(version_dir)
    write_json(cache_root / "installed_plugins.json", {
        "plugins": [{
            "id": "math-modeling-agent-system@math-modeling",
            "version": "1.2.3",
            "source": {"path": str(tmp_path / "wrong-source")},
            "installPath": str(tmp_path / "wrong-install"),
        }],
    })
    write_json(version_dir / "manifest.json", {"version": "9.9.9"})
    paths = registry.RegistryPaths.from_args(repo, cache_root)
    issues: list[str] = []

    registry.check_installed_metadata(issues, ["1.2.3"], paths)

    assert any("source.path" in issue for issue in issues)
    assert any("installPath" in issue for issue in issues)
    assert any("manifest" in issue for issue in issues)


def test_registry_reports_real_user_residue_instead_of_always_no_residue(tmp_path: Path):
    repo_root = tmp_path / "repo"
    user_root = tmp_path / "zcode"
    write_tree(repo_root, "skills/demo/SKILL.md", "repo")
    write_tree(user_root, "skills/demo/SKILL.md", "old")
    issues: list[str] = []

    registry.check_user_level_residue(issues, user_roots=(user_root,), repo_root=repo_root)

    assert any("skills" in issue for issue in issues)
    assert registry.user_level_residue(user_roots=(user_root,), repo_root=repo_root)


def test_sync_tree_hashes_common_files_and_reports_size_difference(tmp_path: Path):
    repo = tmp_path / "repo"
    user = tmp_path / "user"
    write_tree(repo, "skills/demo/SKILL.md", "new content")
    write_tree(user, "skills/demo/SKILL.md", "old")
    write_tree(repo, "skills/demo/same-size.txt", "abcd")
    write_tree(user, "skills/demo/same-size.txt", "wxyz")
    sync.REPO = repo
    sync.USER_ROOTS = (user, tmp_path / "agents-user")

    issues = sync.diff_report()

    assert any("大小不同" in issue for issue in issues)
    assert any("内容不同" in issue for issue in issues)


def test_sync_plugin_only_covers_agents_root_and_creates_missing_target_dirs(tmp_path: Path):
    repo = tmp_path / "repo"
    zcode = tmp_path / "zcode"
    agents_home = tmp_path / "agents-home"
    write_tree(repo, "agents/a.md", "agent")
    write_tree(zcode, "skills/unused.txt", "keep")
    write_tree(agents_home, "agents/a.md", "old")
    sync.REPO = repo
    sync.USER_ROOTS = (zcode, agents_home)

    assert sync.plugin_only(dry_run=False) == 0
    assert not (agents_home / "agents/a.md").exists()
    assert (zcode / "commands").is_dir()
    assert (agents_home / "skills").is_dir()
