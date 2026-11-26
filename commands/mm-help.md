---
name: mm-help
description: 数学建模多智能体系统总览与使用指引（文档参考入口）
---

输出数学建模多智能体协同系统（v1.8.0，24 Agent / 34 Skill / 22 命令）的使用总览，按用户语言（中文优先）回复：

1. **全流程**：输入 `/mathematical-modeling` 或"帮我做国赛数学建模"触发主控 Skill；开工前必须过 `/mm-boot`（MCP Checkpoint 0 门禁）；orchestrator 按 9 阶段（Phase 0-8）委托执行（每节点验证上游→按需 Deep Research→自检→配对独立审阅→FAIL 修复≤2次→超限升级→产物落盘）。
2. **单独调用节点**：说出"代码迭代 / 论文修改 / 只画图 / 敏感性分析"等意图，节点 Agent 自治联动（检查前置→执行→配对审阅→修复→交付）。指定“第几问/某章/某节”时先走 `scope-plan --round <n>`，避免整篇上下文稀释。
3. **分片工作流（N4/N5/N7/N8）**：`scope-plan --round <n>` 生成带 scope_id、轮次、时间戳、输入哈希的审阅文件夹；reviewer 内容审阅与 latex_linter 格式审阅可并行；内容修订串行且先于 typesetting；排版后重新构建，再反向复审和 join-promote。空返回只重试一次，二次立即 BLOCKED/ESCALATE。
4. **接手已有项目**：`python state/state_utils.py project-audit --dir <项目>` 审计 → `handover-review` 接手复核（completed 不直接信任）→ `project-repair --apply` 标准化修复；题目含图形时先 `problem_guard.py figures --mode vision|human` 处理。
5. **自动迭代**：未指定局部范围时使用 `python shared/state-engine/orchestrator_runtime.py --plan-iteration N4 --dir <项目> --git`；指定问题/章节时先使用 `python state/state_utils.py scope-plan N4|N5|N7|N8 --round <n> --scope-kind adaptive --target <范围> --apply --dir <项目>`，再逐 scope 迭代（SEARCH 根因分析→DECIDE 失败原因，核心节点每轮强制重新检索，禁止纯内生）。
6. **MCP 知识卡片派发**：`python state/state_utils.py search-evidence <Nx>` 汇总节点检索证据（知识卡片/案例/台账/留痕），委派对应 Agent 时随派发携带。
   - **全命令清单（6 个，全部为 /mm 主线）**：
     - `/mm`（总控：识别现状→路由）、`/mm-boot`（MCP Checkpoint 0 启动门禁，开工必跑）、`/mm-init`（初始化项目）、`/mm-iterate`（生成并驱动 N4/N5/N7/N8 全自动迭代序列）、`/mm-audit`（项目审计/修复/升级自愈）、`/mm-help`（本总览）。
7. **学术专项命令**：深度研究 / 文献综述 / 论文写作 / 同行评审等由 `academic-research-skills` 插件承接（其 `/ars-*` 命令与 academic-paper / deep-research / academic-paper-reviewer / academic-pipeline 技能均在彼处提供），本插件不再重复分发。

8. **关键文档**：README.md（总览）、docs/optimization/（重叠合并清单 / Deep Research 迭代融合 / 8 类 BUG 修复 / 全组件联动地图）、docs/迭代工作流说明.md、skills/mm-iteration-engine/SKILL.md（状态与迭代）、skills/mathematical-modeling/SKILL.md（主控与路由）、skills/latex-guard/SKILL.md（LaTeX 质检与反例速查）、CHANGELOG.md（版本）。

按用户需求给出下一步具体命令，不要只列目录。
