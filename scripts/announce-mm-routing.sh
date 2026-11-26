#!/usr/bin/env bash
# version: 1.0.0
#
# SessionStart hook script for the math-modeling-agent-system plugin.
#
# Injects the MM routing doctrine into the LLM's first turn so that, even in a
# plain chat (no /mm command), the main agent knows HOW to route "审阅/修改/
# 润色/质检论文" style requests: delegate to the specialized subagents via the
# Agent tool, forbidden to inline-edit node artifacts, and complete the
# verify loop (writing → reviewer → latex_linter → compile) before returning.
#
# Why this exists: subagent definitions are all `mode: subagent` + `hidden: true`
# and no built-in routing forces the main agent to use them. Before this hook,
# a plain chat request like "审阅并修改论文" caused the main agent to load
# `mm-latex-writing` itself and edit every .tex inline — no state protocol, no
# reviewer, no latex_linter, no compile verify (observed incident, 2026-08).
#
# Same contract as announce-ars-loaded.sh: reads the SessionStart event JSON on
# stdin, emits hookSpecificOutput.additionalContext. Exit 0 always; on any
# parse/emit failure it must never block the session.
#
# Bash 3.2 / POSIX sh compatible (runs under Git Bash on Windows).

set -euo pipefail

INPUT=""
if [[ ! -t 0 ]]; then
  INPUT=$(cat)
fi

SOURCE="startup"
if [[ -n "${INPUT}" ]]; then
  if [[ "${INPUT}" =~ \"source\"[[:space:]]*:[[:space:]]*\"([a-z]+)\" ]]; then
    SOURCE="${BASH_REMATCH[1]}"
  fi
fi

case "${SOURCE}" in
  compact|resume)
    ANNOUNCE="学术研究与数学建模系统已加载（通用学术 + 建模双轨）。先判定任务属于哪一轨再动手：普通论文/综述/审稿/绘图/数据分析 → 通用学术轨（academic-paper / deep-research / academic-paper-reviewer / visualization）；数学建模竞赛 → 建模轨（/mm* 命令 + mathematical-modeling）。禁止把竞赛规则套到普通论文上。"
    ;;
  startup|clear|*)
    ANNOUNCE="学术研究与数学建模多智能体系统已加载：24 Agent / 34 Skill / 22 命令。

🔴 第一步永远是分流（判错轨比不做更糟）：

【A 通用学术轨】论文写作与修订、文献综述、深度研究、模拟审稿、去 AI 化、数据分析与统计解释、出版级绘图、LaTeX 排版编译、PDF/Word/Excel 交付 —— 不要求是竞赛场景。
  典型入口：academic-paper（写作/修订/摘要/格式转换）、deep-research（调研/综述/fact-check）、academic-paper-reviewer（审稿）、academic-pipeline（端到端）、humanizer + academic-humanize（去 AI 味）、visualization（出版级图表）、latex-guard（LaTeX 编译排错）、make-pdf（Markdown→PDF）、xlsx / drawio-skill / theme-factory（交付物与图示）。

【B 数学建模竞赛轨】仅当用户明确是数学建模竞赛（CUMCM/MCM/校赛、赛题、A/B/C/D/E 题、提交论文比赛）时启用：/mm 总控、mathematical-modeling、mm-problem-analysis、mm-model-library、mm-iteration-engine、mm-self-review、mm-latex-writing（国赛 10 节结构与 20 页限制）。

【C 混合】竞赛项目内的论文写作/绘图 → 走 B 轨规范；其中通用的表达润色与代码调试可借用 A 轨技能。

🔴 派发规则：
- 有对应专业子 Agent（writing/reviewer/visualization/latex_linter/humanize/coder/analyze/literature 等）时优先派发，subagent_type=math-modeling-agent-system:<name>；简单单点任务可直接加载对应 Skill。
- 竞赛轨的节点产物（state 协议、ProblemInfo/、ResultFigures/、ReportPaper/）必须由子代理执行，主对话不内联代做。
- 通用轨没有这个限制：常规论文写作/润色可直接完成，涉及长流程或需独立审阅时再派发。

🔴 与外部插件的协作（不要重复造轮子）：
- 若已装 academic-research-skills 且其 academic-paper / deep-research / academic-paper-reviewer / academic-pipeline 更贴合任务，可直接用它的版本（含完整 ARS 管线）；本插件同名技能提供等价能力，二者择一，不要同时驱动。
- 电子表格优先 spreadsheets:xlsx，演示文稿优先 presentations:pptx，Word 优先 documents:docx；本插件 xlsx/theme-factory 作为补充。
- 用户级 AGENTS.md 的结构优先规则同样适用：skill 明确要求的结构优先于通用默认骨架。

命令速查：/mm 建模总控、/mm-iterate 迭代、/mm-audit 接手审计、/ars-* 学术支撑。详见 docs/optimization/skill组合加载与命令路由.md。"
    ;;
esac

escape_json() {
  local raw="$1"
  raw="${raw//\\/\\\\}"
  raw="${raw//\"/\\\"}"
  raw="${raw//$'\n'/\\n}"
  raw="${raw//$'\r'/}"
  if command -v tr >/dev/null 2>&1; then
    raw="$(printf '%s' "${raw}" | LC_ALL=C tr -d '\001-\037')"
  fi
  printf '%s' "${raw}"
}

ESCAPED=$(escape_json "${ANNOUNCE}")

cat <<JSON
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"${ESCAPED}"}}
JSON

exit 0
