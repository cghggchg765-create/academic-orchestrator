"""Skill 发现层：运行时扫描本机已安装 skill，读取其自报 description。

设计约束（协调层架构）：
- 本模块**不持有任何 skill 名称白名单**。它只负责"这台机器上现在有哪些 skill、
  它们自称能做什么"。专业 skill 升级/替换/新增后无需改动本插件。
- 多来源扫描并按宿主优先级去重（`~/.zcode/skills` > `~/.agents/skills` >
  项目 `.zcode/skills` > 项目 `.agents/skills` > 已安装插件包），与 ZCode 的
  "同名先发现者胜"加载语义保持一致。
- 只读 frontmatter 的 name/description/disable-model-invocation，不加载正文，
  避免把专业 skill 的内部流程复制进本插件。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# 宿主实际加载 skill 的候选根目录（按优先级从高到低）。
# 环境变量 MM_SKILL_ROOTS 可用 os.pathsep 追加/覆盖，便于测试与异构部署。
_ENV_ROOTS = "MM_SKILL_ROOTS"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)


def _user_home() -> Path:
    return Path(os.path.expanduser("~"))


def skill_roots(project: str | os.PathLike[str] | None = None, extra: list[str] | None = None) -> list[Path]:
    """返回按优先级排序的 skill 根目录（只保留真实存在的）。

    `MM_SKILL_ROOTS`（os.pathsep 分隔）为**覆盖**语义：设置后只扫描这些目录，
    用于测试固定环境与异构部署——否则测试结果会随本机装了什么 skill 而漂移。
    """
    env = os.environ.get(_ENV_ROOTS, "")
    if env:
        candidates = [Path(p) for p in env.split(os.pathsep) if p.strip()]
        if extra:
            candidates.extend(Path(p) for p in extra if p)
        return [p for p in candidates if p.is_dir()]
    roots: list[Path] = []
    home = _user_home()
    roots.extend([home / ".zcode" / "skills", home / ".agents" / "skills"])
    if project:
        proj = Path(project).resolve()
        roots.extend([proj / ".zcode" / "skills", proj / ".agents" / "skills"])
    roots.extend(_plugin_skill_roots())
    if extra:
        roots.extend(Path(p) for p in extra if p)
    seen: set[str] = set()
    ordered: list[Path] = []
    for root in roots:
        key = str(root).casefold()
        if key in seen:
            continue
        seen.add(key)
        if root.is_dir():
            ordered.append(root)
    return ordered


def _plugin_skill_roots() -> list[Path]:
    """已安装插件包声明的 skill 目录。

    插件的 skill 布局并不统一：有的放 `skills/`，有的把每个 skill 直接放在插件根
    （如 academic-research-skills）。因此以 `plugin.json` 的 `skills` 声明为准确来源，
    回退到 `skills/` 约定；结构不符时静默跳过——发现层不能因目录布局不同而报错。
    """
    home = _user_home()
    caches = [home / ".zcode" / "cli" / "plugins" / "cache"]
    found: list[Path] = []
    for cache in caches:
        if not cache.is_dir():
            continue
        for marketplace in sorted(cache.iterdir()):
            if not marketplace.is_dir():
                continue
            for plugin in sorted(marketplace.iterdir()):
                if not plugin.is_dir():
                    continue
                for pkg in _package_dirs(plugin):
                    found.extend(_declared_skill_dirs(pkg))
    return found


def _package_dirs(plugin: Path) -> list[Path]:
    """插件根下的实际包目录（兼容 `<plugin>/<version>/` 与 `<plugin>/` 两种布局）。"""
    if (plugin / "skills").is_dir() or _read_manifest(plugin) is not None:
        return [plugin]
    return sorted((p for p in plugin.iterdir() if p.is_dir()), reverse=True)


def _read_manifest(pkg: Path) -> dict | None:
    for rel in (Path(".zcode-plugin") / "plugin.json",
                Path(".claude-plugin") / "plugin.json",
                Path(".codex-plugin") / "plugin.json",
                Path("plugin.json")):
        candidate = pkg / rel
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _declared_skill_dirs(pkg: Path) -> list[Path]:
    """按 plugin.json 的 skills 声明解析 skill 目录；无声明时回退 `skills/`。"""
    manifest = _read_manifest(pkg) or {}
    declared = manifest.get("skills")
    dirs: list[Path] = []
    if isinstance(declared, list) and declared:
        for item in declared:
            if isinstance(item, str):
                target = (pkg / item).resolve()
                # 声明可以是单个 skill 目录，也可以是聚合目录（其下每个子目录是一个 skill）
                if (target / "SKILL.md").is_file():
                    dirs.append(target.parent)
                elif target.is_dir():
                    dirs.append(target)
    if not dirs:
        fallback = pkg / "skills"
        if fallback.is_dir():
            dirs.append(fallback)
    # 只保留真正含 skill 的目录，避免污染根目录优先级
    return [d for d in dirs if d.is_dir() and any((c / "SKILL.md").is_file() for c in d.iterdir() if c.is_dir())]


def _plugin_of(root: Path) -> str:
    """从 skill 根目录反推所属插件名（仅用于排除本插件自身，不参与匹配打分）。"""
    parts = list(root.parts)
    lowered = [p.casefold() for p in parts]
    if "cache" in lowered:
        idx = lowered.index("cache")
        # <cache>/<marketplace>/<plugin>/<version>/skills
        if len(parts) - idx >= 4:
            return parts[idx + 2]
    return ""


def parse_frontmatter(text: str) -> dict:
    """极简 frontmatter 解析：只取顶层 `key: value` 与块标量，不引入 YAML 依赖。

    目的不是通用 YAML 解析，而是稳定取出 name/description 这类标量字段；
    遇到复杂结构（嵌套 map/list）整体忽略，避免误解析。
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    body = match.group(1)
    data: dict[str, str] = {}
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[:1] in (" ", "\t", "-") or ":" not in line:
            i += 1
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if raw in (">-", ">", "|", "|-", "|+"):
            block: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and not nxt[:1].isspace():
                    break
                block.append(nxt.strip())
                i += 1
            data[key] = " ".join(part for part in block if part).strip()
            continue
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        data[key] = raw
        i += 1
    return data


def _skill_flags(meta: dict) -> dict:
    disabled = str(meta.get("disable-model-invocation", "")).strip().lower() in {"true", "yes", "1"}
    return {"disabled": disabled}


def discover(project: str | os.PathLike[str] | None = None, extra: list[str] | None = None) -> list[dict]:
    """扫描全部 skill 根目录，返回去重后的 skill 清单（按宿主优先级先发现者胜）。

    每条记录只含协调层需要的元数据：id/name/description/来源/是否可被模型调用。
    不读取 SKILL.md 正文——专业流程留在专业 skill 内部。
    """
    seen: dict[str, dict] = {}
    for root in skill_roots(project, extra):
        try:
            entries = sorted(p for p in root.iterdir() if p.is_dir())
        except OSError:
            continue
        for entry in entries:
            skill_md = entry / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                text = skill_md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            meta = parse_frontmatter(text)
            name = (meta.get("name") or entry.name).strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue  # 高优先级来源已提供同名 skill，后者不生效
            record = {
                "skill_id": name,
                "dir_name": entry.name,
                "description": " ".join((meta.get("description") or "").split()),
                "root": str(root),
                "path": str(skill_md),
                "source": root.name if root.parent.name in {"skills", "cache"} else root.name,
                "scope": _scope_of(root),
                "plugin": _plugin_of(root),
            }
            record.update(_skill_flags(meta))
            seen[key] = record
    return sorted(seen.values(), key=lambda r: r["skill_id"].casefold())


def _scope_of(root: Path) -> str:
    parts = {p.casefold() for p in root.parts}
    if "plugins" in parts and "cache" in parts:
        return "plugin"
    if ".zcode" in parts:
        return "user"
    if ".agents" in parts:
        return "user-agents"
    return "project"
