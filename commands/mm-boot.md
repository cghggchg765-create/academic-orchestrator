---
name: mm-boot
description: MCP 启动初始化（Checkpoint 0）：全局MCP扫描→筛选四类适配MCP→内嵌确认→自检就绪→放行建模任务，顺序不可逆不可跳过
---

执行插件 Checkpoint 0 强制 MCP 初始化流程（唯一入口、必跑流程）。**任何数学建模任务启动前必须先过本门禁。**

## 第 0 步：运行环境健康检查（推荐，防资源耗尽）

先跑 `python scripts/env_health_check.py [--clean]` 检查运行环境资源风险（历史会话日志 `~/.zcode/cli/exec` 膨胀、测试临时残留、磁盘余量）。

### 构建/运行虚拟环境门禁

任何运行代码、生成算法结果、执行数据处理或进行需要项目依赖的构建前，必须在目标项目目录执行：

```bash
python scripts/venv_guard.py --project <项目目录>
```

只有输出 `VENV_READY` 才能继续；`VENV_BLOCKED` 时必须创建并激活项目 `.venv`，禁止用系统全局 Python 越过门禁。该检查只读，不会自动创建环境或安装依赖。

## 第 0.5 步：插件注册链路一致性检查（推荐，防"子 Agent 无法启动"）

跑 `python scripts/plugin_registry_check.py` 校验：版本五方对齐（仓库/marketplace/installed/缓存目录/manifest）、缓存与仓库逐文件一致（agents/skills/commands）、无嵌套版本目录（历史事故：`1.5.0/1.3.0` 嵌套导致子 Agent 路径失效无法启动）、Agent frontmatter 合法、用户级无遮蔽残留、MCP 密钥在位。输出 `PASS` 才继续；`FAIL` 时按提示修复（重新同步缓存或清理嵌套目录）后再开工。

## 第 1 步：加载启动协议

读取 `mcp/checkpoint-0-boot.md`，按序执行 ①全局MCP扫描 → ②筛选 → ③内嵌封装确认 → ④自检：

1. **① 全局 MCP 扫描**：读取 `mcp/mcp-scan-results.md` 基线，并按 checkpoint-0-boot.md 步骤1 重新核对本机真实注册的 MCP 命名空间（`mcp__*` 工具清单 + 本机 MCP 配置），以实测为准，禁止虚构/硬编码；
2. **② 筛选**：按 `mcp/cluster-roles.md` 四类逐一确认：论文搜索MCP / GitHub MCP / Context7 MCP / Tavily全网搜索MCP；
3. **③ 内嵌确认**：按 `mcp_boot_check.py` 的显式 carrier 清单校验必需协议文件、模板和 `/mm-boot` 命令均在库；不再使用“8 项/10 文件”等模糊数量；
4. **④ 自检**：运行
   ```bash
   python scripts/mcp_boot_check.py --report --namespaces "<会话内真实注册的mcp命名空间，逗号分隔>"
   ```

## 第 2 步：判定放行 / 终止

- 输出 `MCP_READY` → 允许建模任务启动，向用户汇报四类 MCP 就绪状态；
- 输出 `MCP_BLOCKED` → **立即终止任务**，精准列出异常/缺失 MCP 名称与修复路径（Tavily 未装时提示按 `mcp/tavily-mcp.config.json` 安装或启用 tokenhub-tools 回退），修复后重跑本命令，未通过禁止开工。

## 第 3 步：闭环登记

- 将本次自检时间与判定追加登记到 `mcp/mcp-boot-report.md`（`--report` 已生成）；
- 后续核心节点执行时，委托 Agent 按 `mcp/call-hierarchy.md` 强制调用对应 MCP，并沉淀知识卡片与 GB/T 7714 台账（见 `mcp/validation-checkpoints.md` 闭环校验）。

## 注

- `--namespaces` 传入的是当前会话**实际可调用**的 MCP 命名空间（如 `paper-mcp,github,context7,tokenhub-tools`），与配置文件扫描互补，共同构成"真实安装依据"；
- 常规辅助任务（润色/查询）可跳过本命令；任何新建建模任务（/mm 全流程、单节点、接手、迭代）开工前必须执行。
