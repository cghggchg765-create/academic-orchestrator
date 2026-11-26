#!/usr/bin/env bash
# version: 2.0.0
#
# SessionStart hook for the academic-orchestrator plugin.
#
# Injects routing doctrine into the first turn so that, even in a plain chat
# (no /mm command), the main agent knows HOW to route academic work: load the
# orchestration protocol, dispatch per-node subagents, and never inline-edit
# node artifacts.
#
# Why this exists: subagent definitions are not auto-invoked, and no built-in
# routing forces the main agent to use them. Observed incident (2026-08): a
# plain "审阅并修改论文" request made the main agent load mm-latex-writing itself
# and edit every .tex inline — no state protocol, no reviewer, no compile verify.
#
# 2.0.0 rework: the old text was stale in ways that actively misled the agent
# every single session — it advertised the pre-rename namespace
# (math-modeling-agent-system:), claimed 24 Agent / 34 Skill / 22 命令, and told
# the agent to load skills that were physically deleted in 2.0.0 (xlsx,
# drawio-skill, theme-factory, make-pdf) plus /ars-* commands this repo no longer
# ships. Counts are now read from .zcode-plugin/plugin.json so they cannot drift.
#
# Contract: reads SessionStart JSON on stdin, emits
# hookSpecificOutput.additionalContext, always exits 0 (never block a session).
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

# --- 从 plugin.json 读取真实版本与组件计数（单一事实源，避免再次漂移）---
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-${ZCODE_PLUGIN_ROOT:-}}"
VERSION="?"
NDESC=""
if [[ -n "${PLUGIN_ROOT}" ]]; then
  MANIFEST="${PLUGIN_ROOT}/.zcode-plugin/plugin.json"
  if [[ -f "${MANIFEST}" ]]; then
    if command -v python >/dev/null 2>&1; then
      READ=$(python - "${MANIFEST}" <<'PY' 2>/dev/null || true
import json, re, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(0)
ver = d.get("version", "?")
desc = d.get("description", "") or ""
m = re.search(r"(\d+)\s*个\s*Skill\s*\+\s*(\d+)\s*个\s*Agent\s*\+\s*(\d+)\s*个命令", desc)
counts = f"{m.group(2)} Agent / {m.group(1)} Skill / {m.group(3)} 命令" if m else ""
print(ver, "|", counts)
PY
)
      if [[ -n "${READ}" ]]; then
        VERSION="${READ%%|*}"
        NDESC="${READ#*|}"
        VERSION="$(printf '%s' "${VERSION}" | tr -d '[:space:]')"
        NDESC="$(printf '%s' "${NDESC}" | sed 's/^ *//')"
      fi
    fi
  fi
fi

CORE_NOTE="${NDESC:-组件计数见 scripts/lint_contracts.py 的 EXPECTED_COUNTS}"

case "${SOURCE}" in
  compact|resume)
    ANNOUNCE="academic-orchestrator v${VERSION} 已加载。先判轨再动手：普通论文/综述/审稿/绘图/数据分析走通用学术轨（本插件提供编排骨架，学术界主体能力由 academic-research-skills 提供）；数学建模竞赛走建模轨（/mm* + mathematical-modeling）。禁止把竞赛规则套到普通论文上。"
    ;;
  startup|clear|*)
    ANNOUNCE="academic-orchestrator v${VERSION} 已加载（${CORE_NOTE}）。

🔴 第一步永远是判轨（判错比不做更糟）：

【A 通用学术轨】论文写作/修订、文献综述、深度研究、模拟审稿、去 AI 化、数据分析、出版级绘图、LaTeX 排版、PDF/Word/Excel 交付。
  · 本插件提供：编排协议 academic-orchestration、状态机与门禁、graph/table 文献对标 figure-table-benchmark、去AI化 humanizer + academic-humanize、LaTeX 质检 latex-guard、图表规范 mm-visualization、运行时路由 mm-skill-router。
  · 学术界主体能力由外部插件 academic-research-skills 提供：academic-paper / deep-research / academic-paper-reviewer / academic-pipeline。本插件不再持有其副本。
  · 其余专业能力（表格 xlsx、演示 pptx、Word docx、PDF、绘图等）由 mm-skill-router 运行时扫描本机已装 skill 自动匹配；未安装则该能力记为 unresolved，如实报告，不要假装可用。

【B 数学建模竞赛轨】仅当用户明确是数学建模竞赛（CUMCM/MCM/校赛、赛题、A/B/C/D/E 题）时启用：/mm 总控、mathematical-modeling、mm-problem-analysis、mm-model-library、mm-iteration-engine、mm-self-review、mm-latex-writing。

【C 混合】竞赛项目内的论文写作/绘图走 B 轨规范；通用润色与代码调试可借用 A 轨能力。

🔴 派发规则：
- 主 Agent 就是编排者：先加载 academic-orchestration，再按 registry 逐节点派发。不存在可委托的 orchestrator agent。
- 子 Agent 无法再派子 Agent（宿主剔除 Agent/Task 工具），所有派发由主 Agent 在顶层完成。
- 竞赛轨节点产物（ProblemInfo/、Data/、ModelDocs/、Code/、ResultFigures/、ReportPaper/）必须由对应子 Agent 执行，禁止主对话内联代做。
- 派发时把 state/skill-routing/<节点>.json 的 must_load 写进 prompt；子 Agent 必须逐个加载并声明。
- 长任务必须分阶段归档：每个 Phase 结束跑 state_utils.py checkpoint，中断后 checkpoint-list 续跑。

🔴 门禁不可绕过：
- 审阅类门禁（M1/D1/P1/P2/T1/V1/B1/W2/A3）只能由 node-review 落盘，gate-set 无法伪造 PASS。
- N2 的 D1 要求数据血缘台账通过 validate_data_lineage.py（raw 锁定 + 链式连续 + 变换可复现）。
- N6/N7/N8 的 B1 要求图表/表格文献对标矩阵（≥3 篇同领域论文）。

命令速查：/mm 建模总控、/mm-iterate 迭代、/mm-audit 接手审计、/mm-help 总览、/academic-update 上游更新检查。"
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
