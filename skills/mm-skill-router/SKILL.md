---
name: mm-skill-router
description: "技能路由协调层：任务开工前分析本节点需要什么能力，运行时扫描本机已装的专业 skill，按能力匹配选出本次应加载的 skill 清单并产出派发依据。只做识别、匹配、排序与交接，不复制任何专业 skill 的内部流程。触发词：skill 路由, 技能选择, 派发技能, 该用哪个 skill, 能力匹配, skill routing"
metadata:
  version: "1.0.0"
  last_updated: "2026-11-19"
  status: active
  related_skills:
    - mathematical-modeling
    - mm-iteration-engine
---

# Skill Router — 协调层 → 专业 skill 的运行时接线

## 这个技能负责什么

一句话：**把"这个任务需要什么能力"翻译成"本机现在该加载哪几个 skill"，并留下可核对的依据。**

它属于协调层，只做四件事：

1. 识别本次任务/节点需要哪些**能力**（capability）；
2. 运行时**扫描本机实际安装**的专业 skill，读各自 description 自报的能力；
3. 按能力匹配、打分、排序，产出 `must_load`（必须加载）与 `supporting`（建议加载）；
4. 把结果落盘成派发清单，交给执行/审阅 Agent，并参与门禁校验。

## 它明确不做什么

- **不复制任何专业 skill 的流程**。写作怎么写、审稿怎么评、图怎么画，全部由被选中的 skill 自己定义。
- **不维护 skill 名称白名单**。`capability_taxonomy.json` 里只有能力与关键词，没有具体 skill 名。
- **不缓存匹配结果当作长期知识**。清单是"本次"的快照；专业 skill 升级/替换/新增后重跑即刷新。
- **不替专业 skill 干活**。路由层的产出是"清单 + 依据"，不是产物。

这正是设计目标：**你随时更新、替换、新增专业 skill，都不需要改动本插件。**

## 三个数据文件（唯一事实源）

| 文件 | 归属 | 作用 |
|---|---|---|
| `shared/skill-routing/capability_taxonomy.json` | 协调层知识 | 能力清单、关键词、阶段→能力映射、打分策略。**改这里才需要改插件** |
| `state/skill-routing/<节点>.json` | 运行时产物 | 本次派发清单（must_load / supporting / 每个能力的候选与分数 / 未解决项） |
| 本机已装 skill 的 `SKILL.md` frontmatter | 专业层自治 | 各 skill 自报 name/description；路由层只读取、不修改 |

## 执行流程

### 第一步：开工前生成清单（必须）

`node-start` 会自动生成；也可显式按任务描述生成：

```bash
# 按节点阶段能力（默认，读 taxonomy.stage_capabilities）
python state/state_utils.py skill-plan N7 --apply

# 按自由文本任务识别能力（单点请求、聊天直呼、跨阶段任务）
python state/state_utils.py skill-plan N7 --task "把第 4 章按审稿意见改写并核对引用" --apply

# 追加临时能力（词表里没覆盖的专项）
python state/state_utils.py skill-plan N6 --capability figure.audit --apply
```

清单结构（节选）：

```json
{
  "node": "N7",
  "required_skills": ["mm-iteration-engine", "mm-latex-writing", "mm-self-review"],
  "dynamic_skills": ["academic-paper", "top-journal-econ-writing-mentor", "latex-guard"],
  "supporting_skills": ["econ-write", "zotero"],
  "must_load": ["academic-paper", "latex-guard", "mm-iteration-engine",
                "mm-latex-writing", "mm-self-review", "top-journal-econ-writing-mentor"],
  "capabilities": [
    {"capability": "paper.writing",
     "primary": [{"skill_id": "academic-paper", "score": 3.585,
                  "matched_keywords": ["academic writing"], "path": "..."}],
     "status": "matched"}
  ],
  "unresolved": []
}
```

- `required_skills`：节点固有必读（来自 registry，不可省）。
- `dynamic_skills`：**本次运行时匹配出来的专业 skill**（这就是"联动"的落点）。
- `supporting_skills`：同能力的次优候选，按需加载，不进硬门禁。
- `unresolved`：本机没有匹配 skill 的能力——**如实报告，不硬凑**。

### 第二步：按清单派发

派发子 Agent 时，把 `must_load` 写进 prompt，并附上清单路径：

```
[路由] 域=数学建模, node=N7, subagent_type=writing
必须加载 skill（来自 state/skill-routing/N7.json）：
  mm-iteration-engine, mm-latex-writing, mm-self-review,
  academic-paper, top-journal-econ-writing-mentor, latex-guard
建议加载：econ-write, zotero
派发依据：state/skill-routing/N7.json（含每个能力的匹配分数与来源路径）
```

子 Agent 必须**逐个加载并声明**。加载的专业 skill 内部怎么写、走什么步骤，由该 skill 自己决定，编排方不干预、不复述。

### 第三步：落盘时校验

`node-finish --skills` 与 `node-review --skills` 都会做两层校验：

1. 节点 `required_skills` 是否齐（原有契约）；
2. 派发清单的 `must_load` 是否齐（本次新增）。

缺任一项 → 拒绝落盘。若清单本身已过期（例如刚换了 skill），重跑 `skill-plan <节点> --apply` 再继续。

```bash
# 只查不改（排障用）
python state/state_utils.py skill-audit N7 --skills "mm-iteration-engine,mm-latex-writing"
```

### 第四步：核对与维护

```bash
# 看本机到底发现了哪些 skill（按来源过滤）
python state/state_utils.py skill-list --scope user
python state/state_utils.py skill-list --scope plugin

# 看某个能力有哪些候选、分数多少（判断词表是否需要补关键词）
python state/state_utils.py skill-list --capability paper.review
```

## 匹配机制

打分（权重在 `taxonomy.selection_policy`，可调）：

```
score = 名称命中数 × name_weight + 描述命中数 × description_weight + log2(1+命中词数)
```

- **名称命中**权重高：skill 名/目录名里出现该能力关键词，是最强信号。
- **描述命中**权重低：description 文本命中，作为覆盖面证据。
- **同质去重**：一个能力默认只取 1 个 primary（`per_capability_primary`），其余降为 supporting——避免同时加载多份互相冲突的规范。
- **阶段上限**：单节点 primary 总量受 `max_stage_primary` 约束（默认 4），超出的降级。
- **编排入口排除**：`routing_skills` 里的纯流程 skill（如 `mathematical-modeling`）不参与匹配——加载它等于再套一层流程。
- **关键词匹配规则**：纯 ASCII 关键词按词边界匹配（避免 `tex` 命中 `contextual`）；含中文的关键词按子串匹配。

## 能力词表怎么维护

只有两种情况需要改 `capability_taxonomy.json`：

1. **出现词表没覆盖的新能力需求** → 在 `capabilities` 加一条（id/label/keywords/output_kinds）。
2. **某能力的匹配质量差**（候选不相关 / 漏掉明显该选的）→ 调该能力的 `keywords`，或调 `selection_policy` 的权重与阈值。

**不要**在词表里写具体 skill 名称。你要换 skill，只需要把它装到本机——下次运行自动被扫到。

## 扫描范围与优先级

按宿主加载语义去重（同名先发现者胜）：

1. `MM_SKILL_ROOTS`（env，覆盖语义，用于测试与异构部署）
2. `~/.zcode/skills`
3. `~/.agents/skills`
4. `<项目>/.zcode/skills`、`<项目>/.agents/skills`
5. 已安装插件包：按其 `plugin.json` 的 `skills` 声明解析（兼容"每个 skill 一个目录"与"统一 skills/ 目录"两种布局）

## 失败与降级

| 场景 | 处理 |
|---|---|
| 路由模块缺失 | `node-start` 打印警告并按节点 `required_skills` 继续，不阻断建模主流程 |
| 某能力无匹配 skill | 记入 `unresolved`，如实报告；**用既有 skill 硬凑属于伪造能力证据，禁止** |
| 派发清单过期 | 重跑 `skill-plan <节点> --apply`；或在 node-finish 报错提示后重跑 |
| 离线/试验环境 | `node-start --no-skill-routing`（豁免会写入节点记录留痕） |
| 匹配结果明显不合理 | 先用 `skill-list --capability X` 看候选与分数，再调词表关键词，不要手改清单 |

## Anti-Patterns

| # | 反模式 | 后果 | 正确做法 |
|---|---|---|---|
| 1 | 词表里写死 skill 名单 | 换 skill 要改插件，违背协调层设计 | 只写能力关键词，让运行时发现 |
| 2 | 把被选中 skill 的流程抄进派发 prompt | 双份维护、版本漂移 | 只传清单与路径，流程由该 skill 自己定义 |
| 3 | 同能力并列加载多个同质 skill | 规范互相覆盖，产物不一致 | 一个能力一个 primary，其余 supporting |
| 4 | 能力无匹配时随便挑一个顶上 | 伪造能力证据 | 记入 unresolved 并如实升级 |
| 5 | 手改 `state/skill-routing/*.json` 绕过匹配 | 失去可核对依据 | 调词表或重跑 skill-plan |
| 6 | 清单生成后不声明就 finish | 门禁拒绝（设计如此） | 子 Agent 逐个加载并声明 |
