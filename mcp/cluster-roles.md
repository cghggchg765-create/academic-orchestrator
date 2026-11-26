# 独立 MCP 集群专属分工规则（插件原生固化）

> 所有内嵌 MCP 各司其职、独立联动、专项服务数学建模全流程，**分工固定、不可篡改**。

| MCP | 专项定位 | 服务对象（数学建模环节） | 对应的内置能力 |
|-----|---------|------------------------|---------------|
| **Context7 MCP** | 算法技术专项 | 算法原理、模型公式细节、求解器 API、工程代码技术文档、算法优化方案检索 | `mcp__context7::resolve-library-id` + `query-docs` |
| **GitHub MCP** | 开源工程专项 | 数学建模开源项目、完整仿真源码、高性能算法实现、模型优化工程案例 | `mcp__github::search_repositories / search_code / get_file_contents / list_commits 等` |
| **论文搜索 MCP** | 文献检索 & 归档专项（**核心常驻**） | 问题对标、方法依据、文献归档、国标引用补全 | `mcp__paper-mcp::paper_search / download_paper / vpn_login` |
| **Tavily 全网搜索 MCP** | 前沿资料专项 | 数据集、行业建模案例、前沿优化算法、学术资料补充检索 | tavily-mcp（待装）；就绪回退 `mcp__tokenhub-tools::search` |

## 各专项职责细则

### 1. Context7 MCP（算法技术专项）
- 模型搭建（N3）阶段：为模型选型、公式推导、求解器选择提供**最新官方文档与代码示例**支撑；
- 代码开发与调优（N4/N5）阶段：检索算法库 API、数值方法实现细节、性能优化技术文档。
- 禁止：用旧记忆硬写 API（一律 query-docs 核实后再编码）。

### 2. GitHub MCP（开源工程专项）
- 代码编写（N4）：检索同类开源建模项目/完整仿真源码，支撑复现与起步；
- 算法提速、资源降载（N4/N5 迭代）：搬运/参考高性能实现；
- 实验仿真、结果校验（N5）：对照开源基线校验实现正确性与量级。

### 3. 论文搜索 MCP（文献检索 & 归档专项｜核心常驻）
执行**双分支强制归档逻辑**，严格遵循国标 **GB/T 7714** 参考文献规范：
- **分支 A（可下载文献）**：`download_paper` 自动下载，归类保存至项目 `Literature/`（或任务目录 `MCP-Archive/`）对应子文件夹，留存原文资源，可随时复用、解析、对照参考；
- **分支 B（无下载权限 / 不可获取全文）**：**禁止空置跳过**，必须整理完整 GB/T 7714 参考文献条目（作者、题名、刊名、年份、卷期、DOI、链接等全量信息），统一录入 `state/reports/references-ledger.md` 台账（模板见 `mcp/reference-ledger.template.md`），供论文写作随时查阅、引用、补全。

### 4. Tavily 全网搜索 MCP（前沿资料专项）
- 选题拆题（N1）：行业案例、同类建模方案、赛题背景资料；
- 数据（N2）：公开数据集发现与获取链接；
- 可视化（N6）：补充同类图表案例、官方可视化规范和数据展示方案；
- 调优（N5）：前沿优化算法、SOTA 指标对照；
- **内置双密钥自动轮换**：两枚密钥（见 `mcp/tavily-mcp.config.json`）自动切换，失效自动切换，保障检索永不中断。

### 5. 可视化方案联合调用（N6 前置，不得先画后查）
- 模型与数据确定后，论文搜索 MCP 负责检索学术图表方案/同类论文，Tavily/WebSearch 负责补充官方规范、行业案例和公开数据口径；不确定绘图库 API 时由 Context7 核实。
- visualization 只能在方案比较、数据分类、MCP 留痕和最终方案定型后绘图；调用记录写 `state/reports/mcp-calls.jsonl`，方案卡片写 `state/reports/mcp-cards/`。
- mm-viz-reviewer 将上述前置证据作为 V1 门禁的一部分，缺任一项不得 PASS。

## 铁律
1. 分工固定：Context7 不代 GitHub 查源码、论文 MCP 不代 Tavily 查行业资料、GitHub 不代论文 MCP 归档文献——各按其表。
2. 四类 MCP 独立联动：同一节点按需可同时调用多个（如 N4 代码 = Context7 文档 + GitHub 源码）。
3. 任何 MCP 产出必须按 `mcp/knowledge-card.template.md` 沉淀知识卡片（可溯源、可复用、可归档）。
