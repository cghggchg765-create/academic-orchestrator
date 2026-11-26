# MCP 联网检索与知识卡片沉淀分发体系（专项 3）

> 独立专项：建立"检索 → 沉淀 → 分发"闭环。机制为机器强制（`mcp_boot_check.py`、`round-score`/`node-review` 检索门禁、`knowledge_cards`、`dr-note`/`dr-list`、`search-evidence`），本文为执行口径（SSOT：`mcp/checkpoint-0-boot.md`、`mcp/call-hierarchy.md`、`mcp/validation-checkpoints.md`、`mcp/knowledge-card.template.md`、`mcp/reference-ledger.template.md`）。
> 版本：1.5.0 ｜ 复核：2026-08-19 ｜ 验收：lint 零报错 + `tests/test_mcp_gates.py`（13）+ `tests/test_dr_intervention.py`（10，含轮次卡片追踪）全过。

## 一、MCP 启动门禁执行流程（Checkpoint 0 · 顺序不可逆）

```
任务开工（/mm、/mm-init、单节点、接手、迭代——一切建模任务）
  │  ① 全局 MCP 扫描（以本机真实注册为准：mcp__* 命名空间 + 本机 mcp 配置，禁止虚构/硬编码）
  ▼  ② 筛选四类适配 MCP：paper-mcp（论文搜索·核心常驻） / context7（算法技术） / github（开源工程） / tavily（前沿·双密钥，未装由 tokenhub-tools 回退）
  ▼  ③ 内嵌确认：mcp/ 模块 8 项载体在库（协议/规范/门禁/模板）
  ▼  ④ 自检：python scripts/mcp_boot_check.py --report --namespaces "<会话内真实命名空间>"
         → MCP_READY  放行（register 到 mcp/mcp-boot-report.md）
         → MCP_BLOCKED 立即终止任务，列出异常 MCP 与修复路径，修复后重跑
```

- 入口命令：`/mm-boot`；`/mm` 第 0 步；orchestrator IRON RULE 13/14；主控 SKILL 铁律 11。
- 校验项：加载状态 / 调用权限（无 deny）/ 联网探测 / 密钥有效性；任一不过 → MCP_BLOCKED。
- 铁律：①→④ 不可逆不可跳；扫描结果必须本地真实；自检未过 N1-N8 不得启动。

## 二、核心节点必调映射表（含迭代每轮要求）

机器常量 `MANDATORY`（`scripts/mcp_boot_check.py`）与 `call-hierarchy.md` 一致；`--coverage` 按节点统计留痕覆盖。

| 核心节点 | 必调 MCP（不可跳过） | 用途 | 机器强制（禁止纯内生） |
|:---:|----------------------|------|----------------------|
| **N1** 选题拆解 | 论文搜索 + Tavily/tokenhub | 赛题背景、同类案例、前沿资料 | `node-review N1 PASS` 前校验 `mcp-calls.jsonl`/`cases` 留痕 |
| **N3** 模型搭建 | Context7 + 论文搜索 | 模型原理、公式细节、方法依据文献 | `node-review N3 PASS` 前校验留痕 |
| **N4** 代码开发（迭代环） | Context7 + GitHub | API 文档、开源实现、高性能算法 | `round-score` 每轮校验**本轮**留痕（跨轮不通用） |
| **N5** 模型调优（迭代环） | GitHub + Tavily/tokenhub | 开源基线、SOTA / 前沿优化算法 | `round-score` 每轮校验**本轮**留痕 |
| **N7** 论文撰写（迭代环） | 论文搜索 | 文献检索、GB/T 7714 双分支归档 | `round-score` 每轮校验**本轮**留痕 |

**🔴 迭代每轮必须重新检索**：
1. `round-score`（N4/N5/N7）机器门禁：本轮无 `state/reports/mcp-calls.jsonl`（node+round 行）或 `state/cases/index.json`（该轮 `used_in_rounds`）→ 拒绝评分，提示"禁止纯内生输出"（`--allow-missing-mcp` 显式豁免，仅离线/人工特批）。
2. **禁止只靠旧卡片不做新检索**：跨轮留痕不通用（测试 `test_n4_round_score_cross_round_evidence_not_reused` 实证 round1 留痕不能给 round2）。
3. 每轮检索→沉淀→`round-score` 自动采集 `rounds[n].knowledge_cards`（命名约定 `{节点}_r{轮}_{slug}.md`），使"每轮有新检索、有卡片"可追踪。

## 三、知识卡片沉淀规范

| 项 | 规范 |
|----|------|
| **路径** | `state/reports/mcp-cards/`（机器事实源；`search-evidence` 与 `collect_round_cards` 都读它） |
| **模板** | `mcp/knowledge-card.template.md`（来源/依据/引用齐全，禁止空卡） |
| **命名约定** | `{节点}_r{轮}_{slug}.md`（迭代每轮）；阶段级用 `{节点}_{slug}.md`（如 N1_case_map.md）；由 `collect_round_cards` 按 `{节点}_r{轮}_` 前缀采集进轮次 |
| **留痕** | 每次 MCP 调用写 `state/reports/mcp-calls.jsonl`（node/round/mcp/query/卡片路径）；机器门禁与 coverage、N8 终检共用 |
| **台账** | 文献按 `mcp/reference-ledger.template.md` 归入 `state/reports/references-ledger.md`（GB/T 7714：作者/题名/年份/DOI 齐全） |
| **DR 介入** | Deep Research 链介入另记 `state/reports/dr-interventions.jsonl`（dr-note）+ `rounds[n].deep_research` |
| **沉淀责任** | 执行 Agent（selector/modeler/coder/tuner/writing）在 SEARCH/MCP 调用后即落卡片 + 留痕；orchestrator 兜底查验 |

## 四、场景化精准分发规则（派发时必须传入对应卡片）

| 场景 | 必须随派发传入 | 命令/载体 |
|------|----------------|----------|
| **写作（N7 初稿）** | 知识卡片 + 论文大纲（academic-paper 大纲 / /ars-outline 产物）+ 检索证据清单 | `search-evidence N7` + 大纲路径随派发 prompt |
| **修改迭代（N4/N5/N7 下一轮）** | 原文 + 代码 + **新旧卡片**（本轮新增 + 上轮卡片）+ 历史记录（rounds[n].knowledge_cards / dr-list / feedback / failure_analysis） | `dr-list Nx --round n` + `search-evidence Nx` + 上轮 `rounds[n]` 数据 |
| **审阅（配对审阅 / N8 终审）** | 数据（Code/output/tables 等）+ 原文 + 代码 + 检索资料（mcp-cards/references-ledger）+ 全量卡片 | `search-evidence Nx`（汇总）或逐项路径；审阅记录附 evidence |
| **接手/断点恢复** | handoff（write_handoff 输出）+ 检索留痕汇总 | `handoff Nx` + `search-evidence` |

> 通用入口：`search-evidence <Nx>` 汇总该节点知识卡片/案例/台账/MCP 留痕；`dr-list <Nx> [--round]` 汇总 DR 介入。orchestrator 委派任一节点前先调用并把清单附入派发 prompt（禁止纯内生、禁止"不带依据就写/改/审"）。

## 五、N8 终检校验清单（`mcp/validation-checkpoints.md` 执行口径）

终审（reviewer N8）按以下逐项核对，任一不过 → 评审不通过，返回补全：

- [ ] **五节点必调留痕**：N1/N3/N4/N5/N7 在 `state/reports/mcp-calls.jsonl` 各有调用记录（`mcp_boot_check.py --coverage` 核对，无必调记录不过）；
- [ ] **迭代每轮新检索**：N4/N5/N7 每个迭代轮次 `rounds[n]` 有检索留痕（case_refs/mcp-calls）且 `knowledge_cards` 非空（无新检索 = 纯内生 = 不过）；
- [ ] **知识卡片齐全**：所有核心节点检索结果均有卡片（`state/reports/mcp-cards/`，模板字段完整、来源可溯源，无空卡）；
- [ ] **GB/T 7714 台账完整**：`references-ledger.md` 与论文参考文献表一一对应（条数/内容不漂移，`mcp_boot_check.py --ledger` 校验）；
- [ ] **DR 介入留痕**：N4/N5/N7 每轮按需介入可查（`dr-list`，含 SEARCH/SCORE/DECIDE 阶段介入）；
- [ ] **闭环**：记录/档案/卡片闭环后 A3 终审通过，产出 `SubmissionPackage/参赛提交清单.md`。
