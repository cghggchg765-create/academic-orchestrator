---
name: mm-iteration-engine
description: "数学建模迭代引擎与外部状态统一节点：state 状态工作栏、节点独立执行与自治联动、专用审阅 Agent 配对、SEARCH（检索地址注册表）→IMPLEMENT→RUN→COMMIT→SCORE→DECIDE 迭代循环、Git 分支/提交规范、代码与论文双评分体系、ZCode/Codex goal/loop 插件适配。触发词：迭代, iteration, 评分, score, 分支, branch, round, 状态节点, state, 案例搜索, 检索地址, 代码迭代, 论文修改"
metadata:
  version: "2.0.0"
  last_updated: "2026-08-19"
  status: active
  related_skills:
    - mathematical-modeling
    - mm-algorithm-dev
    - mm-model-tuning
    - mm-self-review
    - mm-visualization
    - code-review
    - deep-research
    - literature
    - researcher
---

【范围】竞赛项目的迭代评分与状态节点。普通项目的开发迭代用 test-driven-development / systematic-debugging / subagent-driven-development。

# 迭代引擎与外部状态统一节点（mm-iteration-engine）

本 Skill 是数学建模多智能体系统的**状态底座 + 迭代引擎**。它定义：

1. 标准项目结构（MathModel_Contest 适配版）与产物落点映射
2. 外部状态统一节点 `state/decision_log.json`（schema 2.0，参考项目 ref/math_model schema 1.0 的严格超集）
3. 状态工作栏与 9 个节点单独首页（初始化时全量预建，属前期工作）
4. 节点自治联动协议（单独调用任一节点也能自主推进、高质量交付）
5. 专用审阅 Agent 配对矩阵与调用路由注册表（总体调用机制）
6. 迭代循环状态机（SEARCH→DECIDE）与 Git 分支/提交规范
7. 代码/论文双评分体系、硬上限与终止条件
8. **检索地址注册表**（SEARCH 网络搜索源：开源项目/代码、论文、算法、获奖论文等渠道，结合实际需求选源）
9. ZCode/Codex goal/loop 插件适配

宿主为 Codex CLI / ZCode CLI 等命令行 Agent 工具。**全部机制基于文件**（JSON 状态 + Markdown 状态页），不依赖常驻服务。
统一命令入口：初始化后使用项目内副本 `python state/state_utils.py <命令>`（脚本在 init 时自动复制进项目，随仓库提交）。

---

## 1. 标准项目结构（MathModel_Contest 适配版）

每个竞赛项目初始化时按以下结构搭建（由 `python state/state_utils.py init` 一键生成）：

```
MathModel_Contest/
├── .gitignore                  # Python/LaTeX/IDE/虚拟环境/缓存日志全量忽略
├── README-项目总说明.md         # 项目总览、运行环境、复现步骤、团队分工（Phase 0 生成）
├── state/                   # 【核心】外部状态统一节点（前期工作，初始化全量预建）
│   ├── decision_log.json       # 全局状态（schema 2.0，唯一事实源）
│   ├── dashboard.md            # 总状态工作栏（9 节点卡片+门禁+待办）
│   ├── registry.json           # 调用路由注册表（任务→执行/审阅 Agent→必读 Skill→门禁→产物）
│   ├── search_sources.json     # 检索地址注册表（SEARCH 网络搜索源，见 §12）
│   ├── human_checkpoint.md     # 人工在环挂起记录（H1-H3）
│   ├── state_utils.py          # 状态节点命令行助手（init 时复制，项目自包含）
│   ├── cases/index.json        # 优秀案例库索引（SEARCH 沉淀，case_*.json 同目录）
│   ├── reports/                # 迭代报告留存（review/decision/result 自动归档 + index.json，跨轮复读对比）
│   ├── agents/<agent-id>/      # result.json（唯一写回点）+ claim.json（租约）
│   └── nodes/                  # 9 个节点单独首页（初始化预建，全部 pending）
│       ├── N0-需求确认/dashboard.md  ├── N1-选题拆解/dashboard.md
│       ├── N2-数据处理/dashboard.md  ├── N3-建模/dashboard.md
│       ├── N4-代码/dashboard.md      ├── N5-调优/dashboard.md
│       ├── N6-图表/dashboard.md      ├── N7-论文/dashboard.md
│       └── N8-评审/dashboard.md
├── ProblemInfo/            # Problem.pdf + ProblemNotes.md（selector 产物）+ TeamInfo.txt + TimePlan.md + KeyRequirements.md
├── Data/                    # raw（禁改）/ processed / feature / test_result + DataLog.md（dataprep 产物）
├── Code/                    # config.py + main.py（统一入口）+ requirements.txt + README-Code.md
│   ├── utils/（data_io/preprocess/metrics/logger/model_utils）
│   ├── problem_1~4/（按职责分文件：solver/model/data/analysis；单文件≤300行、单函数≤50行）
│   ├── visualization/（plot_base.py + 按需出图脚本）
│   └── output/                 # 【唯一输出口】tables/ figures/ txt_result/ model_save/（runs 日志亦在此）
├── ResultFigures/          # 论文级统一图库（visualization 从 output 精选入库，去冗余）
│   ├── schematic/ curve/ heatmap/ comparison/ + figure-list.md（编号/用途/对应论文章节）
├── ReportPaper/            # LaTeX（main/preamble/config/ref.bib/sections/img/tables；PDF 仅为编译产物）
├── ModelDocs/              # model-framework.md + formula.md + assumption.md（modeler 产物）+ sensitivity/error/validation（tuner 产物）
├── SubmissionPackage/      # 论文.pdf + README-提交说明 + Appendix_附件 + 代码压缩包 + 参赛提交清单.md（reviewer 终审核对生成）
├── Material/               # 自有笔记：training_notes / contest_experience（第三方资料不放这里）
├── External/refs/          # 只读引用区：同行代码/方案/论文/模板（哈希锁定 + 污染检测）
│   ├── papers/  templates/    #   转成自有产物须 derive 登记来源
├── LogRecord/              # daily-log.md + bug-fix-log.md + version-update.md（AI 每轮迭代自动追加，随状态一起 git 提交）
├── BackupArchive/          # draft/mid/final 人工备份（git round 分支为主，此目录人工兜底）
└── DefenseMaterial/        # defense_ppt / defense-script / show-figures（答辩期可选）
```

关键规则：
- **代码只写 `Code/output/`**（唯一输出口）；论文级图片由 visualization 去冗余精选到 `ResultFigures/` 并维护 `figure-list.md`。
- `ReportPaper/LaTeX/img/` 用**相对路径引用** `../../ResultFigures/`（Windows 下不用软链接）。
- `BackupArchive/` 与 git 分工：git round 分支为主备份手段，该目录供人工兜底。
- 初始化幂等：已初始化的项目再次 init 会被拒绝（`--force` 才重建，⚠ 清空全部状态）。
- 🔴 **目录与文件命名规范**：项目根目录用项目名（如 `2026_CUMCM_Problem_A` / `MathModel_Contest`）；**禁止 `xxx-main` / `xxx-master` 后缀目录名**（GitHub zip 解压产物形态），禁止在项目内再嵌套同名子目录（init 会自动去除 `-main/-master` 后缀）；**项目名/目录名/文件名禁止纯数字**（如 `01`、`000`），文件一律语义命名（`fig1_results_comparison.png`、`main_round1.pdf`、`p1_solver.py`），禁止 `main_v000.pdf`、`000.png` 式纯数字版本命名（版本文件用 `main_roundN.pdf` / `main_final.pdf`）。
- 🔴 **虚拟环境铁律**：运行任何代码前必须创建并激活虚拟环境（`python -m venv .venv` → Windows: `.venv\Scripts\activate` / Linux/macOS: `source .venv/bin/activate` → `pip install -r Code/requirements.txt`），禁止用系统全局 Python 直接运行。

## 2. 产物落点映射表（取代 01-08 平铺命名）

| 阶段（产物编号） | 落点 | 执行 Agent | 审阅 Agent | 门禁 |
|---|---|---|---|---|
| Phase 0 需求确认 | README-项目总说明 + TeamInfo + TimePlan + state 全量预建 + git init | orchestrator | — | — |
| Phase 1 选题拆解 | `ProblemInfo/ProblemNotes.md` + `KeyRequirements.md` | selector | reviewer（节点审阅） | M1 + H1 |
| Phase 2 数据处理 | `Data/DataLog.md` + processed/feature/test_result | dataprep | reviewer（节点审阅） | D1 |
| Phase 3 建模 | `ModelDocs/model-framework.md`+`formula.md`+`assumption.md` | modeler | reviewer（节点审阅） | P1 |
| Phase 4 代码 | `Code/`（config/utils/problem_1~4，output 唯一输出口） | coder | **mm-code-reviewer** | P2 + A1 + H2 + S\<n\>-N4 |
| Phase 5 调优 | `ModelDocs/sensitivity-analysis.md`+`error-analysis.md`+`model-validation.md` | tuner | **mm-code-reviewer** | T1 |
| Phase 6 图表 | `Code/output/figures` → `ResultFigures/` 精选 + `figure-list.md` | visualization | **mm-viz-reviewer** | V1 |
| Phase 7 论文 | `ReportPaper/LaTeX/`（+Word 转换） | writing | reviewer（论文评审） | W1 + A2 + W2 + H3 + S\<n\>-N7 |
| Phase 8 评审 | `state/nodes/评审/` 审阅记录 + `SubmissionPackage/参赛提交清单.md` | reviewer | 终稿评审报告 | A3 |

> N8 为终审节点：由 reviewer 执行并输出终稿评审报告 + 提交清单核对（A3），属"评审环节的执行者即评审方"的设计豁免，不适用"审阅≠执行"铁律（其余节点必须独立审阅）。

## 3. 外部状态统一节点（`state/decision_log.json`）

### 3.1 Schema 2.0（ref schema 1.0 的严格超集）

```json
{
  "_schema": "2.0",
  "competition": { "name": "", "year": "", "problem": "", "language": "zh" },
  "stages": {
    "0_init":         { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {} },
    "1_analysis":     { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {} },
    "2_data":         { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {} },
    "3_modeling":     { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {} },
    "4_solving":      { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {}, "random_seed": null },
    "5_tuning":       { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {} },
    "6_visualization":{ "status": "pending", "completed_at": null, "artifacts": [], "decisions": {} },
    "7_writing":      { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {} },
    "8_review":       { "status": "pending", "completed_at": null, "artifacts": [], "decisions": {}, "final_score": null, "passed": false }
  },
  "nodes": { "N0": {"name":"需求确认","status":"pending","homepage":"state/nodes/需求确认/dashboard.md","goal":""}, "..." },
  "gates": {
    "M1": {"status":"pending","agent":null,"timestamp":null,"result":null},
    "D1": {}, "P1": {}, "P2": {}, "A1": {}, "T1": {}, "V1": {},
    "W1": {}, "A2": {}, "W2": {}, "A3": {},
    "H1": {"status":"pending","note":null}, "H2": {"status":"pending","note":null}, "H3": {"status":"pending","note":null}
  },
  "rounds": [],
  "decisions": [],
  "termination": {
    "code":  { "pass": 7.0, "target": 8.0, "max_rounds": 5, "plateau": {"window": 2, "epsilon": 0.3}, "budget": {"deadline": null} },
    "paper": { "pass": 6.5, "target": 7.5, "max_rounds": 4, "plateau": {"window": 2, "epsilon": 0.3}, "budget": {"deadline": null} }
  },
  "meta": { "created_at": "", "updated_at": "", "seq": 0, "skill_version": "1.1.0",
            "platform_mode": "", "current_round": null, "current_stage": null, "state_git_sha": null }
}
```

- **动态门禁键**：迭代评分门禁由 round-score 创建，键为 `S<轮次>-<节点>`（如 `S1-N4`、`S1-N7`），两环互不覆盖。
- `rounds[]` 每轮结构：`{ round, node, branch, goal, started, status, case_refs[], agent_claims[], artifacts[{path, sha256}], run{exit_code, stdout_ref, checks[]}, commits[{sha, message, when}], score{total, dimensions{}, judge, notes_sha}, gates_sn, decision{action, reason, feedback, best_round?, decided_by, timestamp} }`
- `decisions[]`：`{ id, stage, round, decision, reason, timestamp }`（追加式）。
- 兼容性：`competition/stages/meta` 键名语义沿用 ref；新字段全部增量，旧解析器可读新文件。

### 3.2 读写协议（铁律）

1. **单写者**：只有 orchestrator（主编排）写 `decision_log.json` 全局文件。
2. **子 Agent 唯一写回点**：执行/审阅 Agent 只写 `state/agents/<agent-id>/result.json`；开动前写 `state/agents/<agent-id>/claim.json` 租约：`{agent_id, node, round, claimed_at, ttl_s}`。orchestrator 派发前检查租约（claim 命令内置 ttl 检查），防止同一节点被重复派发。
3. **原子写**：一律"写临时文件 → `os.replace` 原子替换"，禁止直接覆盖写入（防读到半截 JSON）。
4. **seq 与并发**：每次写全局文件 `meta.seq += 1`（审计递增）。**单宿主进程假设**：多宿主并发的最终裁决以 git 提交顺序为准，配合租约 ttl 防重复派发。
5. **每阶段必读必写**：任何 Agent 开工前先读 `decision_log.json` 与本节点首页；收工后由 orchestrator 落盘决策。
6. **每次状态变更单独 git commit**（信息含 `State-Sha` trailer），`git reflog` 即撤销栈；`LogRecord/version-update.md` 随状态一起提交（不进工作区滞留）。

### 3.3 断点恢复算法

```
读 decision_log.json 快照
→ 找第一个 status != completed 的 stage / 非 PASS 门禁
→ 重放 rounds[] 确认已消费部分（claim/result 文件佐证）
→ 从该节点重新派发（已 PASS 门禁在相关产物变更后按"级联失效"规则重验）
```

### 3.4 阶段交接文件（handoff，🔴 独立拉出任何阶段前先读/生成）

**作用**：每个阶段"单独拉出来用"的自检入口——交接文件把"上游给了什么、本阶段要做什么、输出什么、是否就绪"固化成一个文件，脱离全流程也能独立开工。

- 生成/刷新：`python state/state_utils.py handoff <Nx> --dir <项目>`（`node-start` 会自动刷新本节点交接文件）；
- 内容：① 本阶段信息（执行/审阅 Agent、必读 skill、产物目录、门禁）；② **上游交接表**（每个上游节点的状态、审阅门禁、产物路径 + sha256 前 12 位）；③ 输入与输出约定（读上游产物时按 sha256 校验；输出只落本节点产物目录）；④ 待办与小步骤入口（todo.md / steps.md）；⑤ **就绪判定**（ready/blocked——上游未 completed 或门禁未过 → blocked，需先补跑上游"审阅→修改→再审阅"循环或输出 `[PREREQ-REQUEST]`）；
- **阶段联动铁律（防"阶段不完全/修改不完善就推进下一步"）**：
  1. `node-start` 机器校验：上游必须 completed **且审阅门禁 PASS/auto_passed/confirmed**（M1/D1/P1/P2/T1/V1/W2），否则拒绝开工并提示先完成上游审阅循环；
  2. `project-audit` 的 `premature_progression` 检测：任何已推进节点的上游未完成/未审阅 → 报告"阶段不完全即推进"（拦截绕过 node-start 的手工改状态）；
  3. 断点恢复/单节点拉出：先 `handoff <Nx>` 自检就绪判定，blocked 则先补上游再回来。

## 4. 状态工作栏与节点首页

- **总工作栏** `state/dashboard.md`：竞赛信息、git 分支/最近提交、9 节点卡片（状态/产物/最近审阅结论/门禁）、迭代轮次总览、待办区（next node、待人工 H1-H3）。由 orchestrator 用 `python state/state_utils.py dashboard-refresh` 维护。
- **节点单独首页** `state/nodes/<名称>/dashboard.md` 七区：基本信息（状态/最近更新实时刷新）/ 本节点 goal / 产物清单（path+sha256）/ 迭代记录（round→评分→决策→feedback→goal，按轮次更新不重复）/ 审阅记录（时间/审阅 Agent/**声明已读 Skill**/结论/问题清单）/ 门禁状态（含动态 S 门禁，自动同步）/ 回退备注。
- **初始化铁律**：Phase 0 必须预建全部 9 份节点首页 + 总工作栏 + decision_log.json + registry.json + search_sources.json + cases（全部 pending），随首次 git commit 入库。**即使只启动中间某几个节点**（如单独跑"代码迭代"），只刷新对应节点首页与总工作栏，其余节点首页保持 pending。
- 每次执行/审阅完成后：执行方与审阅方各自刷新本节点首页（`node-finish / node-review` 自动刷新状态行与门禁表），orchestrator 刷新总工作栏。

## 5. 节点自治联动协议（单独调用任一节点）

单独触发某节点（如"代码迭代""论文修改""只画图"）时，该节点 Agent 自主驱动闭环，不依赖人工逐步指挥：

1. **读状态**：读 `decision_log.json` + 本节点首页 + `registry.json`。
2. **前置联动检查**：
   - 上游产物缺失 → 优先直接委派上游节点 Agent 补跑（平台支持子代理委派时，执行 Agent 可放开 `task` 权限，**限定只能委派其上游节点 Agent 与配对审阅 Agent**）；
   - 平台不支持委派 → 输出信号 `[PREREQ-REQUEST] 缺失节点=<Nx>, 原因=<...>, 建议=<...>`，由 orchestrator 转派；
   - 产物存在但状态未登记 → 先补登记再继续。
3. **执行**：先写 `claim.json` 租约 → 执行本节点任务 → 自检 checkpoint。
   > 🔴 **节点执行三重强制**（node-finish 机器校验）：① 必须由**对应专业子 Agent** 执行并声明 `--agent`（须匹配 registry executor，禁止 orchestrator/主 agent 内联代做）；② 必须声明**已加载本节点 required_skills**（`--skills` 须含 registry 技能清单）；③ 迭代节点（N4/N5/N7/N8）必须经 `round-start` 开启迭代环，禁止直接标完成。执行者与技能声明写入 `state/nodes/...` 状态（executed_by / skills_used），供审计追溯。
4. **审阅联动**：请求配对专用审阅 Agent（直接委派，或输出 `[REVIEW-REQUEST] 节点=<Nx>` 由 orchestrator 转派）。审阅铁律见 §6。
5. **修复小循环**：审阅 FAIL → 据反馈自主修复（≤2 次）；仍失败 → `[ESCALATE]`。
6. **交付**：刷新本节点首页 + 写 `result.json` → 交付报告（产物 + 审阅记录 + 首页状态），保证单节点交付质量。

### 5.1 容错与降级协议（子代理失败自动重试 · 限流自适应降级 · H 门禁自动核查）

**子代理失败自动重试**：任何子代理调用失败/超时/返回非零，不得直接放弃——先按指数退避自动重新调起（工具：`scripts/resilience.py::retry_with_backoff`，默认 3 次、1s→2s→4s）；重试仍失败 → 按失败类型分流：

| 失败类型 | 处理 |
|---|---|
| 限流/超时（429、timeout、rate limit） | 进入"自适应并发"阶梯（见下）；单任务串行重试最多 2 次 |
| 逻辑失败（审阅 FAIL、校验不过） | 走修复小循环（≤2 次）→ 仍失败 → `[ESCALATE]` 或写 `status=failed` 的 result 供 orchestrator 重派 |
| 工具/环境缺失 | 如实写 `BLOCKED` + 原因 + 恢复建议，不伪装完成 |

**高并发限流自适应降级**：批量任务（如多问求解、多参数搜索、并发检索）默认 `max_workers` 并发；检测到限流错误后自动降级阶梯：`并发 → 减半 → … → 串行`，每档失败项先按指数退避重试（工具：`scripts/resilience.py::adaptive_parallel`）。降级过程与最终档位如实记录（`on_degrade` 回调 → 写入迭代报告），不得静默吞掉限流。

**H 门禁自动核查（减少人工介入）**：H1/H2/H3 人工确认环节默认启用"自动核查先行"：

1. orchestrator 委托**配对核查 Agent** 自动核验（H2 数值量级 → mm-code-reviewer；H3 论文整体/主张证据 → reviewer；H1 题型判定 → reviewer），核查 Agent 必须独立于执行 Agent；
2. 核查通过 → `python state/state_utils.py auto-check <Nx> --gate H2 --agent <配对审阅> --skills <...> --summary <结论> [--report <核查报告路径>]`：门禁置 `auto_passed`、生成核查报告（`state/reports/` kind=verification）、节点首页记录"自动核查"、human_checkpoint 登记"待人工追认"——**流程继续不挂起**；
3. 核查 FAIL → 走修复小循环（≤2 次）→ 仍失败 → `[ESCALATE]` + 人工挂起；
4. 用户回来后 `python state/state_utils.py h-confirm H2 [--note 说明]` 追认（auto_passed → confirmed）；需要严格人工把关时可把该步骤改回直接挂起。

**容错原则**：所有降级/重试/自动核查都必须留痕（reports/、human_checkpoint、decision_log），最终交付报告说明哪些环节自动完成、哪些待人工追认。

### 5.2 节点自动审阅与返修协议（独立 Agent 把关质量 · 防死循环 · 防 AI 偷懒）

节点交付默认走"独立审阅 → FAIL 返修 → 复审"闭环，生成序列命令：

```bash
python state/state_utils.py review-loop <Nx> --dir .
```

**自动审阅覆盖节点**（审阅 Agent 必须独立于执行 Agent）：

| 节点 | 自动审阅 Agent | 审阅内容 | 证据要求 |
|---|---|---|---|
| N1 选题拆解 | reviewer | 问题覆盖/隐性约束≥3/题型判定依据/各维度≥150字 | 引用 ProblemInfo 产物 |
| N2 数据处理 | reviewer | 缺失/异常/来源可追溯/数据量达标 | 引用 Data 产物与统计输出 |
| N3 建模 | reviewer | 公式完整/假设有依据/模型对比≥2 | 引用 ModelDocs 产物 |
| N4 代码 | **mm-code-reviewer** | 五维评分 + 硬上限 + 仲裁 | Code/output 运行证据 |
| N5 调优 | **mm-code-reviewer** | 基线/超参≥3组/敏感性/鲁棒性≥2 | 调优报告 + 运行日志 |
| N6 图表 | **mm-viz-reviewer** | 5 项前置门禁 + 20 项质量核对 + 图库去冗余 | 图文件 + figure-list |
| N7 论文 | reviewer | 五维评分 + 主张↔证据映射 | LaTeX + 运行证据 |
| N8 评审 | reviewer（终审） | 全维度反模式终扫 + 提交清单 | 全文核对 |

**返修循环（防死循环）**：审阅 FAIL → 执行 Agent 按 feedback 返修 → 复审；**返修硬上限 2 次**，达上限仍未通过 → `BLOCKED/ESCALATE` + 人工介入（绝不无限循环）。

**防空返修（防 AI 偷懒）**：
1. **审阅侧**：FAIL/BLOCKED 审阅必须附 `--evidence`（证据路径），无证据直接拒绝落盘（防走过场）；审阅必须声明 skills_read（已有铁律）；
2. **返修侧**：每次返修前后对比节点产物哈希（`node-repair-check`：记录快照 → 返修后对比），**产物无变化 = 空返修**，打回并计入返修次数；空返修累计达上限同样转 ESCALATE。

**执行要求**：返修必须基于审阅 feedback 的具体问题逐条修改，并在本轮报告中说明"改了什么、对应哪条 feedback、新证据在哪"；审阅 Agent 复审时核对问题清单逐条关闭，未关闭的不得 PASS。

### 5.3 审阅-修改-再审阅循环协议（🔴 通用：单项任务 / 阶段任务 / 整体系列任务统一执行路径）

**唯一合法路径**（无论处于哪个节点、任务规模多大，都严格按此往复）：

```
① 调用配对独立审阅子 Agent（先加载配对 skill 并声明）审阅产物
        │
        ├─ PASS → ② node-review 落门禁 → 节点 completed / 进入下一任务
        │
        └─ FAIL/BLOCKED（附 evidence）→ ③ 调用对应修改 Agent（= 该节点执行 Agent）
             先加载本节点 required_skills → 按 feedback 逐条修改/润色（node-log 记录修改步骤）
             → ④ 再审阅（同审阅 Agent，核对 feedback 逐条关闭）
             → 循环 ③④（硬上限 2 次，空修改打回）→ 仍不过 → BLOCKED/ESCALATE
```

**每节点循环角色表**（修改 Agent = 执行 Agent，修改时必须加载对应 skill）：

| 节点 | ① 审阅 Agent | ③ 修改 Agent（=执行 Agent） | 修改时必加载 skill |
|---|---|---|---|
| N1 选题拆解 | reviewer（节点审阅） | selector | mm-problem-analysis + mm-self-review |
| N2 数据处理 | reviewer（节点审阅） | dataprep | mm-data-preprocessing |
| N3 建模 | reviewer（节点审阅） | modeler | mm-model-library |
| N4 代码 | mm-code-reviewer | coder | mm-iteration-engine + mm-algorithm-dev + code-review |
| N5 调优 | mm-code-reviewer | tuner | mm-model-tuning + mm-iteration-engine |
| N6 图表 | mm-viz-reviewer | visualization | mm-visualization + mm-iteration-engine |
| N7 论文 | reviewer（论文评审，含去AI化检测） | writing | mm-iteration-engine + mm-latex-writing + mm-self-review |
| N8 评审 | reviewer（终审） | reviewer（按终审问题返修） | mm-self-review |

**禁止事项（违反即流程违规）**：
1. 执行完**不审阅直接标完成**——audit 的 `unreviewed_completion` 会检测"completed 但门禁未过"；
2. 审阅 FAIL 后**不修改直接再审或直接放行**——复审必须核对上轮 feedback 逐条关闭；
3. 修改时**不加载本节点 skill**（node-finish 的 --skills 校验缺失即拒绝）；
4. 修改**空转不产生产物变化**（node-repair-check 哈希对比打回）；
5. 循环**超过 2 次硬上限**（转 BLOCKED/ESCALATE，防死循环）。

> 单项任务：一个节点的完整循环；阶段任务：迭代节点（N4/N5/N7/N8）每轮走"审阅→评分→修改→再审阅"（round-score/round-decide 裁决）；整体系列任务：每个阶段依次完成各自循环后进入下一阶段。生成循环序列：`python state/state_utils.py review-loop <Nx> --dir .`。

### 5.4 分片审阅与修复协议（scope-aware，防上下文稀释）

当 N7 论文、N4 代码或 N5 调优任务可按章节/小节/子问题拆分时，必须先执行 `scope-plan`，保留父节点 N4/N5/N7/N8，不创建伪节点：

1. **分片边界**：N7 默认按章节；模型建立与求解等超长章节按子问题/小节再拆分；N4/N5 默认按 `question_1`…`question_4`。每个 scope 有唯一 `scope_id`、父节点、轮次、UTC 时间戳、输入文件哈希和 registry 哈希。
2. **有界上下文**：Agent 只读取 scope manifest 指定的目标文件、相邻上下文和证据指针；不得为“全面检查”读取整篇论文、全部问题代码或全部输出。跨 scope 问题写入 aggregate/join 检查项。
3. **只读审阅可并行**：首轮 `reviewer` 内容审阅和 `latex_linter` 格式审阅可以并行；各自只能写 scope 工作区报告，不能改业务产物。
4. **写入必须串行且分阶段**：内容问题先由 writing/coder/tuner 按 scope 串行修订，并由 reviewer 反向复审；所有内容 scope PASS 前，typesetting 不得写共享 `.tex`、preamble、交叉引用或公共配置。
5. **排版后重建与反向复核**：内容全部通过后，typesetting 串行修订格式；随后重新编译/运行，latex_linter 与 reviewer 可并行复核，最后 reviewer 执行 join review。join 通过后才能 `scope-promote`，再由父节点执行 `round-score/round-decide`。
6. **父子状态隔离**：scope 结果、报告、claim、artifact hash 使用 `(node, round, scope_id)` 隔离；单个 scope PASS 不得直接把父节点标记 completed；无 scope 的旧记录继续按全局流程解释。
7. **空返回门禁**：空/全空白返回、只有“已完成”或缺少 artifact、changed_files、checks、timestamps 的结果统一为 `EMPTY_RETURN`；自动缩小上下文并重试一次，第二次仍空则写 recovery、`BLOCKED/ESCALATE`，不得无限等待或内联代做。

## 6. 专用审阅 Agent 体系 + 调用路由注册表

### 6.1 审阅配对矩阵（审阅独立于执行）

| 节点 | 执行 Agent | 配对审阅 Agent | 审阅前必读 Skill（在审阅记录中声明） | 门禁 |
|---|---|---|---|---|
| N1 选题拆解 | selector | reviewer（节点审阅模式） | mm-problem-analysis + mm-self-review | M1 + H1 |
| N2 数据处理 | dataprep | reviewer（节点审阅模式） | mm-data-preprocessing | D1 |
| N3 建模 | modeler | reviewer（节点审阅模式） | mm-model-library | P1 |
| N4 代码/代码迭代 | coder | **mm-code-reviewer（专用）** | mm-iteration-engine + mm-algorithm-dev + code-review | P2 + A1 + H2 + S\<n\>-N4 |
| N5 调优 | tuner | **mm-code-reviewer（专用）** | mm-model-tuning + mm-iteration-engine（审 N5 加读 mm-model-tuning） | T1 |
| N6 图表 | visualization | **mm-viz-reviewer（专用）**；另有 mm-figure-table-benchmarker 出 B1 | mm-visualization + mm-iteration-engine + **figure-table-benchmark** | V1 + **B1** |
| N7 论文/论文修改 | writing | reviewer（论文评审专用模式） | mm-iteration-engine + mm-latex-writing + mm-self-review | W1 + A2 + W2 + H3 + S\<n\>-N7 |
| N8 评审 | reviewer | 终稿评审报告 + 提交清单核对（§2 豁免说明） | mm-self-review | A3 |

### 6.2 调用路由注册表（总体调用机制）

`state/registry.json`（机器可读，与本 SKILL 的 §6.1 表格双份一致）。每节点条目：

```json
{
  "id": "N4",
  "name": "代码/代码迭代",
  "trigger_phrases": ["写代码", "实现算法", "代码迭代", "修代码"],
  "executor": "coder",
  "reviewer": "mm-code-reviewer",
  "review_mode": "code-score",
  "required_skills": ["mm-iteration-engine", "mm-algorithm-dev", "code-review"],
  "gates": ["P2", "A1", "H2"],
  "artifact_dir": "Code/",
  "homepage": "state/nodes/代码/dashboard.md",
  "upstream": ["N3"]
}
```

（review_mode 取值：node-review / code-score / tune-check / viz-check / paper-review / final-review；迭代动态门禁 S\<n\>-节点 不在静态注册表中，运行时由 round-score 创建。）

**调用铁律**：
1. 任何委派必须与 registry 匹配（执行任务 → executor；审阅任务 → reviewer），不匹配 → orchestrator 纠正或 `[ESCALATE]`。
2. 被调用 Agent 必须先加载/阅读其 `required_skills`，并在输出/审阅记录中**声明所读 Skill 与版本**。
3. 审阅 Agent ≠ 执行 Agent（N8 终审为显式豁免）；专用审阅 Agent 只审不写业务文件（只写 `state/` 下的记录）。
4. 门禁结果带签名：`{agent_id + 时间戳 + 检查摘要}`；不支持的平台如实记 `BLOCKED`，不得谎称独立验收通过。
5. 🔴 **交叉审阅 = 独立 Agent 逐项核对执行 Agent 的产物**（审阅≠执行）：N7 论文由 reviewer 论文评审抽查**数据同源**（正文数字 vs `Code/output/tables/` 运行结果，结果正确性 30 分维度）；N4/N5 由 mm-code-reviewer 五维评分（效率维度核对实测耗时/GPU 正确性）；N6 由 mm-viz-reviewer 5 个前置门禁 + 20 项编号质量核对（含图-文-数据三方一致与数据同源抽查）。审阅 FAIL/BLOCKED 必须附 evidence，返修 ≤2 次（空返修打回），超限转 BLOCKED/ESCALATE。节点首页第 9 节固化该流程。

### 6.3 门禁定义（借鉴 ref 08-stage-verification 并扩展）

| 门禁 | 时机 | 通过标准（摘要） | 落盘路径 | 阻断级别 |
|---|---|---|---|---|
| M1 | N1 后 | 审题完整性：问题覆盖/隐性约束≥3 条有推导/题型判定≥3 条依据/**各维度 ≥150 字** | node-review N1 PASS | 阻塞进 N2 |
| D1 | N2 后 | CSV 可读 + 缺失报告 + 来源可追溯 + 数据量达标（行数≥指标列数×3）；**且数据血缘完整：`Data/data-lineage.json` 经 `scripts/validate_data_lineage.py` 校验 PASS（raw 哈希与 `Data/raw_lock.json` 一致、raw→processed→feature→test_result 链式连续、每级有变换脚本+参数+种子、diff.rows_delta 与实测一致）** | node-review N2 PASS（`--allow-missing-lineage` 仅离线特批） | 阻塞进 N3 |
| P1 | N3 后 | 算法正确性论证无漏洞（公式完整/假设有依据/选择有对比） | node-review N3 PASS | 阻塞编码 |
| P2 | N4 后 | 代码可运行 + 输出可追溯 + 代码-公式一致 | node-review N4 PASS | 阻塞进 N5 |
| A1 | N4 后 | 代码反模式扫描 0 个 High 命中 | **round-score N4 达标（total≥pass）自动 PASS** | ⛔ 硬阻断 |
| T1 | N5 后 | 基线已跑/超参对比≥3 组/敏感性覆盖关键参数/鲁棒性≥2 方法 | node-review N5 PASS | 阻塞进 N6 |
| V1 | N6 后 | 图号连续/中文无乱码/≥300dpi/每图有标注 | node-review N6 PASS | 阻塞进 N7 |
| **B1** | **N6/N7/N8** | **图表/表格文献对标：七维（列完备/统计量/单位/可比性/分组/图型/学术表达）逐维有证据，对标 ≥3 篇同领域论文，无 `GAP_MAJOR`；矩阵落 `state/reports/figure-table-benchmark/`** | **node-review B1 PASS（审阅者 = mm-figure-table-benchmarker）** | **阻塞图表定稿与论文提交** |
| W1 | N7 写作前 | 每个主张有代码输出/图表支撑 | **node-start N7 时 V1 已过自动 PASS** | 阻塞正文写作 |
| A2 | N7 后 | 写作反模式扫描 + 摘要 ≥4 数字 + 无套话黑名单 | **round-score N7 达标（total≥pass）自动 PASS** | ⛔ 硬阻断 |
| W2 | N7 后 | 论文五维评分 ≥ 6.0（入门门禁；迭代达标线为 termination.paper 的 pass 6.5 / target 7.5） | node-review N7 PASS | 阻塞进 N8 |
| A3 | N8 前 | 全维度反模式终扫 0 个 High 命中 | node-review N8 PASS | ⛔ 硬阻断 |
| H1/H2/H3 | N1/N4/N7 后 | 人工确认（题型判定/数值量级/论文整体），用户不在时写 `human_checkpoint.md` 挂起 | auto-check（自动核查）+ h-confirm（人工追认） | 人工在环 |
| S\<n\>-Nx | N4/N5/N7/N8 每轮 | 迭代轮次评分 ≥ pass（termination 配置） | round-score 自动创建 | 轮次内 |

> 说明：M1/D1/P1/P2/A1/A2/A3 与参考项目同类门禁对齐；T1/V1/W1/W2/B1/H1-H3 为系统扩展（ref 无对应定义）——"对齐参考项目"为**部分对齐**。
>
> **B1 判定口径**：`COMPLETE`（七维全 PASS 且 ≥3 篇对标）/ `GAP_MINOR`（仅单位/图型/学术表达问题）/ `GAP_MAJOR`（列完备/统计量/可比性/分组任一缺失，或对标不足 3 篇）/ `BLOCKED`（检索不可用）。
> 只有 `COMPLETE` 与 `GAP_MINOR` 可放行；`GAP_MAJOR` 必须回传 visualization（图）或 writing（表）补齐后复检；`BLOCKED` 由编排方决定降级并留痕。
> 判据来源：`skills/figure-table-benchmark/SKILL.md` 七维口径 + `references/benchmark-matrix.schema.json` 矩阵结构。

## 7. 迭代循环状态机（作用于 N4/N5 代码环、N7/N8 论文环）

> **scope 优先入口**：用户说“只迭代第几问/只改某章/检查某节”时，先 `scope-plan` 再进入本节；每问/每章独立记录运行证据和反馈，父节点只在 scope aggregate/join 通过后评分。

```
SEARCH  ① 根因分析（本轮要解决的缺陷 = 上轮 DECIDE failure_analysis / SCORE feedback / 项目 audit 发现）
        → ② 方案论证（为什么选此方案/渠道）→ ③ 读 state/search_sources.json 按需求重新检索外部资料
        （MCP/WebSearch/paper-mcp/gh_grep/context7/竞赛论文库，禁止纯内生、禁止沿用旧轮留痕）
        → 命中案例 case-add 沉淀 cases/（登记 source_type/search_query）+ 知识卡片沉淀 state/reports/mcp-cards/
        → 留痕写 state/reports/mcp-calls.jsonl；未命中 → 退化为内置方法库（mm-model-library / mm-algorithm-dev）并如实记录
SELECT  案例选型 + 记录 decision
  ↓
IMPLEMENT  创建分支 round{N}_{任务}_{slug} → 写 claim → 实现/优化/修改代码或论文
  ↓
RUN  运行验证（exit_code + checks[]，代码环强制 python 运行 + 关键数字 ≥3 个可追溯）
  ↓
COMMIT  每轮至少 3 次提交：implement（产物）→ run（运行日志/结果）→ score（状态+评分，含 State-Sha trailer）
  ↓
SCORE  配对审阅 Agent 多维评分（代码/论文 rubric + 硬上限 + 极差仲裁）→ 落盘 S{n}-<节点> 门禁
        🔴 机器校验（禁止纯内生）：核心节点（N4/N5/N7）本轮无检索留痕 → round-score 拒绝评分
        🔴 先进性核查：innovation/建模创造性维度必须与检索到的外部基线（case_refs/SOTA/获奖论文）对比给分，
        无外部基线时该维度 ≤ 6 并标注 [NO-BASELINE]（防"自说自话的创新"）
  ↓
DECIDE  读 termination 决策：
   score ≥ target          → early_stop：merge 回 main，节点完成
   pass ≤ score < target   → pass_continue：merge 回 main，可继续优化（记录 feedback+新 goal，下一轮重新 SEARCH）
   score < pass            → repair_and_rerun：不 merge，feedback 进入下一轮；
                              🔴 机器强制：必须提供 --reason 失败原因分析（根因/差距/下轮方案），
                              写入 decision.failure_analysis 作为下一轮 SEARCH ① 根因分析的输入
   达轮数上限 / 预算截止 / 平台期：
       score ≥ pass        → max_rounds_pass / budget_pass / plateau_pass：merge 并按达标收尾
       score < pass        → keep_best：记录历史最优轮（best_round/best_total/best_branch）+ [ESCALATE]
                              （同样强制 --reason 失败原因分析）
```

- 每个节点落盘契约：每步都写 `decision_log.json`（orchestrator 侧）或本节点首页（执行/审阅侧），崩溃可从任意节点恢复。
- 轮次状态：round-start 置 in_progress，round-decide 置 completed；同节点存在未决策轮次时禁止开新轮。
- 未达标分支不删除，标记 `abandoned`（写入该轮 decision），供后续横向对比借鉴。
- 🔴 **核心节点每轮必须重新检索（机器强制）**：`round-score`（N4/N5/N7 本轮）与 `node-review`（N1/N3 PASS）前置校验 `state/reports/mcp-calls.jsonl` 或 `state/cases/index.json` 留痕；缺失 → 拒绝并提示"禁止纯内生输出"（可 `--allow-missing-mcp` 显式豁免，仅离线/人工特批并留痕）。

### 7.2 Deep Research 自动迭代审阅 + 知识卡片派发（学术能力嵌入迭代环）

**触发**：一轮迭代不达标（repair_and_rerun / keep_best）需要深挖根因、或 SEARCH 需要系统性文献调研时，orchestrator **按需唤起 Deep Research**（`deep-research` Skill 及其已注册 Agent `research_architect_agent / synthesis_agent / report_compiler_agent`，或 `literature / researcher`）对失败根因做针对性调研，结果**回填下一轮 SEARCH 的依据**（根因分析 → 推荐方案 → 参考来源），并把检索结果沉淀为知识卡片。

**知识卡片派发（机器入口 `search-evidence <Nx>`）**：
- 所有核心节点 MCP 检索结果按 `mcp/knowledge-card.template.md` 沉淀为知识卡片（落 `state/reports/mcp-cards/`）、留痕 `state/reports/mcp-calls.jsonl`、文献归 `state/reports/references-ledger.md`（GB/T 7714）；
- orchestrator 后续派发该节点（或下游节点）时，先 `python state/state_utils.py search-evidence <Nx>` 汇总该节点知识卡片/案例/台账/MCP 留痕，**随派发 prompt / handoff 分发给对应执行与审阅 Agent**，作为其外部依据（禁止纯内生）；
- N8 终检按 `mcp/validation-checkpoints.md` 校验"六节点必调留痕 + 知识卡片 + 台账"闭环，无记录不通过。
- 🔴 **每轮介入留痕（可审计）**：N4/N5/N7 每次 Deep Research 介入（SEARCH 检索方案 / SCORE 先进性核查 / DECIDE 失败分析）执行 `dr-note <Nx> --round <n> --phase <...> --role <...> --topic <...>`，落 `state/reports/dr-interventions.jsonl` 并同步 `rounds[n].deep_research`；`dr-list <Nx> [--round n]` 查询，N8 终检可用其核对"每轮有据介入"。
- **统一规格（SSOT）**：9 阶段协作闭环、Deep Research 嵌入点清单、迭代环融合方案的完整口径见 `docs/optimization/agent-collaboration-loop.md`（orchestrator / 主控 SKILL / 本 SKILL 均引用之）。

### 7.1 迭代报告留存（跨轮复读、进步与修改的依据）

每轮迭代的报告**自动归档**到 `state/reports/`（`state_utils.py` 在执行 `round-score / round-decide / result-ingest` 时自动留存，无需额外操作）：

| 类型 | 触发 | 内容 |
|---|---|---|
| `review` | round-score | 独立审阅 Agent 实验报告：judge、五维评分、skills_read、evidence、verdict、阈值 |
| `decision` | round-decide | 决策报告：action、reason、feedback、best_round/best_total/best_branch |
| `result` | result-ingest | 完整结果 envelope 归档（含 checks、feedback、artifacts 与哈希） |

`state/reports/index.json` 维护全量索引；查询命令：

```bash
python state/state_utils.py report-list [--node N4] [--round 1] [--json]
```

报告随 `state/` 一起 git 提交（`git_commit_state` 已包含），跨轮对比时以 `report-list --json` + `git log --show-notes=score` 双通道为准。修复循环（≤2 次）产生的多份同轮报告按时间戳独立保留，不互相覆盖。

## 8. Git 规范（只作用于算法/代码与论文迭代）

- **分支**：`round{N}_{任务}_{slug}`（如 `round1_q1_solver`、`round2_paper_review`），从 `main` 切出；评分 ≥ pass 才 merge 回 main；每轮一个分支。
- **提交信息**：Conventional Commits + 结构化 trailer：

```
<type>(<scope>): <imperative summary>

<改动说明 2-4 行>

Round: <n>
Agent: <agent-id>
Stage: <Nx>
Gate: <S<n>-<Nx> PASS|FAIL>
Goal: <本轮目标（goal 插件写入）>
Score: {"total": 7.8, "dimensions": {...}}
State-Sha: <decision_log.json 写后 sha256 前 8 位>
```

  - `type` 扩展：`feat/fix/refactor/docs/chore/score/gate/exp/state`。
  - 评分同时挂 `git notes`：`git notes --ref=score add -f -m '<json>' <score-commit>`，`git log --show-notes=score` 横向对比各轮。
  - 每轮同步追加 `LogRecord/version-update.md`（一行一轮：分支/评分/决策/feedback），**随状态一起 commit**（不滞留工作区）。
  - **提交与 merge 顺序**：先 save_state → commit（在 round 分支上，含 state 与 version-update）→ 再 merge 回 main（状态提交随 merge 进入 main）；merge 失败必须停止并人工处理。
- **项目初始化（Phase 0）**：标准脚手架 + 本地 `git init` + 首次提交（含 state 全部预建页）→ **输出提醒：请用户创建 GitHub 仓库并执行 `git remote add origin <url>` 后自行推送（Agent 不代做推送）**。
- 禁止：`git push --force`、无确认删除分支/文件（需 `[ESCALATE]` 审批）。

## 9. 评分体系（termination 配置，可改）

### 9.1 代码环五维（0-10 分档锚点，由 mm-code-reviewer 执行）

| 维度 | 权重 | 锚点要点 |
|---|---|---|
| correctness 正确性 | 0.30 | 零报错运行/测试通过/代码-公式一致/数值可复现/输出可追溯（对齐 mm-algorithm-dev 运行验证 Checklist） |
| efficiency 效率 | 0.15 | 复杂度合理/无热点循环浪费/运行时间达标（单轮 <30min） |
| readability 可读性 | 0.15 | 模块化/命名规范/注释引用公式编号/README 完整 |
| robustness 鲁棒性 | 0.20 | 边界与异常处理/seed=42/参数集中 config/防零防溢出 |
| innovation 创新性 | 0.20 | 案例借鉴有出处（case_refs）/改进点有对比或消融证明/方法适配性论证；🔴 **先进性核查**：与检索外部基线（case_refs/SOTA/获奖论文）对比给分，无外部基线 → 该维 ≤6 并标注 `[NO-BASELINE]` |

### 9.2 论文环五维（国赛口径，归一化 0-10，由 reviewer 论文评审执行）

| 维度 | 权重 | 说明 |
|---|---|---|
| 假设合理性 | 0.15 | 每条假设有依据、有影响评估 |
| 建模创造性 | 0.25 | 创新点/方法恰当性/多模型对比；🔴 **先进性核查**：与检索外部基线（case_refs/SOTA/获奖论文）对比给分，无外部基线 → 该维 ≤6 并标注 `[NO-BASELINE]` |
| 结果正确性 | 0.30 | 结果可信/**与代码输出同源一致**/验证充分 |
| 表述清晰性 | 0.20 | 结构完整/语言清晰/图表规范/**去AI化（AI-ness 检测，加载 humanizer 技能执行）** |
| 格式规范性 | 0.10 | LaTeX 可编译/页数合规/引用与编号 |

> 🔴 **去 AI 化（humanize）**：论文评审（N7 每轮 + N8 终审）必须加载 `humanizer` / `academic-humanize` 技能做 AI-ness 检测（AI 套话/模板句式/机械排比/空泛总结），结果计入表述清晰性；N8 终审前由 orchestrator 委托 **humanize** 专项检测（报告落 `state/reports/`），有残留 AI 模式 → 返回 writing 修订后复审，检测通过才放行 A3。

### 9.3 硬上限与仲裁（两环共用，借鉴 ref 15-scoring-rubric）

- 硬上限（综合分取"加权值"与"规则值"较低者）：
  - 代码环：correctness < 6 → 总分 ≤ 5.0；robustness < 5 → ≤ 5.5；correctness < 3 → ≤ 4.0；任一维 < 3 → ≤ 4.0；两维及以上 < 5 → ≤ 5.0。
  - 论文环：结果正确性 < 5 → ≤ 5.5；建模创造性 < 3 → ≤ 4.0；任一维 < 3 → ≤ 4.0；两维及以上 < 5 → ≤ 5.0。
- 极差仲裁：多评审人同维度极差 ≥ 4.0 → 取中位数并标记 `[ARBITRATED]`；2.0-3.9 → 加权平均标记 `[SPLIT]`。
- 默认阈值（termination，可在状态文件中修改）：代码环 pass 7.0 / target 8.0 / ≤5 轮；论文环 pass 6.5 / target 7.5 / ≤4 轮。
- **与 ref 的关系**：维度体系为国赛五维（假设/创造性/结果/表述/格式），硬上限规则**借鉴** ref 的"rigor/results/modeling"上限结构并做维度映射（**部分对齐**，非原文照搬）。

## 10. ZCode/Codex 插件适配（goal / loop 等）

| 插件/机制 | 映射 | 说明 |
|---|---|---|
| **goal 插件** | 项目总目标 ↔ `termination`（pass/target/max_rounds）；每轮目标 ↔ `rounds[n].goal` + 节点首页"本节点 goal"区 | goal 未达成 → 触发下一轮；达成 → early_stop |
| **loop 插件** | loop 驱动 SEARCH→DECIDE 循环，退出条件读 `termination` | 每轮结果落盘 `rounds[]`，loop 退出条件与 DECIDE 决策同源（含 keep_best/max_rounds_pass 等动作） |
| TaskCreate/TaskUpdate | ↔ 节点首页刷新 + node-start/node-finish | 任务清单与节点首页双向同步 |
| subagent | ↔ 专用审阅 Agent（mm-code-reviewer / mm-viz-reviewer / reviewer） | 审阅必须独立子代理执行 |
| **降级（无插件平台）** | orchestrator 手动驱动等价循环；`meta.platform_mode` 记录实际模式 | 降级不谎报：不支持独立 Subagent 时门禁记 `BLOCKED` 并如实说明 |

- 分支名 / commit trailer / `git notes` 均设计为可被 goal/loop 插件与 `git log --grep "Round:"` 直接检索的格式。
- 平台支持插件时，loop 插件可读 `rounds[n].decision.action` 决定继续或退出；goal 插件可读 `rounds[n].goal` 检查达成状态。

## 11. 案例库（`state/cases/`）

- `index.json`：`{ "version": "1.0", "cases": [ {id, title, source, source_type, search_query, url, score, applicable, added_at, used_in_rounds[]} ] }`
- `case_<id>.json`：单案例摘要（方法/适用场景/关键参数/借鉴点/来源链接）。
- SEARCH 步骤产出：按 §12 选检索地址 → 命中案例 `case-add` 沉淀（**登记 source_type 检索渠道与 search_query 检索词**，保证"哪个地址+什么词"可追溯）→ IMPLEMENT 时把命中的案例写入 `rounds[n].case_refs`。
- 案例是跨轮、跨节点复用的资产：横向（同类题不同方法）与纵向（同方法不同改进）对比都以案例库为索引。

## 12. 检索地址注册表与需求驱动检索（SEARCH 网络搜索源）

`state/search_sources.json`（init 预建，可 `search-source add` 扩充）登记迭代搜索的网络地址。**SEARCH 步骤先读此注册表，按实际需求选源**。

| 渠道 id | 类型 | 地址 | 调用方式 | 检索词模板 | 适用场景 |
|---|---|---|---|---|---|
| github-code | 开源项目/代码 | github.com/search?type=code / Gitee / GitLab | gh_grep searchGitHub + WebSearch | `<题型关键词> <算法名> python` | 需要参考实现、开源代码 |
| paper-academic | 论文/算法 | arxiv.org / api.openalex.org / api.semanticscholar.org | paper-mcp paper_search + WebSearch | `<方法名> <问题域>` | 需要方法论论文、算法原理 |
| paperswithcode | 论文+代码对照 | paperswithcode.com | WebSearch / WebFetch | `<任务名> state of the art` | 需要论文+官方实现成对证据 |
| contest-papers | 竞赛优秀论文 | 数学中国 madio.net / CUMCM 官网历年优秀论文库 / GitHub 数模仓库 | WebSearch / WebFetch | `CUMCM <年份> <题号> 优秀论文 <方法>` | 获奖论文参照、评分点对齐 |
| lib-docs | 库/框架文档 | context7.com | context7 resolve-library-id + query-docs | `<库名> <API/用法>` | 不确定库 API、报错排查 |
| model-zoo | 预训练模型/数据 | huggingface.co/models \| datasets | WebSearch / WebFetch | `<任务> <数据形态> dataset/model` | 需要数据集、预训练模型 |
| zh-knowledge | 中文方法线索（非权威） | 知乎 / CSDN / 博客园 | WebSearch | `<题型> 数学建模 <方法>` | 仅作线索，落地前回源头验证 |

**需求驱动检索规则**：
1. **需求→渠道映射**：要代码 → github-code/paperswithcode；要原理 → paper-academic；要对标获奖论文 → contest-papers；要库用法 → lib-docs；要数据/模型 → model-zoo。
2. **检索词构造**：`题型关键词（ProblemNotes §1.7 判定）+ 任务动词（求解/预测/优化/评价）+ 数据形态`，中英文各一轮；命中案例 `case-add --source-type <渠道id> --query <检索词>` 沉淀，跨轮复用。
3. **优先级铁律**：官方文档/论文/获奖论文/开源实现 > 社区帖；社区帖只作线索，落地前必须回源头验证。
4. **失败回退**：指定渠道未命中 → 换同级渠道 → 退化为内置方法库（mm-model-library/mm-algorithm-dev）并如实记录。

## 13. state_utils.py 命令速查（统一用项目内副本）

```
python state/state_utils.py init --dir <项目目录> --name <竞赛> [--year YYYY] [--problem X] [--language zh] [--git] [--force]
python state/state_utils.py dump [--dir .]
python state/state_utils.py stage-set <key> <status> [--artifact p] [--decision d] [--dir .]
python state/state_utils.py gate-set <GATE> <PASS|FAIL|BLOCKED> [--agent A] [--result R] [--dir .]
python state/state_utils.py node-start <N4> [--goal G] [--dir .]
python state/state_utils.py node-finish <N4> --agent coder --skills "mm-iteration-engine,mm-algorithm-dev,code-review" [--artifact p ...] [--allow-empty-artifacts] [--dir .]   # 执行 Agent 与技能必填声明；空产物默认拒绝完成
python state/state_utils.py checkpoint <Nx> --phase "<阶段名>" [--done D ...] [--pending P ...] [--artifact <路径> ...] [--note "<决策/阻塞>"] [--by <agent>] [--dir .]
         # 🔴 子 Agent 分阶段归档：每个 Phase 结束落一次快照到 state/checkpoints/<Nx>.jsonl（append-only）
python state/state_utils.py checkpoint-list <Nx> [--latest] [--dir .]
         # 中断续跑：读最后一条快照的 resume_hint（从哪个 Phase 之后继续、已完成/待完成几项），不必从头重跑
python state/state_utils.py register-artifact <Nx> --path <相对路径> --kind <dataset|figure|table|prose|code|report> [--note S] [--by <agent>] [--dir .]
         # 🔴 产物入库登记：路径必须在本节点 artifact 目录内，否则拒绝（防乱放）；落 state/reports/artifacts-registry.json
python state/state_utils.py orphan-scan [--apply] [--dir .]
         # 孤儿文件扫描：找出不在任何节点产物目录、也未登记的散落文件；收尾与 N8 终审前各跑一次
python state/state_utils.py node-review <N4> --agent <id> --result <PASS|FAIL|BLOCKED> --skills s1,s2 [--evidence <路径>] [--summary S] [--dir .]
python state/state_utils.py round-start <N4|N5|N7|N8> [--goal G] [--branch B] [--git] [--dir .]
python state/state_utils.py round-score <N4|N5|N7|N8> --round N --total 7.8 --dims '{"correctness":8.0,...}' [--judge A] [--git] [--dir .]
python state/state_utils.py round-decide <N4|N5|N7|N8> --round N [--feedback F] [--reason <失败原因分析>] [--git] [--dir .]
         # 未达标分支（repair_and_rerun/keep_best）必须 --reason：根因/差距/下轮方案，写入 decision.failure_analysis
python state/state_utils.py round-score <N4|N5|N7|N8> --round N --total T --dims '{...}' --judge <审阅Agent> [--allow-missing-mcp] [--git] [--dir .]
         # 🔴 核心节点（N4/N5/N7）本轮必须有 MCP 检索留痕（mcp-calls.jsonl/cases），否则拒绝评分（禁止纯内生）
python state/state_utils.py node-review <Nx> --agent <id> --result <PASS|FAIL|BLOCKED> --skills s1,s2 [--allow-missing-mcp] [--dir .]
         # 🔴 N1/N3/N4/N5/N7 的 PASS 审阅必须有 MCP 检索留痕，否则拒绝（可 --allow-missing-mcp 显式豁免）
python state/state_utils.py search-evidence <Nx> [--dir .]                                     # 汇总节点检索证据派发清单（知识卡片/案例/台账/MCP 留痕，派发 Agent 时携带）
python state/state_utils.py dr-note <Nx> [--round N] --phase <SEARCH|SCORE|DECIDE|NODE> --role <research_architect|literature|researcher|synthesis|report_compiler> --topic <问题> [--input I] [--output O] [--ref R] [--dir .]
         # 🔴 Deep Research 介入留痕：落 state/reports/dr-interventions.jsonl 并同步 rounds[n].deep_research（N4/N5/N7 每轮介入必留）
python state/state_utils.py dr-list <Nx> [--round N] [--dir .]                                 # 查询节点 Deep Research 介入留痕（N8 终检核对"每轮有据介入"）
python state/state_utils.py case-add --title T --source S [--url U] [--summary X] [--score n] [--source-type github-code] [--query Q] [--dir .]
python state/state_utils.py search-source add --id <id> --type <类型> --name <名> --address <URL> --tool <工具> [--query-template T] [--apply-when a,b] [--priority n] [--dir .]
python state/state_utils.py dashboard-refresh [--dir .]
python state/state_utils.py claim <agent-id> --node N4 [--dir .]
python state/state_utils.py node-log <N4> --step <小步骤描述> [--by <执行者>] [--dir .]   # 追加到 state/nodes/<名称>/steps.md（执行中逐条记录）
python state/state_utils.py todo add <待办> [--node N4] [--dir .]                         # 任务清单动态更新
python state/state_utils.py todo done <匹配文本> [--dir .]                                 # 标记完成（[x] + 时间戳）
python state/state_utils.py todo plan [--dir .]                                            # 按状态自动生成/更新全流程执行+审阅任务清单
python state/state_utils.py todo list [--dir .]                                            # 查看全部条目
python state/state_utils.py cascade-invalidate [--node N3] [--apply] [--dir .]             # 级联失效：上游产物变更 → 下游状态/门禁重置 pending（改代码/模型后必跑，联动同步）
python state/state_utils.py flow-coverage [--dir .]                                        # 全流程覆盖检查：预期 Agent/Skill 集 vs 实际记录（查漏派/漏 skill）
python state/state_utils.py handoff <Nx> [--dir .]
python state/state_utils.py handover-review [--dir .]                                        # 接手复核：9 阶段逐节点检查，completed 强制审阅复核（门禁/产物漂移→修改→复审）                                         # 生成/刷新阶段交接文件（上游状态/门禁/产物哈希 + 就绪判定；单独拉出阶段前先读）
python state/state_utils.py project-audit [--dir .]                                        # 接手审计：真实性/题目锁定/结构/registry/产物漂移/未审阅完成/阶段不完全推进/内联代做/旧命名
python state/state_utils.py project-repair --apply [--dir .]                               # 按审计结果补建标准结构
python state/state_utils.py upgrade-heal --apply [--dir .]                                 # 升级自愈：旧版遗留迁移修复 + 补建 + 复检
python state/state_utils.py review-loop <Nx> [--dir .]                                     # 审阅→修改→再审阅循环序列（含修改 Agent 与修改 skill）
python state/state_utils.py node-repair-check <Nx> --attempt N [--dir .]                   # 修改哈希对比（空修改打回）
python state/state_utils.py auto-check <Nx> --gate <H1|H2|H3> --agent <审阅Agent> --skills s1,s2 [--report <路径>] [--dir .]   # H 门禁自动核查（流程不挂起）
python state/state_utils.py h-confirm --gate <H1|H2|H3> [--note 说明] [--dir .]             # 人工追认 H 门禁
python state/state_utils.py result-validate <result.json路径> [--dir .]                    # 验证 result.json 协议/产物/哈希
python state/state_utils.py result-ingest <result.json路径> [--agent A] [--node Nx] [--dir .]  # 验证并合并结果到状态
python state/state_utils.py report-list [--dir .]                                           # 留存迭代报告清单（review/run/decision/result）
python state/state_utils.py sync-plan [--dir .]                                             # 已有论文/代码/数据同步兼容计划
```

所有写操作：UTF-8、原子替换、自动 `meta.seq += 1`；`--git` 参数会在状态变更后自动 `git add state + LogRecord` 并 commit（带 trailer），非 git 目录会明确报错。init 幂等：已初始化需 `--force`。

> 🔴 **实现拆分说明（1.5.0）**：`state_utils.py` 已按领域拆分到同目录兄弟模块以便维护——`state_defs.py`（常量/助手）、`state_scaffold.py`（脚手架/init/交接）、`state_nodes.py`（节点生命周期）、`state_review.py`（独立审阅与返修）、`state_audit.py`（审计/结果管理）、`state_rounds.py`（迭代轮次）、`state_search.py`（检索/案例/claim）。CLI 入口仍为 `python state/state_utils.py <命令>`（薄分发层），`init` 会把全部兄弟模块一并复制进项目 `state/`，命令用法不变。

### 🔴 派发与等待纪律（防 general-purpose 包办 / 防内联代做）

1. **逐节点、逐章节派发**：每个节点、每个章节（哪怕只写一节）都必须单独 `task` 派发对应专业子 Agent（`subagent_type=<registry executor>`：N1→selector、N2→dataprep、N3→modeler、N4→coder、N5→tuner、N6→visualization、N7→writing、N8→reviewer；审阅→mm-code-reviewer/mm-viz-reviewer）。**禁止 general-purpose 代做任何节点产物**（只允许编排/检索/文件整理等辅助）。
2. **子 Agent 必读 Skill**：被派发的子 Agent 必须加载其 required_skills 并声明（node-finish 的 `--skills` 强制校验缺失即拒绝）。
3. **等待纪律**：子 Agent 后台运行期间，主 agent/orchestrator **禁止写该节点及任何节点的业务产物**（只允许 node-log 记录进度、todo 更新清单、准备下一节点的派发参数）；子 Agent 返回后才 `node-finish` + 派发配对审阅。
4. **执行者证据**：`project-audit` 检查每个已推进节点是否有其执行 Agent 的 `state/agents/<executor>/result.json`——缺失即报告"疑似内联代做（绕过派发）"。子 Agent 收工必须写 result.json。

## 14. Anti-Patterns

| # | 反模式 | 后果 | 正确做法 |
|---|---|---|---|
| 1 | 多个 Agent 同时直接写 decision_log.json | 状态互相覆盖 | 单写者协议，子 Agent 只写 result.json |
| 2 | 跳过初始化直接开跑中间节点 | 状态页缺失、无法联动 | Phase 0 先 `init` |
| 3 | 审阅 Agent 与执行 Agent 是同一个（N8 豁免除外） | 自审失真 | 按配对矩阵派发独立审阅 |
| 4 | 审阅前不读对应 Skill | 审阅标准漂移 | 先加载 required_skills 并在记录中声明 |
| 5 | 未达标分支也 merge 回 main | 低质版本污染主线 | 评分 ≥ pass 才 merge |
| 6 | 每轮不提交 / 提交信息无 trailer | 无法回溯对比各轮 | implement/run/score 三次提交 + trailer + notes |
| 7 | 状态文件直接覆盖写 | 读到半截 JSON | 临时文件 + 原子替换 |
| 8 | 无插件平台谎称"插件已驱动" | 降级失真 | platform_mode 如实记录，门禁记 BLOCKED |
| 9 | SEARCH 不查 search_sources.json 盲目搜索 | 检索低效、案例不可追溯 | 按需求选源 + 登记 source_type/search_query |
| 10 | 对已初始化项目重复 init | 状态清空 | 幂等保护，--force 才重建 |
| 11 | 同节点未决策就开新轮 | 轮次错位 | 先 round-score + round-decide |
| 12 | 用 general-purpose / 主 agent 内联代做节点产物 | 专业分工失效、skill 空转 | 逐节点/逐章节派发专业子 Agent（subagent_type=executor），audit 会查执行者 result.json 证据 |
| 13 | 子 Agent 后台运行期间主 agent 顺手写业务产物 | 产物无主、状态与产物时间线矛盾 | 等待纪律：只做 node-log/todo/派发准备 |
| 14 | 一口气做完再补记小步骤与 to-do | 进度不可见、无法追溯 | 每完成一个动作立即 node-log + todo add/done |

## 15. References

| 资源 | 说明 |
|---|---|
| `ref/math_model/…`（**外部参考项目，不随本插件分发**） | 下列 4 条为该参考项目的路径，仅作设计来源标注。本机若未放置该参考仓库（`.gitignore` 已忽略 `ref/`），这些路径不可读，属正常情况，**不得当作本地文件引用**。 |
| `ref/math_model/state/decision_log.json` | 状态 schema 1.0 蓝本（本 schema 2.0 为其严格超集） |
| `ref/math_model/references/08-stage-verification.md` | 门禁思想来源（M1/D1/P1/P2/A1/A2/A3 同类对齐；T1/V1/W1/W2/B1/H1-H3 为系统扩展） |
| `ref/math_model/references/15-scoring-rubric.md` | 五维评分锚点、硬上限、仲裁规则借鉴来源（部分对齐） |
| `ref/math_model/workflows/adversarial-review.js` | 对抗审稿聚合实现参考（≤4 轮、目标 7.5） |
| `shared/state-engine/state_utils.py` | 状态节点 CLI 入口（薄分发层；init 时连同 `state_defs/state_scaffold/state_nodes/state_review/state_audit/state_rounds/state_search` 兄弟模块一并复制进项目 state/） |
| `shared/contracts/gates-registry.json` | **门禁登记单一事实源**（2.0.0 新增）：全部门禁的 id/节点/时机/类型/阻断级别/判据/产出者/阈值。改门禁先改此处。 |
| `mcp/call-hierarchy.md` | 核心节点 MCP 必调六节点表（N1/N3/N4/N5/N7，禁止纯内生） |
| `mcp/knowledge-card.template.md` / `mcp/reference-ledger.template.md` | 检索知识卡片与 GB/T 7714 台账模板（search-evidence 派发载体） |
| `deep-research` Skill | 迭代不达标时的自动迭代审阅与根因深度调研（按需唤起，回填下一轮 SEARCH） |
| `mathematical-modeling/SKILL.md` | 主控 Skill（阶段表与本规范联动） |
