# 专项 5：8 类 BUG 全面排查与修复表

> 执行方式：契约/自检/测试/路径/引用/材料链路逐类实测 + 专项 1-4 与历史轮次累积修复核对。本文为最终排查表（发现 → 严重度 → 修复方案 → 修复状态）。
> 验证结论：`python scripts/lint_contracts.py` **零报错**；`python scripts/self_check.py` **全部健康**；`python -m unittest discover -s tests` **65 用例全通过**；仓库内文件引用断链扫描 **0 处**。

## 排查表

| # | 类别 | 发现的问题 | 严重度 | 修复方案（实际执行） | 状态 |
|:-:|------|-----------|:---:|----------------------|:----:|
| 1 | **契约一致性** | lint 原先 6 项失败：版本×3 漂移（mm-iteration-engine SKILL / state_utils 脚手架 / decision_log 模板 1.4.8 ≠ pyproject 1.5.0）、agents 断言 21≠24、agents 计数、commands 计数 5≠22；文档口径 21/5、mm-viz 12 vs 16 打架 | 高 | 版本统一 1.5.0（SKILL / state_scaffold / templates/decision_log / 三份 plugin.json 含 description）；lint 断言 24/34/22 且版本/LaTeX 检查改读拆分模块；README/能力盘点/冒烟/orchestrator 口径同步；mm-viz 统一 16 项 | ✅ lint 0 |
| 2 | **联动断裂** | deep-research 在 mm-iteration-engine **零引用**（学术未嵌入迭代）；17→16 个 /ars-* 在 /mm 中零路由；sync-and-compatibility 仅地图提及、无 agent 加载；知识卡片无派发落地；handoff 归属不清 | 高 | DR 融入迭代环 §7.2 + `dr-note`/`dr-list` 留痕 + Deep Research 链=每轮介入链（orchestrator §3.1）；主控 SKILL 新增 /ars-* 路由表 + 按阶段加载；sync-and-compatibility 在 orchestrator Phase 0 与主控材料复用协议显式加载（专项 2 补丁）；`search-evidence` 派发落地；**handoff 分域说明**：`shared/handoff_schemas.md` 为 ARS 学术交接契约（deep-research→paper 等 Schema），数学建模环节交接由 `state_utils write_handoff` 按迭代引擎 §3.4 生成——两套各自服务对应流水线，非冲突 | ✅ |
| 3 | **迭代逻辑** | "每轮重新检索、禁止纯内生"只有文档铁律无机器校验；DECIDE 不达标不写失败原因；轮次间知识卡片无引用传递 | 高 | `round-score`（N4/N5/N7）本轮检索留痕门禁（跨轮不通用，测试实证）；`round-decide` 未达标分支强制 `--reason` → `decision.failure_analysis`；**本轮新增** `rounds[n].knowledge_cards`（命名 `{节点}_r{轮}_*.md`，评分自动采集）实现卡片传递；termination/merge/result-ingest 均正确（code 7.0/8.0/≤5；paper 6.5/7.5/≤4；≥pass 才 merge；自评拒绝有测试） | ✅ 65 测试 |
| 4 | **MCP 协同** | mcp_boot_check.py 零单测；留痕路径歧义（"handoff 或 mcp-calls.jsonl"）；N8 缺乏"迭代无新检索"校验点；Tavily 回退健壮性待确认 | 高 | 新增 `tests/test_mcp_gates.py` 13 用例（无留痕拒绝/豁免/跨轮不通用/失败原因/N8 豁免/search-evidence）；`call-hierarchy.md` 统一 `state/reports/mcp-calls.jsonl` 为唯一机器事实源；**N8 终检**：`rounds[n].knowledge_cards` 非空 = "迭代有新检索"校验（validation-checkpoints §4）+ `mcp_boot_check.py --coverage/--ledger`；Tavily→tokenhub 回退已在启动自检实现（MANDATORY 常量 `tavily/tokenhub`） | ✅ |
| 5 | **状态流转** | templates/decision_log 与脚手架 `skill_version` 漂移；state_utils 拆分后 argparse 模块解析 NameError；单写者/级联/断点/git commit 需证实 | 中 | 版本字段全部 1.5.0；facade 显式接管导入 + `__all__` 含 stdlib 与跨模块助手；单写者（orchestrator 唯一写 decision_log，子 Agent 只写 result.json）+ 状态变更单独 git commit（State-Sha）协议；node-start/log/finish/review 调用链与 cascade-invalidate/断点恢复均有测试覆盖 | ✅ |
| 6 | **路径引用** | mm-iteration-engine SKILL §15 引用不存在的 `scripts/state_utils.py`；ARS 三 agent 文件名（report_compiler_agent）与派发别名（ars_report_compiler）前后缀不一致；一次 heredoc 转义导致模板字符串中断 | 中 | SKILL 路径修正 + 拆分模块说明；orchestrator/主控补"ARS 命名映射"（文件↔派发别名双名等价）；修复 `sha256_of_bytes` 字符串；**仓库内文件引用断链扫描 0 处**（agents/commands/mcp/docs/skills 中 `scripts/`、`skills/`、`shared/` 等前缀引用全部在库；`state/` 运行时路径为项目构件，合法） | ✅ |
| 7 | **材料导入** | init 复制循环旧逻辑只复制固定 5 模块，拆分后项目内 CLI 崩溃；材料导入全链需实测 | 高 | `state_scaffold.py` 复制循环改为复制同目录全部 `.py` 模块；`detect→organize→material-plan→sync_import` 链路测试覆盖（不覆盖原文件/自动归档/哈希可追溯）；legacy 材料进入 `Code/legacy` 由 N4 审阅修复、Markdown→LaTeX 转换任务（`state/latex_conversion`）正确生成并处理 | ✅ |
| 8 | **学术竞赛割裂** | 初版无两套独立流程，但学术能力未深嵌：deep-research 不进迭代环、/ars-* 无路由、shared/ 学术契约归属不清——融合不彻底 | 高 | 无两套迭代机制并存（DR 自动迭代审阅并入 mm-iteration-engine §7.2，`dr-note` 统一留痕）；deep-research 在 N1/N3/N4/N5/N7/N8 持续嵌入（专项 3/4 文档）；/ars-* 16 命令统一路由嵌入 /mm 各阶段（主控 SKILL 路由表）；shared/ 学术契约分域遵循（handoff_schemas→ARS、建模环节交接→write_handoff）；Skill 按阶段组合加载（34 无闲置） | ✅ |

## 实际修复的文件清单（本会话累计）

**代码/机器校验**
- `scripts/lint_contracts.py`（数量断言 24/34/22、版本与 LaTeX 检查改读拆分模块）
- `skills/mm-iteration-engine/scripts/`：`state_utils.py` 拆分 → `state_defs/scaffold/nodes/review/audit/rounds/search` + 薄 facade；`state_defs.py`（MCP 必调常量、mcp_search_evidence/require_mcp_search_evidence/collect_round_cards 辅助、`DR_INTERVENTIONS_FILE`）；`state_rounds.py`（round-score 检索门禁 + `knowledge_cards`、round-decide `--reason`→failure_analysis）；`state_review.py`（node-review PASS 检索门禁）；`state_search.py`（search-evidence、dr-note、dr-list）；`state_scaffold.py`（复制全部 .py 模块）
- 版本同步：`.claude-plugin|.codex-plugin|.zcode-plugin/plugin.json`、`skills/mm-iteration-engine/SKILL.md`、`templates/state/decision_log.json`

**测试**
- `tests/test_mcp_gates.py`（13 新增：检索门禁/豁免/跨轮/失败原因/N8 豁免/search-evidence）
- `tests/test_dr_intervention.py`（10 新增：DR 留痕/轮次同步/**轮次知识卡片**/规格一致性）
- `tests/test_workflow_contracts.py`（setUp 种子化 MCP 留痕；低分用例补 --reason）

**编排与协议文档**
- `agents/orchestrator.md`（DR 链 §3.1、迭代协议 SEARCH/SCORE/DECIDE、ARS 命名映射、sync-and-compatibility 接线、调用地图 24/34）
- `skills/mathematical-modeling/SKILL.md`（协作闭环浓缩表、/ars-* 路由表、按阶段加载、材料复用加载）
- `skills/mm-iteration-engine/SKILL.md`（§7 迭代环、§7.2 DR 融入+卡片派发、§9 锚点、§13 命令、拆分说明）
- `commands/mm-help.md`（22 命令全量清单；/ars-* 计数校正）
- `mcp/call-hierarchy.md`（jsonl 唯一事实源）；`docs/冒烟验证报告.md`、`能力盘点.md`、`README.md`、`CHANGELOG.md`（口径与版本）
- `docs/optimization/`：重叠合并清单 / 组件盘点与合并规划 / agent-collaboration-loop / deep-research-迭代融合报告 / 8类BUG修复报告 / mcp-检索卡片体系 / skill组合加载与命令路由 / 全组件联动地图

## 验证结果

| 检查 | 结果 |
|------|------|
| `python scripts/lint_contracts.py` | ✅ 契约检查通过（exit 0） |
| `python scripts/self_check.py` | ✅ 全部健康（版本/契约/用户级同步） |
| `python -m unittest discover -s tests -p 'test_*.py'` | ✅ 65 用例全通过 |
| 仓库内文件引用断链扫描 | ✅ 0 处 |
| registry ↔ NODES（lint 强制） | ✅ 双份一致 |
| 版本单一来源 | ✅ 全部 1.5.0 |
