# MCP 检索结果 · 知识卡片

> 用途：核心节点（N1/N3/N4/N5/N7）MCP 检索结果的结构化沉淀。每张卡片：来源、依据、引用可溯源、可复用、可归档。归档位置：`state/reports/mcp-cards/`，文件命名 `YYYY-MM-DD_<节点>_<主题>.md`。

## 卡片元信息

```yaml
card_id: CARD-<节点>-<序号>          # 例：CARD-N1-001
created_at: 2026-08-19T10:00:00+08:00
node: N1                              # 触发节点（N1/N3/N4/N5/N7）
mcp_source: paper-mcp                 # 来源 MCP：paper-mcp / github / context7 / tavily / tokenhub-tools
tags: [选题拆解, 同类案例]
source_file: <原始来源文件或URL>
source_span: <页码/行号/段落范围>
claim_type: factual|method|heuristic|prompt_policy
evidence_level: verified|partially_verified|unverified
applicability: <适用题型/年份/数据条件>
assumptions: []
counterexamples: []
conflicts: []
uncertainty: []
human_verification: pending|passed|failed|not_required
derived_from: []
supersedes: null

```

## 主题

<一句话说明本次检索回答的问题>

## 检索记录

| 项 | 值 |
|----|----|
| 时间 | <%datetime> |
| 查询词 | <检索式/关键词> |
| MCP 工具 | <paper_search / query-docs / search_repositories / search 等> |
| 结果条数 | <N> |
| 筛选后采用 | <n> |

## 关键结论（依据条目化）

1. **结论**：<信息点>　**来源**：<作者/仓库/文档/站点>（<年份>）　**引用**：<DOI / URL / 版本号>
2. 结论：…　来源：…　引用：…

## 可复用片段

- <可直接复用的引言/公式片段/代码骨架/接口签名，标注出处>

## 引用清单（进入台账）

- <GB/T 7714 条目；或标注 "已入台账 #id"，见 `state/reports/references-ledger.md`>

## 局限性 / 待核

- <检索覆盖范围、时效、需要人工复核的点>（如：该来源非同行评审，需人工确认）

---
**归档要求**：核心节点每次必调 MCP 后必须产出本卡片；空卡（无来源/依据）视为未执行必调。
