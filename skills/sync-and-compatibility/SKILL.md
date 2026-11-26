---
name: sync-and-compatibility
description: "已有论文、代码与数据的同步兼容接入规范：材料清单与哈希锁定、代码审阅与修复、数据一致性验证、论文改写门禁、Markdown 转 LaTeX 转换协议（输出 BLOCKED 转换任务，禁止脚本直接生成权威 LaTeX）。触发词：同步, 兼容, 导入, 已有论文, 已有代码, 格式转换, markdown 转 latex"
metadata:
  version: "1.0.0"
  last_updated: "2026-08-19"
  status: active
  canonical: true
---

# 同步和兼容：已有论文、代码与数据接入规范

本 Skill 用于**已有论文、代码和数据**的接入、审阅、修复、同步和格式转换。它不是从零写作流程，核心原则是：

> 先建立兼容性事实，再独立审阅代码和数据；只有质量门禁通过，才允许论文改写；Markdown 最终转换为唯一的 LaTeX 文档源，PDF 由 LaTeX 编译生成。

## 1. 输入与输出

必须识别三类输入：

- 已有代码：入口、依赖、配置、运行方式、输出文件和版本信息；
- 已有数据：来源、格式、字段、缺失值、异常值、划分策略和处理脚本；
- 已有论文：Markdown、LaTeX 或 PDF。PDF 只能作为阅读/比对输入，不能直接作为可维护源文件。

接入阶段必须生成：

- `state/compatibility_manifest.json`：材料清单、格式、哈希、入口和依赖；
- `state/source_inventory.md`：代码、数据、论文之间的对应关系；
- `state/claim_evidence_map.json`：论文主张到代码运行证据、数据字段和图表的映射。

## 2. 自动标准化接入

对已有材料执行标准化导入：

```bash
python shared/state-engine/state_utils.py init --dir <标准项目目录> --name <项目名>
python shared/state-engine/sync_import.py --source <已有材料目录> --project <标准项目目录>
# 审阅计划后再执行实际导入
python shared/state-engine/sync_import.py --source <已有材料目录> --project <标准项目目录> --apply
```

导入规则：

- 原始材料只读保留，不覆盖已有标准项目文件；目标文件冲突时自动追加 `_imported`；
- 代码统一进入 `Code/legacy/`，随后由 `coder` 审阅、拆分和迁移到标准入口；
- 数据统一进入 `Data/raw/`，禁止在 raw 目录直接修改；清洗结果由 `dataprep` 写入 `Data/processed/`、`Data/feature/` 和 `Data/test_result/`；
- Markdown 自动转换为 LaTeX 草稿，进入 `ReportPaper/LaTeX/imports/`，必须经过写作 Agent 和独立审阅后再合并到 `sections/`；
- PDF、DOCX 等不可直接维护格式只进入 `state/imports/`，用于比对和溯源，不作为最终源文件；
- 自动生成或更新 `compatibility_manifest.json`、`source_inventory.md` 和 `claim_evidence_map.json`，记录来源、目标、哈希、转换状态和待完善项。

自动导入只负责结构整理，不替代代码审阅、数据验证、论文改写和 LaTeX 编译门禁。

## 2.1 题目事实锁定与偏移防护

在任何分析或做题任务开始前，必须先阅读题目原文，并创建 `state/problem_lock.json`。锁定文件至少记录：

- 题目原文路径和 SHA-256；
- 任务目标 `objectives`；
- 前提约束 `constraints`；
- 前提条件 `preconditions`；
- 相关数据要求 `data_requirements`；
- 评价指标 `evaluation_metrics`。

标准命令：

```bash
python shared/state-engine/problem_guard.py create \\
  --project <项目目录> --source <题目原文> \\
  --objectives '["目标1"]' --constraints '["约束1"]' \\
  --preconditions '["条件1"]' --data-requirements '["数据1"]' \\
  --evaluation-metrics '["指标1"]'
python shared/state-engine/problem_guard.py verify --project <项目目录>
```

N1 及之后所有 Agent 开始前必须读取并验证该文件；每次代码运行、数据处理、敏感性分析、误差分析、图表生成和论文改写前都要复核。题目原文哈希变化、目标/约束/数据/指标缺失或任务输出与锁定事实冲突时，必须阻断当前任务，回到题目重新分析，不得依赖记忆或沿用旧假设。

## 3. 强制顺序

```text
现有材料接入
  → 代码审阅与更新
  → 数据一致性验证
  → 独立评分与门禁
  → 论文改写
  → Markdown 转 LaTeX
  → LaTeX 编译 PDF
  → 论文与代码/数据最终一致性审阅
```

禁止在代码和数据门禁未通过时开始论文改写。若用户只要求论文转换，也必须先检查是否存在未验证的代码/数据主张；无法验证的数字必须标记为待核对，不得写入确定性结论。

## 4. 代码审阅与更新

### 4.1 执行 Agent

`coder` 负责：

1. 读取已有代码和运行说明；
2. 建立基线运行；
3. 对照 `ModelDocs/formula.md`、数据字段和论文主张；
4. 修复正确性、效率、可读性、鲁棒性和可复现性问题；
5. 对敏感性分析、误差分析、异常输出进行针对性修改；
6. 修改后必须重新运行并保存退出码、stdout/stderr、参数、随机种子和产物哈希。

### 4.2 独立评分 Agent

评分必须由注册的独立审阅 Agent 完成：

- N4/N5：`mm-code-reviewer`；
- N2：`reviewer`；
- N7/N8：`reviewer`，但不能给自己产生的业务修改评分；
- 执行 Agent 与评分 Agent 不得相同。

评分 Agent 必须先读取对应评审 Skill，并在结果中声明：

- `skills_read` 及版本；
- 检查项和运行证据；
- 缺陷类别、严重度和复现步骤；
- `review_verdict` 与 `decision_action`。

评分不得只基于代码浏览或主观印象，必须关联可复现运行证据。

### 4.3 问题修复闭环

当出现以下任一问题时，不得直接通过：

- 敏感性分析不稳定或结论不支持；
- 误差分析缺失、指标计算错误或误差过大未解释；
- 鲁棒性检验失败；
- 代码与公式/论文不一致；
- 数据泄漏、随机性不可复现或输出缺失；
- 运行失败或 LaTeX 依赖的图表/表格无法生成。

必须执行：

```text
独立评审 FAIL
  → 结构化 feedback
  → 原执行 Agent 修复
  → 保留原轮次和问题历史
  → 重新运行同一检查/实验
  → 独立评分 Agent 复评
```

最多自动修复 2 次；仍失败则写入 `escalated`，交由人工决定，不得降级为 PASS。

## 5. 论文改写门禁

只有同时满足以下条件，`writing` 才能改写论文：

- 代码独立评分达到 `pass`，或明确记录人工接受的降级结论；
- 数据质量门禁 PASS；
- 关键实验有运行证据和产物哈希；
- 论文中的数字、图表和结论可以追溯到代码和数据；
- 敏感性、误差和鲁棒性问题已完成修复或被明确标记为限制。

论文改写必须优先更新 `claim_evidence_map.json`，每个主张至少绑定一个证据来源。

## 6. Markdown 转 LaTeX

转换协议：

1. Markdown 作为输入快照保留，不覆盖原始文件；脚本只做结构归档与任务登记；
2. `sync_import.py --apply` 把 Markdown 复制到 `ReportPaper/LaTeX/drafts/import-<名称>/source.md`，并在同目录与 `state/latex_conversion/<名称>/task.json` 生成 `document_to_latex` 转换任务（`status: BLOCKED`，声明必读 Skill 与人工复核点）；
3. 脚本禁止直接生成权威 LaTeX 源；正式转换必须由专用 Agent 读取 `mm-latex-writing` 与 `latex-guard` 后完成，并经过独立审阅；
4. 转换后按国赛 10 节结构映射到 `ReportPaper/LaTeX/sections/`，公式转为标准数学环境并生成 `\label`/`\eqref`，图片转 `figure` 环境，表格转 `booktabs` 三线表，引用转 `\cite{}` 并补齐 `ref.bib`；
5. 只维护 `ReportPaper/LaTeX/` 下的 `.tex`、`.bib`、资源和配置；
6. 用 `latexmk -xelatex -interaction=nonstopmode main.tex` 编译 PDF；
7. PDF 是发布产物，不是源文件，不允许手工编辑 PDF 代替修正 LaTeX。

转换完成后必须检查：

- `\ref`、`\eqref`、`\cite` 是否全部解析；
- 图片和表格路径是否存在；
- 章节顺序、公式编号、图表编号是否连续；
- 编译日志无 undefined reference/citation 和致命错误；
- 页数、摘要长度和参考文献格式符合 profile；
- **图表排版质量**（详见 latex-guard Skill）：表格宽度/字号全文统一（≤\textwidth，\small 或 \footnotesize 二选一）；无图表插在文段中间（禁止 [H]、图表前后有空行、图表不早于首次引用）；同类多图已合并为 subfigure 子图；图注/表注统一 \footnotesize 且以"注："开头；表格后无字段与表格同行。

## 7. 状态与交付

每个阶段都要写入统一结果 envelope，并区分：

- `review_verdict`: PASS/FAIL/BLOCKED；
- `decision_action`: continue/repair_and_rerun/pass_continue/early_stop/escalated；
- `status`: completed/repair_pending/blocked/escalated。

交付至少包括：代码审阅报告、数据质量报告、运行证据、独立评分记录、论文改写报告、LaTeX 源码和编译 PDF。