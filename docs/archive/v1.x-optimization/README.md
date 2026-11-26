# v1.x 优化文档归档

> ⚠️ **历史文档，v1.x 口径，勿作为现行规范使用。**

本目录保留的是 academic-orchestrator 2.0.0 之前的优化整改记录。它们描述的是
**v1.5.0 / v1.7.0 时期的 24 Agent / 34~35 Skill / 22 命令**结构，其中大量组件
（ARS 四技能副本、`/ars-*` 16 个命令、`xlsx` / `drawio-skill` / `make-pdf` 等
第三方副本、`orchestrator` 子 Agent）已在 2.0.0 物理删除。

## 现行规范请读这些

| 主题 | 现行文件 |
|---|---|
| 组件口径（21 Agent / 23 Skill / 7 命令） | `scripts/lint_contracts.py` 的 `EXPECTED_COUNTS` |
| 门禁定义（单一事实源） | `shared/contracts/gates-registry.json` |
| 门禁阈值与判据说明 | `skills/mm-iteration-engine/SKILL.md` §6.3 |
| 编排协议（主 Agent 专用） | `skills/academic-orchestration/SKILL.md` |
| 技能运行时路由 | `skills/mm-skill-router/SKILL.md` + `shared/skill-routing/capability_taxonomy.json` |
| 数据血缘契约 | `shared/contracts/math_modeling/data_lineage.schema.json` |
| 图表/表格对标 | `skills/figure-table-benchmark/SKILL.md` |
| 上游更新 | `upstream-manifest.json` + `commands/academic-update.md` |

## 为什么保留

这些记录包含当时的决策理由、BUG 排查过程与取舍权衡，对理解"为什么现在的结构是这样"
仍有参考价值。**但其中的计数、组件清单、路径引用一律以 2.0.0 现状为准。**

## 归档清单

| 文件 | 原口径 | 主要过期点 |
|---|---|---|
| `agent-collaboration-loop.md` | v1.5.0 | 24/34/22 口径；ARS 副本与 `/ars-*` 命令已移除；N7 scope 协议已迁入 `academic-orchestration` |
| `全组件联动地图.md` | v1.5.0 | 组件清单含已删项 |
| `组件盘点与合并规划.md` | v1.5.0 | 同上 |
| `重叠合并清单.md` | v1.5.0 + 1.8.0 追加 | 主辅裁决仍可参考，但组件清单过期 |
| `8类BUG修复报告.md` | 21 Agent | 修复项多半仍有效，计数过期 |
| `pro-library-fusion.md` | v1.7.0 | Pro 案例库融合记录（139 卡仍在 `skills/mathematical-modeling/assets/case-library/`），版本口径过期 |
