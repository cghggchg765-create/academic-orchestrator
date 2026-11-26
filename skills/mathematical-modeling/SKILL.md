---
name: mathematical-modeling
description: "数学建模国赛(CUMCM)全流程总控Skill：9阶段链路（Phase 0-8）、标准项目结构（MathModel_Contest）、外部状态统一节点（state）、节点独立执行与审阅配对、迭代循环、阶段门控、产物交接协议、路由规则。触发词：数学建模, 数模, CUMCM, math modeling, 竞赛, 建模比赛"
metadata:
  version: "1.8.0"
  last_updated: "2026-09-03"
  status: active
  related_skills:
    - mm-iteration-engine
    - mm-skill-router
    - mm-problem-analysis
    - mm-data-preprocessing
    - mm-model-library
    - mm-algorithm-dev
    - mm-model-tuning
    - mm-visualization
    - mm-latex-writing
    - mm-self-review
---

【范围】仅用于数学建模竞赛（CUMCM/MCM/校赛）全流程。若任务是普通学术论文、课程论文、期刊投稿、文献综述、单纯绘图或数据分析，改用 academic-paper / deep-research / academic-pipeline / visualization 等通用技能。

# Mathematical Modeling — CUMCM 数学建模全流程总控

国赛(CUMCM)数学建模多智能体协同系统的主控 Skill。定义 9 阶段工作流（Phase 0-8）、标准项目结构、外部状态统一节点、节点独立执行与审阅配对、迭代循环、阶段门控、产物交接协议与路由规则。

---

## Quick Start

**最小命令：**
```
/mathematical-modeling
```
```
帮我做国赛数学建模
```
```
CUMCM 数学建模全流程
```

**执行流程：**
0. **MCP 启动门禁（Checkpoint 0）**：开工前按 `mcp/checkpoint-0-boot.md` 执行 ①全局MCP扫描 → ②筛选四类适配MCP → ③内嵌确认 → ④自检（`python scripts/mcp_boot_check.py --report`），`MCP_READY` 才允许开工；核心节点强制必调对应 MCP 并沉淀知识卡片 + GB/T 7714 台账（见 `mcp/call-hierarchy.md`、`mcp/validation-checkpoints.md`）
1. Phase 0 项目初始化：标准结构（MathModel_Contest）+ state 全量预建 + git init + 提醒创建远端仓库
2. 选题拆解 → 数据处理 → 建模 → 代码（迭代环）→ 调优 → 图表 → 论文（迭代环）→ 评审
3. 每阶段产出落盘 + 配对审阅 + 门禁通过后推进

---

## Trigger Conditions

### Trigger Keywords

- **中文**: 数学建模, 数模, CUMCM, 国赛, 建模比赛, 帮我做建模, 数学建模论文, 数学建模流程
- **English**: math modeling, CUMCM, mathematical modeling competition, modeling pipeline, model building

### Does NOT Trigger

| Scenario | Use Instead |
|----------|-------------|
| 课程作业/毕业论文 | `academic-paper` |
| 单一模型使用（非建模流程） | 对应具体模型 Skill |
| 数据分析（非建模竞赛） | `deep-research` |

---

## 🔴 执行铁律（不可违反，违反即流程失败）

1. **禁止手工创建状态文件/目录结构**：必须使用 `python state/state_utils.py init` 生成标准结构与 `state/`（decision_log/registry/节点首页/dashboard 全量预建，带 generator 标记）。手工 `mkdir` + 手写 decision_log/registry 属于**绕过 CLI 的伪造状态**，`project-audit` 的 state_authenticity 会检测并报告。
2. **所有状态变更必须经 CLI**：节点开工/收工用 `node-start / node-finish`（带 `--agent <执行Agent> --skills <已加载技能>`），迭代节点必须 `round-start / round-score / round-decide`；禁止跳过 CLI 直接改 JSON 或只靠 git commit 声称"Gate 通过"。
3. **每个阶段必须唤起对应专业子 Agent 执行**：Phase 1-8 通过 `task` 委托 registry 对应的执行 Agent（N1→selector、N2→dataprep、N3→modeler、N4→coder、N5→tuner、N6→visualization、N7→writing、N8→reviewer），子 Agent 开工前加载其 required_skills；**主 agent/orchestrator 禁止内联代写各节点产物**（node-finish 会校验 --agent 与 --skills，错 Agent/缺技能拒绝落盘）。
3b. **🔴 专业 skill 由路由层按需选择，不在本插件内写死**：节点 `required_skills` 只是保底；本次还该加载哪些专业 skill，由 `mm-skill-router` 在开工前运行时扫描本机已装 skill、按能力匹配得出（`node-start` 自动生成 `state/skill-routing/<节点>.json`）。派生 Agent 必须加载清单 `must_load` 的**全部** skill 并在 `node-finish --skills` 中声明，否则拒绝落盘。**专业 skill 的内部流程由其自身定义，本插件不复述、不替代**——skill 升级/替换/新增都只需装到本机，插件不改。
4. **审阅独立**：每阶段由配对独立审阅 Agent 把关（审阅≠执行）；代码/论文迭代节点必须走 SEARCH→DECIDE 迭代环（无 round 直接标完成会被拒绝）。
5. **先计划后执行**：动手前输出阶段计划（将唤起哪些子 Agent、写哪些产物、跑哪些 CLI 命令）；每阶段结束汇报产物/审阅/门禁。
5b. **🔴 构建/运行虚拟环境门禁**：任何代码运行、数据处理、算法输出、绘图或依赖构建前执行 `python scripts/venv_guard.py --project <项目>`；只有 `VENV_READY` 才能继续，`VENV_BLOCKED` 时禁止用系统全局 Python 绕过。
6. **🔴 禁止 general-purpose 包办节点**：Phase 1-8 必须按 registry 以 `task` + `subagent_type=<executor>` 唤起**对应专业子 Agent**（selector/dataprep/modeler/coder/tuner/visualization/writing/reviewer 等）；`general-purpose` 只允许做编排/检索/文件整理等辅助工作，**禁止代做任何节点产物**（node-finish 校验 --agent 与 registry executor 一致，错 Agent 拒绝落盘）。被唤起的子 Agent 必须**先加载其 required_skills 并声明**（见 `state/registry.json`），未读齐不得开工。
7. **🔴 逐节点、逐章节/逐问题派发**：宁可多派几次，不要合并。论文默认先 `scope-plan N7 --round <n>`，按章节自适应拆分，超长模型章节按子问题/小节拆分；算法 N4/N5 默认按 `question_<n>` scope。每个派发只交付一个明确子任务，Agent 只读 bounded manifest，不得一次性读取整篇论文/全部问题；禁止"一个 Agent 一次写完所有节点/所有章节/所有问题"。
8. **🔴 审阅并行、写入串行**：reviewer 内容审阅与 latex_linter 格式审阅可并行；内容修订和内容复审全部 PASS 前，禁止 typesetting 写共享论文文件；排版后必须重新构建并反向复审，join 通过后父节点才能完成。
9. **🔴 空返回不得通过**：空/全空白/只有“已完成”或缺 artifact、checks、timestamps 的子 Agent 结果标记 `EMPTY_RETURN`，只重试一次；再次空返回立即 BLOCKED/ESCALATE，保留 recovery 留痕，不得无限等待或主对话内联代做。。
8. **🔴 动态进度更新**：每完成一个可独立描述的动作立即更新状态——小步骤用 `python state/state_utils.py node-log <节点> --step "<做了什么>"` 追加到 `state/nodes/<名称>/steps.md`；待办用 `todo add <待办> [--node <节点>]` 新增、`todo done <匹配文本>` 标记完成、`todo list` 查看；节点全部小步骤完成后用 `node-finish` 标记该阶段完成（completed）。禁止一口气做完再补记录。
9. **🔴 审阅-修改-再审阅是唯一合法路径（单项/阶段/整体系列任务通用）**：每个节点产物必须"① 调用配对独立审阅子 Agent → ② PASS 落门禁完成 / FAIL → ③ 调用对应修改 Agent（=执行 Agent）加载本节点 skill 按 feedback 修改润色 → ④ 再审阅往复"（硬上限 2 次，空修改打回，超限 BLOCKED/ESCALATE）；**禁止执行完不审阅直接标完成**（audit 的 unreviewed_completion 检测）、禁止 FAIL 不改直接放行、禁止修改时不加载 skill。详见 mm-iteration-engine §5.3。
10. **🔴 阶段联动与交接（防"阶段不完全/修改不完善就推进下一步"）**：上游节点必须 completed **且审阅门禁 PASS** 才能开工下游（node-start 机器校验，不满足拒绝并提示先补上游审阅循环）；任何已推进节点的上游未完成/未审阅都会被 audit 的 premature_progression 检测报告；**单独拉出某阶段前先 `state_utils.py handoff <Nx>` 生成/刷新交接文件**（上游状态/门禁/产物哈希 + 就绪判定），blocked 则先补上游再回来。详见 mm-iteration-engine §3.4。
11. **🔴 MCP 集成铁律（Checkpoint 0 + 核心节点必调）**：任何建模/学术任务开工前必须先过 MCP 启动门禁（见 Quick Start 第 0 步，`MCP_BLOCKED` 禁止开工）；核心节点强制调用对应 MCP：N1 选题→论文搜索+Tavily/tokenhub、N3 建模→Context7+论文搜索、N4 代码→Context7+GitHub MCP、N5 调优→GitHub MCP+Tavily/tokenhub、N7 论文→论文搜索（GB/T 7714 双分支归档）；每次检索按 `mcp/knowledge-card.template.md` 沉淀知识卡片（落 `state/reports/mcp-cards/`）、留痕 `state/reports/mcp-calls.jsonl`，文献归入 `state/reports/references-ledger.md`；N8 终检查点见 `mcp/validation-checkpoints.md`。禁止纯内生、禁止跳过必调。

---

## 9 阶段定义（Phase 0-8）

| Phase | 名称 | Agent | 产物落点 | 配对审阅 Agent | Checkpoint |
|:-----:|------|-------|----------------|----------------|------------|
| 0 | 需求确认/项目初始化 | orchestrator（自己完成） | 标准项目结构 + `state/` 全量预建 + git init | — | state 预建齐全、git 首次提交、提醒用户创建远端仓库 |
| 1 | 选题拆解 | selector | `ProblemInfo/ProblemNotes.md` + `KeyRequirements.md` | reviewer（节点审阅） | M1 通过 + 用户确认（H1） |
| 2 | 数据处理 | dataprep | `Data/DataLog.md` + processed/feature/test_result | reviewer（节点审阅） | D1 通过 |
| 3 | 建模 | modeler | `ModelDocs/model-framework.md`+`formula.md`+`assumption.md` | reviewer（节点审阅） | P1 通过 |
| 4 | 代码（迭代环） | coder | `Code/`（output 唯一输出口） | **mm-code-reviewer** | P2 + A1 通过 + H2 人工确认，评分达 termination 决策 |
| 5 | 调优 | tuner | `ModelDocs/sensitivity-analysis.md`+`error-analysis.md`+`model-validation.md` | **mm-code-reviewer** | T1 通过 |
| 6 | 图表 | visualization | `Code/output/figures` → `ResultFigures/` 精选 + `figure-list.md` | **mm-viz-reviewer** | V1 通过 |
| 7 | 论文（迭代环） | writing | `ReportPaper/LaTeX/` | reviewer（论文评审，**含去AI化检测**） | W1 + A2 + W2 通过 + H3 人工确认，评分达 termination 决策 |
| 8 | 评审 | reviewer | `state/nodes/评审/` 审阅记录 + `SubmissionPackage/参赛提交清单.md` | 终稿评审报告 + **humanize 去AI化专项** | A3 通过 |

> 阶段与产物细节、门禁定义、审阅配对、迭代循环、评分体系以 `mm-iteration-engine` Skill 为准（本 Skill 与其保持联动）。

---

## 全流程 Agent 与 Skill 覆盖（🔴 完整跑一遍必须全部正确调用）

完整流程（Phase 0→8）必须覆盖以下全部专业子 Agent 与技能；任一缺失 = 流程不完整（用 `python state/state_utils.py flow-coverage --dir <项目>` 对照检查实际调用记录）：

| 环节 | 子 Agent（task 派发） | 必读 Skill（required_skills） |
|------|----------------------|------------------------------|
| Phase 0 初始化 | orchestrator（自己完成） | mathematical-modeling + mm-iteration-engine |
| Phase 1 选题拆解 | selector | mm-problem-analysis + mm-self-review |
| Phase 2 数据处理 | dataprep | mm-data-preprocessing |
| Phase 3 建模 | modeler | mm-model-library |
| Phase 4 代码迭代 | coder | mm-iteration-engine + mm-algorithm-dev + code-review |
| Phase 5 调优 | tuner | mm-model-tuning + mm-iteration-engine |
| Phase 6 图表 | visualization | mm-visualization + mm-iteration-engine |
| Phase 7 论文迭代 | writing | mm-iteration-engine + mm-latex-writing + mm-self-review |
| Phase 4/5 代码+调优审阅 | mm-code-reviewer | mm-iteration-engine + mm-algorithm-dev + code-review（审 N5 加 mm-model-tuning） |
| Phase 6 图表审阅 | mm-viz-reviewer | mm-visualization + mm-iteration-engine |
| Phase 1-3/7-8 审阅 | reviewer（节点/论文评审模式） | 按配对矩阵（mm-iteration-engine §6.1） |
| Phase 8 前 去AI化专项 | **humanize** | humanizer / academic-humanize |
| Phase 8 终审 | reviewer（终审模式） | mm-self-review |

> 每次阶段切换用 `todo plan` 生成/更新任务清单；收尾用 `flow-coverage` 验证全部 Agent 与 Skill 均被正确调用。

---

## 职责边界（任务-职能匹配，🔴 派发前必核对）

**派发铁律**：任务内容与 Agent 职责不符时禁止派发——把"写论文"派给 coder、"实现算法"派给 writing、"评分代码"派给 reviewer、"去AI化"派给 polish 均属职能错位，发现即转派正确 Agent。完整 24 Agent 边界矩阵见 orchestrator；数学建模流程核心边界如下：

| Agent | 负责 | 不负责（越界即转派） |
|---|---|---|
| selector | N1 选题拆解 | 学术设计（design）、建模（modeler） |
| dataprep | N2 数据清洗/特征 | 建模（modeler）、造数据 |
| modeler | N3 数学建模（公式/假设） | 实现代码（coder）、学术大纲（design） |
| coder | N4 代码实现（只落 output/） | 推导公式（modeler）、写论文（writing）、画图（visualization）、统计解读（analyze） |
| tuner | N5 迭代调优 | 重写代码（coder）、改模型结构（modeler）、学术统计解读（analyze） |
| visualization | N6 图表（数据同源） | 造数据（dataprep）、写论文（writing） |
| writing | N7 论文（数据一致性） | 实现代码（coder）、生成图表（visualization）、排版（typesetting） |
| reviewer | N1-N3/N7-N8 审阅 | 竞赛代码评分（mm-code-reviewer）、竞赛图表核对（mm-viz-reviewer）、改代码（coder） |
| mm-code-reviewer | N4/N5 五维评分 | 论文评审（reviewer）、改业务代码 |
| mm-viz-reviewer | N6 图表 V1（5 项预检查 + 20 项编号质量检查） | 生成图表（visualization）、论文评审（reviewer） |
| humanize | 去AI化（AI-ness 检测/改写清单） | 语言润色（polish）、评分（reviewer） |
| polish | 学术润色（术语/语句） | AI 痕迹检测（humanize）、评分（reviewer） |

**重叠区裁决**（同任务多 Agent 可归时的唯一归属）：润色→polish；AI 痕迹→humanize；质量评分→reviewer；统计脚本执行→execute（新写算法→coder）；统计结果解读→analyze（竞赛调优→tuner）；排版→typesetting；LaTeX 质检→latex_linter；学术大纲→design（竞赛选题→selector、竞赛建模→modeler）。lint"职责边界契约"强制：重叠区 Agent 必须互相声明边界，执行 Agent 必须引用其负责节点。

---

## 去 AI 化（humanize）检测环节（🔴 N7 后、N8 终审前必须执行）

1. **论文评审内嵌检测**：N7 每轮 reviewer 论文评审必须包含去 AI 化检测（加载 `humanizer` / `academic-humanize` 技能，检测 AI 套话、模板句式、机械排比、空泛总结等），结果计入"表述清晰性"维度并写入审阅记录；
2. **终审前专项检测**：N8 终审前委托 **humanize** 对全文做 AI-ness 检测，检测报告落 `state/reports/`（kind=deai）；发现 AI 痕迹 → 生成去AI化修改清单返回 writing 修订 → 复审；
3. **提交门禁**：A3 终审通过前必须确认去AI化检测已执行（报告存在且无残留 AI 模式）；检测未执行 = 门禁不通过。

---

## 题目 PDF 图形处理（读题前置，Phase 0/1）

题目 PDF 可能含图形（图/表/地图/示意图/坐标系等）。**在创建 problem_lock 前**必须完成图形处理，按模型能力分两条路径（由 `problem_guard.py` 支撑）：

1. **模型有视觉能力**：把 PDF 逐页渲染为图片，由视觉模型仔细阅读图形后再锁定事实。
   ```bash
   python state/problem_guard.py figures --project <项目目录> --source <题目PDF> --mode vision --dpi 200
   # 输出 ProblemInfo/figures/page-*.png（依赖 pdftoppm；无工具时脚本返回 BLOCKED 并提示替代方案）
   ```
   视觉模型逐页阅读图片（图形类型、坐标/单位、关键数值、趋势、图例、对解题的约束）后登记：
   ```bash
   python state/problem_guard.py figures-read --project <项目目录> --mode vision
   ```
2. **模型没有视觉能力**：把图形要求发给人工，请人工对题目图形进行详细描述。
   ```bash
   python state/problem_guard.py figures --project <项目目录> --source <题目PDF> --mode human
   # 生成 state/problem_figure_request.md 请求单（页/图形类型/需提取的信息）
   ```
   人工填写描述后登记：
   ```bash
   python state/problem_guard.py figures-read --project <项目目录> --mode human --description "<人工完整描述>"
   ```

3. **无图形**：`create --figure-mode none`（默认）。

锁定创建时声明模式：`problem_guard.py create --figure-mode vision|human|none ...`；`verify` 会强制校验：vision 模式必须已登记图片且图片哈希匹配、且 `figures_read=true`；human 模式必须已有 `human_description`。**图形未完成阅读前，N1 及之后的节点不得开工**（verify 即门禁）。

---

## 已有材料复用（Phase 0 必检：现成论文/代码/数据优先复用，不从零开始）

**规则：初始化后必须检测项目内是否已有论文、代码、数据；有则先复用再推进节点，禁止无视现成材料从零开始。**
**实施**：Orchestrator 进入材料复用前必先加载 **`sync-and-compatibility`**（材料接入协议：材料清单与哈希锁定/代码审阅修复/数据一致性验证/论文改写门禁/Markdown→LaTeX 转换门禁），随后按下列步骤执行：

1. **检测**（机器化入口）：`orchestrator_runtime.detect_existing_materials(<项目>)` 或由 orchestrator 执行——扫描 `Material/`、`BackupArchive/`、`Data/raw/`、根目录等位置的 `.tex/.md/.pdf/.docx`（论文）、`.py/.r/.m/.jl`（代码）、`.csv/.xlsx/.json/.dat`（数据），排除脚手架占位；
2. **归位**：`orchestrator_runtime.organize_existing_materials(<项目>)` 把材料复制到标准位置（题目→ProblemInfo/、数据→Data/raw/、代码→Code/legacy/、论文→ReportPaper/LaTeX/drafts/ 或 state/imports/paper/），生成 `state/material_index.json` 索引（原始文件保留，不覆盖）；
3. **🔴 AI 读取内容后真实整理（禁止只按扩展名归类）**：执行 `orchestrator_runtime --material-plan <项目>` 生成内容整理任务包——对每个文件，AI **必须读取真实内容**后填写：
   - 论文：标题/题型、方法/模型、关键结论与数值、与本题相关性（可借鉴点）；
   - 代码：入口/依赖、解决第几问、输入输出格式、关键算法与可复用模块、需修复点；
   - 数据：字段与含义、行数/缺失/异常、来源口径、与题目数据需求对应；
   回填到 `state/material_index.json`（summary/key_attributes/reusable_for/needs_repair）；
4. **调用**：后续节点按索引取用——N1 参考 similar_papers 选题、N2 清洗 Data/raw、N4 审阅修复 Code/legacy、N7 基于 drafts 改写；`sync_import.py --apply` 兼容清单随状态提交；
5. 用户明确"已有材料在别处"时，以用户给出的路径为 `--source`；检测结果与复用决策写入交付报告。

---

## 接手复核协议（🔴 加载/完整阅读已有项目后必跑：已完成 ≠ 跳过）

**规则：接手项目（含"让我读一下这个项目/加载这个项目继续做"）必须先按 9 个阶段逐节点检查；任何标记 completed 的节点都不得直接信任跳过——必须复核审阅，发现问题同步修改并验证。**

1. **逐节点检查**：`python state/state_utils.py handover-review --dir <项目>`——输出 9 节点状态与处置（completed → 复核；in_progress → 补完循环；pending → 待执行）；
2. **completed 节点不直接信任**：
   - 门禁未过（审阅 FAIL/未审阅）或产物哈希漂移（与 node-finish 登记不一致）→ **强制复核**：派发配对审阅 Agent 复核 → FAIL → 派发对应执行 Agent 按 feedback 修改（加载本节点 skill）→ 复审（≤2 次）；
   - 门禁已过且无漂移 → 仍须"复核确认"：配对审阅 Agent 快速审阅已过内容（主张↔产物一致性），发现问题进入修改循环；
3. **同步修改与验证**：复核中修改了任何上游产物 → `python state/state_utils.py cascade-invalidate --apply` 级联重置下游（论文/图表/调优联动重验）→ `python state/state_utils.py project-audit` 复检（unreviewed_completion/premature_progression/内联代做全查）；
4. **继续推进**：从"复核通过 + 未完成节点"继续；每步仍走"审阅→修改→再审阅"循环（执行铁律 9/10）。

---

## 阶段产物交接协议

每个阶段**读取上游产物**，**产出本阶段产物**，形成链式数据流：

```
Phase 0: [赛题+需求] → orchestrator → 标准结构 + state（decision_log/dashboard/9 节点首页/registry）
                                              ↓
Phase 1: [赛题原文] → selector → ProblemInfo/ProblemNotes.md + KeyRequirements.md
                                              ↓ [M1 + H1]
Phase 2: [ProblemNotes + 原始数据] → dataprep → Data/DataLog.md + processed/feature/test_result
                                              ↓ [D1]
Phase 3: [ProblemNotes + DataLog] → modeler → ModelDocs/model-framework+formula+assumption
                                              ↓ [P1]
Phase 4: [formula.md + DataLog] → coder → Code/（SEARCH→IMPLEMENT→RUN→COMMIT→SCORE→DECIDE 迭代环）
                                              ↓ [P2 + A1 + S<n>]
Phase 5: [Code + formula.md] → tuner → ModelDocs/sensitivity+error+validation
                                              ↓ [T1]
Phase 6: [output/figures + 05/06 产物] → visualization → ResultFigures/ 精选 + figure-list.md
                                              ↓ [V1]
Phase 7: [01~06 全部产物] → writing → ReportPaper/LaTeX/（迭代环）
                                              ↓ [W1 + A2 + W2 + S<n>]
Phase 8: [07 产物 + 全部产物] → reviewer → N8 审阅记录 + SubmissionPackage/参赛提交清单.md
                                              ↓ [A3] 完成
```

### 产物格式规范

| 产物 | 落点 | 格式要求 | 必含内容 |
|---------|---------|---------|---------|
| 需求确认 | `README-项目总说明.md` + `ProblemInfo/TeamInfo.txt` + `TimePlan.md` | Markdown/文本 | 项目总览、运行环境、复现步骤、团队分工、时间轴 |
| 题目拆解 | `ProblemInfo/ProblemNotes.md` + `KeyRequirements.md` | Markdown | 目标/约束/数据清单、题型判定、评分点映射 |
| 数据报告 | `Data/DataLog.md` + 数据文件 | Markdown + 附表 | 数据概览、缺失分析、异常值处理、特征清单、来源 |
| 模型文档 | `ModelDocs/model-framework.md`+`formula.md`+`assumption.md` | Markdown | 模型框架、公式推导（连续编号）、假设清单（有依据） |
| 代码 | `Code/` | Python 工程 | `config.py`/`main.py`/`utils/`/`problem_1~4/`/`requirements.txt`/`README-Code.md`；输出只落 `output/` |
| 调优报告 | `ModelDocs/sensitivity-analysis.md`+`error-analysis.md`+`model-validation.md` | Markdown | 基线指标、超参对比、敏感性分析、鲁棒性结论 |
| 图表 | `Code/output/figures` → `ResultFigures/`（精选）+ `figure-list.md` | PDF/PNG（≥300dpi） | 图1~图N 连续编号、每图含标注（标题/单位/来源/图例） |
| 论文 | `ReportPaper/LaTeX/` | LaTeX 源码 | `main.tex`+`preamble.tex`+`sections/`+`ref.bib`，符合国赛格式 |
| 评审报告 | `state/nodes/评审/` 审阅记录 + `SubmissionPackage/参赛提交清单.md` | Markdown | **五维度评分（假设15/创造性25/结果30/表述20/格式10）**、问题清单、修改优先级 |

---

## 路由规则

### Agent 调度矩阵

| 用户意图 | 目标 Agent（节点） | 前置条件 |
|---------|-----------|---------|
| "分析这道题" / "选哪道" | selector (N1) | 有赛题原文 |
| "处理数据" / "数据清洗" | dataprep (N2) | ProblemNotes.md 存在 |
| "选模型" / "怎么建模" | modeler (N3) | DataLog.md 存在 |
| "写代码" / "代码迭代" / "实现算法" | coder (N4，迭代环) | formula.md 存在 |
| "调参" / "优化模型" | tuner (N5) | Code/ 存在 |
| "画图" / "生成图表" | visualization (N6) | output/figures 存在 |
| "写论文" / "论文修改" | writing (N7，迭代环) | Phase 0-6 产物存在 |
| "检查论文" / "评审" | reviewer (N8) | ReportPaper/ 存在 |

### 路由优先级

1. **顺序执行**：默认按 Phase 0→8 顺序推进
2. **跳阶段**：用户可指定从某阶段开始（需确认前置产物存在；见"节点独立执行"）
3. **回退**：评审不通过时回退到对应阶段修改
4. **并行**：Phase 5（调优后收尾）和 Phase 6（图表）可部分并行

### 🔴 专项命令路由（/ars-* 作为 Deep Research 学术专项能力嵌入 /mm 体系，不另起炉灶）

`/ars-*`（16 个）是学术研究（Deep Research / 文献 / 论文 / 评审）专项命令，**统一由本 `/mm` 总控体系路由**：按当前节点/需求调用，服务数学建模各阶段的"搜证、论证、审阅、去 AI"环节，其产物（调研报告/知识卡片/评审意见）沉淀到项目 `state/reports/` 与 `ResultFigures/`、`ReportPaper/`，不脱离主线另建工作流。

| /mm 需求（节点） | 路由到 /ars-* 专项命令 | 作用 |
|---|---|---|
| 深度研究全流程 | `/ars-full` | 系统性研究（选题/文献/综合/报告）→ 供 SEARCH/根因分析 |
| N1 选题文献调研 | `/ars-3w`（三阶段文献扫描）、`/ars-lit-review`（文献综述） | 赛题背景、同类案例证据 |
| N3 建模方案论证 | `/ars-plan`（研究方案）、`/ars-outline`（大纲） | 模型选型论证、方法依据 |
| N7 论文（文献补全/大纲） | `/ars-outline`、`/ars-lit-review` | 论文结构规划与文献矩阵 |
| 论文评审（N7 每轮 + N8） | `/ars-reviewer`（同行评审）、`/ars-revision`（修改）、`/ars-revision-coach`、`/ars-rebuttal-audit` | 独立评审意见、修改建议、答辩质疑预演 |
| 摘要/写作 | `/ars-abstract`（摘要）、`/ars-format-convert`（格式转换） | 摘要精炼与格式统一 |
| 引用合规 | `/ars-citation-check`（引证核查）、`/ars-disclosure`（披露） | GB/T 7714 台账对齐、规范披露 |
| 阅读/缓存 | `/ars-mark-read`、`/ars-unmark-read`、`/ars-cache-invalidate` | 文献已读登记与缓存失效 |

**派生 Agent 侧**：上述专项实际注册的学术 Agent 名为 `research_architect_agent / synthesis_agent / report_compiler_agent`，orchestrator 必须按这三个 frontmatter name 派发；`ars_*` 只作为历史文档别名，不可直接作为 `subagent_type`，除非宿主 alias registry 已验证。

---

## Agent 协作闭环表（浓缩 · 单一事实源 = `docs/optimization/agent-collaboration-loop.md`）

每节点统一执行：**验证上游（node-start 机器校验 completed+门禁 PASS，缺失→`[PREREQ-REQUEST]`）→ 按需 Deep Research（dr-note 留痕）→ 本节点产物落盘 → 自检 → 配对独立审阅（先加载配对 Skill 并声明）→ FAIL 修改 ≤2 次（空返修打回）→ 超限 `[ESCALATE]`**。完整字段（上游输入/下游输出/前置检查/审阅/修改规则）见统一规格文档。

| 节点 | 执行 | 上游输入 | 下游输出 → 谁 | 配对审阅 Agent | 门禁 |
|:----:|------|----------|---------------|----------------|:----:|
| N1 选题拆解 | selector | 题面+problem_lock+similar_papers | ProblemNotes+KeyRequirements → N2/N3 | reviewer | M1+H1 |
| N2 数据预处理 | dataprep | ProblemNotes+Data/raw | DataLog+processed/feature → N3/N4 | reviewer | D1 |
| N3 模型搭建 | modeler | ProblemNotes+DataLog | ModelDocs 三件 → N4/N5/N6/N7 | reviewer | P1 |
| N4 代码（迭代环） | coder | formula.md+DataLog | Code/（output 唯一口）→ N5/N6/N8 | **mm-code-reviewer** | P2+A1+H2+S\<n\> |
| N5 调优（迭代环） | tuner | Code/+ModelDocs | sensitivity/error/validation → N6/N7 | **mm-code-reviewer** | T1 |
| N6 可视化 | visualization | output/figures+ModelDocs | ResultFigures 精选+figure-list → N7 | **mm-viz-reviewer** | V1 |
| N7 论文（迭代环） | writing | 全部前序+台账 | ReportPaper/LaTeX+去AI化 | reviewer（论文评审含去AI检测） | W1+A2+W2+H3+S\<n\> |
| N8 终审 | reviewer | ReportPaper+全产物+留痕 | 审阅记录+提交清单 | 终稿评审报告（豁免审阅≠执行） | A3+闭环终检 |

**Deep Research 每轮介入（N4/N5/N7 必须按需；每次 `dr-note` 留痕，N8 可 `dr-list` 核对）**：SEARCH（research_architect 结构化根因→RQ、literature/researcher 检索+卡片、synthesis 方案对比）；SCORE（synthesis 对照 case_refs/SOTA 核查技术先进性，无基线 ≤6 [NO-BASELINE]）；DECIDE（不达标 report_compiler 出失败根因+下轮方向、synthesis 给候选方案）。触发判据：技术瓶颈→检索方案；需论证→查文献；需系统梳理→全链深度调研。

---

## 题目事实锁定（所有阶段的前置门禁）

AI 在分析、建模、编程、调优、绘图或写作前，必须先读取题目原文，而不是仅凭用户摘要或历史上下文。编排 Agent 将题目原文 SHA-256、任务目标、前提条件、硬约束、数据要求和评价指标写入 `state/problem_lock.json`；N1 及之后节点启动前必须验证该锁定文件。

任何阶段发现题目原文、目标、约束、数据定义或评价指标发生变化，必须暂停当前任务，重新执行题目拆解并更新锁定文件；不得继续沿用旧模型、旧代码或旧论文结论。每次运行实验和论文改写前都要复核题目事实锁定，确保输出与题目要求一致。

推荐命令：

```bash
python shared/state-engine/problem_guard.py verify --project <项目目录>
```

## 状态统一节点与节点独立执行

（完整协议见 `mm-iteration-engine` Skill，此处为总控口径。）

- 每个项目维护一个外部状态统一节点 `state/`：`decision_log.json`（schema 2.0，唯一事实源）+ 总状态工作栏 `dashboard.md` + 9 个节点单独首页 `nodes/<名称>/dashboard.md` + 调用路由注册表 `registry.json` + 案例库 `cases/`。
- **Phase 0 铁律**：初始化时全量预建 state（全部 pending）随首次 commit 入库——状态节点属前期工作，之后即使只启动中间某几个节点，也只刷新对应节点首页。
- **节点独立执行**：单独触发某节点时，该节点 Agent 自治联动（检查前置→执行→自检→请求配对审阅→修复小循环≤2 次→刷新首页→交付）；上游缺失时输出 `[PREREQ-REQUEST]`，审阅请求输出 `[REVIEW-REQUEST]`。
- **审阅配对铁律**：审阅 Agent ≠ 执行 Agent；审阅前必须加载配对 Skill 并在审阅记录中声明；代码/算法审阅用 **mm-code-reviewer**，图表审阅用 **mm-viz-reviewer**，选题/数据/建模/论文审阅用 **reviewer**（按 §9 阶段定义表）。

---

## 迭代循环接线

- **代码迭代环（N4/N5）**：`SEARCH（读 state/search_sources.json 按实际需求选检索地址：要代码→github-code/paperswithcode，要原理→paper-academic，要对标获奖论文→contest-papers，要库用法→lib-docs，要数据/模型→model-zoo；命中案例 case-add --source-type/--query 沉淀）→ SELECT → IMPLEMENT（roundN 分支）→ RUN → COMMIT → SCORE（mm-code-reviewer 代码五维评分，落盘 S\<n\>-N4/N5 门禁）→ DECIDE`。默认 pass 7.0 / target 8.0 / ≤5 轮。
- **论文迭代环（N7/N8）**：同状态机，reviewer 论文五维评分。默认 pass 6.5 / target 7.5 / ≤4 轮。
- 每轮至少 3 次 git 提交（implement/run/score），commit 信息带 `Round:/Agent:/Stage:/Gate:/Goal:/Score:/State-Sha:` trailer，评分挂 `git notes --ref=score`；评分 ≥ pass 才 merge 回 main（决策动作含 early_stop/pass_continue/max_rounds_pass/plateau_pass/budget_pass/keep_best）。
- 阈值与轮数可改：编辑 `state/decision_log.json` 的 `termination` 配置。

---

## Phase 门控规则

| 门控点 | 条件 | 不满足时处理 |
|-------|------|------------|
| Phase 0 → 1 | `state/` 预建齐全 + git 首次提交完成 | 补齐初始化 |
| Phase 1 → 2 | M1 通过 + 用户确认（H1） | 回退 selector 修订 |
| Phase 2 → 3 | D1 通过（数据质量合格） | 回退补充数据处理 |
| Phase 3 → 4 | P1 通过（公式完整/假设有据/选择有对比） | 重新选型 |
| Phase 4 → 5 | P2 + A1 通过 + H2 人工确认（数值量级），迭代评分达 termination 决策 | 进入下一轮迭代或修复代码 |
| Phase 5 → 6 | T1 通过（基线/对比/敏感性/鲁棒性齐备） | 继续调优或换模型 |
| Phase 6 → 7 | V1 通过（图表规范核对） | 修复图表 |
| Phase 7 → 8 | W1 + A2 + W2 通过 + H3 人工确认（论文整体），迭代评分达 termination 决策 | 进入下一轮论文迭代或补充写作 |
| Phase 8 → 完成 | A3 终扫通过 + 提交清单核对完成 | 返回对应阶段修复 |

> A1/A2/A3 为硬阻断门禁，不通过不得推进。人工门 H1/H2/H3 在用户不在时写入 `state/human_checkpoint.md` 挂起。

---

## 产出格式规范摘要

### 通用规范
- 所有 Markdown 产物使用 UTF-8 编码
- 图表统一输出 PDF（矢量）或 PNG（≥300dpi）
- 代码文件统一使用 Python 3.11+ 语法（与 pyproject 和 CI matrix 一致）
- 🔴 运行代码前必须创建并激活虚拟环境（`python -m venv .venv` + activate），依赖装于 venv 内（Windows: `.venv\Scripts\activate`；Linux/macOS: `source .venv/bin/activate`）
- 论文使用 LaTeX (ctexart)，遵循 GB/T 7714 参考文献格式

### 国赛论文硬性约束
- CUMCM 2026 profile：PDF 第1承诺书/第2编号页/第3摘要页（≤1页）/第4起正文≤30页，附录不限；PDF≤20MB，支撑材料包≤20MB且与 PDF 分离
- 正文页数以导出 PDF 第4页起实际页数核对，禁止用 Word 页数替代
- 图表连续编号（图1, 图2, ...；表1, 表2, ...）
- 公式使用 `\eqref{}` 交叉引用

---

## Anti-Patterns

| # | 反模式 | 后果 | 正确做法 |
|---|--------|------|---------|
| 1 | 跳过 Phase 0 初始化直接开跑 | 状态页缺失、无法联动恢复 | 先 `state_utils.py init` 预建 state |
| 2 | 跳过数据直接建模 | 模型脱离实际 | 必须先完成 Phase 2 |
| 3 | 不看上游产物直接开发 | 方向偏差 | 每阶段读取全部上游产物 |
| 4 | 代码不加注释 | 论文附录不可读 | 代码与公式对应注释 |
| 5 | 图表不编号 | 论文引用混乱 | 连续编号 + 交叉引用 |
| 6 | 执行 Agent 自己审自己 | 自审失真 | 按配对矩阵派发独立审阅 Agent |
| 7 | 审阅前不读对应 Skill | 审阅标准漂移 | 先加载配对 Skill 并声明 |
| 8 | 每轮迭代不提交 git | 无法回溯对比 | implement/run/score 三次提交 + trailer |

---

## Integration with Sub-Skills（协调层：按能力选择，不写死名单）

本插件**不再维护"阶段 → 具体 skill 名"的固定清单**。该映射由 `mm-skill-router` 在每次开工前
运行时生成：扫本机已装 skill → 按能力词表匹配 → 产出派发清单。理由：专业 skill 会升级、
被替换、被新增，写死在插件里就会过期，且会把插件的副本与专业 skill 的真实版本割裂。

```
数学建模主线（本插件自带，固定）：
  mathematical-modeling + mm-iteration-engine  -> Phase 0/4/5/7/8：状态节点、迭代循环、审阅配对、git 规范
  mm-skill-router                              -> 全阶段：开工前按能力选择本次要加载的专业 skill
  mm-problem-analysis / mm-data-preprocessing / mm-model-library /
  mm-algorithm-dev / mm-model-tuning / mm-visualization /
  mm-latex-writing / mm-self-review            -> Phase 1-8 各阶段专业规范（registry.required_skills）

专业支撑 skill（运行时发现，示例仅示意，非白名单）：
  Phase 1 选题    -> 文献检索/研究设计类能力（如 deep-research 类）
  Phase 2/5 数据  -> 统计分析/数据清洗类能力
  Phase 3 建模    -> 研究设计/方法论证类能力
  Phase 6 图表    -> 数据图/结构图/图表审计类能力
  Phase 7 论文    -> 论文写作/写作风格/LaTeX 编译/引用核查类能力
  Phase 8 评审    -> 同行评审/证据边界核查/去 AI 化类能力
```

**更换或新增专业 skill 的操作**：把 skill 装到本机即可（`~/.zcode/skills` 或插件包）。
下次 `node-start` 自动重新扫描并反映到派发清单；如需立即刷新，跑
`python state/state_utils.py skill-plan <节点> --apply`。

**能力词表**（唯一需要改插件的地方，仅当"能力"本身变化时）：
`shared/skill-routing/capability_taxonomy.json` —— 只写能力与关键词，**不写 skill 名**。

---

## References

| 资源 | 说明 |
|------|------|
| CUMCM 官网 | 国赛赛题、评分标准、格式要求 |
| `mm-iteration-engine/SKILL.md` | 迭代引擎与状态统一节点（schema 2.0、审阅配对、迭代循环、git 规范、评分体系、goal/loop 插件适配；状态引擎源在共享层 `shared/state-engine/`，旧路径垫片兼容） |
| `mm-skill-router/SKILL.md` | 技能路由协调层：开工前按能力匹配本机已装专业 skill，产出派发清单并参与门禁校验 |
| `shared/state-engine/state_utils.py` | 状态节点命令行助手（源；init 时复制进项目 state/，统一用 `python state/state_utils.py <命令>`；引擎技能原 scripts 目录保留转发垫片兼容旧调用） |
| `mm-problem-analysis/SKILL.md` | 选题拆题详细规范 |
| `mm-data-preprocessing/SKILL.md` | 数据预处理 SOP |
| `mm-model-library/SKILL.md` | 高频模型速查库 |
| `mm-algorithm-dev/SKILL.md` | 算法开发规范 |
| `mm-model-tuning/SKILL.md` | 迭代调优规范 |
| `mm-visualization/SKILL.md` | 竞赛图表规范 |
| `mm-latex-writing/SKILL.md` | 国赛论文写作规范 |
| `mm-self-review/SKILL.md` | 自检评审规范 |

---

## Pro 知识库融合（v1.7.0）：优秀论文案例库与 A/B/C 方案

> 融合自 math-modeling-skill-pro（作者授权）：139 张 CUMCM 优秀论文案例卡（2012—2025）与选型/验证/创新决策规则，挂接既有 Phase 0-8，不新增组件、不改门禁。

### 资产位置
- 案例库：`skills/mathematical-modeling/assets/case-library/`（case-001..139 + index.json/csv/md + case-card-template + corpus-provenance）
- 决策规则总览：`skills/mathematical-modeling/assets/pro-library/overview.md`（原仓库 SKILL.md 决策链与输出契约）
- 语料观察图谱：`skills/mathematical-modeling/assets/pro-library/corpus-analysis.md`（问题类型/模型/验证分布，仅作检索线索）

### Phase 1 案例检索闭环（N1 必做）
选题拆解（selector）在 M1 审阅前必须执行：
1. `python state/state_utils.py case-search "<问题结构检索词>" --top 6`（`--skill-root` 指向技能安装根；推荐按「问题结构/数据结构/数学结构」分 2-3 次检索，混合链每个阶段一次再并集去重）
2. 读取 top 命中卡片的 `transferable_patterns`/`models`/`validation_methods`，比较问题/依赖结构、数据 regime、目标与约束形式、验证设计
3. `--save` 沉淀命中卡到 `state/cases/`（source_type=pro-case-library），随 N1 派发携带；禁止纯内生，也禁止把历史模型名称当普遍最优
4. 案例中的阈值/权重/参数/题目专属机制为不可迁移信息；OCR 抽样卡未核验细节不得当作已核验

### 与既有流程的关系
- Phase 0-8 主线、门禁、铁律、MCP 必调链、state 协议全部不变；本小节只新增案例检索调用点与证据来源。
- 案例检索是 MCP 论文搜索的补充（本地结构化检索），不替代 N1 必调 MCP 论文搜索与知识卡片沉淀。
- 证据边界：案例卡是决策记忆转述，非论文原文库；模型频次只能用于检索，不能证明模型优越（corpus-provenance.md 约束）。

### 使用时机（全链路）
| 节点 | Pro 资产接入点 |
|---|---|
| N1 选题 | case-search 案例类比 + problem-types/problem-dependencies（mm-problem-analysis） |
| N3 建模 | model-selection 三方案 A/B/C + model-library 模型卡（mm-model-library） |
| N4 代码 | code-skeletons 骨架 + 断言纪律（mm-algorithm-dev） |
| N5 调优 | validation-methods 四层验证 + 敏感性/稳健性（mm-model-tuning） |
| N7 论文 | innovation-patterns + paper-writing + abstract/outline 模板（mm-latex-writing） |
