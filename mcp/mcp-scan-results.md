# 全局 MCP 扫描结果与适配筛选（实测）

> 本表依据 **Checkpoint 0 步骤 1 实测结果**填写，以本机真实安装/注册为唯一依据，不虚构、不硬编码。每次启动扫描可刷新下表与扫描指纹。

## 一、当前扫描结果

| # | MCP 服务 | 命名空间前缀 | 关键工具（实测） | 状态 | 备注 |
|:-:|---------|-------------|-----------------|:----:|------|
| 1 | paper-mcp（论文搜索） | `mcp__paper-mcp` | `paper_search`（多源自动回退：CrossRef→OpenAlex→Semantic Scholar）、`download_paper`（OA→出版商→DOI→Sci-Hub、校园网/VPN 模式）、`vpn_login`（东北大学 VPN） | ✅ 已安装 | 已发表论文精准匹配，默认排除预印本 |
| 2 | github（GitHub） | `mcp__github` | `search_repositories` / `search_code` / `get_file_contents` / `create_issue` / `create_pull_request` / `list_commits` 等 | ✅ 已安装 | GitHub 官方 API MCP |
| 3 | context7（Context7 文档） | `mcp__context7` | `resolve-library-id`（解析库 ID）、`query-docs`（按概念查最新文档+示例） | ✅ 已安装 | 权威库文档检索（高信誉源优先） |
| 4 | tokenhub-tools（全网搜索·回退） | `mcp__tokenhub-tools` | `search`（批量搜索、新鲜度过滤、摘要） | ✅ 已安装 | 当前承接"全网搜索"职责的已就绪 MCP |
| 5 | tavily-mcp（Tavily 官方） | （未注册） | 无 | ❌ 未安装 | 配置与双密钥见 `tavily-mcp.config.json`；安装自检通过后优先接管 |

## 二、适配筛选结论（对应 Checkpoint 0 步骤 2）

| 插件四类 | 适配 | 迁移/内嵌状态 |
|---------|------|-------------|
| 论文搜索 MCP | `mcp__paper-mcp` | ✅ 内嵌（常驻） |
| GitHub MCP | `mcp__github` | ✅ 内嵌（常驻） |
| Context7 MCP | `mcp__context7` | ✅ 内嵌（常驻） |
| Tavily 全网搜索 MCP | `tavily-mcp`（待装）＋ 就绪回退 `mcp__tokenhub-tools` | ⚠️ 回退就绪 / Tavily 待安装接管 |

## 三、Tavily 安装与接管步骤（补齐后自动优先）

1. 将 `mcp/tavily-mcp.config.json` 内容合并进本机 MCP 配置文件（`~/.zcode/mcp*.json` 或项目 `.mcp.json`）。
2. `npm install -g tavily-mcp`（或用 loanne/langchain Tavily MCP 包），链路：`context-suite · mcp-server-tavily`。
3. 重启会话后重跑 `python scripts/mcp_boot_check.py --report`，确认第 5 行状态变为 ✅。
4. 接管判定：自检通过即由 Tavily 承担全网搜索；`mcp__tokenhub-tools` 降级为冷备（不可用时互切）。

## 扫描指纹

- 扫描时间：`2026-08-19`
- 扫描来源：当前会话注册的 MCP 工具命名空间（`mcp__*`）＋ 本机 MCP 配置
- 指纹说明：本表为基线快照；每次启动应按 `checkpoint-0-boot.md` 重新扫描校验，若与基线不符以实测为准。
