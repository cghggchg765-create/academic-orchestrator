#!/usr/bin/env python3
"""state_utils.py — 状态统一节点命令行助手（schema 2.0）——CLI 入口与 argparse 分发。

逻辑按领域拆分到同目录兄弟模块（state_defs 常量/助手、state_scaffold 脚手架、
state_nodes 节点、state_review 审阅、state_audit 审计、state_rounds 迭代、state_search 检索），
本文件仅做：模块导出（lint 通过 importlib 读取 NODES/UPSTREAM 等常量）+ subcommand 注册。

初始化后本脚本会复制一份到项目的 state/state_utils.py（连同全部兄弟模块，项目自包含，随仓库提交）。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile


def _bootstrap_runtime_sync() -> None:
    """Repair stale project runtime modules before importing the CLI siblings.

    A project copy may contain an old/broken state_search.py; importing this
    facade first would otherwise fail before --sync-runtime can be parsed.
    This narrow bootstrap only runs for an explicit init sync request and never
    touches decision_log or other project state files.
    """
    argv = sys.argv[1:]
    if "init" not in argv or "--sync-runtime" not in argv:
        return
    try:
        project = os.path.abspath(argv[argv.index("--dir") + 1]) if "--dir" in argv else os.getcwd()
        source = os.path.abspath(argv[argv.index("--runtime-source") + 1]) if "--runtime-source" in argv else ""
    except (IndexError, ValueError):
        return
    if not source or not os.path.isfile(os.path.join(source, "state_utils.py")):
        return
    target_dir = os.path.join(project, "state")
    os.makedirs(target_dir, exist_ok=True)
    for name in os.listdir(source):
        if not name.endswith(".py"):
            continue
        src = os.path.join(source, name)
        dst = os.path.join(target_dir, name)
        if not os.path.isfile(src) or os.path.abspath(src) == os.path.abspath(dst):
            continue
        fd, tmp = tempfile.mkstemp(prefix=f".{name}.", dir=target_dir)
        os.close(fd)
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


_bootstrap_runtime_sync()

# 使同目录兄弟模块在脚本运行与 importlib 加载两种方式下均可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state_defs import *  # noqa: F401,F403,E402
from state_scaffold import *  # noqa: F401,F403,E402
from state_nodes import *  # noqa: F401,F403,E402
from state_review import *  # noqa: F401,F403,E402
from state_audit import *  # noqa: F401,F403,E402
from state_rounds import *  # noqa: F401,F403,E402
from state_search import *  # noqa: F401,F403,E402
from state_scopes import *  # noqa: F401,F403,E402
from state_skills import *  # noqa: F401,F403,E402
from state_progress import *  # noqa: F401,F403,E402
from state_events import *  # noqa: F401,F403,E402

def main():
    parser = argparse.ArgumentParser(description="状态统一节点命令行助手（schema 2.0）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化标准项目结构与 状态目录全量预建（幂等：已初始化需 --force）")
    p.add_argument("--dir", default=".", help="项目目录（默认当前目录）")
    p.add_argument("--name", help="竞赛名称")
    p.add_argument("--year", help="年份")
    p.add_argument("--problem", help="题号")
    p.add_argument("--language", default="zh", help="语言（默认 zh）")
    p.add_argument("--git", action="store_true", help="git init + 首次提交（含提醒创建远端仓库）")
    p.add_argument("--force", action="store_true", help="强制重建（清空已有状态）")
    p.add_argument("--sync-runtime", action="store_true", help="在不触碰项目状态的前提下同步最新 state/*.py 运行模块")
    p.add_argument("--runtime-source", help="运行模块源目录（包含 state_utils.py；项目内副本同步时显式指定）")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("dump", help="打印 decision_log.json")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("sync-plan", help="生成已有论文、代码和数据的同步兼容计划")
    p.add_argument("--node", choices=["N4", "N5", "N7"], default="N4")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=lambda a: print(json.dumps({
        "mode": "sync-and-compatibility",
        "order": ["intake", "code_review", "data_validation", "independent_score", "paper_rewrite", "markdown_to_latex", "latex_compile"],
        "target_node": a.node,
        "reviewer": NODES[a.node]["reviewer"],
        "paper_source": "Markdown/LaTeX/PDF input; LaTeX is canonical output",
        "state_dir": STATE_DIR,
    }, ensure_ascii=False, indent=2)))

    p = sub.add_parser("stage-set", help="设置阶段状态")
    p.add_argument("key"); p.add_argument("status", choices=["pending", "in_progress", "completed"])
    p.add_argument("--artifact"); p.add_argument("--decision"); p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_stage_set)

    p = sub.add_parser("gate-set", help="设置门禁状态")
    p.add_argument("gate"); p.add_argument("status", choices=["PASS", "FAIL", "BLOCKED", "pending"])
    p.add_argument("--agent"); p.add_argument("--result"); p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_gate_set)

    p = sub.add_parser("node-start", help="节点开始执行")
    p.add_argument("node"); p.add_argument("--goal")
    p.add_argument("--no-skill-routing", action="store_true",
                   help="豁免技能派发清单门禁（离线/试验环境；豁免会留痕到节点记录）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_node_start)

    p = sub.add_parser("node-finish", help="节点执行完成（须声明执行 Agent 与已加载技能；迭代环节点由 round-decide 决定 completed）")
    p.add_argument("node"); p.add_argument("--agent", help="执行该节点的 Agent（N0 可省，其余必填且须匹配 registry executor）")
    p.add_argument("--skills", help="执行时已加载的技能，逗号分隔（非 N0 必填且须含本节点 required_skills）")
    p.add_argument("--artifact", action="append"); p.add_argument("--dir", default=".")
    p.add_argument("--allow-empty-artifacts", action="store_true",
                   help="允许产物目录为空时仍标完成（仅异常情况，须说明原因并留痕）")
    p.add_argument("--allow-no-checkpoint", action="store_true",
                   help="允许无进度快照时标完成（仅单步节点，须说明原因并留痕）")
    p.add_argument("--skip-prereq", action="store_true",
                   help="跳过未开工/上游完成守卫（仅单测/历史项目迁移，会写 meta.prereq_skips 留痕）")
    p.set_defaults(func=cmd_node_finish)

    p = sub.add_parser("node-review", help="登记节点审阅记录（审阅 Agent 调用；FAIL/BLOCKED 必须附 evidence）")
    p.add_argument("node"); p.add_argument("--agent", required=True)
    p.add_argument("--result", required=True, choices=["PASS", "FAIL", "BLOCKED"])
    p.add_argument("--skills", required=True, help="审阅前已读 Skill，逗号分隔（声明）")
    p.add_argument("--evidence", help="审阅依据的证据路径，逗号分隔（FAIL/BLOCKED 必填）")
    p.add_argument("--summary", help="审阅结论摘要")
    p.add_argument("--scope-id", help="可选作用域 ID；省略时使用 legacy 节点审阅")
    p.add_argument("--round", type=int, help="作用域关联轮次（可选）")
    p.add_argument("--phase", choices=["CONTENT_REVIEW", "REVIEW", "FORMAT_REVIEW", "JOIN"],
                   default="REVIEW", help="scope 审阅阶段")
    p.add_argument("--allow-missing-mcp", action="store_true",
                   help="核心节点（N1/N3/N4/N5/N7）PASS 审阅豁免 MCP 检索留痕校验（仅离线/人工特批，须留痕说明）")
    p.add_argument("--allow-missing-lineage", action="store_true",
                   help="N2 PASS 审阅豁免数据血缘校验（仅离线/人工特批，须留痕说明）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_node_review)

    p = sub.add_parser("review-loop", help="生成节点自动审阅+返修循环序列（dry-run；防死循环/防空返修）")
    p.add_argument("node"); p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_review_loop)

    p = sub.add_parser("node-repair-check", help="返修哈希对比（防空返修：无产物变化视为空返修打回）")
    p.add_argument("node"); p.add_argument("--attempt", type=int, required=True); p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_node_repair_check)

    p = sub.add_parser("auto-check", help="H 门禁自动核查：委托配对核查 Agent 核验并生成核查报告，流程不挂起")
    p.add_argument("node"); p.add_argument("--gate", required=True, choices=["H1", "H2", "H3"])
    p.add_argument("--agent", required=True, help="核查 Agent（必须等于该节点配对审阅 Agent）")
    p.add_argument("--skills", required=True, help="核查前已读 Skill，逗号分隔")
    p.add_argument("--summary", default="自动核查通过"); p.add_argument("--report", help="核查报告文件路径（可选）")
    p.add_argument("--round", type=int); p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_auto_check)

    p = sub.add_parser("h-confirm", help="人工追认 H 门禁（auto_passed -> confirmed）")
    p.add_argument("gate", choices=["H1", "H2", "H3"]); p.add_argument("--note"); p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_h_confirm)

    p = sub.add_parser("result-validate", help="验证 Agent result.json 的协议、产物和哈希")
    p.add_argument("result", help="result.json 路径"); p.add_argument("--node"); p.add_argument("--run-id"); p.add_argument("--scope-id")
    p.add_argument("--dir", default="."); p.set_defaults(func=cmd_result_validate)

    p = sub.add_parser("result-ingest", help="验证并将 result.json 摘要合并到状态")
    p.add_argument("result", help="result.json 路径"); p.add_argument("--node"); p.add_argument("--run-id"); p.add_argument("--scope-id")
    p.add_argument("--dir", default=".")
    p.add_argument("--allow-empty-artifacts", action="store_true",
                   help="完成时豁免空产物校验")
    p.add_argument("--allow-no-checkpoint", action="store_true",
                   help="完成时豁免进度快照校验")
    p.add_argument("--skip-prereq", action="store_true",
                   help="完成时跳过完成守卫（仅供单测/迁移；会留痕）")
    p.set_defaults(func=cmd_result_ingest)

    p = sub.add_parser("project-audit", help="接手审计：题目比对/标准结构/节点首页/registry/状态-产物一致性/旧命名")
    p.add_argument("--source", help="题目原文路径（可选，与 problem_lock 比对）")
    p.add_argument("--dir", default="."); p.set_defaults(func=cmd_project_audit)

    p = sub.add_parser("upgrade-heal", help="升级自愈：检测旧版遗留（旧状态目录/旧文件名/旧节点目录/重复目录）→ 迁移修复 → 补建 → 复检")
    p.add_argument("--apply", action="store_true", help="实际迁移修复；默认只输出迁移计划")
    p.add_argument("--source", help="题目原文路径（可选）")
    p.add_argument("--dir", default="."); p.set_defaults(func=cmd_upgrade_heal)

    p = sub.add_parser("project-repair", help="按审计结果补建标准结构（目录/节点首页/registry/human_checkpoint）；题目锁定缺失需先 problem_guard create")
    p.add_argument("--apply", action="store_true", help="实际补建；默认只输出计划")
    p.add_argument("--source", help="题目原文路径（可选，用于检查锁定漂移）")
    p.add_argument("--dir", default="."); p.set_defaults(func=cmd_project_repair)

    p = sub.add_parser("report-list", help="列出留存的历史迭代报告（review/run/decision/result）")
    p.add_argument("--node"); p.add_argument("--round", type=int); p.add_argument("--scope")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--dir", default="."); p.set_defaults(func=cmd_report_list)

    p = sub.add_parser("round-start", help="开启一轮迭代（可选建分支；仅 N4/N5/N7/N8）")
    p.add_argument("node"); p.add_argument("--goal"); p.add_argument("--branch"); p.add_argument("--scope-id")
    p.add_argument("--git", action="store_true"); p.add_argument("--dir", default=".")
    p.add_argument("--skip-prereq", action="store_true",
                   help="跳过上游前置校验（仅供单测/迁移构造场景；会在 meta.prereq_skips 留痕）")
    p.set_defaults(func=cmd_round_start)

    p = sub.add_parser("round-score", help="记录一轮独立评分（仅 N4/N5/N7/N8）")
    p.add_argument("node"); p.add_argument("--round", type=int, required=True); p.add_argument("--scope-id")
    p.add_argument("--total", type=float,
                   help="0-10 整体分（主审阅者必填）。维度分工的第二审阅者只提交自己负责的维度，可省略")
    p.add_argument("--dims", required=True, help='JSON 字符串，如 \'{"correctness":8.0,"efficiency":7.0}\'')
    p.add_argument("--judge", required=True, help="独立评审 Agent")
    p.add_argument("--skills-read", required=True, help="评分 Agent 已阅读的评审 Skill，逗号分隔")
    p.add_argument("--evidence", required=True, help="评分依据的运行证据路径，逗号分隔")
    p.add_argument("--allow-missing-mcp", action="store_true",
                   help="本轮豁免 MCP 检索留痕校验（禁止纯内生输出的显式例外，仅离线/人工特批并留痕说明）")
    p.add_argument("--git", action="store_true")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_round_score)

    p = sub.add_parser("round-decide", help="按 termination 计算决策（仅 N4/N5/N7/N8）")
    p.add_argument("node"); p.add_argument("--round", type=int, required=True); p.add_argument("--scope-id")
    p.add_argument("--feedback")
    p.add_argument("--reason", help="未达标分支（repair_and_rerun/keep_best）必填：失败原因分析（根因/差距/下轮方案），写入 decision.failure_analysis")
    p.add_argument("--git", action="store_true"); p.add_argument("--dir", default=".")
    p.add_argument("--allow-empty-artifacts", action="store_true",
                   help="完成分支豁免空产物校验（仅异常情况，须说明原因）")
    p.add_argument("--allow-no-checkpoint", action="store_true",
                   help="完成分支豁免进度快照校验（仅单步节点，须说明原因）")
    p.add_argument("--skip-prereq", action="store_true",
                   help="完成分支跳过完成守卫（仅供单测构造场景；会留痕）")
    p.set_defaults(func=cmd_round_decide)

    p = sub.add_parser("scope-plan", help="为 N4/N5/N7/N8 创建可选作用域工作区与派发计划")
    p.add_argument("node", choices=["N4", "N5", "N7", "N8"])
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--scope-id")
    p.add_argument("--target")
    p.add_argument("--mode", choices=["adaptive", "static"], default="adaptive")
    p.add_argument("--max-chars", type=int, default=12000)
    p.add_argument("--attempt", type=int, default=1)
    p.add_argument("--run-id")
    p.add_argument("--scope-kind", choices=["adaptive", "chapter", "question", "static"], default=None,
                   help="兼容入口：adaptive/chapter/question；chapter/question 映射到 static 规划")
    p.add_argument("--apply", action="store_true", help="确认创建工作区（当前命令默认即写入；保留该参数兼容统一路由）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_scope_plan)

    p = sub.add_parser("scope-aggregate", help="聚合作用域阶段并阻断缺失阶段")
    p.add_argument("node", choices=["N4", "N5", "N7", "N8"])
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--scope-id")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_scope_aggregate)

    p = sub.add_parser("scope-promote", help="验证作用域并在全部通过后提升父节点")
    p.add_argument("node", choices=["N4", "N5", "N7", "N8"])
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--scope-id")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_scope_promote)

    p = sub.add_parser("case-add", help="沉淀一个优秀案例（含检索渠道与检索词）")
    p.add_argument("--title", required=True); p.add_argument("--source", required=True)
    p.add_argument("--url"); p.add_argument("--summary"); p.add_argument("--score", type=float)
    p.add_argument("--source-type", help="检索渠道 id（对应 search_sources.json，如 github-code/paper-academic）")
    p.add_argument("--query", help="命中该案例的检索词")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_case_add)

    p = sub.add_parser("case-search", help="Pro 案例库结构化检索（139 张 CUMCM 优秀论文案例卡，2012-2025；TF-IDF 加权，支持 --save 沉淀证据）")
    p.add_argument("query", help="问题描述/结构检索词，如「小样本 多指标 综合评价 稳健性」")
    p.add_argument("--top", type=int, default=6, help="返回 top-N（默认 6）")
    p.add_argument("--year", type=int, help="按年份过滤")
    p.add_argument("--type", dest="problem_type", help="按问题类型过滤（预测/评价/优化/聚类/网络/机理/仿真…）")
    p.add_argument("--model", help="按模型过滤（如 K-Means、遗传算法）")
    p.add_argument("--json", action="store_true", help="JSON 输出（供脚本消费）")
    p.add_argument("--skill-root", help="技能安装根目录（含 skills/；缺省按 MM_SKILL_ROOT 或向上探测）")
    p.add_argument("--save", action="store_true", help="将 top-N 命中案例沉淀进项目 state/cases/（证据链，供派发携带）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_case_search)

    p = sub.add_parser("search-source", help="检索地址注册表管理")
    ss = p.add_subparsers(dest="ss_cmd", required=True)
    p1 = ss.add_parser("add", help="新增/更新一个检索渠道")
    p1.add_argument("--id", required=True); p1.add_argument("--type", required=True)
    p1.add_argument("--name", required=True); p1.add_argument("--address", required=True)
    p1.add_argument("--tool"); p1.add_argument("--query-template")
    p1.add_argument("--apply-when", help="适用场景，逗号分隔"); p1.add_argument("--priority", type=int)
    p1.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_search_source_add)

    p = sub.add_parser("search-evidence", help="汇总节点检索证据派发清单（知识卡片/案例/台账/MCP 留痕，派发 Agent 时携带；禁止纯内生）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_search_evidence)

    p = sub.add_parser("dr-note", help="登记一次 Deep Research 介入（Deep Research 链嵌入迭代环的可审计留痕；落 dr-interventions.jsonl 并同步 rounds[n].deep_research）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--round", type=int, help="迭代轮次（可选；N4/N5/N7 每轮介入建议登记）")
    p.add_argument("--phase", choices=["SEARCH", "SCORE", "DECIDE", "NODE"], default="NODE",
                   help="介入所处迭代环节：SEARCH/SCORE/DECIDE/NODE(阶段)")
    p.add_argument("--role", required=True,
                   help="Deep Research 链角色：research_architect / literature / researcher / synthesis / report_compiler")
    p.add_argument("--topic", required=True, help="介入解决的问题/瓶颈/待论证点")
    p.add_argument("--input", help="输入（根因/failure_analysis/feedback/瓶颈描述）")
    p.add_argument("--output", help="产出（调研报告/方案/决策报告/知识卡片路径）")
    p.add_argument("--ref", help="依据参考（case id / mcp-calls / 卡片引用，逗号分隔）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_dr_note)

    p = sub.add_parser("dr-list", help="列出节点（+可选轮次）的 Deep Research 介入留痕（dr-interventions.jsonl + rounds[n].deep_research 汇总）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--round", type=int)
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_dr_list)

    p = sub.add_parser("dashboard-refresh", help="重建总状态工作栏")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=lambda a: (refresh_dashboard(os.path.abspath(a.dir)),
                                   print(f"[state_utils] dashboard-refresh: {os.path.abspath(a.dir)}")))

    p = sub.add_parser("claim", help="写子 Agent 租约（同 agent 重复认领与跨 agent 占用都拒绝）")
    p.add_argument("agent_id"); p.add_argument("--node", required=True); p.add_argument("--dir", default=".")
    p.add_argument("--ttl", type=int, default=3600, help="租约有效期秒数（默认 3600）")
    p.add_argument("--force", action="store_true", help="抢占其他 Agent 的有效租约（会留痕）")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("node-log", help="记录节点执行小步骤（追加 state/nodes/<name>/steps.md，时间线留痕）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--step", required=True, help="小步骤描述")
    p.add_argument("--by", default="", help="执行者（默认本节点 registry executor）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_node_log)

    p = sub.add_parser("checkpoint", help="子 Agent 分阶段归档：把当前进度快照落盘（中断可续跑，不必重来）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--phase", required=True, help="阶段标识（如 Phase 0 数据探查 / Phase 2 清洗）")
    p.add_argument("--done", action="append", default=[], help="已完成项（可多次传）")
    p.add_argument("--pending", action="append", default=[], help="待完成项（可多次传）")
    p.add_argument("--artifact", action="append", default=[], help="本阶段已产出的文件路径（可多次传，自动算 sha256）")
    p.add_argument("--note", default="", help="备注（决策/阻塞/下一步）")
    p.add_argument("--by", default="", help="执行者（默认本节点 registry executor）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_checkpoint)

    p = sub.add_parser("checkpoint-list", help="列出某节点的全部进度快照（续跑时读最后一条恢复现场）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--latest", action="store_true", help="只输出最近一条")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_checkpoint_list)

    # ---- 运行中纠正协议（主→子纠正留痕 / 子→主回执 / 派发句柄生命周期）----
    p = sub.add_parser("correction-add",
                       help="记录一条运行中纠正（主 Agent 调用；A3/B1 据此校验 CORRECTION_UNACKED）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--agent", required=True, help="被纠正的子 Agent（agent_id，回执必须由本人提交）")
    p.add_argument("--type", required=True,
                   help="纠正类型：需求变更/前提失效/范围纠正/门禁风险/冲突消解（也接受 requirement_change 等 code）")
    p.add_argument("--finding", required=True, help="主 Agent 观察到的事实与证据路径")
    p.add_argument("--requirement", required=True, help="本次必须如何调整；是否需要重跑")
    p.add_argument("--impact", default="", help="受影响的后续节点/产物")
    p.add_argument("--round", type=int, help="迭代轮次（可选）")
    p.add_argument("--delivery", choices=["steered", "queued", "resumed_background"], default="queued",
                   help="SendMessage 投递语义（默认 queued）")
    p.add_argument("--by", default="main-agent", help="登记人（默认 main-agent）")
    p.add_argument("--note", default="")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_correction_add)

    p = sub.add_parser("correction-ack",
                       help="回执一条纠正（子 Agent 本人调用；agent_id 必须与纠正记录一致，代签无效）")
    p.add_argument("correction_id", help="correction-add 返回的 correction_id")
    p.add_argument("--agent", required=True, help="回执人（必须等于纠正记录的 agent_id）")
    p.add_argument("--note", default="", help="如何落实/是否需要重跑")
    p.add_argument("--by", default="")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_correction_ack)

    p = sub.add_parser("correction-list", help="列出纠正留痕与回执状态（未回执的即 CORRECTION_UNACKED）")
    p.add_argument("--node", choices=list(NODES))
    p.add_argument("--unacked", action="store_true", help="只列未回执条目")
    p.add_argument("--json", action="store_true")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_correction_list)

    p = sub.add_parser("dispatch-start",
                       help="登记后台派发句柄 state/agents/<id>/dispatch.json（防僵尸 + 回收核对）")
    p.add_argument("agent_id")
    p.add_argument("--node", required=True, choices=list(NODES))
    p.add_argument("--round", type=int)
    p.add_argument("--must-load", default="", help="本批 must_load 技能清单，逗号分隔")
    p.add_argument("--writes", default="",
                   help="本 Agent 的写入目标（文件或目录，逗号分隔）——用于并行写冲突检测")
    p.add_argument("--task", default="", help="派发子任务摘要")
    p.add_argument("--ttl", type=int, default=1800, help="僵尸判定阈值秒数（默认 1800）")
    p.add_argument("--force", action="store_true", help="接管仍 running 的旧句柄（原 Agent 已失联）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_dispatch_start)

    p = sub.add_parser("dispatch-heartbeat", help="续期派发句柄（长任务主动报活）")
    p.add_argument("agent_id")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_dispatch_heartbeat)

    p = sub.add_parser("dispatch-close",
                       help="收尾派发句柄（done/failed/timeout/cancelled；--artifact 记产物哈希供回收核对）")
    p.add_argument("agent_id")
    p.add_argument("--status", required=True, choices=["done", "failed", "timeout", "cancelled"])
    p.add_argument("--artifact", action="append", default=[], help="产物路径（可多次传，自动算 sha256）")
    p.add_argument("--note", default="")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_dispatch_close)

    p = sub.add_parser("dispatch-list", help="列出派发句柄（running/已收尾/僵尸）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_dispatch_list)

    p = sub.add_parser("register-artifact", help="登记产物入库记录（文件必须落在节点产物目录内，否则拒绝）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--path", required=True, help="产物路径（相对项目根）")
    p.add_argument("--kind", default="", help="产物类型（dataset/figure/table/prose/code/report）")
    p.add_argument("--note", default="", help="说明")
    p.add_argument("--by", default="", help="登记者（默认本节点 registry executor）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_register_artifact)

    p = sub.add_parser("orphan-scan", help="孤儿文件扫描：找出落在节点产物目录之外、未被登记的文件")
    p.add_argument("--apply", action="store_true", help="把扫描结果写入 state/reports/orphan-files.json")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_orphan_scan)

    p = sub.add_parser("todo", help="项目任务清单动态更新（add 新增 / done 标记完成 / list 列出 / plan 按状态自动规划）")
    ts = p.add_subparsers(dest="action", required=True)
    ta = ts.add_parser("add", help="新增待办"); ta.add_argument("item")
    ta.add_argument("--node", default="", help="关联节点，如 N4"); ta.add_argument("--dir", default=".")
    td = ts.add_parser("done", help="按匹配文本标记未完成条目为完成"); td.add_argument("item")
    td.add_argument("--dir", default=".")
    tp = ts.add_parser("plan", help="按 decision_log 状态自动生成/更新全流程执行+审阅任务清单")
    tp.add_argument("--dir", default=".")
    tl = ts.add_parser("list", help="列出全部条目"); tl.add_argument("--dir", default=".")
    ta.set_defaults(func=cmd_todo); td.set_defaults(func=cmd_todo); tp.set_defaults(func=cmd_todo); tl.set_defaults(func=cmd_todo)

    p = sub.add_parser("cascade-invalidate", help="级联失效：上游产物变更/缺失 → 下游节点状态与门禁重置 pending（联动同步，默认预览）")
    p.add_argument("--node", default="", help="只检查该节点（默认全部 N1-N8）")
    p.add_argument("--apply", action="store_true", help="实际重置（不传为预览）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_cascade_invalidate)

    p = sub.add_parser("flow-coverage", help="全流程覆盖检查：预期调用的 Agent/Skill 集 vs 实际记录（查漏用/漏 skill）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_flow_coverage)

    p = sub.add_parser("handoff", help="生成/刷新节点交接文件 handoff.md（上游状态/门禁/产物哈希 + 输入输出约定 + 就绪判定）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("handover-review", help="接手复核：按 9 阶段逐节点检查；completed 节点强制复核审阅（门禁/产物漂移检测），发现问题→修改→复审")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_handover_review)

    # ---- 技能路由（协调层 → 专业 skill 的运行时接线）----
    p = sub.add_parser("skill-plan", help="生成本节点的专业 skill 派发清单（运行时扫描本机已装 skill 并匹配能力；--apply 落盘供门禁校验）")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--task", default="", help="按自由文本任务推断能力（省略则按节点阶段能力）")
    p.add_argument("--capability", help="追加能力 id，逗号分隔（词表见 shared/skill-routing/capability_taxonomy.json）")
    p.add_argument("--skill-root", action="append", help="追加 skill 扫描根目录（可多次）")
    p.add_argument("--apply", action="store_true", help="落盘 state/skill-routing/<节点>.json")
    p.add_argument("--allow-unresolved", action="store_true", help="能力无匹配时不打印警告")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_skill_plan)

    p = sub.add_parser("skill-list", help="列出本机已发现的 skill（或按能力排序候选），用于核对路由结果")
    p.add_argument("--capability", help="按能力 id 输出排序候选")
    p.add_argument("--scope", choices=["user", "user-agents", "plugin", "project"], help="按来源过滤")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_skill_list)

    p = sub.add_parser("skill-audit", help="硬门禁：校验本次声明的 skill 是否覆盖派发清单的 must_load")
    p.add_argument("node", choices=list(NODES))
    p.add_argument("--skills", required=True, help="实际已加载的 skill，逗号分隔")
    p.add_argument("--require-manifest", action="store_true", help="缺少派发清单时直接失败（默认按未启用处理）")
    p.add_argument("--dir", default=".")
    p.set_defaults(func=cmd_skill_audit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
