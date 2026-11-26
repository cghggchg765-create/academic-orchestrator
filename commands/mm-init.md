---
name: mm-init
description: 初始化一个标准数学建模项目（脚手架 + state 状态节点 + git）
---

按以下步骤初始化标准项目并预建状态节点（参数按实际替换）：

```bash
python shared/state-engine/state_utils.py init --dir <项目目录> --name CUMCM --year 2026 --problem A --language zh --git
```

1. 若题目是 PDF 且含图形：先读图——有视觉能力用 `problem_guard.py figures --mode vision`（渲染 ProblemInfo/figures/page-*.png 逐页阅读）；无视觉能力用 `--mode human`（生成人工描述请求单）。
2. 锁定题目事实：`python shared/state-engine/problem_guard.py create --project <项目> --source <题目> --objectives '[...]' --constraints '[...]' --preconditions '[...]' --data-requirements '[...]' --evaluation-metrics '[...]' [--figure-mode vision|human|none]`。
3. 验证：`python shared/state-engine/problem_guard.py verify --project <项目>`；`state/state_utils.py project-audit --dir <项目>` 应收敛为仅剩待执行节点。
4. 提醒用户创建 GitHub 远端仓库并自行 `git remote add origin <url> && git push`（Agent 不代做推送）。

完成后向用户输出：项目结构、state/ 状态节点、下一步应触发哪个节点。
