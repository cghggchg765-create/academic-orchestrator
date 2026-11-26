#!/usr/bin/env python3
"""题目事实锁定与偏移检查。

AI 必须先阅读题目原文，再由编排 Agent 写入结构化事实；后续节点只消费通过 verify 的快照。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE = "state"
LOCK = "problem_lock.json"
REQUIRED = ("objectives", "constraints", "preconditions", "data_requirements", "evaluation_metrics")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(project: Path) -> dict:
    path = project / STATE / LOCK
    if not path.exists():
        raise ValueError(f"缺少 {path}；必须先阅读题目并执行 problem_guard.py create")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"题目事实锁定文件不是合法 JSON: {exc}") from exc


def verify(project: Path) -> dict:
    lock = read_json(project)
    errors = []
    source = Path(lock.get("source_path", ""))
    if not source.is_absolute():
        source = project / source
    if not source.is_file():
        errors.append(f"题目原文不存在: {source}")
    else:
        actual = digest(source)
        if actual != lock.get("source_sha256"):
            errors.append("题目原文已变化，source_sha256 不匹配；必须重新阅读并锁定")
    for key in REQUIRED:
        value = lock.get(key)
        if not isinstance(value, list) or not value or any(not str(x).strip() for x in value):
            errors.append(f"事实字段 {key} 必须是非空列表")
    if lock.get("status") != "verified":
        errors.append("题目事实锁定状态不是 verified")
    figure = lock.get("figure") or {}
    mode = figure.get("mode", "none")
    if mode == "vision":
        figs = figure.get("figures", [])
        if not figs:
            errors.append("题目含图形且声明 vision 模式，但未登记图形（先 problem_guard.py figures --mode vision）")
        else:
            for item in figs:
                p = project / item.get("path", "")
                if not p.is_file():
                    errors.append(f"图形文件缺失: {item.get('path')}")
                elif item.get("sha256") and digest(p) != item.get("sha256"):
                    errors.append(f"图形文件哈希变化: {item.get('path')}")
        if not figure.get("figures_read"):
            errors.append("图形尚未由视觉模型逐页阅读并登记（figures-read --mode vision）")
    elif mode == "human":
        if not figure.get("human_description"):
            errors.append("题目图形需要人工描述：problem_guard.py figures --mode human 生成请求单，人工填写后 figures-read --mode human --description <文本>")
    result = {"verified": not errors, "checked_at": now(), "errors": errors,
              "source_path": str(source), "source_sha256": lock.get("source_sha256"),
              "figure": figure, "facts": {key: lock.get(key, []) for key in REQUIRED}}
    if errors:
        raise ValueError(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def write_lock(project: Path, lock: dict) -> Path:
    target = project / STATE / LOCK
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def create(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve()
    source = Path(args.source).resolve()
    if not source.is_file():
        raise ValueError(f"题目原文不存在: {source}")
    lists = {}
    for key in REQUIRED:
        raw = getattr(args, key)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{key} 必须是 JSON 数组: {exc}") from exc
        if not isinstance(value, list) or not value:
            raise ValueError(f"{key} 必须是非空 JSON 数组")
        lists[key] = value
    try:
        portable_source = source.relative_to(project)
        source_path = portable_source.as_posix()
    except ValueError:
        source_path = str(source)
    figure_mode = getattr(args, "figure_mode", "none")
    lock = {"version": "1.0", "status": "verified", "locked_at": now(),
            "source_path": source_path, "source_sha256": digest(source), **lists,
            "figure": {"mode": figure_mode, "figures": [], "figures_read": False,
                       "human_description": None, "request_path": None},
            "drift_policy": "题目原文、目标、约束、数据或指标变化时必须重新锁定"}
    target = write_lock(project, lock)
    print(json.dumps({"written": str(target), "source_sha256": lock["source_sha256"], "status": "verified",
                      "figure_mode": figure_mode}, ensure_ascii=False, indent=2))


FIGURE_REQUEST_TEMPLATE = """# 题目图形人工描述请求单（state/problem_figure_request.md）

当前模型**不具备视觉能力**，无法直接阅读题目 PDF 中的图形。请人工打开题目 PDF，逐页描述所有图形后，由人工执行：

    python state/problem_guard.py figures-read --project <项目目录> --mode human --description "<完整描述>"

## 需要人工描述的内容

- 第几页出现图形（图/表/地图/示意图/流程图/坐标系等）；
- 图形类型与标题、坐标轴含义与单位；
- 关键数值、趋势、特殊标注、图例说明；
- 图形对解题的影响（哪些约束/数据/指标来自图形）。

## 人工描述（请填写后执行 figures-read）

（待填写）
"""


def cmd_figures(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve()
    source = Path(args.source).resolve()
    if not source.is_file():
        raise ValueError(f"题目原文不存在: {source}")
    lock = read_json(project)
    if args.mode == "vision":
        tool = shutil.which("pdftoppm")
        if not tool:
            print(json.dumps({"status": "BLOCKED",
                              "reason": "未找到 pdftoppm（poppler）；可用 pdf2image/PyMuPDF 转换，或改用 --mode human 请求人工描述"},
                             ensure_ascii=False, indent=2))
            return
        outdir = Path(args.outdir or "ProblemInfo/figures")
        if not outdir.is_absolute():
            outdir = project / outdir
        outdir.mkdir(parents=True, exist_ok=True)
        prefix = outdir / "page"
        r = subprocess.run([tool, "-png", "-r", str(args.dpi), str(source), str(prefix)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise ValueError(f"pdftoppm 转换失败: {r.stderr.strip()}")
        figures = sorted(outdir.glob("page-*.png"))
        if not figures:
            raise ValueError("pdftoppm 未产出图片，请检查 PDF 是否为空或加密")
        lock["figure"] = {"mode": "vision",
                          "figures": [{"path": f.relative_to(project).as_posix(), "sha256": digest(f)} for f in figures],
                          "figures_read": False, "human_description": None, "request_path": None}
    else:  # human
        request = project / STATE / "problem_figure_request.md"
        request.parent.mkdir(parents=True, exist_ok=True)
        request.write_text(FIGURE_REQUEST_TEMPLATE, encoding="utf-8")
        lock["figure"] = {"mode": "human", "figures": [], "figures_read": False,
                          "human_description": None, "request_path": request.relative_to(project).as_posix()}
    write_lock(project, lock)
    print(json.dumps({"status": "updated", "figure": lock["figure"]}, ensure_ascii=False, indent=2))
    if args.mode == "vision":
        print("提示：请视觉模型逐页阅读 ProblemInfo/figures/page-*.png 中的图形，"
              "确认无遗漏后执行 figures-read --mode vision 登记。", flush=True)


def cmd_figures_read(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve()
    lock = read_json(project)
    figure = lock.get("figure") or {}
    if args.mode == "vision":
        figs = figure.get("figures", [])
        if not figs:
            raise ValueError("vision 模式尚未登记图形；请先运行 figures --mode vision")
        missing = [item.get("path") for item in figs if not (project / item.get("path", "")).is_file()]
        if missing:
            raise ValueError(f"图形文件缺失，无法确认已阅读: {missing}")
        figure["figures_read"] = True
    else:
        if not args.description or not args.description.strip():
            raise ValueError("human 模式必须提供 --description（人工对题目的完整描述）")
        figure["human_description"] = args.description.strip()
        figure["figures_read"] = True
    lock["figure"] = figure
    write_lock(project, lock)
    print(json.dumps({"status": "verified_reading", "figure": figure}, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="锁定并校验数学建模题目事实")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create", help="在阅读题目后创建事实锁定")
    p.add_argument("--project", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--figure-mode", choices=["vision", "human", "none"], default="none",
                  help="题目是否含图形及处理方式：vision=PDF 转图片交视觉模型；human=请求人工描述")
    for key in REQUIRED:
        p.add_argument(f"--{key.replace('_', '-')}", dest=key, required=True, help="JSON 数组")
    p.set_defaults(func=create)
    p = sub.add_parser("verify", help="检查题目原文和结构化事实是否发生偏移")
    p.add_argument("--project", required=True)
    p.set_defaults(func=lambda a: print(json.dumps(verify(Path(a.project).resolve()), ensure_ascii=False, indent=2)))
    p = sub.add_parser("figures", help="处理题目 PDF 中的图形：vision=渲染为图片交视觉模型；human=生成人工描述请求单")
    p.add_argument("--project", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--mode", required=True, choices=["vision", "human"])
    p.add_argument("--dpi", type=int, default=200, help="vision 模式渲染 DPI（默认 200）")
    p.add_argument("--outdir", default="ProblemInfo/figures", help="vision 模式图片输出目录（默认 ProblemInfo/figures）")
    p.set_defaults(func=cmd_figures)
    p = sub.add_parser("figures-read", help="登记图形已阅读：vision=视觉模型确认；human=提交人工描述")
    p.add_argument("--project", required=True)
    p.add_argument("--mode", required=True, choices=["vision", "human"])
    p.add_argument("--description", help="human 模式必填：人工对题目图形的完整描述")
    p.set_defaults(func=cmd_figures_read)
    args = parser.parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
