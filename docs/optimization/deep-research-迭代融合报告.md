# Deep Research 迭代融合报告（mm-iteration-engine SEARCH→DECIDE ↔ deep-research）

> 目标：把学术研究能力（Deep Research 自动迭代审阅）与数学建模迭代环**完全打通**——每轮 SEARCH 做根因分析与方案论证、SCORE 核查先进性、DECIDE 不达标时分析失败原因；迭代每轮强制重新检索、禁止纯内生输出；检索结果沉淀知识卡片并在后续派发时分发给对应 Agent。
>
> 交付：2026-08-19 ｜ 验收：`python scripts/lint_contracts.py` 零报错 + `python -m unittest discover -s tests` 全通过（含 13 个新增 MCP 门禁用例）

## 1. 现状基线（整改前缺口，实证）

- `grep -c "deep-research" skills/mm-iteration-engine/*.md` = **0**：迭代引擎对 deep-research **零引用**，学术能力未嵌入迭代环（学术-竞赛割裂的核心证据）；
- `SEARCH → DECIDE` 的"每轮重新检索、禁止纯内生"仅停留在文档铁律层（`mcp/call-hierarchy.md`），`state_utils.py` 无机器校验，存在"纯内生也能评分/过审"的漏洞；
- SEARCH 无"根因分析 + 方案论证"要求；DECIDE 不达标分支（repair_and_rerun/keep_best）不强制写失败原因；
- 知识卡片（`state/reports/mcp-cards/`）只有模板与文档约定，无"派发到对应 Agent"的落地入口。

## 2. 融合设计

```
┌─────────────────────────────── mm-iteration-engine 迭代环（N4/N5/N7/N8）────────────────────────────────┐
│                                                                                                          │
│  SEARCH  ── ① 根因分析（上轮 DECIDE failure_analysis / SCORE feedback / audit）                          │
│           → ② 方案论证（为何选此方案/渠道）                                                               │
│           → ③ 强制重新检索（search_sources 选源：MCP/websearch/paper-mcp/gh_grep/context7/竞赛论文库）     │
│              命中→ case-add 沉淀 cases/ + 知识卡片沉淀 state/reports/mcp-cards/ + 留痕 mcp-calls.jsonl     │
│           → 需系统性文献调研时按需唤起 deep-research（ars_research_architect/synthesis/report_compiler）   │
│           │  结果回填本轮依据（针对性调研失败根因）                                                        │
│  IMPLEMENT → RUN → COMMIT                                                                                 │
│  SCORE    配对审阅 Agent 五维评分；🔴 机器校验：本轮无检索留痕→ round-score 拒绝评分（禁止纯内生）         │
│           🔴 先进性核查：innovation/建模创造性 与 case_refs/SOTA/获奖论文对比给分，无外部基线 ≤6 [NO-BASELINE]│
│  DECIDE   ≤达标分支 → 强制 --reason 失败原因分析（根因/差距/下轮方案）→ decision.failure_analysis         │
│           │ 作为下一轮 SEARCH ① 的输入（Deep Research 自动迭代审阅的落点）                                │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
知识卡片派发：委派任一节点前 `python state/state_utils.py search-evidence <Nx>`
→ 汇总该节点 知识卡片/案例/GB-T7714 台账/MCP 留痕 → 随派发 prompt/handoff 分发给执行与审阅 Agent
```

## 3. 落点文件与改动

| 层 | 文件 | 改动 |
|----|------|------|
| 文档/协议 | `skills/mm-iteration-engine/SKILL.md` | related_skills + §7 迭代环改造（SEARCH 根因/方案论证、SCORE 先进性核查、DECIDE 失败原因）+ 新增 §7.2"Deep Research 自动迭代审阅 + 知识卡片派发" + §9 评分锚点 + §13 命令与拆分说明 + §15 引用 |
| 文档/协议 | `agents/orchestrator.md` | 迭代循环执行协议升级为"①根因→②方案→③强制重检索 + 按需 Deep Research + SCORE 机器校验 + DECIDE --reason + search-evidence 派发" |
| 文档/协议 | `skills/mathematical-modeling/SKILL.md` | Integration with Sub-Skills 补 deep-research/academic-paper-reviewer/humanizer 按阶段加载；新增 /ars-* 路由表 |
| 机器校验 | `state_defs.py`（拆分后核心模块） | `MCP_MANDATORY_NODES`（N1/N3/N4/N5/N7 必调表）+ `MCP_CALLS_FILE` + `mcp_search_evidence()` + `require_mcp_search_evidence()`（禁止纯内生硬门禁，`--allow-missing-mcp` 显式豁免） |
| 机器校验 | `state_rounds.py` | `round-score` 本轮检索留痕门禁；`round-decide` 未达标分支强制 `--reason`（写入 `decision.failure_analysis`） |
| 机器校验 | `state_review.py` | `node-review` PASS（N1/N3/N4/N5/N7）检索留痕门禁 |
| 机器校验 | `state_search.py` | 新增 `cmd_search_evidence`（知识卡片/案例/台账/留痕派发清单） |
| CLI | `state_utils.py`（facade） | 新增 `search-evidence` 子命令 + `--allow-missing-mcp` / `--reason` 参数注册 |
| 测试 | `tests/test_mcp_gates.py` | 13 用例覆盖：无留痕拒绝 / 有留痕通过 / 豁免 / 跨轮不通用 / 失败原因强制 / N8 豁免 / search-evidence |
| 测试 | `tests/test_workflow_contracts.py` | setUp 种子化检索留痕（等价真实 MCP 调用）；低分用例补 `--reason` |

> 配合性重构：`state_utils.py`（2966 行）按领域拆分为 `state_defs / state_scaffold / state_nodes / state_review / state_audit / state_rounds / state_search` + 薄 facade（227 行），`init` 复制全部兄弟模块进项目 `state/`，CLI 用法不变——可维护性提升的同时零行为回归（55 测试全绿）。

## 4. 机器校验语义（"禁止纯内生输出"的执行路径）

- **触发**：`round-score`（N4/N5/N7，本轮）与 `node-review`（N1/N3/N4/N5/N7，PASS）→ `require_mcp_search_evidence`；
- **判定**：`state/reports/mcp-calls.jsonl` 存在该节点（+该轮）行，**或** `state/cases/index.json` 该轮 `used_in_rounds` 命中 → 通过；否则 `sys.exit` 拒绝并提示"禁止纯内生输出"；
- **豁免**：`--allow-missing-mcp` 显式传入才放行（仅离线/人工特批，须在交付说明留痕）；
- **失败原因**：`round-decide` 当 `action ∈ {repair_and_rerun, keep_best}` 且无 `--reason` → 拒绝；通过后写入 `rounds[n].decision.failure_analysis`；
- **先进性**：`round-score` 允许维度给分，但创新/创造性维度的评分依据必须来自审阅 Agent 对照外部基线（SKILL §9 锚点已写死"无基线 ≤6 [NO-BASELINE]"，由 mm-code-reviewer/reviewer 执行时遵守）。

## 5. 验收与回归

- `python scripts/lint_contracts.py` → `契约检查通过`（exit 0）；
- `python -m unittest discover -s tests -p 'test_*.py'` → 55 用例 OK（原 42 + 新 13）；
- 项目内副本自包含：`init` 后 `python state/state_utils.py <命令>` 正常（含 node-finish/dashboard-refresh/search-evidence）。

## 6. 边界与后续

- Deep Research 触发是"**按需**"而非每轮强调——一轮不达标需深挖根因或 SEARCH 需系统性调研时才唤起，避免无区别地拖慢迭代；强制的仅是"检索留痕 + 失败原因 + 先进性参照"这三个机器可判定契约。
- **统一规格**：9 阶段协作闭环 / Deep Research 嵌入点清单 / 迭代环融合方案的完整口径见 `docs/optimization/agent-collaboration-loop.md`（本报告为其融合方案详述；每轮介入用 `dr-note`/`dr-list` 可审计留痕）。
- 后续可把 `deep-research` 的失败根因调研报告格式与 `decision.failure_analysis` schema 做字段级对齐（当前以自由文本 + `search-evidence`/`dr-note` 派发留痕为主）。
