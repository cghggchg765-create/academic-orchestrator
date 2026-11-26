# 贡献指南

## 环境要求

- Python 3.9+（CI 覆盖 3.9 / 3.11 / 3.13）
- 纯标准库运行，无第三方运行依赖（可选：`pip install -e .[dev]` 获得 pytest）

## 推送与 CI 权限（重要）

本仓库含 GitHub Actions 工作流（`.github/workflows/contracts.yml`）。GitHub 要求**推送包含 workflow 文件的提交时，凭据必须具有 `workflow` scope**（OAuth token 默认 `repo` scope 会被拒绝，报错 `refusing to allow an OAuth App to create or update workflow ... without workflow scope`）。

首次推送前请完成一次授权（二选一）：

```bash
# 方式一：gh CLI 追加 workflow scope（会输出设备码，浏览器打开 https://github.com/login/device 输入确认）
gh auth refresh -s workflow --hostname github.com

# 方式二：GitHub 网页 → Settings → Developer settings → OAuth Apps / Personal access tokens
#        给当前使用的 token 勾选 workflow scope
```

授权完成后重新 `git push origin main` 即可；之后推送无需重复授权。

## 本地验证（提交前必跑）

```bash
python -m py_compile skills/mm-iteration-engine/scripts/*.py shared/state-engine/*.py scripts/*.py   # 编译检查
python scripts/lint_contracts.py                                            # 仓库级契约检查
python -m unittest discover -s tests -p 'test_*.py'                         # 全量测试
```

契约检查覆盖：重复命令/旧命名残留、`state_utils.py` 的 NODES 与 `templates/state/registry.json` 双份一致、SKILL frontmatter 必填、版本单一来源（pyproject == 脚手架 == Skill）、agents/skills 数量断言、压缩包禁止跟踪、LaTeX 初始化结构。

## 变更规则

1. **版本单一来源**：修改 `pyproject.toml` 的 `version`，并同步 `state_utils.py` 脚手架 `skill_version`、`mm-iteration-engine/SKILL.md` 与 `mathematical-modeling/SKILL.md` 的 frontmatter 版本、`templates/state/decision_log.json`；同时更新 `CHANGELOG.md`（Keep a Changelog 格式）。
2. **双份一致**：修改节点定义（executor/reviewer/skills/gates/artifact/upstream）时，必须同时更新 `state_utils.py::NODES/UPSTREAM`、`templates/state/registry.json` 与 SKILL §6.1 表格。
3. **协议变更**：修改状态枚举、裁决枚举或结果结构时，同步 `spec/result.schema.json`、`spec/review_protocol.json` 并在测试中增加样例。
4. **审阅独立铁律**：任何新入口不得允许执行 Agent 自评；带 `review_verdict` 的结果必须由注册审阅 Agent 提交。
5. **文档口径**：阶段数（9 阶段 Phase 0-8）、门禁集合、数量断言以契约检查为准，文档不硬编码可漂移的数字。
6. **提交信息**：Conventional Commits（`feat/fix/refactor/docs/chore/state`），状态变更提交含 `State-Sha` trailer。

## 测试要求

- 新命令/新流程必须附带回归测试（`tests/test_workflow_contracts.py`，unittest，临时目录 + 子进程调用，不污染仓库）。
- 测试不得依赖网络、外部服务或系统级工具（如 pdftoppm 缺失场景要覆盖 BLOCKED 分支）。
- 全量测试通过后再提交。
