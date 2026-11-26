---
name: mm
description: 数学建模总控：自动识别项目现状，按描述执行全流程/单节点/接手/迭代/检查
---

执行数学建模项目总控流程。`$ARGUMENTS` 是你的目标描述，例如"做国赛 A 题全流程"、"接手这个项目"、"只迭代第一问代码"、"检查项目状态"、"帮我处理题目图形"。

## 第 0 步：MCP 启动门禁（Checkpoint 0，必跑、顺序不可逆）

任何建模任务开工前，先执行 `mm-boot` 流程（等价调 `mcp/checkpoint-0-boot.md` ①→④）：

1. **全局 MCP 扫描**（以本机真实注册为准）→ **筛选四类适配 MCP**（论文搜索 / GitHub / Context7 / Tavily·回退 tokenhub-tools）→ **内嵌确认** → **自检**：
   ```bash
   python scripts/mcp_boot_check.py --report --namespaces "<会话内真实mcp命名空间>"
   ```
2. 判定：`MCP_READY` → 放行；`MCP_BLOCKED` → **终止任务**，修复异常 MCP 后重跑，未通过禁止开工。
3. 四类 MCP 分工与调用规则见 `mcp/cluster-roles.md`、`mcp/call-hierarchy.md`；闭环校验见 `mcp/validation-checkpoints.md`。核心节点必调 MCP，禁止纯内生输出。

## 第 1 步：自动识别现状

- 目标目录：参数中含目录则用该目录，否则用当前工作目录；
- 若 `state/decision_log.json` 存在（已初始化）：运行
  `python state/state_utils.py project-audit --dir <目录>`
  读取：题目锁定状态（problem_lock 漂移？）、9 个节点状态（pending/in_progress/completed）、结构缺失、状态-产物漂移、旧命名残留、未登记产物；
- 若不存在：项目未初始化 → 走"初始化分支"；
- 同时探查目录内容：有没有题目 PDF（Problem.pdf/题面文件）、数据文件（csv/xlsx）、已有代码（*.py）或论文（*.tex/*.md），纳入计划判断。

## 第 2 步：按描述解析意图并路由

| 描述关键词 | 执行路径 |
|---|---|
| 全流程 / 国赛 / 完整做 / 帮我做 | 未初始化则先初始化（`state_utils.py init` → 读题锁题）→ **检测已有材料（detect_existing_materials：论文/代码/数据）→ 有则先 sync_import 复用** → 触发 `mathematical-modeling` Skill 或按 9 阶段（N1→N8）逐节点委托 |
| 接手 / 已有项目 / 旧项目 | `project-audit` → `project-repair --apply`（先预览计划）→ **检测已有材料并复用（sync_import）** → **`handover-review` 接手复核**（按 9 阶段逐节点检查；completed 节点不直接信任——门禁未过/产物漂移强制审阅→修改→再审阅）→ 修改后 `cascade-invalidate --apply` 联动下游 → `project-audit` 复检 → 从复核通过/未完成节点继续 |
| 复用 / 已有材料 / 用现成的 | 检测 `Material/`、`BackupArchive/` 等位置的论文/代码/数据 → `sync_import` 计划 + `--apply` → 对应节点基于 legacy/imports 审阅修复 |
| 单节点（选题/数据/建模/代码/调优/图表/论文/评审） | 节点自治联动：检查前置 → 缺失则补跑上游或输出 PREREQ-REQUEST → 执行 → 请求配对独立审阅 → 修复（≤2 次）→ 交付 |
| 迭代 / 调优 / 改代码 / 改论文 | 用户未指定范围时生成全局迭代；指定“第几问/某章/某节”时先执行 `scope-plan N4|N5|N7|N8 --round <n>`，再按 scope 生成序列；scope 结果不直接完成父节点 |
| 审阅 / 修改 / 润色 / 质检 / 格式检查已有论文（普通对话未走 /mm 时同样适用） | 先 `scope-plan N7 --round <n> --scope-kind adaptive`：① 按章节/超长章节子问题生成带轮次、时间戳、输入哈希的工作区；② reviewer 内容审阅与 latex_linter 格式审阅可并行；③ orchestrator 汇总后只派 writing **串行**改内容；④ 内容复审全部通过后才派 typesetting **串行**改格式；⑤ 重新编译后派 latex_linter + reviewer 反向复核，最后 join-review 与 scope-promote。空返回只重试一次，二次阻断；🔴 禁止主对话内联代改 `.tex` |
| 按第几问迭代 / 只改某章某节 / 局部检查 | `scope-plan <N4|N5|N7|N8> --round <n> --scope-kind adaptive --target <question_n|chapter_n|section_ref> --apply`；每个 scope 独立 evidence、report、claim、round 和 recovery，已 PASS scope 不重复重跑 |
| 图形 / 读题 / 题目 | `problem_guard.py figures --mode vision|human` 处理题目 PDF 图形（有视觉能力转图阅读，无则生成人工描述请求单） |
| 检查 / 状态 / 进度 | `project-audit` + `state/state_utils.py report-list` + `flow-coverage`（全流程 Agent/Skill 覆盖）汇总输出 |
| 联动 / 改了代码模型 / 同步 | `cascade-invalidate --apply`（上游产物变更 → 下游节点/门禁重置，论文图表调优必须同步更新后重验） |
| 去AI化 / humanize / AI痕迹 | 委托 humanize 专项检测（N8 终审前必做，报告落 state/reports/），发现 AI 模式返回 writing 修订 |
| 未识别 | 输出可执行选项请用户选择，**不擅自动手** |

## 第 3 步：先计划后执行

- 执行任何写操作前，先输出简短计划：将调用哪些节点/命令、会写哪些文件、预计影响哪些状态；
- 涉及"重跑已完成节点/覆盖产物"等破坏性分支，先向用户确认；
- 题目未锁定且含图形时，先完成图形处理再锁题（`verify` 是硬门禁）。

## 第 4 步：执行与汇报

- 按计划逐步执行，每完成一个环节汇报：产物位置、独立审阅结论、门禁状态；
- 结束时给出交付摘要：完成度（9 节点状态）、论文/提交清单位置、待人工事项（H1-H3 人工确认、未锁定项、BLOCKED 项）；
- 用户中途插话指定某个节点时，立即切换到该节点自治流程。
