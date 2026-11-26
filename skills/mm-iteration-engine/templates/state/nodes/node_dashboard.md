# 节点首页：{NODE_ID}-{NODE_NAME}

> 本页为节点独立状态页，由执行 Agent 与配对审阅 Agent 在每次执行/审阅后刷新（`state_utils.py node-finish / node-review`）。
> 机器事实源为 `state/decision_log.json`（以 JSON 为准，本页为可读视图）。

## 1. 基本信息

| 项 | 值 |
|----|----|
| 节点 | {NODE_ID}-{NODE_NAME} |
| 执行 Agent | {EXECUTOR} |
| 配对审阅 Agent | {REVIEWER} |
| 审阅前必读 Skill | {SKILLS} |
| 产物目录 | {ARTIFACT_DIR} |
| 门禁 | {GATES} |
| 状态 | pending |
| 最近更新 | - |

## 2. 本节点 goal

- （本节点当前迭代目标，与 `decision_log.json` 中 `nodes.{NODE_ID}.goal` 及 `rounds[n].goal` 对应；goal 插件写入，达成后清空）

## 3. 产物清单

| 路径 | sha256 | 备注 |
|------|--------|------|
| - | - | - |

## 4. 迭代记录（round → 评分 → 决策 → feedback → goal）

| round | 分支 | 评分 | 决策 | feedback / 下轮 goal |
|:-----:|------|:----:|------|----------------------|
| - | - | - | - | - |

## 5. 审阅记录

| 时间 | 审阅 Agent | 声明已读 Skill | 结论 | 问题清单 |
|------|-----------|---------------|------|---------|
| - | - | - | - | - |

## 6. 门禁状态

| 门禁 | 状态 | 结果 |
|------|------|------|
| - | pending | - |

## 7. 回退与备注

- （回退原因、人工确认记录、abandoned 分支说明）
