# Agent 协作闭环与 Deep Research 迭代融合规格（统一机制）

> 单一事实源（SSOT）：数学建模 9 阶段为主线，学术研究（Deep Research 链）作为支撑深度嵌入各阶段尤其迭代环节，二者不可拆分。
> 本规格是 `agents/orchestrator.md`、`skills/mathematical-modeling/SKILL.md`、`skills/mm-iteration-engine/SKILL.md` 三处的统一口径；三者引用本文不复制二次口径。
> 配套机器入口：`python state/state_utils.py <命令>`（search-evidence / dr-note / dr-list / round-score 检索门禁 / round-decide 失败原因）。
> 版本：1.5.0 ｜ 复核：2026-08-19 ｜ 验收：`lint_contracts.py` 零报错 + `tests` 全通过。 
> 🔴 **插件命名空间（插件独占模式）**：本插件组件以 `组件名` 前缀注册
> （插件技能/子代理/插件 MCP 各显示在对应「Plugin」分组）。本文中所有组件引用均已使用插件前缀名
> （如 `skill("mm-problem-analysis")`、`subagent_type=selector`）；
> 内部标识（registry executor/reviewer、`state/agents/<id>/`、`--agent` 落盘名）保持无前缀。
> 仓库根 `.plugin-only` 标志生效时，**用户级目录不得存在本仓库组件副本**（lint/self_check 拦截，
> 用 `python scripts/sync_user_level.py --plugin-only` 清理）；运行环境健康检查：
> `python scripts/env_health_check.py [--clean]`。

---

## 一、9 阶段协作闭环表（每节点完整规格）

> 通用铁律：① node-start 机器校验上游 completed 且审阅门禁 PASS，否则拒绝并 `[PREREQ-REQUEST] 缺失节点=<Nx>, 原因=<...>, 建议=<...>`；② 审阅≠执行，审阅 Agent 先加载配对 Skill 并声明（node-review --skills 强制）；③ FAIL → 执行 Agent 按 feedback 修改（加载本节点 skill）→ 复审，**硬上限 ≤2 次**，空修改打回，超限 `[ESCALATE]`；④ 每节点完成后刷新本节点首页 + `node-finish` + 配对审阅落门禁，产物落盘才推进。迭代节点（N4/N5/N7/N8）必须经 `round-start` 开启迭代环。

| # | 节点 | 执行 Agent | 上游输入（接收） | 下游输出（交付→谁） | 前置检查（缺失→[PREREQ-REQUEST]） | 配对审阅（先加载 Skill） | 门禁 | FAIL/超限规则 |
|:-:|:----:|-----------|------------------|----------------------|----------------------------------|--------------------------|:----:|--------------|
| N1 | 选题拆解 | selector | 题目 PDF/题面原文 + `state/problem_lock.json`（题目事实锁定）+ Material/similar_papers | `ProblemInfo/ProblemNotes.md`（目标/约束/数据清单/题型判定/评分点）+ `KeyRequirements.md` → N2/N3 | problem_lock verified（`problem_guard verify` 硬门禁）；题目图形已处理（figures vision/human）；N0 初始化完成 | reviewer（节点审阅）、读 mm-problem-analysis + mm-self-review | M1 + H1 | FAIL→selector 改≤2 次→超限 [ESCALATE] |
| N2 | 数据预处理 | dataprep | ProblemNotes.md + Data/raw（禁改）+ 数据来源说明 | `Data/DataLog.md`（缺失/异常/来源/可复现）+ Data/{processed,feature,test_result} → N3/N4 | N1 completed 且 M1 PASS；原始数据文件存在 | reviewer（节点审阅）、读 mm-data-preprocessing | D1 | FAIL→dataprep 改≤2 次→超限 [ESCALATE] |
| N3 | 模型搭建 | modeler | ProblemNotes.md + DataLog.md + Data/processed | `ModelDocs/{model-framework,formula,assumption}.md`（公式编号连续/假设有据/模型对比≥2）→ N4/N5/N6/N7 | N1+N2 completed（M1/D1） | reviewer（节点审阅）、读 mm-model-library | P1 | FAIL→modeler 改≤2 次→超限 [ESCALATE] |
| N4 | 算法代码开发（迭代环） | coder | formula.md + DataLog.md + Data/processed | `Code/`（config/main/utils/problem_1~4，输出只落 `Code/output/`）+ 运行证据 → N5/N6/N8 | N3 completed 且 P1 PASS；`round-start` 开启迭代环 | **mm-code-reviewer**、读 mm-iteration-engine + mm-algorithm-dev + code-review | P2 + A1 + H2 + S\<n\> | 每轮 SCORE 独立审阅；FAIL/continue→coder 按 feedback 改≤2 次→超限 [ESCALATE]；每轮强制重新检索 |
| N5 | 模型迭代调优（迭代环） | tuner | Code/ + formula.md + ModelDocs | `ModelDocs/{sensitivity-analysis,error-analysis,model-validation}.md`（基线/超参≥3/敏感性/鲁棒性≥2）→ N6/N7/N8 | N4 completed（P2 等门禁）；`round-start` 开启迭代环 | **mm-code-reviewer**、读 mm-model-tuning + mm-iteration-engine | T1 | 同 N4：独立审阅→tuner 改≤2 次→[ESCALATE]；每轮强制重新检索 |
| N6 | 结果可视化 | visualization | Code/output/figures + ModelDocs + 调优产物 | `Code/output/figures`（唯一输出口）→ `ResultFigures/` 精选（去冗余）+ `figure-list.md` → N7 | N4/N5 completed（T1）；图表对应数据存在 | **mm-viz-reviewer**、读 mm-visualization + mm-iteration-engine | V1 | FAIL→visualization 改≤2 次→超限 [ESCALATE]（16 项核对 + 数据同源抽查） |
| N7 | 论文撰写（scope 迭代环） | writing | 只接收当前 scope 的 bounded manifest（ProblemNotes/ModelDocs/Code output/ResultFigures 指针） | `ReportPaper/LaTeX/`（main+preamble+sections+ref.bib，国赛 10 节）+ scope review workspace + 去AI化 | N6 completed（V1）；`scope-plan` + `round-start` 开启迭代环 | 首轮 reviewer 内容审阅 + latex_linter 格式审阅可并行；内容修订后 reviewer 复审；排版后 linter/reviewer 反向复核；最后 join-review | W1 + A2 + W2 + H3 + S\<n\> | **并行只读、串行写入**；内容修订/复审全部 PASS 前禁止 typesetting；排版后重建；scope 空返回二次即 BLOCKED/ESCALATE；全部 scope + join 通过后才 promote/评分；每轮文献检索 |
| N8 | 自检评审（终审） | reviewer | ReportPaper + 全部产物 + SubmissionPackage + 五节点 MCP 留痕 + 去AI化报告 | N8 审阅记录 + `SubmissionPackage/参赛提交清单.md` + 终稿评审报告 | N7 completed（W2）；humanize 去AI化专项已执行（报告在 state/reports/） | 终稿评审报告 + 提交清单核对（终审=执行方豁免，审阅≠执行不适用） | A3 | FAIL→对应阶段修复（标注具体问题）→复审≤2 次→超限 [ESCALATE]；**MCP 闭环终检**：五节点必调留痕 + 知识卡片 + 台账一一对应 |

**产物数据流（链式）**：
`ProblemInfo/ → Data/ → ModelDocs/ → Code/output/ → ResultFigures/ → ReportPaper/LaTeX/ → SubmissionPackage/`
（每节点读上游产物时按 sha256 校验，输出只落本节点产物目录；迭代环每轮产物随 git round 分支提交。）

---

## N7/N4/N5 scope 分片工作流（🔴 单一事实源）

### Scope fan-out → join 拓扑

1. `scope-plan` 生成 `state/reviews/<node>/round_<n>/<scope_id>/`，写入 workspace manifest、bounded input manifest、handoff 和 dispatch plan；scope 记录父节点、轮次、UTC 时间戳、输入/registry/artifact 哈希。
2. 首轮只读审阅 fan-out：reviewer 做 `content_review`，latex_linter 做 `format_review`；两者可并行，但只写各自 scope 报告，不能改业务产物。
3. orchestrator 等所有首轮报告齐全后写 `aggregate_plan.json`，按 scope、问题类型和依赖排序；空报告、无 evidence、无 artifact 或 `EMPTY_RETURN` 阻断汇总。
4. 内容修订 fan-in：writing/coder/tuner 只能按 scope 串行写入声明范围；内容修订及 reviewer 反向复审全部 PASS 前，typesetting 不得写共享 canonical 文件。
5. 排版修订：全部内容 scope PASS 后由 typesetting 串行处理；完成后重新编译/运行，latex_linter 与 reviewer 可并行反向复核。
6. join-review：reviewer 对完整组装稿核对跨章节逻辑、编号、交叉引用、术语、摘要、参考文献和全局格式；全部 scope + join PASS 后才 `scope-promote`，再进行父节点 round-score/round-decide。

### 上下文和失败门禁

- scope Agent 只消费 manifest 指定的目标文件、相邻上下文和证据指针；不得把整篇论文/全部问题代码作为默认输入。
- 空/全空白返回、只有“已完成”、缺少 changed_files/checks/timestamps/artifact 的结果统一 `EMPTY_RETURN`；自动缩小 scope 重试一次，第二次仍空写 recovery 并 BLOCKED/ESCALATE，保留其他已完成 scope。
- scope 结果不能直接把父 N4/N5/N7/N8 标记 completed；旧的无 scope 记录按全局流程兼容解释。

---

## 二、Deep Research 嵌入点清单（全阶段 + 每轮迭代）

### 2.1 Deep Research 链（角色 × 职责）

| 链角色 | 对应 Agent（派发别名） | 在数学建模中的职责 |
|--------|------------------------|--------------------|
| 架构（定义问题） | research_architect（`ars_research_architect`） | 把"瓶颈/根因/待论证点"结构化为可检索的研究问题（RQ）与方案论证框架 |
| 检索（搜证据） | literature + researcher | 按 RQ 检索文献/方案/开源实现（MCP + websearch + 论文库），沉淀 case + 知识卡片 |
| 综合（比较证据） | synthesis（`ars_synthesis`） | 跨来源综合：方案比较（优劣/适用性/复杂度）、矛盾解析、基线对照 |
| 报告（产出结论） | report_compiler（`ars_report_compiler`） | 把根因/方案/调研结果整理为结构化报告（供下轮 SEARCH 输入 / 决策留痕） |

> 链式调用：`research_architect（定义）→ literature/researcher（检索）→ synthesis（综合）→ report_compiler（报告）`。按需截断：只检索方案不系统梳理时，可只走 literature→synthesis。
> 🔴 每次介入用 `state_utils.py dr-note` 留痕（节点/轮次/阶段/角色/问题/输入/产物），落 `state/reports/dr-interventions.jsonl` 并同步 `rounds[n].deep_research`。

### 2.2 各阶段调用时机 / 输入 / 输出

| 阶段 | 调用时机（触发条件） | Deep Research 做什么 | 输入 | 输出 |
|:----:|----------------------|----------------------|------|------|
| N1 选题拆解 | 需要赛题背景/同类案例/题型证据时 | 全部或部分链：research_architect 定义调研问题 → literature 检索同类建模案例 → synthesis 汇总证据 → report_compiler 出背景综述 | 赛题原文/题型判定 | 背景综述 + 案例证据（供 ProblemNotes 依据；沉淀 case+卡片） |
| N2 数据预处理 | 数据源发现/异常可疑需佐证（支撑性） | researcher/literature 检索数据口径、异常模式佐证 | DataLog/可疑记录 | 数据口径/异常模式说明 |
| N3 模型搭建 | 模型选型/公式论证/方法对比需要依据 | research_architect 结构化"选型问题" → literature 检索方法与文献 → synthesis 多模型对比（优劣/复杂度）→ report_compiler 出选型论证 | 题型/约束/数据特征 | 方法对比表 + 文献依据（供 ModelDocs；GB/T 7714 入台账） |
| N4 代码迭代 **每轮** | 🔴 技术瓶颈/性能优化/库用法不确定；或轮次不达标需根因调研 | SEARCH 阶段：researcher/literature + context7/GitHub 检索方案 → synthesis 比较候选实现；系统性瓶颈时全链 → 方案报告 | 根因（上轮 failure_analysis）/feedback/瓶颈描述 | 优化方案 + case/卡片 + 方案对比（→ IMPLEMENT；dr-note 留痕） |
| N5 调优迭代 **每轮** | 🔴 超参空间/SOTA 对照/稳健性方法不确定；或轮次不达标 | SEARCH：researcher/literature 检索调优方法与 SOTA 基线 → synthesis 对照 → 调优方案；SCORE：synthesis 核对先进性基线 | 超参范围/当前结果/瓶颈 | 调优方案 + SOTA 基线对照表（→ 调优 + SCORE 先进性参照） |
| N6 可视化 | 图表选型/配色规范存疑（支撑性） | researcher 检索可视化最佳实践 | 图数据形态 | 图表选型建议 |
| N7 论文撰写 **每轮** | 🔴 论证查文献/参考文献补全/方法引用；或轮次不达标 | SEARCH：literature 检索文献（GB/T 7714 双分支归档 + 台账）；论证处 synthesis 综合证据；DECIDE：report_compiler 整理修改方向 | 论文章节/主张/缺口 | 文献条目（入 ref.bib）+ 论证依据 + 修改方向报告 |
| N8 终审 | 评审发现证据缺口需回溯 | literature 复核引用真实性（GB/T 7714 台账一一对应） | 参考文献表/主张 | 引用核验结论 |

> **N4/N5/N7 每轮"按需介入"判据**：① 技术瓶颈（无法解决/性能不达标）→ 检索方案；② 需论证（方法选择/结果解释要依据）→ 查文献；③ 需系统梳理（根因不清/方向不明）→ 全链深度调研。三者至少满足其一即介入；每轮介入必须 `dr-note` 留痕（否则 N8 无法核对"有据"）。
> N1/N3 为核心必调节点（MCP 必调），其余为支撑性"按需"——但迭代轮次的"有据产出"（SCORE 先进性必须对照外部基线）对所有核心环节强制。

---

## 三、迭代环融合方案（SEARCH / SCORE / DECIDE × Deep Research）

```
迭代轮次（N4/N5/N7）                     Deep Research 链（按需介入，dr-note 留痕）
──────────────────────────────────────  ─────────────────────────────────────────────
SEARCH ① 根因分析                        research_architect：把根因/瓶颈结构化为 RQ
       ② 方案论证                        literature/researcher：按 RQ 重新检索（禁纯内生）→ case+卡片
       ③ 强制重检索                        synthesis：候选方案综合对比（优劣/适用/复杂度）
        （机器门禁：round-score 校验留痕）   → 方案对比回填 IMPLEMENT；dr-note(phase=SEARCH)
IMPLEMENT
RUN
COMMIT
SCORE  配对审阅五维评分                   synthesis/researcher：核对"技术先进性"——
        🔴 创新性/创造性必须对照            用 case_refs/SOTA/获奖论文对照本轮成果是否达/超基线，
          外部基线给分，无基线≤6[NO-BASELINE]  产出先进性对照表；dr-note(phase=SCORE)
DECIDE 达标→merge；不达标→强制--reason    report_compiler：把失败分析整理为结构化决策报告
       并写 decision.failure_analysis      synthesis：基于根因给出下轮候选方案
       （机器门禁：未达标无reason拒绝）        → 作为下一轮 SEARCH ① 输入；dr-note(phase=DECIDE)
```

| 迭代环节 | Deep Research 具体动作 | 准入/输出 | 机器强制/留痕 |
|---------|------------------------|-----------|---------------|
| **SEARCH** | research_architect 把"上轮 failure_analysis + SCORE feedback"结构化为检索 RQ；literature/researcher 按 RQ 用 MCP/websearch/论文库检索并沉淀 case+知识卡片；synthesis 综合候选方案（对比表）供 IMPLEMENT | 输入：根因/RQ | 输出：方案对比 + case + 卡片 | 每轮必留痕（`round-score` 检索门禁；`dr-note phase=SEARCH`） |
| **SCORE** | synthesis 做"技术先进性核查"：对照 case_refs/SOTA/获奖论文评估本轮成果的新颖性/先进性，产出对照表注入审阅；无外部基线时创新维度 ≤6 `[NO-BASELINE]` | 输入：本轮成果 + case_refs | 输出：先进性对照表 | mm-code-reviewer/reviewer 评分时必须对照（SKILL §9 锚点）；`dr-note phase=SCORE` |
| **DECIDE** | 不达标（repair_and_rerun/keep_best）时 report_compiler 生成结构化"失败根因 + 差距 + 下轮方向"报告；synthesis 给出下轮候选方案清单 | 输入：本轮整体证据 | 输出：决策报告 → 下一轮 SEARCH ① | `--reason` 强制（机器拒绝缺失）；写入 `decision.failure_analysis`；`dr-note phase=DECIDE` |

**闭环**：每轮检索结果（case + 知识卡片 + 台账）沉淀于 `state/{cases,reports/mcp-cards,reports/references-ledger}.json` → 后续派发节点用 `search-evidence <Nx>` 打包分发给执行/审阅 Agent → 下一轮 SEARCH 直接复用 → N8 终检核对"每轮备案 + 里程碑"闭环（`validation-checkpoints.md` + `dr-list`）。

---

## 四、orchestrator 居中协调（状态/派发/升级/地图）

1. **唯一状态写者**：orchestrator 独写 `state/decision_log.json`（schema 2.0）；子 Agent 只写 `state/agents/<id>/result.json` + claim 租约；每次状态变更单独 git commit（`State-Sha` trailer）；`git reflog` 即撤销栈。
2. **逐节点派发**：Phase 1-8 每节点 `task` + `subagent_type=<registry executor>`（审阅→mm-code-reviewer/mm-viz-reviewer/reviewer）；**禁止 general-purpose 代做节点产物**、禁止一次派发写完所有节点/章节；每批并行 ≤3 个。
3. **升级规则**：连续 2 次同一阶段失败 → `[ESCALATE] P1`（原因/反馈/新计划）；返修 ≤2 次超限 → `BLOCKED/ESCALATE`；审阅 FAIL 必须附 `--evidence`，空返修哈希对比打回。
4. **MCP 门禁**：任务开工前过 `/mm-boot`（Checkpoint 0）；核心节点必调对应 MCP；N8 终检五节点留痕 + 卡片 + 台账闭环（`validation-checkpoints.md`）。
5. **全系统调用地图（无闲置）**：24 Agent / 34 Skill / 22 命令全部在 orchestrator"全系统调用地图" + 主控 SKILL + 本规格内有归属；`flow-coverage` 对照预期集 vs 实际调用记录查漏用/漏 skill；lint"全组件引用契约"强制零孤儿组件。

**参考实现**：orchestrator.md（编排协议/迭代协议/委托模板）；mathematical-modeling/SKILL.md（阶段/门控/路由）；mm-iteration-engine/SKILL.md（迭代环/审阅配对/评分）；状态引擎源在 `shared/state-engine/state_utils.py` + state_* 模块（1.8.0 自引擎技能迁出，旧路径 `mm-iteration-engine/scripts/` 保留转发垫片；机器校验与留痕命令）。
