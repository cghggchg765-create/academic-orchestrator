---
name: academic-update
description: 检查并更新本插件依赖的外部学术能力上游（ARS / ARIS / nature 家族 / figure-pipeline / nsfc / zotero 等）
argument-hint: "[--id <上游id>] [--apply] [--json]"
---

# /academic-update — 上游更新检查与同步

检查本插件的**外部能力提供方**是否有新版本。默认**只读报告**，加 `--apply` 才对 git 源执行快进拉取。

## 执行步骤

### 第 1 步：跑检查（只读）

```bash
python scripts/check_upstream_updates.py $ARGUMENTS
```

输出每个上游的状态：`UP_TO_DATE` / `BEHIND` / `VERSION_DIFF` / `NOT_INSTALLED` / `FETCH_FAILED` / `NOT_GIT`。

### 第 2 步：解读结果

| 状态 | 含义 | 处理 |
|---|---|---|
| `UP_TO_DATE` | 已是最新 | 无需动作 |
| `BEHIND` | git 源落后 n 个提交 | 确认无本地改动后 `--apply` |
| `VERSION_DIFF` | 插件实际版本 ≠ 清单声明 | 更新 `upstream-manifest.json` 的 `installed_version`，或去 Plugin Management 更新插件 |
| `NOT_INSTALLED` | 清单里的插件未安装 | 报告给用户，不自行安装 |
| `FETCH_FAILED` | 网络不可达 / 认证失败 | **如实报告**，不重试刷屏；提示用户检查网络或代理 |
| `NOT_GIT` | 该目录不是 git 仓库 | 只能做版本字段比对，无法自动更新 |

### 第 3 步：应用（仅在用户明确要求时）

```bash
python scripts/check_upstream_updates.py --apply --id <上游id>
```

约束（脚本内已强制）：
- 只对 `update_method: git_pull` 的条目执行 `git pull --ff-only`；
- **工作区有未提交改动时拒绝 pull**（状态 `DIRTY`），避免覆盖用户改动；
- **非 fast-forward 时拒绝**（状态 `PULL_FAILED`），不强行合并；
- 插件类（`plugin_marketplace`）**不自动更新**，只报告版本差异，更新走 ZCode 的 Plugin Management。

### 第 4 步：更新后复验

git 源拉取成功后：
```bash
python scripts/lint_contracts.py
python -m pytest tests -q
```
确认本插件的路由与契约未因上游结构变化而失效。

## 重要约束

1. **不要 `git push`**：上游仓库只读拉取，不向他人仓库推送。
2. **不要跨上游批量 apply**：一次只更新一个，逐个验证（`--id` 指定）。
3. **用户级同名副本会遮蔽插件版**：更新 ARS 后，若 `~/.zcode/skills/` 下有同名旧副本，实际生效的仍是旧副本。需检查遮蔽情况：
   ```bash
   python scripts/self_check.py --json
   ```
4. **网络失败不是配置错误**：`FETCH_FAILED` 多半是网络不可达，不要反复重试，也不要改用镜像或跳过校验。

## 上游清单维护

`upstream-manifest.json` 是唯一事实源。新增上游时：
1. 在 `upstreams` 数组加一条，必填 `id` / `kind` / `role` / `local_paths` / `update_method` / `tracked`；
2. `update_method` 取值：`git_pull` / `plugin_marketplace` / `manual`；
3. `git_pull` 类必须写 `git_source`（本地 git 仓库路径）；
4. 跑 `python scripts/check_upstream_updates.py --id <新id>` 验证能被正确识别。
