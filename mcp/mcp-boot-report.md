# MCP 自检报告（Checkpoint 0）

- 时间：2026-09-11T23:51:51
- 判定：**MCP_READY**
- 扫描到 MCP 服务数：13
- Tavily 内嵌密钥：0 枚

## 分类自检

| 类别 | 是否注册 | 联网探测 | 备注 |
|------|:------:|:------:|------|
| 论文搜索MCP(paper-mcp) | ✅ paper-mcp | ✅ | core 常驻 · 文献检索&归档 |
| GitHub MCP(github) | ✅ github | ✅ | core 常驻 · 开源工程 |
| Context7 MCP(context7) | ✅ context7 | ✅ | core 常驻 · 算法技术 |
| Tavily全网搜索MCP(tavily) | ✅ tavily-mcp | ✅ | 待装·已内嵌双密钥；就绪回退见 tokenhub |
| 全网搜索回退MCP(tokenhub-tools) | ✅ tokenhub-tools | — | Tavily 未就绪时承接全网搜索 |

## 门禁

`MCP_READY` — 允许建模任务启动。
