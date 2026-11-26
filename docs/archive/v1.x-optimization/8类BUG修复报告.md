# 8 类 BUG 修复报告（全面排查整改）

> 对照任务要求八类：①契约一致性 ②联动断裂 ③迭代逻辑 ④MCP 协同 ⑤状态流转 ⑥路径引用 ⑦材料导入 ⑧学术竞赛割裂。
> 每类给出：现象（实证）→ 根因 → 修复动作（文件）→ 验证。终验：`lint_contracts.py` 零报错、`unittest` 全通过。

## ① 契约一致性

- **现象**：`python scripts/lint_contracts.py` 报 6 项失败——版本 ×3（mm-iteration-engine/SKILL.md、state_utils scaffold、decision_log 模板均 1.4.8 ≠ pyproject 1.5.0）、`agents/` 断言 21 ≠ 实际 24、`agents/` 计数 24 ≠ 期望 21、`commands/` 计数 22 ≠ 期望 5。
- **根因**：ARS v3.21.0 融合后组件数从 21/5 涨到 24/22，但 lint 数量断言、三份 plugin.json version、README/能力盘点/冒烟报告口径未同步；mm-viz-reviewer 核对项 12 与 16 口径打架。
- **修复**：
  - 版本统一 1.5.0：`skills/mm-iteration-engine/SKILL.md`、`scripts/state_utils.py`(scaffold)、`templates/state/decision_log.json`、三份 `plugin.json`（含 description 24/34/22）；
  - lint 断言改 24/34/22（`check_component_counts` / `check_plugin_manifest`），版本/LaTeX 检查改读拆分后的 `state_scaffold.py`；
  - 文档口径：README / 能力盘点.md / docs/冒烟验证报告.md / orchestrator.md 全部"21 Agent、5 命令"→"24/34/22"；mm-viz-reviewer 数字统一为 16 项。
- **验证**：lint 零报错（exit 0）。

## ② 联动断裂

- **现象**：deep-research 在 mm-iteration-engine **零引用**（`grep` 计数 0）；17 个 `/ars-*` 命令在 `/mm` 体系中**零路由**；知识卡片无"派发"落地。
- **根因**：数学建模主线与 ARS 学术侧物理平铺、互不接线。
- **修复**：
  - `mm-iteration-engine/SKILL.md` §7.2 新增"Deep Research 自动迭代审阅 + 知识卡片派发"；
  - `mathematical-modeling/SKILL.md` 新增"/ars-* 专项命令路由"节（16 命令 × /mm 需求映射表）+ Integration with Sub-Skills 补 ARS 按阶段加载；
  - `commands/mm-help.md` 更新为 22 命令全量清单 + 路由说明；
  - `orchestrator.md` 迭代协议融入 Deep Research、`search-evidence` 派发。
- **验证**：grep deep-research 于 mm-iteration-engine SKILL 现为多行命中；主控 SKILL 含路由表。

## ③ 迭代逻辑

- **现象**："每轮重新检索、禁止纯内生"只有文档铁律，无机器强制；SEARCH 无根因分析/方案论证；DECIDE 不达标不写失败原因。
- **修复**（机器强制，见迭代融合报告 §3/§4）：
  - `round-score`（N4/N5/N7）本轮检索留痕门禁（`require_mcp_search_evidence`）；跨轮留痕不通用（新增测试验证）；
  - `round-decide` 未达标分支强制 `--reason` → `decision.failure_analysis`（下一轮 SEARCH 根因输入）；
  - SKILL §7 细化 SEARCH①根因→②方案论证→③强制重检索；SCORE 先进性核查（无基线 ≤6 [NO-BASELINE]）。
- **验证**：`tests/test_mcp_gates.py` 5 个迭代逻辑用例全过（含"留痕在 round1，round2 拒绝"）。

## ④ MCP 协同

- **现象**：`mcp_boot_check.py` 具备 --report/--coverage/--ledger 子命令但零单测；`call-hierarchy.md` 留痕口径"handoff 或 mcp-calls.jsonl"有歧义。
- **修复**：
  - `call-hierarchy.md` 统一：`state/reports/mcp-calls.jsonl` 为唯一机器事实源（round-score/node-review 门禁、--coverage、N8 终检共用），handoff 仅可读视图；
  - 新增 `tests/test_mcp_gates.py` 覆盖 N1 无必调记录→拒绝、N4 无本轮留痕→拒绝、豁免、N8 不强制；
  - Tavily→tokenhub 回退声明与 `checkpoint-0-boot.md`/`mm-boot.md` 一致（文档核对无误）。
- **验证**：11 个 MCP 协同相关用例通过。

## ⑤ 状态流转

- **现象**：`decision_log.json` 模板/脚手架 `skill_version` 停在 1.4.8；`if __name__=="__main__"` 与 argparse 曾因拆分产生 `argparse` 未定义（NameError）。
- **修复**：
  - 模板与脚手架 `skill_version` → 1.5.0；
  - 拆分后 facade 显式接管 `argparse/os/sys` 导入与 `sys.path` 插入，`__all__` 同时导出 stdlib 与跨模块下划线助手（`_is_placeholder_row`），消除 NameError；
  - lint 版本/LaTeX 检查改读新模块位置。
- **验证**：dump/init/node-finish/dashboard-refresh/search-evidence 全链路 CLI 正常；42 个原流程测试覆盖状态流转无回归。

## ⑥ 路径引用

- **现象**：`mm-iteration-engine/SKILL.md` §15 引用 `scripts/state_utils.py` 但该文件**不存在**（实际在 `skills/mm-iteration-engine/scripts/`）；ARS 三 agent 文件名（`report_compiler_agent` 等）与文档引用（`ars_report_compiler` 等）前后缀不一致；拆分裂析中一次 heredoc 双反斜杠折叠导致模板字符串中断。
- **修复**：
  - SKILL §15 路径修正 + 拆分模块说明；
  - orchestrator/主控 SKILL 补 **ARS agent 命名映射**（文件 `research_architect_agent` 等 = 派发别名 `ars_research_architect` 等，双名等价）；
  - state_defs 中 `sha256_of_bytes(...)` 修复为 `str("\n").join(...)`（消除真实换行）。
- **验证**：grep 确认三 agent 双名均被系统引用；py_compile 全过。

## ⑦ 材料导入

- **现象**：init 复制循环只复制固定 5 个兄弟模块，拆分后新模块（state_defs 等）缺失 → 项目内 CLI 崩溃；材料导入链 detect/organize/material-plan 的文档调用与 CLI 需核对。
- **修复**：
  - `state_scaffold.py` 复制循环改为**复制同目录全部 `.py` 模块**（未来新增模块自动带上）；
  - 核对 `orchestrator_runtime.py`：`detect_existing_materials`（L224）/`organize_existing_materials`（L267）/`material_intake_plan`（L342）与 `--material-plan` CLI（L428）齐全，`sync_import.py` 用法与测试一致（`test_import_preserves_source...` 等通过）。
- **验证**：`init` 后项目 `state/` 含全部 13 个运行态 `.py`，`python state/state_utils.py node-finish N0` 正常。

## ⑧ 学术竞赛割裂

- **现象**：deep-research 未进迭代环、`/ars-*` 未嵌入 `/mm`、知识卡片无派发。
- **修复**：同 ②（路由 + 按阶段加载 + search-evidence 派发）；DFS 迭代融合报告与全组件联动地图将 ARS 组件标为数学建模主线支撑。
- **验证**：`/ars-*` 出现在 `/mm-help`、主控 SKILL 路由表、迭代协议；deep-research 出现在迭代引擎 related_skills 与 §7.2。

## 附加：state_utils.py 可维护性重构（应需求拆分）

2966 行单文件 → `state_defs/state_scaffold/state_nodes/state_review/state_audit/state_rounds/state_search` + 227 行薄 facade。行为零回归（55 测试全绿），`init` 自动复制全部模块进项目 `state/`，命令用法不变。详见迭代融合报告 §3 表格。

## 验收汇总

| 项 | 结果 |
|----|------|
| `python scripts/lint_contracts.py` | ✅ `契约检查通过`（exit 0） |
| `python -m unittest discover -s tests -p 'test_*.py'` | ✅ 55 用例全通过 |
| 四份报告（重叠合并/迭代融合/8类BUG/联动地图） | ✅ 已落盘 docs/optimization/ |
| 机器强制（检索留痕/失败原因/先进性/N8 闭环） | ✅ 已实现并有单测 |
