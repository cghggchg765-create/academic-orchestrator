---
name: mm-iterate
description: 生成并驱动迭代节点（N4/N5/N7/N8）的全自动迭代序列
---

为迭代节点生成自动迭代序列。若用户指定章节/小节/问题，必须先生成 scope 工作区；若未指定范围才使用全局节点序列。节点与目录通过 $ARGUMENTS 传入，例如 `N4 第4问 项目目录` 或 `N7 第7章 项目目录`：

```bash
python state/state_utils.py scope-plan <N4|N5|N7|N8> --round <n> --scope-kind adaptive --target <question_n|chapter_n|section_ref> --apply --dir <项目目录>
python shared/state-engine/orchestrator_runtime.py --plan-iteration <N4|N5|N7|N8> --dir <项目目录> [--git]
```

scope 模式下遵循：只读审阅并行 → 内容/算法修订串行 → 反向复审 → 排版修订串行（N7）→ 重新构建 → linter/reviewer 复核 → join/promote。

按返回的 steps 逐条执行：

1. `round-start`（每轮开分支，`--git` 时自动建分支）；
2. `agent_execute`：由执行 Agent 完成 SEARCH 搜案例沉淀 cases/ → IMPLEMENT → RUN 取证 → COMMIT（trailer 提交）；
3. `round-score`：**独立审阅 Agent**（registry 配对，如 mm-code-reviewer）评分后落盘 S 门禁；
4. `round-decide`：读 termination 决策（≥target 提前终止并 merge；<pass 携带 feedback 下一轮；达上限/平台期按规则收尾）。

约束：

- 前置缺失时序列返回 `blocked` 与缺失清单：先补跑上游（如 N3 建模），再重新生成序列；
- 每轮 `round-score / round-decide / result-ingest` 自动归档独立审阅实验报告到 `state/reports/`（`report-list` 查询），跨轮对比用 `git log --show-notes=score`；
- 审阅独立铁律：带 review_verdict 的 result 必须由注册审阅 Agent 提交，执行 Agent 自评会被 `result-ingest` 拒绝。
