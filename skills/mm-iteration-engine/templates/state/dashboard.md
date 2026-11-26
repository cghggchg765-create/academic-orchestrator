# 状态工作栏（state/dashboard.md）

> DEPRECATED（结构参考）：实际总工作栏由 `state_utils.py dashboard-refresh`（`refresh_dashboard()`）按 `decision_log.json` 动态生成，本项目板仅用于说明生成结果的结构，不参与任何程序路径。
> 机器事实源为 `state/decision_log.json`（以 JSON 为准，本页为可读视图）。

## 竞赛信息

| 竞赛 | 年份 | 题号 | 语言 | 当前分支 | 最近提交 |
|------|------|------|------|---------|---------|
| {name} | {year} | {problem} | {language} | {branch} | {last_commit} |

## 节点卡片

| 节点 | 状态 | 产物 | 最近审阅结论 | 门禁 |
|------|------|------|-------------|------|
| N0 需求确认 | pending | - | - | - |
| N1 选题拆解 | pending | - | - | M1 / H1 |
| N2 数据处理 | pending | - | - | D1 |
| N3 建模 | pending | - | - | P1 |
| N4 代码 | pending | - | - | P2 / A1 / S\<n\> |
| N5 调优 | pending | - | - | T1 |
| N6 图表 | pending | - | - | V1 |
| N7 论文 | pending | - | - | W1 / A2 / W2 / S\<n\> |
| N8 评审 | pending | - | - | A3 |

## 迭代轮次总览

| 节点 | 轮次 | 分支 | 总分 | 决策 | feedback / 下轮 goal |
|------|:----:|------|:----:|------|----------------------|
| - | - | - | - | - | - |

## 待办

- next node: -
- 待人工确认: H1（题型判定）/ H2（数值量级）/ H3（论文整体）
