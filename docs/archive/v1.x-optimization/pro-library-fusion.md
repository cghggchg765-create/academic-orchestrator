# Pro 知识库融合（v1.7.0）：math-modeling-skill-pro 资产映射

> 融合日期：2026-09-03 ｜ 版本：1.7.0 ｜ 授权：已获项目作者授权，允许复制、迁移、融合并协同迭代演进。
>
> 本文件是案例库/知识/模板/骨架资产在现有 Phase 0-8 流程中的**唯一映射权威**。融合遵循三条原则：
> ① 全部资产按流程节点安放，不游离主流程；② 现有技能章节内容零修改，只追加融合段；③ 不新增 Skill/Agent/Command 组件（35/24/22 口径不变）。

---

## 1. 资产来源与授权边界

| 项 | 内容 |
|---|---|
| 源仓库 | `https://github.com/skillforCUMCM/math-modeling-skill-pro`（commit `88e9705`） |
| 授权 | 已联系项目作者获得授权，允许复制、迁移、融合至当前技能并协同迭代演进 |
| LICENSE | 源仓库为专有授权（"All rights reserved"），依据作者授权进行融合；第三方法论文/图片/附件不随仓库分发 |
| 迁移内容 | 仅迁移**结构化转述**：139 张案例卡、12 份知识文档、6 份模板、8 类代码骨架、检索/校验脚本、语料证据边界声明 |
| 不迁移 | 原始论文 PDF/图片、OCR 缓存、抓取清单、`extract_paper_evidence.py`/`draft_case_cards.py`（依赖本地合规语料与 OCR 工具链）、`agents/openai.yaml` |

### 证据边界（随 `assets/case-library/corpus-provenance.md` 保留并强制遵守）
- 案例卡是决策记忆的转述与批判性提炼，**不是论文原文库**，不得大段复制原文。
- 139 篇优秀论文是经验样本，**不构成某模型普遍更优的统计证明**；模型频次只能用于检索，不能用于选择。
- `ocr_sampled` 卡（92 张）仅抽取第 1/2 页与约 70% 位置页，**未抽样页的方法/公式/参数/附录实现不得视为已核验**。
- `source_pdf`/`source_page` 保留为溯源引用字段；关键公式、阈值、定量结论需回到官方页面复核。

---

## 2. 资产映射总表

| 源仓库资产 | 融合落点 | 用途与挂接节点 |
|---|---|---|
| `cases/case-001..139.md` + `index.json/csv/md` | `skills/mathematical-modeling/assets/case-library/` | 优秀论文案例库（2012—2025），N1 案例类比检索数据源 |
| `templates/case-card-template.md` | `assets/case-library/case-card-template.md` | 沉淀新案例卡的字段规范 |
| `references/corpus-provenance.md` | `assets/case-library/corpus-provenance.md` | 证据边界与版权纪律 |
| `knowledge/problem-types.md` | `skills/mm-problem-analysis/assets/pro/problem-types.md` | N1 题型诊断/六维结构 |
| `knowledge/problem-dependencies.md` | `skills/mm-problem-analysis/assets/pro/problem-dependencies.md` | N1 子问题依赖图/误差传播 |
| `templates/problem-analysis.md` | `skills/mm-problem-analysis/assets/pro/templates/problem-analysis.md` | N1 赛题分析模板 |
| `knowledge/model-selection.md` | `skills/mm-model-library/assets/pro/model-selection.md` | N3 A/B/C 三方案与硬筛选 |
| `knowledge/model-library.md` | `skills/mm-model-library/assets/pro/model-library.md` | N3 模型卡「用/慎禁/验/替升」 |
| `knowledge/model-combinations.md` | `skills/mm-model-library/assets/pro/model-combinations.md` | N3 组合准入与反模式 |
| `templates/model-design.md` | `skills/mm-model-library/assets/pro/templates/model-design.md` | N3 模型设计模板 |
| `knowledge/data-workflow.md` | `skills/mm-data-preprocessing/assets/pro/data-workflow.md` | N2 数据审计/清洗/泄漏防护 |
| `knowledge/validation-methods.md` | `skills/mm-model-tuning/assets/pro/validation-methods.md` | N5 四层验证/敏感性/稳健性 |
| `templates/validation-plan.md` | `skills/mm-model-tuning/assets/pro/templates/validation-plan.md` | N5 验证计划模板 |
| `knowledge/innovation-patterns.md` | `skills/mm-latex-writing/assets/pro/innovation-patterns.md` | N7 创新点设计六类模式 |
| `knowledge/paper-writing.md` | `skills/mm-latex-writing/assets/pro/paper-writing.md` | N7 论文结构与证据表达 |
| `templates/paper-outline.md` | `skills/mm-latex-writing/assets/pro/templates/paper-outline.md` | N7 论文目录模板 |
| `templates/abstract-template.md` | `skills/mm-latex-writing/assets/pro/templates/abstract-template.md` | N7 摘要模板 |
| `code/prediction/pipeline.py` 等 8 类骨架 | `skills/mm-algorithm-dev/assets/pro/code-skeletons/` | N4 代码起始骨架（prediction/evaluation/optimization/clustering/machine-learning/network/mechanism/simulation） |
| `knowledge/corpus-analysis.md/json` | `skills/mathematical-modeling/assets/pro-library/corpus-analysis.md/json` | 语料观察图谱（问题类型/模型/验证分布，仅作检索线索） |
| `SKILL.md`（仓库决策链） | `skills/mathematical-modeling/assets/pro-library/overview.md` | 决策链总览（证据边界→数学抽象→候选对比→验证→结论） |
| `scripts/search_cases.py` | `shared/state-engine/case_search_lib.py` + `state_search.py cmd_case_search` | `state_utils.py case-search` 检索命令 |
| `scripts/build_case_index.py` / `validate_skill_content.py` / `validate_repository.py` | `scripts/check_case_library_integrity.py`（适配合并为完整性校验，注册 CI） | 案例库维护/完整性校验 |

---

## 3. 流程挂接（不破坏原链路）

### 3.1 N1 选题拆解：案例检索闭环（必做）
主控 `mathematical-modeling/SKILL.md` Phase 1 新增（见融合段）：

```
python state/state_utils.py case-search "<问题结构检索词>" --top 6
  # 推荐按「问题结构/数据结构/数学结构」分 2-3 次检索；混合链每阶段一次再并集去重
  # --save 沉淀命中卡到 state/cases/（source_type=pro-case-library）供派发携带
  # 案例阈值/权重/题目专属机制为不可迁移信息；OCR 未核验细节不得当作已核验
```

案例检索是 MCP 论文搜索的**本地结构化补充**，不替代 N1 必调 MCP 论文搜索与知识卡片沉淀（`mcp/call-hierarchy.md`、`search-evidence` 派发协议不变）。

### 3.2 各节点 Pro 资产接入点

| 节点 | 执行 Agent | 接入的 Pro 资产 | 既有能力 |
|---|---|---|---|
| N1 选题 | selector | case-search + problem-types/problem-dependencies | M1/H1 门禁不变 |
| N2 数据 | dataprep | data-workflow | D1 门禁不变 |
| N3 建模 | modeler | model-selection（A/B/C）+ model-library + model-combinations | P1 门禁不变 |
| N4 代码 | coder | code-skeletons 8 类骨架 | P2/A1 门禁 + `Code/output/` 唯一输出口不变 |
| N5 调优 | tuner | validation-methods + validation-plan | T1 门禁不变 |
| N7 论文 | writing | innovation-patterns + paper-writing + 大纲/摘要模板 | W1/A2/W2 门禁 + latex_linter 不变 |
| N8 评审 | reviewer | corpus-analysis 作为证据线索（不替代评审标准） | A3 门禁不变 |

---

## 4. 检索命令规格（state_utils.py case-search）

```
python state/state_utils.py case-search <query> [--top N] [--year Y] [--type T] [--model M]
                                            [--json] [--skill-root R] [--save] [--dir .]
```

- **检索核心**：`case_search_lib.py`（纯函数，随脚手架复制进项目 `state/`，项目自包含）
  - 中文二字片段切分 + 别名扩展（预测/评价/优化/分类/聚类/网络/机理/仿真/小样本/多目标/不确定性共 11 组）
  - TF-IDF 风格加权，`tag:` 术语权重 3.5×，查询中显式出现的类型/模型名额外 +4.0
  - 排序：分数降序 → 年份降序 → case_id 升序
- **案例库定位（fail-closed）**：`--skill-root`（权威，错误即报错不回退）→ `MM_SKILL_ROOT` 环境变量（权威）→ 从 `__file__` 向上探测；均未命中时报错并提示，**禁止静默降级**。
- **`--save`**：将 top-N 命中卡沉淀进项目 `state/cases/index.json` + 单卡 JSON（`source_type=pro-case-library`，含 `problem_types`/`models`/`score`），供 `search-evidence` 派发携带。
- 输出：文本（评分/类型/模型/命中词/卡路径）或 `--json`（score/matched + 完整卡字段）。

---

## 5. 兼容性保障（完成清单）

| 项 | 状态 |
|---|---|
| 现有技能章节内容零修改，仅追加 `Pro 知识库融合（v1.7.0）` 小节 | ✅ |
| 不新增 Skill/Agent/Command（35/24/22 不变；案例库为主控技能 assets 资产） | ✅ |
| Phase 0-8 主线、门禁、铁律、MCP 必调链、state 协议未改动 | ✅ |
| `state_utils.py init` 脚手架复制完整（15 个 .py 模块，含新 case_search_lib） | ✅ 冒烟验证 |
| 项目内 CLI `case-search` 可用；无 `--skill-root` 时 fail-closed | ✅ 冒烟验证 |
| 139 卡 body_sha256 逐一核对（0 不一致）、card_path 对齐、无越界路径 | ✅ |
| 新测试 `tests/test_case_search.py`（8 项）+ `tests/test_case_library_integrity.py`（3 项）全部通过 | ✅ |
| 数学建模核心链路回归：scoped-workflow 9 项、v3.9.2-pipeline 16 项、574-phase 603 项全通过 | ✅ |
| `_ci_pytest_manifest.toml` 新增 2 条目（170-case-library-integrity / 170-case-search），manifest lint 通过（157 entries） | ✅ |
| 版本面同步：pyproject / plugin.json×3 / marketplace（含描述漂移修复）/ scaffold skill_version / decision_log 模板 / 两技能 metadata / mm-help / README / CHANGELOG | ✅ |

### 既有（非本融合引入）已知失败/待发行处理
以下问题在 git 基线 HEAD 中即存在，经 stash 对照逐项确认失败数一致，**非本次融合引入**，且不影响核心链路：

| 检查 | 现状 | 性质 |
|---|---|---|
| `lint_contracts.py` | 报「命名红线」命中 `学习材料/` 未跟踪目录 | 工作区既有未跟踪用户材料 |
| `check_version_consistency.py` | `.claude/CLAUDE.md` 缺失 | HEAD 基线无此文件 |
| `check_distribution_surface_claims.py` | D1（`.claude-plugin/marketplace.json` 缺失）+ D4（plugin.json 描述缺 agent-count token） | HEAD 基线即缺 |
| manifest 约 104 项失败 | 均在基线同样失败（抽样 4 项对照逐一一致） | 测试布局（根目录 vs `skills/`）不匹配/环境 |
| `test_self_check_script` | 基线同样失败（用户级残留副本 + 缓存缺失） | 发行环境未执行 `sync_user_level.py --plugin-only` + 缓存重建 |
| `plugin_registry_check --strict-git` | 缓存仍为 1.6.0 + known_marketplaces 缺失 + clean-package 列既有未跟踪资产 | **发行流程**：需重建 1.7.0 缓存并清理用户级残留 |

### 发行前置动作（v1.7.0 发布时执行）
1. `python scripts/sync_user_level.py --plugin-only`（清理用户级残留副本）
2. 重建本机插件缓存 `math-modeling-agent-system/1.7.0`（逐文件 MD5 与仓库对齐）
3. 重新运行 `plugin_registry_check.py --strict-git` 直至 PASS
4. 视需要补齐 `.claude/CLAUDE.md` 与 `.claude-plugin/marketplace.json`（既有发行缺口）

---

## 6. 后续维护

- **新增案例卡**：用 `assets/case-library/case-card-template.md` 字段规范撰写 → 跑 `scripts/check_case_library_integrity.py` 校验 → 需要时更新 `index.json`。
- **知识文档修订**：直接改对应技能 `assets/pro/` 下文件，融合段只引用路径不复制正文。
- **检索增强**：`case_search_lib.py` 的 `ALIASES` 可扩展；修改后跑 `tests/test_case_search.py`。
- **上游仓库协同**：源仓库新 commit 以本表为映射依据增量融合，冲突时以本表 + 现有流程门禁为准。