# Skill 组合加载与命令统一路由（专项 4）

> 依赖专项 1 合并结果（24/34/22 口径、主辅裁决）建立的联动机制。三张表：Skill 阶段组合加载表 / mm- 阶段衔接链 / 命令统一路由表；一条命令间衔接链；一份闲置补全方案。
> 版本：1.5.0 ｜ 复核：2026-08-19 ｜ 验收：lint 零报错 + 全量单测通过。 
> 🔴 **插件命名空间（插件独占模式）**：本插件组件以 `组件名` 前缀注册
> （插件技能/子代理/插件 MCP 各显示在对应「Plugin」分组）。本文中所有组件引用均已使用插件前缀名
> （如 `skill("mm-problem-analysis")`、`subagent_type=selector`）；
> 内部标识（registry executor/reviewer、`state/agents/<id>/`、`--agent` 落盘名）保持无前缀。
> 仓库根 `.plugin-only` 标志生效时，**用户级目录不得存在本仓库组件副本**（lint/self_check 拦截，
> 用 `python scripts/sync_user_level.py --plugin-only` 清理）；运行环境健康检查：
> `python scripts/env_health_check.py [--clean]`。

## 一、Skill 阶段组合加载表（34 个无闲置）

### 1.1 数学建模主线（每阶段"主 Skill" + 流程 Skill）

| 阶段 | 节点 | 主 Skill（required_skills） | 流程 Skill（全流程必载） | 阶段产物（→ 下一阶段输入） |
|:----:|:----:|----------------------------|--------------------------|------------------------------|
| Phase 0 | 初始化 | mathematical-modeling + mm-iteration-engine | 同左 + **sync-and-compatibility**（材料接入协议） | state 全量预建 + 材料归档 |
| Phase 1 | N1 selector | mm-problem-analysis（+mm-self-review） | 同左 | ProblemNotes/KeyRequirements → N2/N3 |
| Phase 2 | N2 dataprep | mm-data-preprocessing | 同左 | DataLog + processed/feature → N3/N4 |
| Phase 3 | N3 modeler | mm-model-library | 同左 | ModelDocs 三件 → N4/N5/N6/N7 |
| Phase 4 | N4 coder | mm-algorithm-dev（+mm-iteration-engine） | code-review（审）+ mm-iteration-engine | Code/（output 唯一口）→ N5/N6/N8 |
| Phase 5 | N5 tuner | mm-model-tuning（+mm-iteration-engine） | 同左 | sensitivity/error/validation → N6/N7 |
| Phase 6 | N6 visualization | mm-visualization（+mm-iteration-engine） | 同左 | ResultFigures 精选 + figure-list → N7 |
| Phase 7 | N7 writing | mm-latex-writing（+mm-self-review） | mm-iteration-engine（迭代环） | ReportPaper/LaTeX → N8 |
| Phase 8 | N8 reviewer | mm-self-review | 同左 | 审阅记录 + 提交清单（A3） |

> **mm- 阶段一一对应（产物链）**：10 个 mm- Skill（mathematical-modeling、mm-iteration-engine + 8 个阶段 mm-\*）与 9 阶段一一对应——mathematical-modeling（总控）+ mm-iteration-engine（引擎）供全流程，其余 8 个各供一个业务阶段，前一个的产物（ProblemNotes→DataLog→ModelDocs→Code→调优报告→图表→论文→评审记录）是后一个的输入，形成完整链路；`sync-and-compatibility` 补充 Phase 0 材料接入。

### 1.2 学术/Deep Research 嵌入点（持续 + 按需）

| 学术 Skill | 嵌入阶段 | 方式 |
|-----------|----------|------|
| **deep-research** | **N1/N3/N4/N5/N7/N8 持续** | N1/N3 搜证论证；N4/N5/N7 每轮迭代按需（根因分析/方案论证/先进性核查——dr-note 留痕）；N8 引用复核 |
| academic-paper | N7（+N3 方法论证结构） | 论文组织/研究方法依据 |
| academic-paper-reviewer | N7/N8 | 同行评审口径（N7 每轮 + N8 终审） |
| academic-pipeline | 学术流程协调（N7 触达） | 学术流水线总控（论文/研究统一组织） |
| humanizer / academic-humanize | N7 每轮（轻量评分）+ N8 前（全量专项一次） | 去 AI 化（AI-ness 检测 + 英文规则引擎；双档：轮内轻量评分 / 专项全量扫描，原 academic-humanizer 备用子集已并入 academic-humanize） |
| literature / researcher | N1/N7 + Deep Research 链 | 文献检索与证据分级（DR 链成员） |

### 1.3 按需支撑 Skill（场景加载，非闲置）

| Skill | 加载场景 | 谁加载 |
|-------|----------|--------|
| metrics-analysis | N2/N5 统计与调优指标 | dataprep/tuner/analyze |
| xlsx | N2 数据表 | dataprep/visualization |
| drawio-skill | N6/模型框架示意图 | visualization/modeler |
| theme-factory | 学术论文图表主题 | design |
| latex-guard / make-pdf | N7/N8 LaTeX 质检与 PDF | writing/latex_linter/reviewer |
| code-review / receiving-code-review | N4/N5 评审方 / 被评审方 | mm-code-reviewer / coder |
| investigate / systematic-debugging / problem-solving | N4 调试排错 | coder |
| test-driven-development / subagent-driven-development / code-philosophy / frontend-design / frontend-philosophy | 通用开发（coder 通用模式） | coder |
| sync-and-compatibility | Phase 0 材料导入 | orchestrator（已接线，专项 2 补丁） |

> 34 个 Skill 全部有主/学术/按需归属（专项 2 盘点复核：无孤儿；`lint "全组件引用"` 强制）。

## 二、命令统一路由表（22 命令 → Agent + Skill + script + 衔接）

### /mm 主线（6）

| 命令 | 路由 Agent | 联动 Skill | 脚本/入口 | 前后衔接 |
|------|-----------|-----------|-----------|----------|
| /mm | orchestrator（按意图路由） | mathematical-modeling + mm-iteration-engine | `state/state_utils.py`（识别现状→路由） | 前置 `/mm-boot`；新项目→init；已有项目→audit；迭代意图→iterate |
| /mm-boot | orchestrator（MCP 门禁） | — | `scripts/mcp_boot_check.py --report` | **一切建模任务开工前置**；MCP_READY 放行 → /mm |
| /mm-init | orchestrator（Phase 0） | sync-and-compatibility + mm-iteration-engine | `state_utils.py init` | 依赖 /mm-boot ↔ 新项目；完成后 /mm 继续 |
| /mm-audit | orchestrator（审计） | mm-iteration-engine | `state_utils.py project-audit/project-repair/upgrade-heal` + `handover-review` | 接手已有项目 / 升级后必跑 |
| /mm-iterate | orchestrator（迭代） | mm-iteration-engine + deep-research（按需） | `orchestrator_runtime.py --plan-iteration N4\|N5\|N7\|N8` | 用户"迭代/改代码/改论文"入此；不达标→DR 根因 |
| /mm-help | —（总览） | — | — | 文档入口 |

### /ars-* 学术专项（16，嵌入 /mm 对应阶段与迭代轮次，不另起炉灶）

| 命令 | 路由 Agent | 联动 Skill | 脚本/入口 | 在 /mm 中的位置 |
|------|-----------|-----------|-----------|------------------|
| /ars-full | research_architect/literature/synthesis/report_compiler | deep-research | deep-research 管线 | 深度研究全流程（N1 选题/N3 建模/N4 迭代根因） |
| /ars-3w | literature/researcher | deep-research | 三阶段文献扫描 | N1 选题文献调研 |
| /ars-lit-review | literature | deep-research | 文献综述 | N1/N7 文献 |
| /ars-plan / /ars-outline | research_architect / design | deep-research / academic-paper | 研究方案/大纲 | N3 方案论证 / N7 论文大纲 |
| /ars-abstract | writing | academic-paper | 摘要 | N7 摘要 |
| /ars-reviewer / /ars-revision / /ars-revision-coach / /ars-rebuttal-audit | reviewer / writing | academic-paper-reviewer | 评审/修改/辅导/答辩 | N7 每轮 + N8 评审 |
| /ars-citation-check / /ars-disclosure | audit | academic-paper | 引证/披露校验 | N7/N8 引用合规 + GB/T 7714 台账 |
| /ars-format-convert | writing/typesetting | latex-guard | 格式/LaTeX 转换 | N7 格式统一 |
| /ars-mark-read / /ars-unmark-read | literature（阅读登记） | — | `scripts/ars_mark_read.py` | N1/N7 文献已读管理 |
| /ars-cache-invalidate | literature（缓存） | — | `scripts/ars_cache_invalidate.py` | 文献缓存失效 |

### 命令间自动衔接链

```
/mm-boot（Checkpoint 0）→ /mm（总控识别并路由）
    ├─ 新项目        → /mm-init（材料接入 sync-and-compatibility）→ 9 阶段推进
    ├─ 已有项目/接手 → /mm-audit（project-audit → handover-review 复核 → repair/upgrade-heal）→ 继续
    ├─ 迭代意图      → /mm-iterate（orchestrator_runtime 生成 SEARCH→DECIDE 序列）
    ├─ 深度支撑需求  → /ars-* 按需（文献/方案/大纲/评审）
    └─ 迭代不达标    → round-decide repair_and_rerun → 自动触发 deep-research 根因分析
                          （dr-note phase=DECIDE / dr-list 留痕）→ 回填下一轮 SEARCH
```

## 三、闲置 Skill / 命令补全方案

| 项 | 判定 | 处置 |
|----|------|------|
| Skill 闲置 | 无（34 全部有主/学术/按需归属） | 保持；`flow-coverage` 与 lint 全组件引用契约持续盯防 |
| 命令闲置 | 无（22 全部有路由/衔接） | 保持；/ars-* 已在主控 SKILL 路由表逐条映射 |
| 半接线历史遗留 | sync-and-compatibility（原仅地图提及） | 已补接线（专项 2 补丁）：orchestrator Phase 0 + 主控材料复用协议显式加载 |
| 备用子集 | academic-humanizer（与 academic-humanize 重复） | 保留标注后备；更新时优先并入 academic-humanize（不留两套维护） |
| 命令计数 | /ars-* 实际 16（历史误写 17） | 已校正 7 处文档 |
