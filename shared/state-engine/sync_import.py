#!/usr/bin/env python3
"""把已有论文、代码和数据导入标准数学建模项目。

默认只生成计划；传入 --apply 后才复制文件和补齐标准设施。原始文件永不覆盖。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

STATE = "state"
CODE_EXT = {".py", ".r", ".R", ".m", ".jl", ".ipynb", ".toml", ".yaml", ".yml"}
DATA_EXT = {".csv", ".xlsx", ".xls", ".json", ".parquet", ".txt", ".dat"}
PAPER_EXT = {".md", ".markdown", ".tex", ".bib", ".pdf", ".docx"}
IGNORED = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_under(source: Path) -> list[Path]:
    """递归列出源目录下的文件，按**相对 source 的路径**排除依赖/构建目录。

    原实现检查 p.parts（绝对路径的每一段）：源目录只要在 .../build/... 或
    .../dist/... 下，所有文件都会被当成"需忽略"，导入计划直接变空。
    """
    source = source.resolve()
    out = []
    for p in source.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel_parts = p.resolve().relative_to(source).parts
        except (ValueError, OSError):
            continue
        if any(part in IGNORED for part in rel_parts):
            continue
        out.append(p)
    return out


def kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in CODE_EXT:
        return "code"
    if suffix in DATA_EXT:
        return "data"
    if suffix in PAPER_EXT:
        return "paper"
    return "other"


def markdown_to_latex(text: str) -> str:
    """Legacy preview-only adapter; never use its output as canonical LaTeX."""
    return (
        "% LEGACY/PREVIEW-ONLY: not a canonical LaTeX source.\n"
        "% AI 专用 Agent 必须复核：请读取 mm-latex-writing 与 latex-guard 后重写。\n"
        "% HUMAN_REVIEW_REQUIRED: 人工复核语义、公式、图表、引用后方可合并。\n"
        "% SOURCE_MARKDOWN_BEGIN\n"
        + text
        + ("" if text.endswith("\n") else "\n")
        + "% SOURCE_MARKDOWN_END\n"
    )


def conversion_task(entry: dict) -> dict:
    """Create the protocol task envelope without generating a final .tex file."""
    return {
        "task_type": "document_to_latex",
        "source_files": [{
            "path": entry["source"],
            "format": Path(entry["source"]).suffix.lower().lstrip("."),
            "sha256": entry["sha256"],
        }],
        "target_scope": {
            "draft_dir": entry["target"],
            "canonical_target": None,
        },
        "required_skills": ["mm-latex-writing", "latex-guard"],
        "parallel_units": ["chapters", "formulas", "figures", "references"],
        "quality_gates": ["encoding", "structure", "formulas", "figures", "references", "compile"],
        "manual_checkpoints": ["AI 专用 Agent 必须复核", "HUMAN_REVIEW_REQUIRED"],
        "prohibited_shortcuts": ["script_direct_markdown_to_canonical_latex"],
        "status": "BLOCKED",
    }


def destination(project: Path, source_root: Path, path: Path, category: str) -> Path | None:
    relative = path.relative_to(source_root)
    if category == "data":
        return project / "Data" / "raw" / relative
    if category == "code":
        return project / "Code" / "legacy" / relative
    if category == "paper":
        if path.suffix.lower() in {".md", ".markdown"}:
            return project / "ReportPaper" / "LaTeX" / "drafts" / f"import-{path.stem}" / "source.md"
        if path.suffix.lower() == ".tex":
            return project / "ReportPaper" / "LaTeX" / "drafts" / f"import-{path.stem}" / path.name
        if path.suffix.lower() == ".bib":
            return project / "ReportPaper" / "LaTeX" / "drafts" / f"import-{path.stem}" / path.name
        return project / STATE / "imports" / "paper" / relative
    return project / STATE / "imports" / "other" / relative


def build_plan(source: Path, project: Path) -> dict:
    entries = []
    for path in files_under(source):
        category = kind(path)
        target = destination(project, source, path, category)
        entries.append({
            "source": path.as_posix(),
            "relative": path.relative_to(source).as_posix(),
            "category": category,
            "target": target.relative_to(project).as_posix() if target else None,
            "sha256": sha256(path),
            "action": "copy" if target else "skip",
        })
    return {
        "version": "1.0",
        "created_at": now(),
        "source_root": source.as_posix(),
        "project_root": project.as_posix(),
        "policy": {
            "overwrite": False,
            "originals_preserved": True,
            "latex_is_canonical": True,
            "pdf_is_generated_artifact": True,
        },
        "summary": {k: sum(1 for e in entries if e["category"] == k) for k in ("paper", "code", "data", "other")},
        "entries": entries,
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _free_target(target: Path) -> Path:
    """为一个非空目标挑一个不覆盖的名字：x.md → x_imported.md → x_imported2.md → …

    原实现只把目标改成 `<stem>_imported<suffix>` 一次；若该文件已存在
    （第二次之后的重复导入），后续 write_text/copy2 会**静默覆盖**它——
    与声明的 `overwrite: false / originals_preserved` 策略直接矛盾，
    用户手工修订过的导入稿会被下一次同步导入抹掉。
    """
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    candidate = target.with_name(f"{stem}_imported{suffix}")
    index = 1
    while candidate.exists():
        index += 1
        candidate = target.with_name(f"{stem}_imported{index}{suffix}")
    return candidate


def _conversion_task_path(project: Path, entry: dict, src: Path) -> Path:
    """转换任务路径：默认 `state/latex_conversion/<stem>/task.json`（文档约定）。

    但不同目录下的同名源文件（a/paper.md 与 b/paper.md）都映射到同一个
    `<stem>/`，后写者会静默覆盖前者的任务文件。冲突时用相对路径的短哈希
    区分：`<stem>__<hash8>/`，既保留默认约定又不丢任务。
    """
    base = project / STATE / "latex_conversion" / src.stem
    default = base / "task.json"
    relative = entry.get("relative") or src.name
    if (default.exists()
            and _read_json_quiet(default).get("source_files", [{}])[0].get("path") != entry.get("source")):
        digest = hashlib.sha256(str(relative).encode("utf-8")).hexdigest()[:8]
        return project / STATE / "latex_conversion" / f"{src.stem}__{digest}" / "task.json"
    return default


def _read_json_quiet(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def apply_plan(plan: dict, source: Path, project: Path) -> None:
    for entry in plan["entries"]:
        if entry["action"] != "copy":
            continue
        src = Path(entry["source"])
        target = project / entry["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = _free_target(target)
            entry["target"] = target.relative_to(project).as_posix()
            entry["action"] = "copy_without_overwrite"
        if src.suffix.lower() in {".md", ".markdown"}:
            target.write_text(markdown_to_latex(src.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
            entry["conversion"] = "legacy_preview_only"
            task = conversion_task(entry)
            task_path = target.parent / "conversion_task.json"
            write_text(task_path, json.dumps(task, ensure_ascii=False, indent=2) + "\n")
            state_task = _conversion_task_path(project, entry, src)
            write_text(state_task, json.dumps(task, ensure_ascii=False, indent=2) + "\n")
        else:
            shutil.copy2(src, target)
            if src.suffix.lower() in {".pdf", ".docx"}:
                entry["conversion"] = "task_required"
                task = conversion_task(entry)
                task_path = _conversion_task_path(project, entry, src)
                write_text(task_path, json.dumps(task, ensure_ascii=False, indent=2) + "\n")
    state = project / STATE
    state.mkdir(parents=True, exist_ok=True)
    write_text(state / "compatibility_manifest.json", json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    inventory = ["# 现有材料标准化接入清单", "", "| 类别 | 原始相对路径 | 标准目标路径 | SHA-256 |", "|---|---|---|---|"]
    for e in plan["entries"]:
        if e["action"] != "skip":
            inventory.append(f"| {e['category']} | `{e['relative']}` | `{e['target']}` | `{e['sha256'][:12]}` |")
    inventory += ["", "> 原始材料只读保留；Markdown 转换生成的 LaTeX 必须经人工/独立审阅后发布。"]
    write_text(state / "source_inventory.md", "\n".join(inventory) + "\n")
    claim_map = {"version": "1.0", "updated_at": now(), "claims": [], "pending": ["补充论文主张与代码/数据证据映射"]}
    write_text(state / "claim_evidence_map.json", json.dumps(claim_map, ensure_ascii=False, indent=2) + "\n")
    latex_readme = project / "ReportPaper" / "LaTeX" / "README-LaTeX.md"
    if not latex_readme.exists():
        write_text(latex_readme, "# LaTeX 文档工程\n\nLaTeX 是唯一可维护源；PDF 通过 `latexmk -xelatex -interaction=nonstopmode main.tex` 生成。\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="将已有论文、代码和数据导入标准项目格式")
    parser.add_argument("--source", required=True, help="已有材料根目录")
    parser.add_argument("--project", required=True, help="已初始化的标准项目目录")
    parser.add_argument("--apply", action="store_true", help="实际复制和生成文件；默认只输出计划")
    parser.add_argument("--plan", help="计划文件路径，默认写入标准输出")
    args = parser.parse_args()
    source, project = Path(args.source).resolve(), Path(args.project).resolve()
    if not source.is_dir():
        parser.error(f"材料目录不存在: {source}")
    if not (project / STATE / "decision_log.json").exists():
        parser.error(f"目标不是已初始化的标准项目: {project}；请先运行 state_utils.py init")
    plan = build_plan(source, project)
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.plan:
        write_text(Path(args.plan).resolve(), rendered)
    if args.apply:
        apply_plan(plan, source, project)
        print(f"已导入 {len(plan['entries'])} 个文件；原始材料未覆盖，清单已写入 {STATE}/compatibility_manifest.json")
    else:
        print(rendered)
        print("预览模式：未修改文件。确认计划后追加 --apply。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
