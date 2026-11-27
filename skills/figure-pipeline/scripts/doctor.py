#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figure-pipeline 自检：registry 契约、入口、Junction、支撑目录、依赖与环境。

用法：
    python doctor.py            # 常规检查
    python doctor.py --deep     # 额外探测 Graphviz / drawio / image2ppt / Nature 后端
    python doctor.py --json     # 机器可读
    python doctor.py --strict   # WARN 也返回非零
退出码：0 = 无 FAIL；1 = 有 FAIL（--strict 时含 WARN）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REGISTRY = SKILL_DIR / "registry.json"

# 可移植路径解析：不再硬编码本机绝对路径，改为在多根下运行时解析。
sys.path.insert(0, str(SKILL_DIR / "scripts"))
try:
    from _roots import resolve_entry, skill_roots as _skill_roots  # noqa: E402
except ImportError:  # 单独拷贝脚本时降级
    def resolve_entry(raw):
        p = Path(os.path.expanduser(os.path.expandvars(str(raw or ""))))
        return p if p.exists() else None

    def _skill_roots():
        return [Path.home() / ".zcode" / "skills", Path.home() / ".agents" / "skills"]

ZCODE_ROOT = Path.home() / ".zcode" / "skills"


def _optional_mirror_roots() -> list[Path]:
    """可选镜像根：环境变量 POINTING_MIRROR_ROOTS（分号分隔）或默认的 ~/.agents/skills。

    这些根**不是**运行必需——技能装在一处即可工作。这里只用于"若存在则抽查一致性"，
    绝不因为镜像缺失而判失败。
    """
    env = os.environ.get("PIPELINE_MIRROR_ROOTS", "")
    if env:
        return [Path(p) for p in env.replace(";", os.pathsep).replace(",", os.pathsep).split(os.pathsep)
                if p.strip()]
    cand = Path.home() / ".agents" / "skills"
    return [cand] if cand.is_dir() else []

STAGE_ORDER = ["S0", "S1", "S2", "S2b", "S3", "S4"]
ROLES = {"decide", "produce", "audit", "convert", "structure", "rebuild"}
SKILL_FIELDS = ["slot", "stage", "name", "path", "entry", "repo", "stars", "role", "best_at", "inputs", "outputs", "not_for", "done_when", "requires_files", "depends", "fallback"]
DEP_MAP = {
    "scipilot-figure-skill": ["matplotlib", "seaborn", "plotly", "pandas", "scipy", "PIL"],
    "scientific-figure-making": ["matplotlib", "numpy", "pandas"],
    "nature-figure": ["fitz"],
    "nature-image2ppt": ["pypdfium2", "PIL", "yaml", "openai"],
    "drawio-skill": [],
    "visio-image-rebuilder": [],
}


def add(rows: list[dict], level: str, item: str, detail: str) -> None:
    rows.append({"level": level, "item": item, "detail": detail})


def run(args: list[str], cwd: Path | None = None, timeout: int = 120, env_path: Path | None = None) -> subprocess.CompletedProcess:
    env = None
    if env_path:
        env = os.environ.copy()
        env["PATH"] = str(env_path) + ";" + env.get("PATH", "")
    return subprocess.run(
        args, cwd=str(cwd) if cwd else None, capture_output=True, env=env,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def git_head(path: Path) -> str:
    out = run(["git", "-C", str(path), "log", "-1", "--format=%h %ad", "--date=short"], timeout=30)
    return out.stdout.strip() if out.returncode == 0 else "not-a-git-repo"


def repo_root(path: Path) -> Path:
    out = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], timeout=30)
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip())
    return path


def read_frontmatter_name(skill_md: Path) -> str:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception:
        return ""
    match = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def has_visio_registration() -> bool:
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Visio.Application")
        return True
    except OSError:
        return False


def summarize_deep(raw: str) -> str:
    try:
        data = json.loads(raw)
    except Exception:
        return raw.strip()[:200]
    keep: dict[str, object] = {}
    if "ok" in data:
        keep["ok"] = data["ok"]
    for key in ("python", "drawio", "graphviz", "ocr", "renderer", "powerpoint", "local_cli"):
        value = data.get(key)
        if isinstance(value, dict):
            keep[key] = value.get("status") or value.get("ok") or "present"
        elif value is not None:
            keep[key] = value if isinstance(value, (str, int, bool)) else "present"
    return json.dumps(keep, ensure_ascii=False) if keep else "ok"


def check_registry_schema(registry: dict, rows: list[dict]) -> bool:
    ok = True
    if not isinstance(registry.get("stage_order"), list):
        add(rows, "FAIL", "schema", "缺少 stage_order")
        ok = False
    elif registry["stage_order"] != STAGE_ORDER:
        add(rows, "FAIL", "schema", f"stage_order={registry['stage_order']}，应为 {STAGE_ORDER}")
        ok = False
    skills = registry.get("skills", [])
    if not isinstance(skills, list) or not skills:
        add(rows, "FAIL", "schema", "skills 为空")
        return False
    names: set[str] = set()
    slots: set[str] = set()
    for item in skills:
        for field in SKILL_FIELDS:
            if field not in item:
                add(rows, "FAIL", "schema", f"{item.get('name', '?')} 缺少字段 {field}")
                ok = False
        name = item.get("name", "")
        if name in names:
            add(rows, "FAIL", "schema", f"技能名重复: {name}")
            ok = False
        names.add(name)
        if item.get("stage") not in STAGE_ORDER:
            add(rows, "FAIL", "schema", f"{name} stage={item.get('stage')} 不在允许值")
            ok = False
        if item.get("role") not in ROLES:
            add(rows, "FAIL", "schema", f"{name} role={item.get('role')!r} 不在 {sorted(ROLES)}")
            ok = False
        if not item.get("best_at"):
            add(rows, "FAIL", "schema", f"{name} best_at 为空")
            ok = False
        if item.get("slot") != item.get("stage"):
            add(rows, "WARN", "schema", f"{name} slot={item.get('slot')} 与 stage={item.get('stage')} 不一致")
        if item.get("slot") in slots:
            add(rows, "FAIL", "schema", f"stage 重复: {item.get('slot')}")
            ok = False
        slots.add(item.get("slot"))
    if ok:
        add(rows, "PASS", "schema", f"{len(skills)} 个技能，stage 唯一，字段齐全")
    return ok


def check_skill(item: dict, rows: list[dict]) -> None:
    name = item["name"]
    # 可移植解析：registry 里写 $SKILLS_ROOT/<name> 或相对路径，运行时在多根下解析
    path = resolve_entry(item.get("path")) or resolve_entry(f"$SKILLS_ROOT/{name}")
    entry = resolve_entry(item.get("entry")) if item.get("entry") else None
    # entry 常写成 $SKILLS_ROOT/<name>/SKILL.md：其父目录可能因仓库布局（<repo>/skills/<name>）
    # 与 path 解析结果不同，失败时回退到 path + SKILL.md。
    if (entry is None or not entry.exists()) and path is not None:
        entry = path / "SKILL.md"
    if path is None:
        add(rows, "FAIL", name,
            f"未找到技能目录（查找根: {', '.join(str(r) for r in _skill_roots()[:3])}…）")
        return
    if entry is None or not entry.exists():
        add(rows, "FAIL", name, f"entry 不存在: {item.get('entry')}")
        return
    actual = read_frontmatter_name(entry)
    if actual != name:
        add(rows, "FAIL", name, f"entry name={actual!r} 与注册名不一致")
    else:
        add(rows, "PASS", name, f"入口与 name 一致；{git_head(repo_root(path))}")

    # requires_files 相对**技能目录**（SKILL.md 所在目录），不是仓库根——
    # 有些仓库把技能放在 <repo>/skills/<name>/，用 path 会全部误报缺失。
    skill_dir = entry.parent if entry is not None else path
    missing = [rel for rel in item.get("requires_files", []) if not (skill_dir / rel).exists()]
    if missing:
        add(rows, "FAIL", name, "requires_files 缺失: " + ", ".join(missing))
    else:
        add(rows, "PASS", f"{name}:files", f"{len(item.get('requires_files', []))} 个关键文件齐全")

    # 技能本体已可解析（path/entry 都在）即为就位。
    # 可选的镜像根（如另一个 agent 平台）只在**确实存在**时才做一致性抽查，
    # 不再把"镜像缺失"判 FAIL —— 单一来源即可工作，镜像纯属本地便利。
    for extra_root in _optional_mirror_roots():
        link = extra_root / name
        if not link.exists():
            continue  # 可选镜像，不存在不算问题
        try:
            target = link.resolve()
        except Exception as exc:
            add(rows, "WARN", f"{name}@mirror", f"镜像解析失败: {exc}")
            continue
        if target != path.resolve():
            add(rows, "WARN", f"{name}@mirror", f"镜像指向 {target}，与该技能实际位置 {path.resolve()} 不一致")
        else:
            add(rows, "PASS", f"{name}@mirror", "镜像指向一致")

    for dep in DEP_MAP.get(name, []):
        if importlib.util.find_spec(dep) is None:
            add(rows, "FAIL", f"{name}:dep", f"缺少 Python 模块 {dep}（宿主解释器 {sys.executable}）")


def check_support(registry: dict, rows: list[dict]) -> None:
    for item in registry.get("support", []):
        name = item.get("name", "")
        path = resolve_entry(item.get("path")) or resolve_entry(f"$SKILLS_ROOT/{name}")
        entry = resolve_entry(item.get("entry")) if item.get("entry") else (
            (path / "SKILL.md") if path else None)
        if path is None or entry is None or not entry.exists():
            add(rows, "FAIL", name, f"支撑入口缺失: {item.get('path')}")
            continue
        add(rows, "PASS", name, "支撑入口就位")


def check_unregistered(registry: dict, rows: list[dict]) -> None:
    keywords = ("figure", "image", "diagram", "plot", "chart", "visio", "drawio")
    registered = {s["name"] for s in registry.get("skills", [])}
    for item in registry.get("skills", []):
        if item["name"] != "nature-figure":
            continue
        resolved = resolve_entry(item.get("path")) or resolve_entry(f"$SKILLS_ROOT/{item['name']}")
        if resolved is None:
            continue  # 未安装则无从检查同仓兄弟技能
        repo_skills = resolved.resolve().parent
        if not repo_skills.is_dir():
            continue
        for child in sorted(repo_skills.iterdir()):
            if not (child / "SKILL.md").exists():
                continue
            child_name = read_frontmatter_name(child / "SKILL.md")
            if not child_name or child_name in registered or child_name == "nature-shared":
                continue
            if any(k in child_name.lower() for k in keywords):
                add(rows, "WARN", "unregistered", f"仓库内绘图相关新技能未注册: {child_name} ({child})")


def check_env(registry: dict, rows: list[dict], deep: bool) -> None:
    dot = shutil.which("dot")
    known_dot = Path(r"C:\Program Files\Graphviz\bin\dot.exe")
    if dot:
        add(rows, "PASS", "graphviz", dot)
        if deep:
            out = run(["dot", "-V"], timeout=30)
            add(rows, "PASS" if out.returncode == 0 else "FAIL", "graphviz:deep", (out.stderr or out.stdout).strip())
    elif known_dot.exists():
        add(rows, "PASS", "graphviz", f"{known_dot}（当前进程 PATH 未继承，重启后生效）")
        if deep:
            out = run([str(known_dot), "-V"], timeout=30)
            add(rows, "PASS" if out.returncode == 0 else "FAIL", "graphviz:deep", (out.stderr or out.stdout).strip())
    else:
        add(rows, "WARN", "graphviz", "dot 不在 PATH；重启继承或手工布局")

    drawio = shutil.which("drawio") or shutil.which("drawio.cmd")
    known = Path(r"C:\Users\11352\AppData\Roaming\npm\drawio.CMD")
    if drawio or known.exists():
        add(rows, "PASS", "drawio-cli", drawio or str(known))
    else:
        add(rows, "WARN", "drawio-cli", "未找到 drawio CLI；导出能力受限")

    if has_visio_registration():
        add(rows, "PASS", "visio", "Visio.Application 已注册")
    else:
        add(rows, "WARN", "visio", "未检测到 Visio.Application")

    image2ppt = next((s for s in registry.get("skills", []) if s["name"] == "nature-image2ppt"), None)
    if image2ppt:
        config = Path(image2ppt["path"]) / "config.yaml"
        if not config.exists():
            add(rows, "WARN", "image2ppt:config", "config.yaml 缺失")
        else:
            data: dict[str, object] = {}
            try:
                import yaml  # type: ignore
                loaded = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
                data = loaded if isinstance(loaded, dict) else {}
            except Exception:
                text = config.read_text(encoding="utf-8", errors="replace")
                for key in ("PADDLE_OCR_TOKEN", "OPENAI_API_KEY", "OPENAI_BASE_URL",
                            "IMAGE2PPT_IMAGE_MODEL", "IMAGE2PPT_IMAGE_BACKEND"):
                    line = next((ln for ln in text.splitlines() if ln.strip().startswith(key)), "")
                    data[key] = line.split(":", 1)[1].strip() if ":" in line else ""
            api_key = str(data.get("OPENAI_API_KEY") or "").strip()
            base_url = str(data.get("OPENAI_BASE_URL") or "").strip()
            model = str(data.get("IMAGE2PPT_IMAGE_MODEL") or "").strip()
            backend = str(data.get("IMAGE2PPT_IMAGE_BACKEND") or "").strip()
            if api_key and base_url and model and backend == "openai-compatible-api":
                add(rows, "PASS", "image2ppt:image-api", f"{model} @ {base_url} ({backend})")
            else:
                missing = [k for k, v in {
                    "OPENAI_API_KEY": api_key, "OPENAI_BASE_URL": base_url,
                    "IMAGE2PPT_IMAGE_MODEL": model, "backend=openai-compatible-api": backend,
                }.items() if not v or (k == "backend=openai-compatible-api" and v != "openai-compatible-api")]
                add(rows, "WARN", "image2ppt:image-api", "未完整配置: " + ", ".join(missing))
            if str(data.get("PADDLE_OCR_TOKEN") or "").strip():
                add(rows, "PASS", "image2ppt:ocr", "PADDLE_OCR_TOKEN 已配置")
            else:
                add(rows, "WARN", "image2ppt:ocr", "PADDLE_OCR_TOKEN 未配；使用本地 builtin-ink")
            if deep:
                cli = Path(image2ppt["path"]) / "cli" / "image2ppt" / "cli.py"
                out = run([sys.executable, str(cli), "doctor", "--json"], cwd=Path(image2ppt["path"]), timeout=90)
                add(rows, "PASS" if out.returncode == 0 else "WARN", "image2ppt:deep", summarize_deep(out.stdout or out.stderr))

    drawio_skill = next((s for s in registry.get("skills", []) if s["name"] == "drawio-skill"), None)
    if drawio_skill:
        skill_md = Path(drawio_skill["entry"])
        head = skill_md.read_text(encoding="utf-8", errors="replace")[:1200] if skill_md.exists() else ""
        if re.search(r"disable-model-invocation:\s*true", head):
            add(rows, "WARN", "drawio:invoke", "frontmatter 带 disable-model-invocation: true；不自动触发时需点名")
        if deep:
            cli = Path(drawio_skill["path"]) / "scripts" / "diagramctl.py"
            out = run([sys.executable, str(cli), "doctor"], cwd=Path(drawio_skill["path"]), timeout=120,
                      env_path=known_dot.parent if known_dot.exists() else None)
            add(rows, "PASS" if out.returncode == 0 else "WARN", "drawio:deep", summarize_deep(out.stdout or out.stderr))

    nature = next((s for s in registry.get("skills", []) if s["name"] == "nature-figure"), None)
    if nature and deep:
        script = Path(nature["path"]) / "scripts" / "nature_figure_backend.py"
        out = run([sys.executable, str(script), "get"], cwd=Path(nature["path"]), timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            add(rows, "PASS", "nature:backend", f"默认后端 {out.stdout.strip()}")
        else:
            add(rows, "INFO", "nature:backend", "未设默认后端；首次绘图会问一次 Python/R")

    add(rows, "INFO", "python", f"{sys.version.split()[0]} ({sys.executable})")
    # 依赖检查用的是本进程解释器（find_spec 只能看见自己）。
    # 在项目 .venv 里跑 doctor 会把"venv 没装绘图库"误报成技能不可用——
    # 技能实际运行在宿主解释器上，所以显式提示这一点，避免误读 SUMMARY。
    if (Path(sys.prefix) / "pyvenv.cfg").is_file():
        add(rows, "WARN", "python:venv",
            f"当前解释器是虚拟环境 {sys.prefix}；:dep 结果反映的是该 venv，"
            f"不代表宿主 Python。判断技能可用性请用宿主解释器重跑本 doctor。")


def finish(rows: list[dict], as_json: bool, strict: bool) -> int:
    fails = [r for r in rows if r["level"] == "FAIL"]
    warns = [r for r in rows if r["level"] == "WARN"]
    if as_json:
        print(json.dumps({"rows": rows, "fail": len(fails), "warn": len(warns)}, ensure_ascii=False, indent=2))
    else:
        width = max((len(r["item"]) for r in rows), default=10) + 2
        for r in rows:
            print(f"[{r['level']}] {r['item']:<{width}} {r['detail']}")
        print(f"\nSUMMARY: PASS={sum(1 for r in rows if r['level']=='PASS')} WARN={len(warns)} FAIL={len(fails)} INFO={sum(1 for r in rows if r['level']=='INFO')}")
    if fails or (strict and warns):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    rows: list[dict] = []
    if not REGISTRY.exists():
        add(rows, "FAIL", "registry", "registry.json 缺失")
        return finish(rows, args.json, args.strict)
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception as exc:
        add(rows, "FAIL", "registry", f"JSON 解析失败: {exc}")
        return finish(rows, args.json, args.strict)

    check_registry_schema(registry, rows)
    for item in registry.get("skills", []):
        check_skill(item, rows)
    check_support(registry, rows)
    check_unregistered(registry, rows)

    for item in registry.get("fallbacks", []):
        p = item.get("path")
        if item.get("installed") and p and not Path(p).exists():
            add(rows, "WARN", "fallback", f"{item.get('use')} 标记已安装但路径缺失")
        elif not item.get("installed"):
            add(rows, "INFO", "fallback", f"{item.get('use')} 未安装（备选）")

    check_env(registry, rows, args.deep)
    return finish(rows, args.json, args.strict)


if __name__ == "__main__":
    sys.exit(main())
