#!/usr/bin/env python3
"""轻量节点协调器：生成单节点任务包、依赖补跑计划和恢复报告。

本模块不调用模型或宿主 CLI，只把自然语言意图和 State 状态转换为可验证协议，
由 ZCode/Codex 等宿主负责实际委派 Agent。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_DIR = "state"
PROBLEM_LOCK = "problem_lock.json"

# P0-10：不再维护第三份 NODES 副本。原副本已漂移（N0 executor=orchestrator、
# N6/N7/N8 缺 figure-table-benchmark、N0 artifact 的 TimePlan.md 少了 ProblemInfo/ 前缀），
# 导致 /mm-iterate 打印出的命令会被自己拒绝。现统一从 state_defs 派生。
try:
    from state_defs import NODES as _DEF_NODES, UPSTREAM as _DEF_UPSTREAM, skill_basename as _sb
    NODES = {
        nid: {
            "name": info.get("name", nid),
            "executor": info.get("executor"),
            "reviewer": info.get("reviewer"),
            "upstream": [up for up, _ in _DEF_UPSTREAM.get(nid, [])],
            "skills": [_sb(s) for s in (info.get("skills") or [])],
            "artifact": info.get("artifact", ""),
        }
        for nid, info in _DEF_NODES.items()
    }
except ImportError:  # 独立运行时降级：保持最小可用的静态表（应与 state_defs 一致）
    NODES = {
        "N0": {"name": "需求确认", "executor": "main-agent", "reviewer": None, "upstream": [], "skills": [],
               "artifact": "README-项目总说明.md, ProblemInfo/TeamInfo.txt, ProblemInfo/TimePlan.md, state/"},
        "N1": {"name": "选题拆解", "executor": "selector", "reviewer": "reviewer", "upstream": ["N0"],
               "skills": ["mm-problem-analysis", "mm-self-review"], "artifact": "ProblemInfo/"},
        "N2": {"name": "数据处理", "executor": "dataprep", "reviewer": "reviewer", "upstream": ["N1"],
               "skills": ["mm-data-preprocessing"], "artifact": "Data/"},
        "N3": {"name": "建模", "executor": "modeler", "reviewer": "reviewer", "upstream": ["N1", "N2"],
               "skills": ["mm-model-library"], "artifact": "ModelDocs/"},
        "N4": {"name": "代码", "executor": "coder", "reviewer": "mm-code-reviewer", "upstream": ["N3"],
               "skills": ["mm-iteration-engine", "mm-algorithm-dev", "code-review"], "artifact": "Code/"},
        "N5": {"name": "调优", "executor": "tuner", "reviewer": "mm-code-reviewer", "upstream": ["N4"],
               "skills": ["mm-model-tuning", "mm-iteration-engine"], "artifact": "ModelDocs/"},
        "N6": {"name": "图表", "executor": "visualization", "reviewer": "mm-viz-reviewer",
               "upstream": ["N4", "N5"],
               "skills": ["mm-visualization", "mm-iteration-engine", "figure-table-benchmark"],
               "artifact": "Code/output/figures, ResultFigures/"},
        "N7": {"name": "论文", "executor": "writing", "reviewer": "reviewer", "upstream": ["N6"],
               "skills": ["mm-iteration-engine", "mm-latex-writing", "mm-self-review",
                          "figure-table-benchmark"], "artifact": "ReportPaper/"},
        "N8": {"name": "评审", "executor": "reviewer", "reviewer": "reviewer", "upstream": ["N7"],
               "skills": ["mm-self-review", "figure-table-benchmark"], "artifact": "SubmissionPackage/"},
    }

@dataclass(frozen=True)
class Task:
    node_id: str
    mode: str
    executor: str
    reviewer: str | None
    required_skills: list[str]
    prerequisites: list[str]
    missing_prerequisites: list[str]
    run_id: str
    output_scope: str
    dispatch_rule: str


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_of(path: Path) -> str:
    """分块 SHA256 校验（64KB 块），避免大文件 OOM。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state(project: str | Path) -> dict[str, Any]:
    path = Path(project) / STATE_DIR / "decision_log.json"
    if not path.exists():
        raise FileNotFoundError(f"未找到 {path}，请先运行 python state/state_utils.py init")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_intent(text: str) -> list[str]:
    if any(word in text for word in ("全流程", "完整流程", "帮我做国赛")):
        return list(NODES)
    matches = []
    phrases = {
        "N1": ("分析这道题", "选题", "审题"), "N2": ("处理数据", "数据清洗", "预处理"),
        "N3": ("建模", "选模型", "公式推导"), "N4": ("写代码", "代码迭代", "实现算法", "修代码"),
        "N5": ("调优", "调参", "敏感性分析", "错误分析", "误差分析"),
        "N6": ("画图", "图表", "可视化"), "N7": ("写论文", "论文修改", "LaTeX"),
        "N8": ("评审", "检查论文", "终审"),
    }
    for node, words in phrases.items():
        if any(word in text for word in words):
            matches.append(node)
    return matches


def verify_problem_lock(project: str | Path) -> dict[str, Any]:
    path = Path(project) / STATE_DIR / PROBLEM_LOCK
    if not path.exists():
        raise ValueError(f"缺少 {path}；请先阅读题目并创建 problem_lock.json")
    lock = json.loads(path.read_text(encoding="utf-8"))
    required = ("objectives", "constraints", "preconditions", "data_requirements", "evaluation_metrics")
    missing = [key for key in required if not isinstance(lock.get(key), list) or not lock[key]]
    source = Path(lock.get("source_path", ""))
    if not source.is_absolute():
        source = Path(project) / source
    if not source.is_file():
        missing.append("source_path")
    else:
        digest = sha256_of(source)
        if digest != lock.get("source_sha256"):
            raise ValueError("题目原文 SHA-256 已变化；必须重新阅读题目并更新 problem_lock.json")
    if lock.get("status") != "verified" or missing:
        raise ValueError(f"题目事实锁定未通过: status={lock.get('status')}, missing={missing}")
    return lock


def prepare_node(project: str | Path, node_id: str, mode: str = "standalone", strict: bool = False) -> dict[str, Any]:
    if node_id not in NODES:
        raise ValueError(f"unknown node: {node_id}")
    state = load_state(project)
    lock = None if node_id == "N0" else verify_problem_lock(project)
    info = NODES[node_id]
    nodes = state.get("nodes", {})
    missing = [up for up in info["upstream"] if nodes.get(up, {}).get("status") != "completed"]
    blocked_reasons: list[str] = []
    if strict:
        for up in info["upstream"]:
            up_info = NODES.get(up, {})
            artifact = up_info.get("artifact", "")
            for art_path in artifact.split(","):
                art_path = art_path.strip()
                if not art_path:
                    continue
                full = Path(project) / art_path
                if not full.exists():
                    blocked_reasons.append(f"upstream {up} artifact missing: {art_path}")
    result: dict[str, Any] = {
        "node_id": node_id, "mode": mode, "ready": not missing and not blocked_reasons,
        "missing_prerequisites": missing,
        "blocked_reasons": blocked_reasons if blocked_reasons else None,
        "status": "blocked" if blocked_reasons else ("ready" if not missing else "pending"),
        "executor": info["executor"], "reviewer": info["reviewer"], "required_skills": info["skills"],
        "problem_lock": {"status": lock.get("status"), "source_sha256": lock.get("source_sha256")} if lock else None,
    }
    return result


def prerequisite_chain(node_id: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    def visit(node: str) -> None:
        for upstream in NODES[node]["upstream"]:
            if upstream not in seen:
                visit(upstream); seen.add(upstream); result.append(upstream)
    visit(node_id)
    return result


def build_task(project: str | Path, node_id: str, run_id: str | None = None, mode: str = "standalone", strict: bool = False) -> dict[str, Any]:
    prep = prepare_node(project, node_id, mode, strict=strict)
    info = NODES[node_id]
    task = Task(node_id=node_id, mode=mode, executor=info["executor"], reviewer=info["reviewer"],
                required_skills=info["skills"], prerequisites=info["upstream"],
                missing_prerequisites=prep["missing_prerequisites"], run_id=run_id or f"{node_id}-{now()}",
                output_scope=f"{STATE_DIR}/nodes/{info['name']}",
                dispatch_rule=(
                    f"必须通过 task 以 subagent_type={info['executor']} 唤起本节点执行 Agent"
                    f"（禁止用 general-purpose 代做节点产物；执行 Agent 开工必须加载并声明必读 Skill: "
                    f"{', '.join(info['skills'])}，node-finish 会校验 --agent/--skills）"))
    result = asdict(task)
    result["blocked_reasons"] = prep.get("blocked_reasons")
    result["status"] = prep.get("status")
    return result


def request_prerequisite(project: str | Path, node_id: str) -> dict[str, Any]:
    task = build_task(project, node_id)
    missing = task["missing_prerequisites"]
    return {"type": "prerequisite_request", "target_node": node_id, "chain": [*missing, node_id],
            "reason": "上游门禁或节点状态未完成", "tasks": [build_task(project, n, mode="prerequisite") for n in missing]}


def resume(project: str | Path) -> dict[str, Any]:
    state = load_state(project)
    pending = [node for node, data in state.get("nodes", {}).items() if data.get("status") in {"in_progress", "review_pending", "blocked"}]
    return {"resumed_at": now(), "pending_nodes": pending,
            "unfinished_rounds": [r for r in state.get("rounds", []) if r.get("status") == "in_progress"]}


ITERATION_NODES = {"N4", "N5", "N7", "N8"}
STATE_SCRIPT = "python state/state_utils.py"

# 已有材料类型 → 扩展名（用于复用检测）
EXISTING_EXTS = {
    "paper": {".tex", ".md", ".markdown", ".pdf", ".docx", ".doc"},
    "code": {".py", ".r", ".R", ".m", ".jl", ".ipynb"},
    "data": {".csv", ".xlsx", ".xls", ".json", ".parquet", ".dat", ".txt"},
}
# 脚手架自身占位（不算"已有材料"，与 state_utils.standard_files_content 一致）
SCAFFOLD_FILES = {
    "README-项目总说明.md",
    "Code/main.py", "Code/config.py", "Code/requirements.txt", "Code/README-Code.md",
    "Code/utils/__init__.py",
    "Code/visualization/__init__.py", "Code/visualization/utils/__init__.py",
    # 分题目录与 utils/ 下都不再预建空壳 .py（见 state_scaffold 的注释）：
    # 因此 Code/ 下任何业务 .py 都是用户真实代码，不得列入占位清单，
    # 否则"已有真实实现"会被误判成"只有脚手架占位"。
    "Data/raw/readme.txt", "Data/DataLog.md",
    "Material/training_notes.md", "Material/contest_experience.md",
    "ModelDocs/model-framework.md", "ModelDocs/formula.md", "ModelDocs/assumption.md",
    "ModelDocs/reference-list.md", "ModelDocs/sensitivity-analysis.md",
    "ModelDocs/error-analysis.md", "ModelDocs/model-validation.md",
    "ProblemInfo/ProblemNotes.md", "ProblemInfo/KeyRequirements.md",
    "ProblemInfo/TeamInfo.txt", "ProblemInfo/TimePlan.md",
    "ReportPaper/LaTeX/main.tex", "ReportPaper/LaTeX/preamble.tex", "ReportPaper/LaTeX/config.tex",
    "ReportPaper/LaTeX/frontmatter/commitment.tex", "ReportPaper/LaTeX/frontmatter/team_number.tex",
    "ReportPaper/LaTeX/ref.bib", "ReportPaper/LaTeX/sections/abstract.tex",
    "ReportPaper/LaTeX/README-LaTeX.md", "ReportPaper/LaTeX/.latexmkrc",
    "ResultFigures/figure-list.md",
    "SubmissionPackage/README-提交说明.txt", "SubmissionPackage/参赛提交清单.md",
    "DefenseMaterial/defense-script.md",
}
IGNORED_PARTS = {".git", "state", "LogRecord", "__pycache__", ".venv", "build", "Code/output",
                 # External/ 是只读引用区（第三方成果，受哈希锁定），不属于"待整理赛题材料"：
                 # 把它算进 material_intake 会要求 AI 去"整理"别人的论文/代码并登记为自有材料，
                 # 既混淆来源也违反隔离设计。它由 external_isolation 单独管理。
                 "External",
                 # scripts/ 是 init 分发的工具转发垫片（external_isolation / raw_lock 等），
                 # 属于运行时基础设施，不是用户带来的"已有代码材料"。
                 "scripts"}


def detect_existing_materials(project: str | Path) -> dict[str, Any]:
    """扫描项目内已有论文/代码/数据（Material/、BackupArchive/、根目录等），返回复用建议。

    供 orchestrator 在 Phase 0 与 /mm 总控调用：检测到已有材料时，应走 sync_import
    复用（代码→Code/legacy 审阅修复、数据→Data/raw、论文→ReportPaper/LaTeX/drafts 转换），
    而不是从零开始。
    """
    root = Path(project).resolve()
    scan_dirs = [root, root / "Material", root / "BackupArchive", root / "Data" / "raw", root / "ProblemInfo"]
    found: dict[str, list[str]] = {"paper": [], "code": [], "data": []}
    seen: set[str] = set()
    for base in scan_dirs:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            # 只按相对项目根的路径片段判断忽略项。原先直接看 p.parts（绝对路径的
            # 每一段），项目只要放在 .../build/... 或 .../state/... 下，
            # 整棵树都会被判成"已忽略"，已有材料检测恒为 False。
            try:
                rel_parts = p.resolve().relative_to(root).parts
            except (ValueError, OSError):
                continue
            if any(part in IGNORED_PARTS for part in rel_parts):
                continue
            rel = Path(*rel_parts).as_posix()
            if rel in SCAFFOLD_FILES or rel in seen:
                continue
            seen.add(rel)
            suffix = p.suffix.lower()
            for kind, exts in EXISTING_EXTS.items():
                if suffix in exts:
                    found[kind].append(rel)
                    break
    has = any(found.values())
    return {
        "has_existing": has,
        "found": found,
        "reuse_plan": None if not has else {
            "steps": [
                "python shared/state-engine/sync_import.py --source <已有材料目录> --project <项目>",
                "python shared/state-engine/sync_import.py --source <已有材料目录> --project <项目> --apply",
            ],
            "mapping": {"code": "Code/legacy/（N4 审阅修复后迁移）", "data": "Data/raw/（dataprep 清洗）",
                        "paper": "ReportPaper/LaTeX/drafts/（专用 Agent 转换 + 独立审阅）"},
            "note": "复用后节点流程优先基于 legacy/imports 审阅修复，不从零开始",
        },
        "dirs_scanned": [str(d) for d in scan_dirs if d.is_dir()],
    }


def organize_existing_materials(project: str | Path) -> dict[str, Any]:
    """自动收集、整理、归类项目内已有材料（题目/数据/代码/论文），生成材料索引供后续节点使用。

    归类规则（原始文件保留，只复制不覆盖）：
      - 题目类（文件名含 problem/题 或在 ProblemInfo/）→ ProblemInfo/；
      - 数据（csv/xlsx/json/dat 等）→ Data/raw/；
      - 代码（py/r/m/jl 等）→ Code/legacy/（N4 审阅修复后迁移）；
      - 论文（md/tex）→ ReportPaper/LaTeX/drafts/（专用 Agent 转换）；
      - 论文（pdf/docx 等不可维护格式）→ state/imports/paper/（比对溯源）。
    结果写入 state/material_index.json，后续节点按索引调用（N2 用 Data/raw、N4 审 Code/legacy、N7 用 drafts）。
    """
    import shutil
    root = Path(project)
    det = detect_existing_materials(project)
    moved: dict[str, list[str]] = {"problem": [], "paper": [], "code": [], "data": []}
    entries: list[dict[str, Any]] = []
    for kind, files in det["found"].items():
        for rel in files:
            src = root / rel
            stem = src.stem.lower()
            is_problem = "problem" in stem or "题" in src.stem or rel.startswith("ProblemInfo/")
            if kind == "paper" and is_problem:
                target = root / "ProblemInfo" / src.name
                entry_type = "problem"
            elif kind == "data":
                target = root / "Data" / "raw" / src.name
                entry_type = "data"
            elif kind == "code":
                target = root / "Code" / "legacy" / src.name
                entry_type = "code"
            elif src.suffix.lower() in {".md", ".markdown"}:
                target = root / "ReportPaper" / "LaTeX" / "drafts" / f"import-{src.stem}" / "source.md"
                entry_type = "paper"
            elif src.suffix.lower() == ".tex":
                target = root / "ReportPaper" / "LaTeX" / "drafts" / f"import-{src.stem}" / src.name
                entry_type = "paper"
            else:
                target = root / "state" / "imports" / "paper" / src.name
                entry_type = "paper"
            if target == src or target.exists():
                continue  # 已在标准位置或目标冲突（不覆盖）
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            moved.setdefault(entry_type, []).append(str(target.relative_to(root)))
            entries.append({"type": entry_type, "source": rel,
                            "target": str(target.relative_to(root)),
                            "sha256": sha256_of(src), "status": "imported"})
    index = {"version": "1.0", "created_at": now(), "entries": entries}
    index_path = root / "state" / "material_index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"has_existing": det["has_existing"], "moved": moved,
            "index": "state/material_index.json", "entries": entries,
            "usage": {"N2": "Data/raw/ 已归类数据直接进入清洗", "N4": "Code/legacy/ 先审阅修复后迁移",
                      "N7": "ReportPaper/LaTeX/drafts/ 先转换后改写", "N1": "ProblemInfo/ 题目供拆解"}}


READ_INTENT = {
    "paper": {
        "read": ["标题/题型", "所用方法/模型", "关键结论与数值", "图表清单", "与本题的相关性（可借鉴点）"],
        "categorize_to": "Material/similar_papers/（按题型/方法归类）",
        "register_to": "state/material_index.json：内容摘要、方法、可借鉴点、对应节点（N1 选题参考 / N7 论文参考）",
    },
    "code": {
        "read": ["入口与依赖", "解决什么问题/对应第几问", "输入输出格式", "关键算法与可复用模块", "可运行性与需修复点"],
        "categorize_to": "Code/legacy/（sync_import 后由 N4 审阅修复迁移）",
        "register_to": "state/material_index.json：功能摘要、输入输出、可复用性、对应节点（N4）",
    },
    "data": {
        "read": ["字段与含义", "行数/缺失/异常", "数据来源与口径", "与题目数据需求的对应"],
        "categorize_to": "Data/raw/（sync_import 后由 dataprep 清洗）",
        "register_to": "state/material_index.json：字段清单、质量概况、用途、对应节点（N2）",
    },
}


def material_intake_plan(project: str | Path) -> dict[str, Any]:
    """生成"AI 内容整理任务包"：对每个已有材料文件，强制 AI 读取真实内容后
    提取要点、归类、登记（state/material_index.json），供后续节点调用。

    与 detect/organize 的区别：检测/归类只按扩展名与文件名；本计划要求 AI 逐文件
    读取内容（标题/方法/字段/结论/可复用性）后真实准确整理，禁止只按扩展名归类。
    流程：detect → organize（归位）→ 本计划（读取内容 → 回填摘要字段）→ 节点调用。
    """
    root = Path(project)
    det = detect_existing_materials(project)
    tasks = []
    for kind, paths in det["found"].items():
        for rel in paths:
            tasks.append({
                "file": rel, "kind": kind, "must_read_content": True,
                "extract": READ_INTENT[kind]["read"],
                "categorize_to": READ_INTENT[kind]["categorize_to"],
                "register_to": READ_INTENT[kind]["register_to"],
                "output_fields": {
                    "summary": "内容摘要（读取后填写）",
                    "key_attributes": "字段/方法/结论等关键属性（读取后填写）",
                    "reusable_for": "对应节点与用途（读取后填写）",
                    "needs_repair": "是否需要修复/清洗/转换（读取后判断）",
                },
            })
    return {
        "project": str(root.resolve()),
        "has_existing": det["has_existing"],
        "total": len(tasks),
        "tasks": tasks,
        "register_file": "state/material_index.json",
        "rule": ("禁止只按扩展名归类：每个文件必须读取内容后真实整理"
                 "（AI 读取 → 摘要 → 归类 → 登记），后续 N1/N2/N4/N7 从 material_index.json 取用"),
    }


def iteration_plan(project: str | Path, node_id: str, git: bool = False) -> dict[str, Any]:
    """生成迭代节点（N4/N5/N7/N8）的完整自动迭代序列（dry-run 命令级）。

    宿主按 steps 顺序执行即可全自动驱动 SEARCH→IMPLEMENT→RUN→COMMIT→SCORE→DECIDE，
    直到 termination 决策（达标合并/达上限/平台期）。评分命令中的 <占位> 由独立审阅
    Agent 的评审结论替换后执行。
    """
    if node_id not in ITERATION_NODES:
        raise ValueError(f"{node_id} 不是迭代节点；仅支持: {sorted(ITERATION_NODES)}")
    prep = prepare_node(project, node_id, strict=True)
    if not prep["ready"]:
        return {"node_id": node_id, "status": "blocked", "executor": prep["executor"],
                "reviewer": prep["reviewer"], "missing_prerequisites": prep["missing_prerequisites"],
                "blocked_reasons": prep["blocked_reasons"], "steps": []}
    state = load_state(project)
    profile = state["termination"]["code" if node_id in {"N4", "N5"} else "paper"]
    info = NODES[node_id]
    existing = [r for r in state.get("rounds", []) if r.get("node") == node_id]
    next_round = max((r["round"] for r in existing), default=0) + 1
    git_flag = " --git" if git else ""
    steps = []
    for i in range(profile["max_rounds"]):
        rno = next_round + i
        steps.append({"round": rno, "kind": "round-start",
                      "cmd": f"{STATE_SCRIPT} round-start {node_id}{git_flag}",
                      "description": "开启第 {rno} 轮迭代分支".format(rno=rno)})
        steps.append({"round": rno, "kind": "agent_execute", "cmd": None,
                      "description": f"由执行 Agent {info['executor']} 完成 SEARCH→IMPLEMENT→RUN→COMMIT：检索案例沉淀 cases/、"
                                     f"实现/修复、运行并保存证据到 Code/output/（或对应产物目录）、按 trailer 提交"})
        steps.append({"round": rno, "kind": "round-score",
                      "cmd": f"{STATE_SCRIPT} round-score {node_id} --round {rno} --total <总分> "
                             f"--dims '<五维JSON>' --judge {info['reviewer']} --skills-read {','.join(info['skills'])} "
                             f"--evidence <证据路径,逗号分隔>{git_flag}",
                      "description": f"独立审阅 Agent {info['reviewer']} 评分后由 orchestrator 落盘（审阅≠执行）"})
        steps.append({"round": rno, "kind": "round-decide",
                      "cmd": f"{STATE_SCRIPT} round-decide {node_id} --round {rno} [--feedback <反馈>]{git_flag}",
                      "description": "按 termination 决策：≥target 提前终止并 merge；≥pass 可继续；<pass 携带 feedback 下一轮；达上限/平台期按规则收尾"})
    return {"node_id": node_id, "status": "ready", "executor": info["executor"], "reviewer": info["reviewer"],
            "termination": {"pass": profile["pass"], "target": profile["target"], "max_rounds": profile["max_rounds"]},
            "next_round": next_round, "steps": steps,
            "exit_conditions": "评分 >= target 提前终止；< pass 携带 feedback 进入下一轮；达到 max_rounds/平台期/预算截止按 termination 决策"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成单节点协同任务计划")
    parser.add_argument("text", nargs="?", default="")
    parser.add_argument("--dir", default=".")
    parser.add_argument("--plan-iteration", choices=sorted(ITERATION_NODES), help="生成迭代节点的完整自动迭代序列（dry-run）")
    parser.add_argument("--git", action="store_true", help="迭代序列中启用 git 分支与提交")
    parser.add_argument("--material-plan", action="store_true",
                        help="生成已有材料 AI 内容整理任务包（读取内容→归类→登记 material_index.json）")
    args = parser.parse_args()
    if args.material_plan:
        print(json.dumps(material_intake_plan(args.dir), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if args.plan_iteration:
        print(json.dumps(iteration_plan(args.dir, args.plan_iteration, git=args.git), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    nodes = resolve_intent(args.text)
    if not nodes:
        parser.error("未识别节点意图；请明确全流程、代码审阅、敏感性分析、论文改写或 Markdown 转 LaTeX")
    try:
        tasks = [build_task(args.dir, node) for node in nodes]
    except FileNotFoundError as exc:
        parser.error(str(exc))
    print(json.dumps({"nodes": nodes, "tasks": tasks}, ensure_ascii=False, indent=2))
