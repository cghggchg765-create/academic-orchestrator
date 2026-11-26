#!/usr/bin/env python3
"""Project virtual-environment guard for build/run entry points.

This command is intentionally read-only.  It never creates an environment or
installs packages implicitly: a build must stop until the project venv is
created, activated, and selected as the current interpreter.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def candidate_dirs(project: Path) -> list[Path]:
    return [project / ".venv", project / "venv"]


def python_candidates(env_dir: Path) -> list[Path]:
    if os.name == "nt":
        return [env_dir / "Scripts" / "python.exe", env_dir / "Scripts" / "python"]
    return [env_dir / "bin" / "python", env_dir / "bin" / "python3"]


def active_interpreter() -> bool:
    # sys.prefix differs from sys.base_prefix for venv/virtualenv.  VIRTUAL_ENV
    # covers hosts that wrap an interpreter without exposing the usual prefix.
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix) or bool(os.environ.get("VIRTUAL_ENV"))


def check(project: Path) -> dict[str, object]:
    project = project.resolve()
    env_dir = next((path for path in candidate_dirs(project) if path.is_dir()), None)
    expected = next((path for path in python_candidates(env_dir) if path.is_file()), None) if env_dir else None
    current = Path(sys.executable).resolve()
    inside = bool(expected and (current == expected.resolve() or expected.resolve() in current.parents))
    active = active_interpreter()
    requirements = project / "Code" / "requirements.txt"
    return {
        "project": str(project),
        "venv_dir": str(env_dir) if env_dir else None,
        "expected_python": str(expected) if expected else None,
        "current_python": str(current),
        "venv_exists": env_dir is not None,
        "venv_active": active,
        "interpreter_matches_project_venv": inside,
        "requirements_file": str(requirements) if requirements.is_file() else None,
        "ok": bool(env_dir and expected and active and inside),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查项目构建/运行是否使用项目虚拟环境")
    parser.add_argument("--project", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    result = check(args.project)
    if result["ok"]:
        print("VENV_READY")
        print(f"python={result['current_python']}")
        return 0
    print("VENV_BLOCKED")
    print(f"project={result['project']}")
    print(f"venv_dir={result['venv_dir'] or '(missing)'}")
    print(f"current_python={result['current_python']}")
    print(f"venv_active={result['venv_active']}")
    print(f"interpreter_matches_project_venv={result['interpreter_matches_project_venv']}")
    print("创建并激活后重试：")
    if os.name == "nt":
        print("  python -m venv .venv")
        print("  .venv\\Scripts\\activate")
    else:
        print("  python3 -m venv .venv")
        print("  source .venv/bin/activate")
    if result["requirements_file"]:
        print(f"  python -m pip install -r {Path(result['requirements_file']).relative_to(Path(result['project']))}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
