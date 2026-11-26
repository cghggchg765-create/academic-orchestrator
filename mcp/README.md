# MCP 集成层（内嵌常驻能力）

> 本模块将系统全局已安装的 MCP 服务筛选、封装、内嵌进数学建模流水线插件内核，作为**插件原生常驻能力**随生命周期自动挂载。任何建模任务启动前必须先过本模块的 **Checkpoint 0 启动门禁**（顺序不可逆、不可跳过）。

## 运行优先级（不可逆、不可跳过）

```
① 全局 MCP 扫描  →  ② 筛选适配 MCP  →  ③ 插件内嵌封装  →  ④ 自检就绪  →  ⑤ 允许建模任务启动
```

| # | 步骤 | 载体 |
|:-:|------|------|
| ① | 全局 MCP 扫描（以本机真实安装为唯一依据，禁止虚构/硬编码） | `mcp/checkpoint-0-boot.md` 步骤1；扫描结果见 `mcp/mcp-scan-results.md` |
| ② | 筛选数学建模流水线专属四类有效 MCP | `mcp/checkpoint-0-boot.md` 步骤2；分工见 `mcp/cluster-roles.md` |
| ③ | 四类 MCP 迁移、打包、内嵌、固化至插件内核，随插件启动自动就绪 | `mcp/checkpoint-0-boot.md` 步骤3；`mcp/cluster-roles.md` |
| ④ | MCP 加载自检：状态/权限/联网/密钥逐项校验，异常即终止任务 | `mcp/checkpoint-0-boot.md` 步骤4；`scripts/mcp_boot_check.py` |
| ⑤ | 全部通过才允许启动建模任务；另有四类闭环校验检查点 | `mcp/validation-checkpoints.md` |

## 文档索引

| 文档 | 内容 |
|------|------|
| [checkpoint-0-boot.md](checkpoint-0-boot.md) | 插件启动强制 MCP 初始化流程（Checkpoint 0，4 步骤，最高优先级） |
| [mcp-scan-results.md](mcp-scan-results.md) | 全局 MCP 实测扫描结果与适配筛选结论 |
| [cluster-roles.md](cluster-roles.md) | 四大内嵌 MCP 专属分工（Context7 / GitHub / 论文搜索 / Tavily） |
| [call-hierarchy.md](call-hierarchy.md) | 调用层级规则（常规灵活 + 核心节点强制必调 5 节点表）+ 知识卡片强制输出 |
| [validation-checkpoints.md](validation-checkpoints.md) | 四类闭环校验检查点（启动/调研/建模工程/终检） |
| [tavily-mcp.config.json](tavily-mcp.config.json) | Tavily MCP 服务器配置（双密钥自动轮换） |
| [knowledge-card.template.md](knowledge-card.template.md) | MCP 检索结果结构化知识卡片模板（可溯源/可复用/可归档） |
| [reference-ledger.template.md](reference-ledger.template.md) | GB/T 7714 国标参考文献台账模板（文献归档双分支用） |

## 快速开始（任务启动前）

1. 加载命令 `/mm-boot`（或主控 `/mm` 第 0 步自动触发）：
   - 读取 `mcp/checkpoint-0-boot.md` 按序执行 ①→④；
   - 运行 `python scripts/mcp_boot_check.py --report` 生成自检报告；
   - 自检任一 MCP 异常 → **立即终止任务**，输出异常 MCP 名称，修复后重跑。
2. 核心节点（N1 选题拆解 / N3 建模 / N4 代码 / N5 调优 / N7 论文）任务运行时，按 `mcp/call-hierarchy.md` 强制调用对应 MCP。
3. 每次 MCP 检索结果按 `mcp/knowledge-card.template.md` 沉淀知识卡片；文献按 GB/T 7714 归入 `mcp/reference-ledger.template.md` 台账。

## 与本项目其它模块的关系

- **触发层**：`commands/mm-boot.md`（显式）、`commands/mm.md` 第 0 步（隐式随总控启动）。
- **编排层**：`agents/orchestrator.md` 启动段强制 Checkpoint 0；核心节点派发时注入 MCP 必调指令。
- **执行层**：selector / modeler / coder / tuner / writing / researcher / literature 等 agent 各自绑定其必调 MCP（见 `call-hierarchy.md` 映射表）。
- **校验层**：`scripts/mcp_boot_check.py` 与 `mcp/validation-checkpoints.md` 构成四类闭环门禁。
- **产物链**：知识卡片落 `state/reports/` 或 `mcp/cards/`，参考文献台账落 `state/reports/references-ledger.md`（由对应节点在任务目录内另行生成，本目录提供模板）。
