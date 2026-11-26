# Markdown/文档到 LaTeX 转换协同协议

版本：1.0.0  
状态：active  
适用范围：Markdown、HTML、DOCX、PDF 阅读稿或其他可维护文档输入转为 `ReportPaper/LaTeX/` 工程。

## 1. 核心原则

1. **转换是语义写作任务，不是机械格式转换**：最终 `.tex` 必须由专用的 LaTeX/论文 Agent 编写、重组和润色。
2. **脚本不得直接生成最终 LaTeX**：脚本只能完成文件盘点、哈希记录、输入快照保存、任务包生成、结构检查和编译质量检查；不得把 Markdown 文本直接当作最终 `.tex` 交付。
3. **专用 Agent 必须读取技能**：执行 Agent 开始前必须读取 `mm-latex-writing`；随后必须按需读取 `latex-guard`，并在结果中声明技能版本和检查范围。
4. **原文不可覆盖**：输入材料以只读快照或导入副本保留，转换输出必须进入隔离的草稿目录，经过独立审阅后才能合并到 canonical LaTeX 工程。
5. **不能诚实完成就阻断**：缺少公式语义、图表资源、引用信息、编码信息或必要的人工确认时，结果必须为 `BLOCKED`，不得用自动转义或占位文本伪装完成。

## 2. 角色与职责

| 角色 | Agent | 责任 | 可写范围 |
|---|---|---|---|
| 编排 | `orchestrator` | 建立任务包、检查前置、并行派发、收集结果、合并状态 | `state/` 状态文件 |
| 转换执行 | `writing` 或专用 LaTeX 转换 Agent | 阅读输入、恢复语义结构、编写 `.tex`、补公式/图表/引用、记录不确定项 | `ReportPaper/LaTeX/drafts/<run_id>/`、结果 envelope |
| LaTeX 质量审阅 | `latex_linter`/`reviewer`（按 registry 配对） | 检查结构、编码、公式、图表、引用、交叉引用、排版规范 | `state/` 审阅记录 |
| 编译验证 | `latex_linter` 或宿主质量工具 | 只在 Agent 产出后执行编译和日志检查，不负责代写内容 | `ReportPaper/LaTeX/build/`、质量报告 |

## 3. 标准流程

```text
intake
  → source_inventory + compatibility_manifest
  → conversion_task（统一任务包）
  → 并行语义处理（章节/公式/图表/引用，互不覆盖）
  → LaTeX Agent 汇总与人工语义复核
  → latex-guard 审阅
  → 编译/日志质量检查
  → reviewer 复核
  → 合并到 ReportPaper/LaTeX canonical 源
```

### 3.1 并行规则

- 并行单元必须按文件或章节分区，每个单元有唯一 `run_id` 和 `output_scope`。
- 公式、图表、引用处理可并行，但不得直接修改同一个 `.tex` 文件；由汇总 Agent 统一整合。
- 任一并行单元 `BLOCKED` 时，汇总 Agent 必须保留阻断原因并暂停对应章节合并。
- 并行处理完成后必须进行一次统一编码和交叉引用审阅，不能以各单元分别通过代替整体审阅。

### 3.2 允许的脚本操作

允许：

- 列出文件、检测编码、计算 SHA-256、记录来源和哈希；
- 保存原始输入快照；
- 生成任务包、章节清单、待确认问题清单；
- 检查 `.tex` 的结构标记、未闭合环境、占位符、未定义引用和编译日志；
- 在 Agent 编写完成后调用编译器验证。

禁止：

- 直接执行 `markdown_to_latex()` 并把结果作为最终论文源；
- 用正则批量替换公式、引用或图表环境后宣称转换完成；
- 在没有读取 `mm-latex-writing`/`latex-guard` 的情况下生成交付 `.tex`；
- 以“能编译”替代“语义、证据和排版均通过”。

## 4. 任务包与结果要求

转换任务包至少包含：

- `task_type: document_to_latex`
- `source_files`：来源路径、格式、编码、SHA-256；
- `target_scope`：目标章节/文件及唯一输出目录；
- `required_skills`：`mm-latex-writing`、`latex-guard`；
- `parallel_units`：章节、公式、图表、引用等处理单元；
- `quality_gates`：编码、结构、公式、图表、引用、编译；
- `manual_checkpoints`：无法自动判断的语义问题；
- `prohibited_shortcuts`：禁止脚本直转最终源。

结果 envelope 必须声明：

- `agent_id`、`node_id`、`run_id`、`status`；
- `skills_read` 及版本；
- `artifacts` 与哈希；
- `checks`、`feedback`、`manual_checkpoints`；
- `review_verdict`：`PASS` / `FAIL` / `BLOCKED`；
- `decision_action`：继续、修复复跑、升级或合并。

## 5. 门禁

只有同时满足以下条件才允许合并到 canonical LaTeX：

- 转换 Agent 已阅读并声明 `mm-latex-writing` 和 `latex-guard`；
- 所有并行单元均完成，或阻断项已被明确记录并获人工接受；
- 公式、图表、引用和交叉引用均有来源或待确认标记；
- LaTeX 结构检查通过，编译日志无致命错误；
- 独立审阅 Agent 给出 `PASS`；
- 原始材料、转换清单和证据映射仍然可追溯。

## 6. 失败与恢复

- `BLOCKED`：保留输入快照、任务包和阻断原因，生成 prerequisite/manual checkpoint，不合并源文件。
- `FAIL`：由原转换 Agent 按反馈修复，最多自动修复 2 次，每次保留新 `run_id` 和 issue history。
- 超过 2 次仍失败：写入 `escalated`，交由人工决定，不得降级为 `PASS`。
- 任一上游输入发生变化：使相关转换任务和下游审阅失效，重新生成任务包。

## 7. 最低交付物

```text
state/compatibility_manifest.json
state/source_inventory.md
state/claim_evidence_map.json
state/latex_conversion/<run_id>/task.json
state/latex_conversion/<run_id>/result.json
state/latex_conversion/<run_id>/review.json
ReportPaper/LaTeX/drafts/<run_id>/...
ReportPaper/LaTeX/quality/<run_id>.md
```

`ReportPaper/LaTeX/main.tex` 只有在专用 Agent、`latex-guard` 和独立审阅全部通过后才能更新。
