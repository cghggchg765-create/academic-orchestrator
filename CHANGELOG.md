# Changelog

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 与 [Conventional Commits](https://www.conventionalcommits.org/)。版本单一来源：`pyproject.toml`。

## [2.0.0] - 2026-11-26

定位变更：**数学建模专用插件 → 学术科研编排核心**（通用学术 + 建模子轨）。学术界主体能力交由 `academic-research-skills`、ARIS、nature-* 家族提供；本插件只保留编排骨架与原生专项。

### Changed（破坏性）

- **插件改名** `math-modeling-agent-system` → `academic-orchestrator`。三份 manifest（`.zcode-plugin/` / `.claude-plugin/` / `.codex-plugin/`）、`marketplace.json`、`pyproject.toml` 同步；命名空间前缀引用（`academic-orchestrator:mm-*`）全量改写。
- **编排载体迁移**：`agents/orchestrator.md`（子 Agent）→ `skills/academic-orchestration/SKILL.md`（主 Agent 协议）。原因是 ZCode 官方运行时把 `Agent`/`Task` 从子 Agent 工具表中剔除（`subagents:{enabled:false}`），子 Agent **无法**再派子 Agent，原设计在宿主上不可执行。
- **agent frontmatter 全面合规**：21 个 agent 由非标准键（`mode` / `temperature` / `steps` / `metadata` / `permission`）改为官方 strict schema（`tools` / `disallowedTools` / `model` / `maxTurns`）。原写法不在 schema 内，`task: deny` 等权限约束**从未真正生效**。
- **N0 executor** `orchestrator` → `main-agent`（项目初始化由主 Agent 完成）。

### Removed（消除重复）

- **10 个第三方复制 skill**：`xlsx`、`frontend-design`、`theme-factory`（源自 anthropics/skills）、`test-driven-development`、`systematic-debugging`、`receiving-code-review`、`subagent-driven-development`（源自 obra/superpowers）、`drawio-skill`（旧版 1.14.0）、`make-pdf`/`investigate`（gstack 依赖已剥离、功能残缺）。能力需求改由 `mm-skill-router` 运行时发现。
- **3 个 ARS 镜像 agent**：`research_architect_agent` / `synthesis_agent` / `report_compiler_agent`（与 ARS 插件重复，且 name 用下划线与上游连字符不一致）。
- **ARS 遗产**：`pi/`、`audits/`、`examples/`、`docs/design/`、`docs/migration/`、`prompts/`，以及死脚本 `check_agents_mirror_sync.py`（断言 `agents/` 只能有 3 个 ARS agent，与本插件结构冲突，从未生效）。
- **`__pycache__` / `*.pyc`**（Python 3.14 编译产物，跨版本死二进制）。

### Added

- **图表/表格文献对标体系**（对应「写论文时查同领域论文实际图表列名与数据项」需求）：
  - `skills/figure-table-benchmark/SKILL.md`：四步法 + 七维判定口径（列完备 / 统计量 / 单位 / 可比性 / 分组 / 图型 / 学术表达）。
  - `agents/mm-figure-table-benchmarker.md`：专职审阅 Agent，产出对标矩阵。
  - **B1 门禁**：N6/N7/N8 阻塞级门禁，要求 ≥3 篇同领域论文、七维逐项有证据、无 `GAP_MAJOR`。
  - `references/benchmark-matrix.schema.json`：矩阵机器可读结构。
- **后台并行派发与运行中纠正协议**（`academic-orchestration` 新增章节）：`run_in_background` 非阻塞派发、等待期可并行的准备项清单、`SendMessage` 纠正触发条件与报文格式、`RespondToCoordinator` 回执、纠偏留痕与 N8 终审核对（`CORRECTION_UNACKED`）。
- **门禁登记单一事实源**：`shared/contracts/gates-registry.json` + schema，lint 校验其与 `state_defs.NODES.gates` 不漂移。
- **上游更新机制**：`upstream-manifest.json`（9 个上游的 repo / git 源 / 版本 / 更新方式）+ `scripts/check_upstream_updates.py`（只读检查，`--apply` 才 `pull --ff-only`）+ `/academic-update` 命令。
- **能力词表扩充**：新增 `figure.benchmark`、`table.build` 两项能力（共 21 项）。

### Fixed

- `node-review` 门禁路由：secondary 审阅者的结论原先会写进主门禁（B1 被记成 V1），现按审阅者路由到专属门禁。
- secondary 审阅者的必读 skill 校验：不再强制声明执行方规范（如 `mm-visualization`），改用其专项清单（`SECONDARY_REVIEWER_SKILLS`）。
- `state_scaffold` 未透传 `secondary_reviewers` 到项目 registry。
- 死引用：`build` agent（不存在）→ 并入 `latex_linter`；`ref/math_model/…` 标注为外部参考项目而非本地路径。
- 换行统一：1714 个文件 CRLF → LF，并加 `.gitattributes`（`* text=auto eol=lf`）防止回归。
- `plugin_registry_check.py` / `self_check.py` / 相关测试的硬编码插件名同步到新名。

### Verification

- `python scripts/lint_contracts.py` 零报错（含新增的 `check_gates_registry` / `check_benchmark_contract`）。
- `python -m pytest tests -q`：159 passed / 5 skipped / 0 failed。
- 空跑：`state_utils.py init` 全量建结构 → N0 由 `main-agent` 完成 → B1 门禁由 `mm-figure-table-benchmarker` 落盘且**不污染 V1**。
- `/academic-update` 实测：正确识别 9 个上游，网络不可达时如实报 `FETCH_FAILED`。

### Known limitations

- 插件缓存**尚未同步**（用户要求先不安装）：源码为 2.0.0，已安装仍为 1.8.0。`self_check` 会如实报告「插件缓存缺失」，对应测试已改为跳过而非误判通过。
- `evals/`、`scripts/check_*.py`（108 个）、`tests/` 保留未删：它们是验证基础设施（177 条 CI pytest 清单依赖），不属于 `plugin.json` 的发布面（只发 skills/agents/commands），删除会破坏验收能力。

## [1.8.0] - 2026-09-05

### Fixed

- **跨平台锁与原子写**：`adjudication_activity.py` / `review_criteria_binding.py` 顶层 `import fcntl`、`os.fchmod`、目录 fd `os.fsync` 在 Windows 全部守卫化（msvcrt 字节锁 + POSIX 分支），两工具在 Windows 下 init-store/validate 实测通过。
- **自检修复方向错误**：`self_check.py --fix` 在插件独占模式下原本会再同步（越修越错），现改为调用 `sync_user_level.py --plugin-only` 清理用户级副本（先备份）；插件缓存路径回退改读 `pyproject.toml`，删除未使用常量。
- **CJK 评分失效**：`humanizer_tools.compute_ai_score` 对无空格分隔的中文永远返回 0.0（`str.split()` 词数恒为 1），现按"英文词 + 中文字符数"计有效词数；PostProcess 跳过原因字符串不再倒置。
- **评测门禁诊断丢失**：`run_writing_quality.py` 对 expected-FAIL 用例在守卫正确拦截后清空失败原因（如 zh-mm-003 的 95%→96% 变更被记录为"无需复核"），现保留 blocked_items/reasons 作为诊断、仅预审定用例不计 review_required；未触发失败补 `EXPECTED_FAIL_NOT_TRIGGERED`。
- **主张保真形同虚设**：fixture 的 `claims` 清单此前从未被检查，现逐条核验（`CLAIM_CHANGED` / `CLAIM_NOT_IN_ORIGINAL`），并对齐 README 承诺的"主张变化必须 FAIL"。
- **导入契约脆弱**：`backends/chinese.py` 裸 `from providers...` 在包导入模式下必炸，现与 `humanizer_tools` 一致提供相对导入回退。
- **文档-实现对齐**：`agents/humanize.md` / `skills/academic-humanize/SKILL.md` / `能力盘点.md` 中"24 种模式"与 C1-C9 加权评分虚述全部改为实际 36 模式 + C1-C7 severity 实现；README marketplace 示例版本 1.3.0→1.7.0；`distill_report.py` 报告路径 OS 归一化；测试改用 `sys.executable` 而非 `python3`（Windows 兼容）。
- **清理**：删除 7 个被跟踪的 `.bak/.bak2/.bak3` 备份；`.gitignore` 增补本机开发产物（Material/学习材料/state/一次性 HTML）。

### Added

- **写作质量离线评测门禁入库**：`scripts/evals/run_writing_quality.py` + `evals/writing-quality/fixtures/`（protected tokens / 中文数学建模 / claim preservation 三组 fixture，新增 claim-002 负例）+ 重生成结果（smoke / chinese-math-modeling / claim-preservation）；新增 7 项回归测试（`tests/test_writing_quality_eval.py` 等）。
- **插件空间同步 1.7.0**：缓存由仓库 git 清单重建（新增 28 项模块文件），旧 1.6.0 归档 `plugin-backup-20260904-003431`，`installed_plugins.json` / `known_marketplaces.json` / 缓存 marketplace 注册同步；用户级 116 个组件副本清理（备份 `.mm-plugin-only-backup-20260904-004025`），self_check / lint_contracts / plugin_registry_check 三门禁全绿。

### Changed

- **组件合并（去冗余）**：`academic-humanizer` 备用子集物理并入 `academic-humanize` —— 英文规则引擎 `academic_humanizer.py` 迁至 `skills/academic-humanize/src/`，humanize.md / orchestrator.md / 能力盘点.md / 优化文档引用同步，lint `check_component_counts` 计数 35→34，回归测试路径指向新位置（`tests/test_academic_humanizer_regressions.py`）。
- **状态引擎上移共享层（模块独立化）**：`state_utils.py` + 全部 state_* 兄弟模块 + `registry.json` 自 `skills/mm-iteration-engine/scripts/` 迁至 `shared/state-engine/`；旧路径保留转发垫片（CLI 与 import 双模式兼容），lint 路径契约、6 个命令、主控/引擎 SKILL、SSOT 文档与 8 个测试文件全部指向新路径；脚手架从共享层复制运行模块（烟测验证 init 完整复制 15 模块 + 生成 registry）。
- **模块独立调用契约**：新增 `tests/test_module_standalone.py`（registry N1-N8 每节点 executor/reviewer/required_skills/门禁可解析、registry↔NODES 双份一致、状态引擎独立加载、旧路径垫片解析一致、5 个曾耦合技能不再引用私有引擎目录）；`mathematical-modeling` / `mm-algorithm-dev` / `mm-problem-analysis` / `sync-and-compatibility` / `mm-iteration-engine` 5 个技能的内部路径引用全部改为共享层或项目 `state/` 产物声明。

### Performance（写作全链路提效，门禁语义不变）

- **编译产物复用**：新增 `skills/latex-guard/scripts/latex_compile_check.py`——源集（.tex/.bib 全量）sha256 判重，`NO_RECOMPILE` 直接复用上次 PDF，`NEEDS_RECOMPILE` 才执行标准编译；latex_linter 每轮验证、typesetting 排版后与反向复核不再对未变更源反复全量重编译（任何源字节变化必然触发重编译，门禁语义不变）；`tests/test_latex_compile_check.py` 7 项哈希判重语义回归（纯 `--check`，无需 LaTeX 环境）。
- **去AI化双档执行**：N7 每轮修订后仅轻量 `compute_ai_score()` 评分；36 模式全量检测 + C1-C7 + GitHub 语料对照只在 N8 前专项执行一次（humanize.md / academic-humanize SKILL.md / 技能加载文档同步双档原则）。
- **join-review 输入瘦身**：跨章节结构载体（目录/标题树/摘要/引用表）全文读取，仅本轮有变更章节读全文，未变更章节按 scope 证据断言核验（reviewer.md join 模式细化）。
- **校验规则单一事实源**：52 项 LaTeX 排版质量清单抽为 `shared/contracts/latex_quality_rules.md`（重编号连续，修复旧表 #42/#43/#46 重复编号断裂、实为 52 项的口径错误）；latex_linter.md 内联 47 行表改为指针，清理 "46 项" 散布表述。

### CI（回归保护全量接线）

- **pytest manifest 接入 CI**：`contracts.yml` 新增 `pytest-manifest` job—— `check_ci_pytest_manifest.py` 漂移守卫 + `run_ci_pytest_manifest.py` 全量 177 套件 + `run_writing_quality.py` 写作质量离线门禁；修复清单头注释对从未存在的 `spec-consistency.yml` 的死引用（改为实际消费者 contracts.yml）。
- **孤儿测试政策落地（#156 闭合）**：2026-09-04 清理后遗留的 30 个未接线测试逐个判定——20 个在本仓库可接线者已入清单（id 前缀 `orphan-wire-`）；10 个排除并内联注明原因（7 个为 ARS 上游内部主题未随融合迁入，3 个依赖 ruamel.yaml/真实网络客户端）。
- **evals/README 死链修正**：删除对不存在的 `.github/workflows/eval-harness.yml` 的接线描述（写作质量门禁为实际 CI 接线；ranking-lift 链为本地按需门禁），并如实标注 gold-set 校验未接入 CI。

### Fixed / Chore（残余修复）

- **audit_artifact 形态校验（Phase 6.3 落地）**：`_load_passport_audit_artifacts` 对"`audit_artifact` 存在但不是列表"从静默强转 `[]` 改为抛 `ValueError` 判 malformed（生命周期所有权 §3.7 E2），CLI 退出码 2 并带详情；缺键与顶层非 dict 仍按合法空集处理；新增对应回归用例（`scripts/test__next_verified_at_ms.py`）。
- **.gitignore 固化**：`state/` 锚定为 `/state/`（消除与已跟踪 `templates/state/`、`examples/pi/state/` 的静默忽略冲突），补 `.pytest_cache/`、`*.old`、`*_backup`、`*~`。
- **文档口径漂移清账**：`docs/冒烟验证报告.md`（agents 21→24、Skill 分组口径 11+23=34 与 lint 断言一致）；`README.md` / `commands/mm-help.md` 的 "35 Skill" 与过期单测计数（62 项）修正为 34 与全量测试口径；`重叠合并清单` 头部追加 1.8.0 合并执行记录。

### Removed

- **零引用/死资产清理**：删除 `legacy/check_re_review_synthesis_v1_0.py`（2215 行，现行版已存在）、`validate_compliance_fixtures.py`（配套测试已删）、`distill/` 管线（extract_assets/ingest_corpus/distill_report）、`evals/run_benchmark.py` 及陈旧产物 `evals/results/smoke.json`、`tools/release-discipline/`（README 声称的 GHA workflows 不存在，3 脚本仅 README 引用）。
- **gstack 死依赖剥离**：`make-pdf`/`investigate` 剥离不存在的 `~/.claude/skills/gstack/*` 前置、遥测与制品同步机械层，删除无生成器的 `SKILL.md.tmpl` 死副本与 make-pdf 不可构建的 TS 源码/测试（技能本体保留，gstack 缺失时走便携回退或降级说明）。
- **开发日志归位**：`skills/metrics-analysis/交接记录/2026-05-15_Skill创建记录.md` 移至 `docs/`；本机未跟踪残留（`.cloudstudio`、空 `prompts/candidates|releases`）清理。

## [1.7.0] - 2026-09-03

### Added

- **融合 math-modeling-skill-pro Pro 知识库（作者授权，协同迭代演进）**：
  - 案例库全量迁入 `skills/mathematical-modeling/assets/case-library/`：139 张 CUMCM 优秀论文案例卡（2012—2025）+ `index.json/csv/md` + 案例卡模板 + `corpus-provenance.md` 证据边界声明；139 卡 body_sha256 逐一校验通过、card_path 与索引对齐、无越界/绝对路径。
  - 12 份决策规则按流程模块映射（不游离主流程）：`mm-problem-analysis`（题型诊断/子问题依赖）、`mm-model-library`（A/B/C 三方案选型/模型卡/组合模式）、`mm-data-preprocessing`（数据工作流/泄漏防护）、`mm-model-tuning`（四层验证/敏感性/稳健性）、`mm-latex-writing`（创新点/论文证据表达）、`mm-algorithm-dev`（8 类代码骨架）。
  - 各目标技能 SKILL.md 追加 `Pro 知识库融合（v1.7.0）` 小节：资产位置、使用时机、与既有流程关系、回退规则；现有章节内容零修改。
  - 新增 `state_utils.py case-search`：139 卡结构化检索（中文二字片段 + 别名扩展 + TF-IDF 加权，问题类型/模型标签加权），支持 `--top/--year/--type/--model/--json/--skill-root/--save`；`--save` 将命中卡沉淀进 `state/cases/`（source_type=pro-case-library）供派发携带；案例库定位 fail-closed（`--skill-root` → `MM_SKILL_ROOT` → 向上探测，缺失报错不静默降级）。检索核心为纯函数模块 `case_search_lib.py`（随脚手架复制进项目 state/）。
  - 主控 `mathematical-modeling` SKILL 新增 Phase 1 案例检索闭环（N1 必做）：按「问题结构/数据结构/数学结构」分次检索 → 读 transferable_patterns → `--save` 沉淀 → 案例证据边界约束（阈值/权重/题目专属机制不可迁移；OCR 未核验内容不视为已核验；频次不作优越性证明）。
  - 新增 `scripts/check_case_library_integrity.py`（139 卡完整/索引一致/哈希核对/无越界路径）与 `tests/test_case_search.py`（切分/别名/加权排序/定位/--save/fail-closed），接入 CI manifest。

### Changed

- **版本同步 1.6.0 → 1.7.0**：pyproject、三份 plugin.json、根 marketplace.json（顺带修复 description 仍写 1.5.0/34 Skill 的漂移）、`state_scaffold` skill_version、mathematical-modeling/mm-iteration-engine SKILL metadata、mm-help、README、CHANGELOG 全部对齐。
- 组件口径不变：24 Agent / 35 Skill / 22 命令（案例库为主控技能 assets 资产，不新增组件计数）。

## [1.6.0] - 2026-08-20

### Added

- **mm-pdf-vision（PDF 视觉逐页阅读与格式核查）**：
  - 新增技能 `mm-pdf-vision`：具备视觉能力时将 PDF 渲染为分页图片并逐页阅读，核查 页序/页码页脚居中/正文从 PDF 第4页起≤30 页/摘要≤1 页/无目录/图表位置与图-文-数据一致/乱码/身份信息；无视觉能力时生成人工核查请求单并置门禁 `PENDING`（不假装已读图）。
  - 新增 `scripts/pdf_render_pages.py`：PDF 分页渲染为 `page-*.png` + manifest（源 SHA-256/页数/引擎/dpi/图片清单）；引擎自动探测 `pdftoppm → mutool → PyMuPDF → gs`，全部缺失输出 `TOOL_BLOCKED`；`--engine fake` 供测试。
  - 接入 `latex_linter`（编译后 PDF 视觉核查）、`reviewer`（join-review 终检）、`mm-viz-reviewer`（版面/位置核对）、`mm-latex-writing`（格式修订后视觉自查）、`orchestrator`（Phase 8 视觉终检 + 全系统地图）。
  - 技能计数 34→35：lint/plugin_registry/self_check/三份 manifest/README/mm-help 同步；缓存 1.6.0 与 installed 注册同步（旧 1.5.0 已归档）。
  - 新增 `tests/test_pdf_render_pages.py`（fake 引擎渲染/manifest/缺文件失败/技能结构与脚本引用）。

### Changed

- **版本同步 1.5.0 → 1.6.0**：pyproject、三份 plugin.json、mathematical-modeling/mm-iteration-engine SKILL、state_scaffold `skill_version`、templates/decision_log、缓存级 marketplace、installed 注册（source/installPath/version）全部对齐；本机插件缓存 1.6.0 由仓库重建并保留 `.mcp.json`/Tavily 密钥配置。
- 1.5.0 变更记录保留为历史版本，不滚动合并。

## [1.5.0] - 2026-08-19

### 系统性审计与发行链路修复（2026-08-20）

- **命令/frontmatter 契约**：6 个 MM 命令补齐 `name: <filename stem>`，命令 checker 已能通过 22 个命令；humanizer Skill description 改为合法 YAML；active 组件数量统一为 24 Agent / 34 Skill / 22 Command。
- **运行环境口径**：最低 Python 版本提升至 3.11，与脚本实际使用的 `tomllib`、PEP 604 注解、`datetime.UTC` 及 CI matrix 对齐；dev extra 增加 PyYAML/jsonschema，academic-humanizer 依赖单列为可选 extra。
- **构建虚拟环境门禁**：新增只读 `scripts/venv_guard.py`，构建/运行/数据处理/绘图前必须确认项目 `.venv`/`venv` 存在、已激活且当前解释器来自项目环境；不满足输出 `VENV_BLOCKED`，禁止用系统 Python 绕过；新增 `tests/test_venv_guard.py`。
- **脚手架 provenance**：DataLog 与 figure-list 模板增加 `data_class/source_ref/citation_ref/accessed_at/sample_size/seed/reproducibility_ref` 字段；缺失值处理改为按变量类型/缺失机制/样本影响的证据驱动策略，不再“低于 5% 直接删行”。
- **Hook/MCP 安全边界**：SessionStart 移除自动用户级同步；MCP 模板使用宿主支持的 `env` 字段；本机明文 MCP 配置继续保持 gitignored，未复制或打印密钥。
- **MCP 证据门禁**：N6 纳入 mandatory map；核心节点留痕要求节点/轮次/查询/时间戳/结果或卡片证据，并按 MCP 类别校验，避免无关 case 或伪造记录满足 PASS。
- **academic-humanizer**：保留为兼容 wrapper，canonical 工作流仍由 `academic-humanize`/humanize Agent 负责；修复 namespace 作为 Python import 的错误示例，禁止模块 import 时自动下载 spaCy 模型。
- **已知外部状态**：本机 installed plugin source path/cache 内容仍需重新安装/刷新以对齐 1.5.0；`~/.agents` 仍有用户级组件残留；审计不自动清理这些用户目录，不打印任何密钥。

### Hotfix（2026-08-20）：普通对话路由守则——修复主对话内联代做论文

基于一次真实对话复盘发现的问题：用户在普通对话中提出"审阅并修改论文"，模型自己读文件 → 加载 `mm-latex-writing` skill → 直接内联改 .tex（13 处修复），全程未派发 `writing`/`reviewer`/`latex_linter` 子代理、未走 state 节点协议、未编译验证——违规内联代做。根因四个环环相扣：① 标准循环指令只存在于被隐藏的流程文档（orchestrator/迭代引擎/mm.md），普通对话不触发 /mm 即不可见；② 全部子代理为 `hidden: true`，主对话没有任何"何时该派发"的规则；③ `mm-latex-writing` 等执行类技能全是规范、零编排指令，且 Quick Start 主动引导主对话自己加载自己干；④ mm.md 路由表未覆盖"审阅并修改论文/润色/修格式"这类复合意图。

- **SessionStart 路由守则注入**：新增 `scripts/announce-mm-routing.sh` 并注册进 `hooks/hooks.json`（SessionStart，ZCode/Claude Code 通用）——会话启动即在首轮向主对话注入 MM 路由守则：收到论文写作/修改/润色/审阅/质检请求 → 判定为 N7 节点 → 派发 `writing` 子代理（加载 mm-latex-writing）→ `reviewer` 审阅 → `latex_linter` 质检 + 编译验证 → `humanize` 去 AI 化 → 通过才交付；明示"子代理与技能不可混用、主对话内联代写 = 违规"。
- **执行类技能加载资格声明**：`mm-latex-writing`/`mm-self-review`/`latex-guard`/`humanizer`/`academic-humanize`/`mm-visualization` 六个 SKILL.md 头部新增"🔴 加载资格与委托守则"块——声明本技能仅供对应子代理（writing/reviewer/latex_linter/humanize/visualization）加载，主对话直接加载内联改产物 = 违规，并指明正确委托路径。技能本身现在拒绝被主对话误用。
- **Agent 触发词补全**：`orchestrator`（论文修改/审阅修改/润色/接手/迭代）、`writing`（修改论文/论文修改/润色/修订）、`reviewer`（审阅修改/论文修改审阅/修改后复审）、`latex_linter`（论文质检/格式检查/排版检查/编译验证）、`humanize`（论文去AI/AI味/机械感）。
- **/mm 路由表补复合意图**：`commands/mm.md` 新增"审阅/修改/润色/质检/格式检查已有论文（普通对话未走 /mm 同样适用）"条目，明确 N7 闭环五步与禁止内联。
- **验证**：`lint_contracts.py` 契约零报错、`self_check.py` 全健康、hooks.json JSON 合法、新脚本 git-bash 下输出合法 SessionStart 载荷（含子代理名完整）。

### 分片审阅与阶段先后（2026-08-20）

针对“整篇论文一次性审阅导致上下文稀释、章节问题漏检、内容排版互相污染、Agent 空返回反复等待”的实测问题，把 N4/N5/N7/N8 升级为可选 scope 分片工作流：

- **scope 状态模块 `scripts/state_scopes.py`**：自适应分片（N7 按章节、超长模型章节按子问题/小节，使用 `\input/\include`、`\subsection/\subsubsection` 和源文件行段做确定性切分；N4/N5 按 question_1~4）；每个 scope 落在 `state/reviews/<node>/round_<n>/<scope_id>/`，生成 `review_workspace_manifest.json`（含 `schema_version`、scope_id、父节点/轮次、UTC 时间戳、registry/输入/base 哈希、`context_budget`、`excluded_full_document`、phase_status）+ `input_manifest.json` + `handoff.md` + `dispatch/aggregate` 计划。
- **CLI**：新增 `scope-plan`（`--mode adaptive|static`、`--target`、`--scope-id`、`--scope-kind`、`--apply` 兼容统一路由）、`scope-aggregate`（缺阶段即 BLOCKED）、`scope-promote`（全部 scope+join 通过才完成父节点）；`round-start/score/decide`、`node-review`、`report-list`、`save_round_report` 支持可选 scope，未传 `--scope-id` 时保持 legacy 行为；scoped `round-decide` 不推进父节点。
- **阶段顺序门禁**：`update_scope_phase` 按 `PAPER_PHASES`（content->format->compile->join）对已完成阶段做前置校验，防止 typesetting 在内容复审前写入共享 .tex；N4/N5 使用 COMMON_PHASES 不引入 FORMAT 阶段。
- **空返回门禁**：`resilience.py` 新增 `EmptyResultError`、`retry_with_nonempty`（空白/空值/校验失败即时重试）；`state_scopes.record_empty_return` 写 `recovery.json` 并置该 scope BLOCKED。策略=只读审阅并行、内容/算法写入串行、内容先于排版、排版后重构建→反向复审→join review→promote。
- **Agent/Skill 同步**：orchestrator/writing/reviewer/latex_linter/typesetting/coder/tuner 的 scope 与阶段规则；`mm-iteration-engine` §5.4 分片协议、`mm-latex-writing` 分片写作、`mm-self-review` 4.16-4.18/5.9-5.10、`agent-collaboration-loop.md` N7 scope 单一事实源；`mm.md/mm-iterate/mm-help` 增加“按第几问/某章/某节”路由。
- **验证**：`tests/test_scoped_workflow.py` 9 例（自适应拆分/spope 隔离/路径穿越/阶段阻断/父节点不越级/空返回）+ 已注册进 `scripts/_ci_pytest_manifest.toml`；`test_workflow_contracts.py` 42 例回归通过；`lint_contracts.py` 与 `self_check.py` 全绿。
- **脚手架门面复制修复（既有缺陷）**：`init` 复制 `state/state_utils.py` 时错用 `__file__`（指向 state_scaffold.py），导致项目内 CLI 缺 `round-*`/`node-*`/`scope-*` 等命令分发；改为显式复制同目录门面 `state_utils.py` 后，项目内 `scope-plan` 等命令可用（复验 scopes 生成 + workspace manifest 存在）。

### 数据来源标注 + 可视化前置链（2026-08-20）

把网络检索整理的四类数据来源判定与“先模型/数据、后画图”规则固化为可执行门禁：

- **数据来源四类判定**：赛题自带（不标来源、不冒充外部数据）/ 外部公开（图注或表注注明机构/数据集/日期或访问时间、正文引用、GB/T 7714 著录、原始数据进支撑材料）/ 代码仿真或模型输出（明确“本文模型计算/仿真得到”、附录带代码与 seed、不进参考文献）/ 问卷与实地调研（标注时间、方式、样本量）；禁止“来源于网络”与内部路径（Code/output、*.txt/*.xlsx/*.log）进论文题注或正文。
- **可视化三步前置链**：①结合实际需求、模型与数据形成可视化需求清单；②调用论文搜索 MCP + Tavily/WebSearch（不确定绘图库 API 时补 Context7）检索学术方案、沉淀卡片与留痕；③确定图形类型与方案后才绘图；`mm-visualization`、visualization Agent、dataprep 的数据分类、`mm-viz-reviewer` 的 V1 前置门禁、`mcp/call-hierarchy.md` 第六行与 `mcp/cluster-roles.md` §5、`mcp/validation-checkpoints.md` N6 检查、`mm-latex-writing` 数据来源章、`mm-self-review` 3.9-3.10/4.18 已同步。

### 论文排版与表达修复规则（2026-08-20）

- 模型缺点/改进方向写成连贯段落（论点+依据+影响），禁止“序号+单句”列表（mm-latex-writing、writing.md 第 8 章、self-review 维度四、latex_linter 第 41 项）。
- 图题=“图N 对象+内容”一行以内、不含数据来源/路径/方法/流程箭头复述；表注放 table 环境内 `\end{tabular}` 后随表浮动、左对齐 footnotesize、一行简短、禁内部路径（修复原“环境外”规则与示例自相矛盾，latex_linter 第 21 项与 self-review 5.8 同步）。
- 图表不得漂移到所属章节标题之前且不早于首次引用；符号表不得出现在“符号说明”标题前（mm-latex-writing 防漂移章、latex_linter 第 44 项、self-review 5.9）。
- Anti-Patterns 扩至 34 项并清除游离表格行；格式问题修复流程（逐条定位→最小修改→重编译→latex_linter 复检→reviewer 复审）写入 mm-latex-writing。

### 注释精简 · 页码居中 · 外部过程零进入（2026-08-20 二轮）

针对“表注/图注机械重复啰嗦、图表与引导文本位置漂移、页码未居中、外部迭代/版本语言混入正文”的实测问题补全：

- **表注/图注“少而精”**：同源数据仅在首次或正文统一说明一次，后续同源图表不再逐表/逐图重复；禁止“完整代码见附件、按式(x)复核、逐条明细见独立附件、不在本文重复、详见提交包”等重复/内务/复现话术；注释只写该表/图本身未体现且必要的信息（单位、缩写、显著性），多数图表可无来源字样。写入 mm-latex-writing「注释精简与去内务话术」、writing.md、mm-visualization、mm-viz-reviewer。
- **表格行按实际数据组织**：每行对应一个真实数据实体（测线/阈值/方案等），禁止为凑对齐补空行/虚行或机械同列数（mm-latex-writing、self-review 5.12、latex_linter 第 44 项）。
- **页码居中**：页脚中部阿拉伯数字、摘要页起编号、承诺书/编号页不编号；typesetting 排版目标 + latex_linter 第 42 项 + self-review 5.11；模板 `\fancyfoot[C]{\thepage}` 已在脚手架。
- **图表不远离首次引用文段**：编译后逐页核对，图表应在引导句所在页或相邻页；被推离两页以上时收紧浮动参数或加 `\FloatBarrier`（mm-latex-writing 防漂移章、latex_linter 第 46 项、self-review 5.9、typesetting）。
- **外部/内部过程语言零进入**：迭代轮数、版本、"与上一版本相比"、修改前后对比及内部对比表不得进入论文正文/题注/表注；内部记录只在 `state/reports/`、`state/reviews/` 与 git（mm-latex-writing、writing.md、reviewer 第③条、latex_linter 第 45 项、self-review 4.20）。
- **校验**：latex_linter 清单 40→46 项（新增 42 页码居中 / 43 注释精简去重复 / 44 行按数据 / 45 外部过程语言零出现 / 46 图表不远离引用文段）；Anti-Patterns 34→38；「格式问题修订流程」检查编号引用同步校正。
- **验证**：`lint_contracts.py`、`self_check.py` 全绿；`tests/test_scoped_workflow.py` 9 例、`tests/test_workflow_contracts.py` 42 例回归通过。

### 图-文-数据三方一致性核验（2026-08-20 三轮）

针对“图 5 标注为 seed42 完整收敛（K=150、重启 k=41/81），但横轴只画到 10、无重启标记、曲线平直、正文描述与图不符”的实测脱钩问题，把“图必须严格按算法实际输出绘制 + 终检三方一致”固化为绘图与审阅门禁：

- **mm-visualization「图-文-数据三方一致性自检」（每图必做）**：坐标轴范围 = 数据/正文声称范围（正文 K=150 → 横轴 0~150；只展示前 10 代必须标注"前 N 代/局部"并删除冲突表述）；关键事件标记（重启点 k=41/81、阈值、切换点）存在且位置正确；曲线形态符合算法预期（收敛曲线应下降，平直/贴 0 须核对是否仅局部片段或读错数据）；图例项数=曲线数且与正文术语一致；点/行数与输出文件一致。自检结果随图写入 `figure-list.md` 与 scope evidence。
- **visualization.md 必守第 11 条 + Phase 2.5**：读输出完整记录绘图、禁估算/手写/头部片段冒充完整、禁先画图再倒推数据；自检不过先重绘再交 V1。
- **mm-viz-reviewer V1 门禁新增 17-20 项**：坐标轴范围 / 事件标记 / 图例-曲线-正文一致 / 曲线形态与点行数；Phase 2.0 新增"图由实际输出完整记录绘制"前置；IRON RULE 7 与反例 6、失败模式补"片段图冒充完整轨迹 → FAIL → visualization 按实际输出重绘后复审"；核对清单 16→20 项。
- **评分与终审**：mm-self-review 维度三新增 3.11（图-文-数据三方一致）；reviewer 数据支撑新增 join 必查项；writing 数据一致性补 2b（正文参数必须与图内容及输出一致）。
- **验证**：既有测试 42+9 仍全通过（本内容级更新不触发状态协议变更）；`lint_contracts.py`/`self_check.py` 全绿。

### Added（ARS 学术研究融合 + MCP 四类内嵌常驻集成）

- **Academic Research Skills（ARS v3.21.0）全量融合**：移除 vendor 子目录 `academic-research-skills/`，四技能树平铺进 `skills/`（academic-paper 63 文件 / academic-paper-reviewer 28 / academic-pipeline 30 / deep-research 53，deep-research 由 2.9.4 升级至 2.12.1）；ARS 基础设施迁入主仓根并保持相对路径几何不变：`shared/`（参考语料/契约/任务原则清单）、`scripts/`（文献客户端 crossref/openalex/semantic_scholar/arxiv/chinese_literature + 200+ 校验脚本）、`docs/`（design/migration 等）、`agents/`（report_compiler / research_architect / synthesis）、`commands/`（ars-* 17 个）、`examples/`、`evals/`、`audits/`、`hooks/`、`pi/`、`tools/`；ARS 根文档收拢（MODE_REGISTRY / POSITIONING / QUICKSTART / GOVERNANCE / NOTICE / THIRD_PARTY / CITATION / LICENSE-ARS / README 多语言），无文件名冲突。
- **MCP 集成层（`mcp/` 模块，10 文件）**：Checkpoint 0 启动协议（全局MCP扫描→筛选四类→内嵌确认→自检→放行，顺序不可逆）+ 实测扫描结果 + 四类分工（论文搜索/Context7/GitHub 官方 API MCP/Tavily·tokenhub-tools 回退）+ 调用层级（常规灵活/核心节点强制必调 5 节点表）+ 四类闭环校验 + Tavily 双密钥轮换配置 + 知识卡片模板 + GB/T 7714 台账模板。
- **MCP 自检脚本 `scripts/mcp_boot_check.py`**：扫描真实 MCP 配置→分类自检（注册/联网/密钥/内嵌载体）→门禁判定 `MCP_READY / MCP_BLOCKED`；附 `--coverage`（五节点必调覆盖）与 `--ledger`（GB/T 7714 台账校验）。
- **接线**：新命令 `/mm-boot`；`/mm` 第 0 步 MCP 启动门禁；orchestrator 新增 MCP 集成铁律（含 IRON RULE 13/14）；selector/modeler/coder/tuner/writing 五个核心节点 Agent 新增"🔴 MCP 必调"条目；reviewer 新增 N8 MCP 闭环终检；literature/researcher 增补 MCP 检索与归档指引；主控 SKILL 新增执行铁律 11 与 Quick Start 第 0 步。
- 版本：pyproject 1.4.8 → 1.5.0；主控 SKILL 1.4.8 → 1.5.0。

### Fixed & Refined（全面优化整改补记，2026-08-19）

- **契约一致性收口**：全组件版本统一 1.5.0（mm-iteration-engine SKILL / state_utils 脚手架 / templates/state/decision_log.json / 三份 plugin.json）；lint 数量断言 21/34/5 → **24/34/22**；README / 能力盘点 / 冒烟报告 / orchestrator 口径同步；mm-viz-reviewer 核对口径统一 16 项；`scripts/lint_contracts.py` 零报错。
- **state_utils.py 可维护性重构**：2966 行单文件按领域拆分为 `state_defs / state_scaffold / state_nodes / state_review / state_audit / state_rounds / state_search` + 227 行薄 facade；`init` 自动复制全部兄弟模块进项目 `state/`，命令用法不变，行为零回归。
- **Deep Research 迭代融合（机器强制"禁止纯内生"）**：`round-score`（N4/N5/N7 本轮）与 `node-review`（N1/N3/N4/N5/N7 PASS）前置校验 MCP 检索留痕（`state/reports/mcp-calls.jsonl` / `state/cases/index.json`），缺失拒绝（`--allow-missing-mcp` 显式豁免）；`round-decide` 未达标分支强制 `--reason` 失败原因分析（写入 `decision.failure_analysis` 供下一轮 SEARCH 根因输入）；SCORE 创新/创造性维度先进性核查（无外部基线 ≤6 [NO-BASELINE]）；新增 `search-evidence <Nx>` 检索证据派发清单。
- **知识卡片派发落地**：委派节点前 `search-evidence` 汇总知识卡片/案例/GB/T 7714 台账/MCP 留痕随派发分发给对应 Agent；`mcp/call-hierarchy.md` 统一 `mcp-calls.jsonl` 为唯一机器事实源。
- **/ars-* 嵌入 /mm 体系**：`mathematical-modeling` SKILL 新增"专项命令路由"节（17 命令 × 节点映射）；`/mm-help` 更新为 22 命令全量清单；Integration with Sub-Skills 补 deep-research/academic-paper-reviewer/humanizer 按阶段加载；orchestrator 迭代协议融入 Deep Research + ARS agent 命名映射。
- **路径/材料收口**：SKILL §15 失效路径修正；init 复制循环改为全部 `.py` 模块；材料导入链（detect→organize→material-plan→sync_import）核对。
- **测试**：原 42 例（setUp 种子化检索留痕 + 低分用例补 --reason）+ 新增 `tests/test_mcp_gates.py` 13 例 = **55 例全通过**。
- **9.0 评分漏洞调查与防护**：调查发现 `2023_CUMCM_ProblemB` 项目 9.0 评分由旧版 1.3.0 引擎（旧副本，无前缀 reviewer + 无版本 skills_read）产生——旧引擎无 MCP 必调/知识卡片/executor 证据/H 门禁一致性等新规则，评审对象（中间稿）也早于最终 PDF；`project-audit` 新增三项机器检查：`h_gate_consistency`（completed 但 H 门禁 pending → 未人工确认即收尾）、`engine_legacy`（state 中 `mm-*@<当前版本` → 旧引擎产物、评审结论不可作为有效依据）、`review_timeline`（审阅时间早于最终 main.pdf mtime → 评审对象非最终交付物、必须重评）；新增 `tests/test_audit_gates.py` 6 例（含 auto_passed 待追认态不误报、无 PDF 不误报）；全量 **71 例测试通过 + lint 零报错**；调查报告见 `docs/optimization/9.0评分漏洞调查与防护报告.md`。
- **插件注册链路全面体检与修复（子 Agent 无法启动事故）**：排查发现（a）`installed_plugins.json` 版本记录 1.3.0 与 marketplace/manifest 1.5.0 漂移（8/18 安装后从未更新）；（b）`known_marketplaces.json` 被清空导致市场不可识别；（c）缓存目录存在 `1.5.0/1.3.0` 嵌套结构（版本目录相互嵌套），旧会话注册路径 `1.3.0` 被改名后失效 → 子 Agent 派发时找不到定义文件而启动失败；已修复：五方版本对齐 1.5.0（pyproject/plugin.json×3/SKILL/marketplace/installed/缓存目录/manifest）、恢复 known_marketplaces（含 math-modeling）、清理嵌套目录、按仓库最新内容重组插件缓存（1.3.0 为旧会话兼容副本，与 1.5.0 逐文件哈希一致）；新增一键检查 `scripts/plugin_registry_check.py`（版本五方/缓存-仓库逐文件一致/嵌套检测/frontmatter 合法性/用户级遮蔽/MCP 密钥，FAIL 即退出码 1），并接入 `/mm-boot` 第 0.5 步；全量 **71 例测试通过 + lint 零报错**。
- **论文格式规范深度修订（基于官方规范 + 韩中庚 + 评审指南联网研读）**：针对论文实测发现的格式问题（引用绿色、AI 味段式、评审元语言混入、表注粘连、符号说明复杂、图大小不一、假设影响矩阵、标题乱起等），**写作与检查由两个独立子 Agent 分别完善**——writing 子 Agent 将 13 条权威规范细节并入 `mm-latex-writing/SKILL.md`（新增官方格式规范章节：A4/页序/页码/附录源码/匿名性/电子版；摘要四要素+禁区；假设有效性铁律+禁万能假设；符号首次出现定义；公式间文字衔接；灵敏度数值硬要求；模型评价必须自评优缺点；层次标题排比；图中文字 6 号-小5 号；表单位右上角；Anti-Patterns 20-28）；latex_linter 子 Agent 将质检清单扩至 **40 项**（新增 26-40：页数合规/附录完整性/身份信息/电子版首页/层次标题/图内文字/表单位/先见文字后见图表/摘要规范/结构完整性/假设质量/符号定义/公式衔接/灵敏度数值/参考文献一一对应，含 6 项人工核对标注）；mm-self-review 同步补检查项（4.11-4.13 元语言/AI 味/图表过渡、5.6-5.8 hyperref 颜色/符号精简/表注）；全量 **71 例测试通过 + lint 零报错 + 缓存同步**。
- **新增文档**：`docs/optimization/`（重叠合并清单 / Deep Research 迭代融合报告 / 8 类 BUG 修复报告 / 全组件联动地图）。
- **Agent 协作闭环与 Deep Research 迭代融合统一规格（二次收口）**：
  - 新增单一事实源 **`docs/optimization/agent-collaboration-loop.md`**：9 阶段协作闭环表（每节点上游输入/下游输出/前置检查 [PREREQ-REQUEST]/配对审阅（先加载 Skill）/FAIL≤2 超限 [ESCALATE]）+ Deep Research 嵌入点清单（全阶段 + N4/N5/N7 每轮调用时机/输入/输出）+ 迭代环融合方案（SEARCH 根因+方案论证、SCORE 先进性核查、DECIDE 失败原因+下轮方向）；orchestrator / 主控 SKILL / mm-iteration-engine SKILL 均引用之。
  - **DR 链固化**：`research_architect→literature→researcher→synthesis→report_compiler` 定义为数学建模每轮介入链（技术瓶颈→检索方案；需论证→查文献；需系统梳理→全链深度调研），orchestrator 新增 §3.1。
  - **可审计留痕命令**：新增 `dr-note <Nx> [--round N] --phase SEARCH/SCORE/DECIDE/NODE --role ...`（落 `state/reports/dr-interventions.jsonl` 并同步 `rounds[n].deep_research`）与 `dr-list` 查询；N8 终检可核对"每轮有据介入"。
  - 测试增至 **62**（新增 `tests/test_dr_intervention.py` 7 条：留痕落盘/轮次同步/按轮过滤/非法节点拒绝/规格一致性）。

### 专项 3/4/5/6 收口（2026-08-19 后补）

- **专项 3 · MCP 检索卡片体系**：新增 `docs/optimization/mcp-检索卡片体系.md`（Checkpoint 0 门禁流程 / 五节点必调映射含迭代每轮要求 / 卡片沉淀规范 / 写作·修改·审阅三场景分发规则 / N8 终检清单）；`rounds[n].knowledge_cards`（`{节点}_r{轮}_*.md` 命名，round-score 自动采集）实现"轮次→卡片"传递，N8 可核对"迭代每轮有新检索"；新增 3 条卡片追踪测试。
- **专项 4 · Skill 组合加载与命令路由**：新增 `docs/optimization/skill组合加载与命令路由.md`（Skill 阶段组合加载表 + mm- 阶段衔接产物链 + 22 命令统一路由表 + boot→init→mm→audit/iterate→ars-*/DR 衔接链 + 闲置补全）。
- **专项 5 · 8 类 BUG 排查**：新增 `docs/optimization/专项5-BUG排查修复表.md`；实测结论 lint 0 + self_check 全健康 + 65 测试全过 + 仓库内引用断链 0 处；handoff 归属明确分域（shared/handoff_schemas.md=ARS 学术契约，数学建模环节交接=write_handoff 按迭代引擎 §3.4）。
- **专项 6 · 验收与联动地图**：`full 组件联动地图.md` 补专项验收索引 + knowledge_cards 字段 + §7 专项验收清单核对表（9 项全过）；测试总计 **65**（62 + 3 轮次卡片）。

### 插件独占强化与资源防护（2026-08-19 后补）

- **插件独占模式（`` 前缀）**：仓库根新增 `.plugin-only` 标志。流程中全部 `skill()` / `subagent_type` / registry / NODES required_skills 引用改用插件前缀名（内部标识 executor/reviewer/状态目录保持无前缀，Windows 路径安全）；tests 传参同步；lint `check_full_pipeline_coverage` 支持前缀→目录映射；`check_user_level_sync` 在独占模式下改为"用户级不得残留本仓库组件"门禁。
- **用户级副本清理**：`sync_user_level.py --plugin-only`（备份后删除用户级本仓库 34 skills/24 agents/22 commands）；同步模式在独占模式下被拒绝（防误操作把旧副本复制回去）；self_check 适配独占模式（残留检查 + 插件缓存版本动态化）；README 明确"插件 vs 用户级同步"互斥。
- **资源防护（防"大 Agent 占用巨量资源"复发）**：新增 `scripts/env_health_check.py`（检查 `~/.zcode/cli/exec` 会话日志膨胀/Temp 残留/磁盘余量，`--clean` 自动清理历史会话日志与残留）；`/mm-boot` 第 0 步接入健康检查；`sync_user_level.py` 的 `tree()` 轻量化（大小快通道，仅大小相同文件做内容哈希，降低 lint 全量 IO）。
- 实测：`~/.zcode/cli/exec` 13GB → 1MB；lint 零报错；**65 单测全通过**。

## [1.4.8] - 2026-08-19

### Added（接手复核：已完成 ≠ 跳过）

- **handover-review 接手复核命令**：`state_utils.py handover-review`——加载/完整阅读已有项目后必跑：按 9 阶段逐节点检查（completed → 复核；in_progress → 补完审阅-修改循环；pending → 待执行）；**completed 节点不直接信任**：门禁未过或产物哈希漂移（与 node-finish 登记不一致）→ 强制复核（审阅→修改→再审阅）；门禁已过无漂移 → 仍须"复核确认"（配对审阅 Agent 快速审阅，发现问题进修改循环）。
- **主控 SKILL 接手复核协议**：加载已有项目必须"逐节点检查 → completed 强制复核 → 同步修改（cascade-invalidate --apply 联动下游）→ project-audit 复检 → 继续推进"。
- **/mm 接手路径强化**：`project-audit → project-repair → 材料复用 → handover-review 接手复核 → cascade-invalidate → 复检 → 继续`。
- 测试增至 42 项（completed 未审阅强制复核、审阅 PASS 复核确认、产物漂移强制复核）。

## [1.4.7] - 2026-08-19

### Added（逻辑链路缜密性修复 + 专业任务-专业 Agent-专业 skill 三角绑定）

- **门禁落盘路径断链修复（A1/A2/W1）**：审阅发现 A1/A2/W1 只有初始化、无任何落盘路径（永远 pending，与文档"P2+A1 通过""W1+A2+W2 通过"矛盾）。修复：
  - A1（N4 代码反模式）：round-score N4 达标（total≥pass）自动 PASS；
  - A2（N7 写作反模式）：round-score N7 达标（total≥pass）自动 PASS；
  - W1（N7 写作前置支撑）：node-start N7 时上游 V1 已过 → 自动 PASS；
  - §6.3 门禁定义表补"落盘路径"列（12 个静态门禁 + 动态 S\<n\>-Nx 全部有机器落盘路径）。
- **round-score 五维键名校验**：code 环仅允许 correctness/efficiency/readability/robustness/innovation，paper 环仅允许 假设合理性/建模创造性/结果正确性/表述清晰性/格式规范性；未知键名拒绝（防乱写维度/评分口径漂移）。
- **专业 skill 调用契约（lint check_professional_skill_contract）**：每个节点 required_skills 中的每个 skill 必须在其**执行 Agent 与审阅 Agent 文件**中被引用（skill 加载指令/声明）——审计确认 8 执行 + 8 审阅全部全引用，固化为契约防回归（"专业任务 → 专业子 Agent → 专业 skill"三角绑定）。
- 测试增至 41 项（round-score 非法键名拒绝、A1 达标自动落盘、W1 开工自动落盘；迭代节点 N5 流程按新门禁校验补全）。

## [1.4.6] - 2026-08-19

### Added（阶段联动强化 + 阶段交接文件）

- **node-start 上游审阅门禁校验（防"阶段不完全/修改不完善就推进下一步"）**：开工下游前除校验上游 completed + 产物存在外，**新增校验上游审阅门禁 PASS/auto_passed/confirmed**（M1/D1/P1/P2/T1/V1/W2）——上游未审阅或审阅 FAIL 时拒绝开工并提示"必须先完成'审阅→修改→再审阅'循环（PASS）再开工"。实测验证：N1 未审阅 → N2 node-start 被拦截；审阅 PASS 后放行。
- **audit 新增 premature_progression 检测**：任何已推进节点（in_progress/review_pending/completed）的上游未 completed 或审阅门禁未过 → 报告"阶段不完全即推进（上游未完成/未审阅）"——拦截绕过 node-start 校验的手工改状态。
- **阶段交接文件（handoff）**：新命令 `state_utils.py handoff <Nx>` 生成/刷新 `state/nodes/<名称>/handoff.md`（node-start 自动刷新）——内容：本阶段信息（执行/审阅 Agent、必读 skill、产物、门禁）、**上游交接表**（状态/门禁/产物路径+sha256 前 12 位）、输入输出约定、待办与小步骤入口、**就绪判定**（ready/blocked + 处理建议）。单独拉出任何阶段前先读 handoff 自检，blocked 则先补上游（或输出 PREREQ-REQUEST）——保证"某些阶段单独拉出来也能正常进行"。
- **文档**：mm-iteration-engine §3.4 阶段交接文件规范（作用/内容/阶段联动铁律）+ §13 命令速查；主控 SKILL 执行铁律 10（阶段联动与交接）。
- 测试增至 39 项（node-start 门禁拦截 + handoff 生成与内容断言 + audit premature 检测；既有 2 项测试按新协议补审阅 PASS 步骤）。

## [1.4.5] - 2026-08-19

### Added（审阅-修改-再审阅循环：所有任务统一执行路径）

- **通用循环协议（mm-iteration-engine §5.3）**：明确"① 调用配对独立审阅子 Agent（先读 skill）→ ② PASS 落门禁完成 / FAIL（附 evidence）→ ③ 调用对应修改 Agent（=执行 Agent）加载本节点 skill 按 feedback 逐条修改 → ④ 再审阅往复（≤2 次硬上限，空修改打回，超限 BLOCKED/ESCALATE）"为**唯一合法路径**，适用于单项任务、阶段任务（迭代环每轮）、整体系列任务（每阶段完成各自循环后进入下一阶段）；附每节点"审阅 Agent / 修改 Agent / 修改时必加载 skill"对照表与 5 条禁止事项。
- **audit 检测"未审阅即完成"（unreviewed_completion）**：节点 completed 但对应门禁（M1/D1/P1/P2/T1/V1/W2/A3）非 PASS/auto_passed/confirmed → 报告"疑似跳过审阅-修改循环"——堵住"执行完直接标完成、不审阅"的最大漏洞。
- **review-loop 升级**：输出从"审阅/返修"改为完整"review → modify（含 modify_agent = 执行 Agent、modify_skills = 本节点必读 skill）→ re_review"往复序列 + protocol 字段；字段 max_repair_attempts → max_modify_attempts。
- **主控 SKILL 铁律 9 + orchestrator 阶段转换规则 5**：把审阅-修改-再审阅循环写死为唯一合法路径（禁止不审阅直接完成、禁止 FAIL 不改直接放行、禁止修改不加载 skill）。
- 测试增至 37 项（未审阅即完成被 audit 检测、补审阅 PASS 后消除；review-loop 修改 Agent/修改 skill/再审阅断言）。

## [1.4.4] - 2026-08-19

### Added（职责边界强化：任务-职能匹配防错位）

- **边界审计**：对 21 Agent × 9 节点的 executor/reviewer 分配、职责关键词、required_skills 语义做了全量核对——结构层全部匹配（无配置错位）；发现**执行期薄弱点**：4 组重叠区 Agent 未互相声明边界（execute/coder、analyze/tuner、typesetting/latex_linter、design/modeler），任务同时可归多个 Agent 时职能划分不清。
- **orchestrator 职责边界矩阵**：21 个 Agent 的"负责（任务范围）/ 不负责（边界）/ 交接给"全表 + 5 条重叠区裁决规则（润色 vs 去AI化 vs 评审、统计执行 vs 代码实现、调优 vs 结果分析、排版 vs 质检、学术设计 vs 竞赛建模）；派发铁律：任务与职责不符禁止派发，发现即转派正确 Agent。
- **重叠区成对互引**：execute↔coder、analyze↔tuner、typesetting↔latex_linter、design↔modeler、polish↔humanize、mm-code-reviewer↔reviewer、mm-viz-reviewer↔reviewer 全部互相声明对方职责归属（如 execute"新写算法代码转 coder"、coder"统计解读转 analyze"、typesetting"质检转 latex_linter"、design"竞赛选题转 selector/建模转 modeler"、reviewer"竞赛代码评分转 mm-code-reviewer/图表核对转 mm-viz-reviewer"）。
- **主控 SKILL 职责边界节**：数学建模流程 12 个核心 Agent 的"负责/不负责"表 + 重叠区唯一归属裁决规则。
- **lint 职责边界契约（check_agent_boundaries）**：① 每个执行 Agent 文件必须引用其负责节点（ID 或名称）；② 7 组重叠区必须互相声明边界（互引）；③ 每个 Agent 必须有边界声明（MUST NOT / 你不做 / Phase Boundary）——任何职能错位/边界缺失在契约检查直接报错。

## [1.4.3] - 2026-08-19

### Added（全组件覆盖：全局跑一遍，全部 Agent 与 Skill 都要被调用）

- **孤儿组件排查**：对 agents/（21）与 skills/（34）做全系统引用分析——结果无零引用组件，但发现 4 个 skill 仅自引用（`drawio-skill` / `make-pdf` / `metrics-analysis` / `theme-factory`），完整流程理论调用不到。已补调用归属：
  - `metrics-analysis` → tuner 误差/敏感性分析（Phase 1）+ analyze 统计指标计算（Phase 0 加载）；
  - `drawio-skill` → modeler 模型框架/流程架构图 + visualization 工具选择表（架构图/示意图矢量输出）；
  - `make-pdf` → reviewer N8 终审电子版制作（SubmissionPackage 转 PDF，符合官方 ≤20MB）；
  - `theme-factory` → design 学术设计流程（主题/标题方案生成）。
- **lint 全组件引用契约（check_all_components_referenced）**：agents/ 与 skills/ 的全部组件必须在系统内被"非自身"来源引用（其他 Agent / 各 SKILL / 命令 / 编排文档 / README / 脚本），自身文件不算——任何新孤儿组件（全局跑一遍调用不到）在契约检查直接报错。
- **全系统调用地图（orchestrator.md）**：6 行工作流 × 组件归属总表——数学建模（12 Agent + 19 skill）、学术论文、深度研究、统计分析、LaTeX 编译、通用开发；21 Agent 与 34 skill 全部有归属，并注明"lint 全组件引用契约强制"。

## [1.4.2] - 2026-08-19

### Added（联动同步 · 动态规划 · 去AI化集成 · 全流程覆盖）

- **级联失效（cascade-invalidate / artifact_hash 登记）**：`node-finish` 起自动登记节点产物快照哈希（文件 sha256 / 目录递归清单哈希，64KB 分块）；`state_utils.py cascade-invalidate [--apply]` 检测上游产物变更/缺失 → 下游 completed/in_progress 节点状态与门禁自动重置 pending 并留痕（`meta.cascade_invalidations`）——**改算法/模型后，论文/图表/调优等下游内容必须联动同步更新并重验**，杜绝"只改代码不改论文数字"；默认预览，`--apply` 生效。
- **todo plan 动态规划**：`state_utils.py todo plan` 按 decision_log 状态自动生成/更新全流程任务清单（8 个执行任务 + 8 个审阅任务：节点 completed → 执行任务标完成；对应门禁 PASS/confirmed/auto_passed → 审阅任务标完成；未推进 → 自动补待办），幂等可重复执行；配合 `todo add/done/list` 形成"计划→执行→勾销"闭环。
- **去 AI 化（humanize）正式接入全流程**：
  - orchestrator：委托限制新增 humanize；Phase 8 终审前**必须**委托 humanize 对全文做 AI-ness 专项检测（报告落 `state/reports/`，发现 AI 痕迹 → 返回 writing 修订 → 复审，通过才放行 A3）；铁律 12 强制全流程覆盖；
  - 主控 SKILL：9 阶段表 N7/N8 标注去AI化；新增"全流程 Agent 与 Skill 覆盖"表（13 个 Agent 角色 + 12 个技能包）与"去 AI 化检测环节"专节（评审内嵌检测 + 终审前专项 + 提交门禁）；
  - reviewer：论文评审去AI化检测必须加载 `humanizer`/`academic-humanize` 技能并声明（未加载即评审 = 无效），结果计入表述清晰性维度；
  - mm-iteration-engine §9.2：论文环五维明确去AI化（AI-ness 检测）计入表述清晰性。
- **flow-coverage 全流程覆盖检查**：`state_utils.py flow-coverage` 对照"预期调用集（registry executor/reviewer/required_skills 并集 + humanize + 主控技能）"与"实际记录（executed_by/skills_used/审阅记录）"，报告未调用的 Agent/Skill——收尾验证"完整流程所有 Agent 与 skill 都被正确调用"。
- **lint 新增全流程覆盖契约**：NODES 的 executor/reviewer/required_skills 必须存在对应 `agents/*.md` 与 `skills/*/`；humanize/humanizer/academic-humanize 组件必须存在；orchestrator 文档必须声明完整专业 Agent 集；主控 SKILL 必须声明 humanize 环节。
- `/mm` 路由表新增：联动同步（cascade-invalidate）、全流程覆盖（flow-coverage）、去AI化（humanize 专项）。
- 测试增至 36 项（cascade-invalidate 预览/生效/留痕、todo plan 全流程任务生成与勾销、flow-coverage 缺失报告）。

## [1.4.1] - 2026-08-19

### Added（性能自审 · 图表审阅强化 · 派发强制 · 动态进度）

- **算法性能与实现时间自审（mm-algorithm-dev 1.2.0 + coder）**：写完代码必须自审——时间预算（单题 ≤5min / 全流程 ≤30min）、性能审查流程（计时→热点→复杂度→优化阶梯：算法级→向量化→numba→多核→GPU，达标即停）、**GPU 加速规范**（何时用/何时不用；正确加载：`cuda.is_available` 检查、device 统一、DataLoader `num_workers/pin_memory`、禁逐元素 `.item()` 同步、`torch.no_grad`；正确搜索：faiss GPU / `torch.cdist+topk` / `cKDTree` 按规模选型）、实现时间 ROI 权衡（优化收益矩阵，避免过度优化）、自审结论写入 `result.json.performance_review`（mm-code-reviewer 效率维度证据）。
- **mm-code-reviewer 性能核对清单**：新增 Phase 3.5 八项检查（实测耗时记录、复杂度分析、GPU 正确加载/搜索、CPU 基线一致性、小数据盲目 GPU=过度优化等），效率维度必须有 performance_review 证据，缺失按证据不足给分。
- **图表审阅质量强化（mm-visualization 1.2.0 + mm-viz-reviewer 16 项核对）**：联网核实官方《论文格式规范》（摘要 ≤1 页 / 正文 ≤30 页 / 页边距 ≥2.5cm / 电子版 ≤20MB / 匿名性 / 支撑材料与论文不符可取消评奖资格）+ matplotlib 官方（感知均匀 colormap、禁 jet、红绿色盲、误差棒、figsize×dpi 换算）+ faiss/PyTorch 官方 GPU 用法；新增出版级字号表、统计标注规范（误差棒/显著性/n=）、图表脚本工程化（数据同源、统一 style、`plt.close`、复用函数）、14 项图表自查清单；mm-viz-reviewer 核对清单 12→16 项（新增数据同源抽查、统计标注、脚本工程化、官方格式约束）。
- **派发强制（禁 general-purpose 包办）**：主控 SKILL 执行铁律新增 3 条（禁止 general-purpose 代做节点、逐节点逐章节派发、动态进度更新）；orchestrator 委托模板显式 `subagent_type=<registry executor>` + 铁律 9-11；7 个执行 Agent（selector/dataprep/modeler/coder/tuner/visualization/writing）新增"必读配对 Skill + node-log 小步骤记录"条款；`orchestrator_runtime` 任务包新增 `dispatch_rule` 字段；**audit 新增执行者证据检查**（节点已推进但执行 Agent 无 `state/agents/<id>/result.json` → 报告"疑似内联代做（绕过派发）"）。
- **动态进度更新（node-log / todo）**：`state_utils.py node-log <Nx> --step <小步骤>` 追加 `state/nodes/<名称>/steps.md` 时间线；`todo add/done/list` 维护 `state/todo.md`（完成标记 [x]+时间戳）；节点首页模板新增第 8 节（小步骤与任务清单）+ 第 9 节（**交叉审阅与数据一致性**：独立审阅 Agent 核对、数据同源、修复循环、门禁）。
- **写作后交叉审阅固化**：writing Agent 交付检查点新增数据一致性核对（关键数字与 `output/tables` 同源，抽查 ≥5 处）+ 显式请求 reviewer 论文评审；reviewer 结果正确性维度明确"数据同源抽查"；mm-iteration-engine §6.1 调用铁律第 5 条固化交叉审阅口径。
- **修复：项目内 CLI 全崩根因**——init 只复制 state_utils.py、漏复制被模块级导入的 legacy_names.py，导致项目副本所有命令 ModuleNotFoundError；init 现同步复制 5 个配套模块，state_utils 导入加容错降级。
- 测试增至 33 项（node-log 小步骤记录、todo 增删查、audit 执行者证据检测）；版本统一升至 1.4.1。

## [1.4.0] - 2026-08-19

### Added（容错与自动核查）

- **容错工具 `scripts/resilience.py`**（纯标准库）：
  - `retry_with_backoff`：子代理调用失败/超时自动按指数退避重新调起（默认 3 次 1s→2s→4s）；
  - `adaptive_parallel`：高并发批量任务检测限流错误后自动降级阶梯（并发→减半→串行），单项失败先退避重试，降级过程可回调留痕，耗尽项如实归入 failures。
- **H 门禁自动核查（auto-check / h-confirm）**：H1/H2/H3 人工确认环节默认"自动核查先行"——orchestrator 委托配对核查 Agent（必须独立于执行 Agent）自动核验，`state_utils.py auto-check` 置门禁 `auto_passed`、生成核查报告（state/reports/ kind=verification）、登记 human_checkpoint"待人工追认"，**流程不挂起**；用户回来后 `h-confirm` 追认（→ confirmed）。dashboard 待办区显示"自动核查通过待追认"。
- **协议文档**：mm-iteration-engine SKILL §5.1 容错与降级协议（失败类型分流表、限流降级阶梯、自动核查流程、留痕原则）；§5.2 节点自动审阅与返修协议（覆盖节点表、防死循环、防 AI 偷懒）；迭代工作流说明同步。
- **节点自动审阅与返修（review-loop / node-repair-check）**：`review-loop <Nx>` 生成"独立审阅 → FAIL 返修（≤2 次硬上限）→ 复审 → 达上限 BLOCKED/ESCALATE"完整序列（防死循环）；`node-review` 的 FAIL/BLOCKED 必须附 `--evidence`（无证据拒绝落盘，防审阅走过场）；`node-repair-check` 对比返修前后产物哈希，无变化判 `EMPTY_REPAIR` 打回并计入返修次数（防 AI 偷懒）。
- **已有材料检测与复用（detect/organize/material_intake_plan）**：`orchestrator_runtime` 新增——`detect_existing_materials` 扫描项目内现成论文/代码/数据（排除脚手架占位）；`organize_existing_materials` 自动归位到标准目录并生成 `state/material_index.json`；`material_intake_plan`（`--material-plan`）生成 **AI 内容整理任务包**——强制逐文件读取真实内容（标题/题型、方法/结论、字段/缺失、可复用性、需修复点）后回填索引，禁止只按扩展名归类；主控 SKILL Phase 0、orchestrator agent、/mm 路由均接入"已有材料必检复用"。
- **升级自愈（upgrade-heal / self_check）**：
  - `state_utils.py upgrade-heal`：检测旧版遗留（旧状态目录 00_State、旧文件名 Data_Log.md 等、旧节点首页目录 N4-代码、重复空目录）→ 迁移修复（含 JSON 旧引用更新）→ 补建 → 复检，一键自动纠正；
  - `scripts/self_check.py`：插件升级自检（仓库契约 + 用户级同步滞后 + 组件完整性 + 插件缓存），`--fix` 自动重新同步用户级目录；
  - 旧名迁移映射收敛到 `legacy_names.py`（命名红线对该文件豁免，其余文件仍强制拦截）。
- 测试增至 28 项：已有材料检测/内容整理任务包、升级自愈迁移（00_State→state、旧文件名、旧节点目录、复检零残留）、self_check 自愈闭环。
- **节点执行三重强制（node-finish 机器校验）**：修复"主 agent 内联代做全部节点"漏洞——① `--agent` 必填且须匹配 registry executor（错 Agent 代做被拒）；② `--skills` 必填且须含该节点 required_skills（强制子 Agent 先加载对应技能）；③ 迭代节点（N4/N5/N7/N8）无进行中 round 时禁止直接标 completed（必须 round-start 走 SEARCH→DECIDE 迭代环）。执行者与技能写入状态（executed_by/skills_used）供追溯；orchestrator 委托协议明确"仅 Phase 0 自己完成，Phase 1-8 必须唤起对应子 Agent"；文档命令示例与测试全部更新（共 29 项测试）。
- **状态真实性检测（防绕过 CLI）**：init 在 decision_log 写入 `generator: state_utils.py init` 标记；`project-audit` 新增 `state_authenticity` 检查（generator 标记、schema 2.0、9 节点齐全）——识别"主 agent 手工 mkdir + 手写状态文件"的伪造状态；主控 SKILL 新增"🔴 执行铁律"（禁止手工创建状态/必须 CLI 记录/每阶段必须 task 唤起对应子 Agent/禁止内联代做/先计划后执行）；测试增至 30 项（伪造状态被 audit 识别）。

## [1.3.1] - 2026-08-19

### Fixed

- **脚手架重复目录**：`STANDARD_DIRS` 与 `.gitkeep` 清单各维护一份目录定义且命名不一致，导致生成项目出现近义重复目录（`BackupArchive/draftbackup` 与 `draft-backup`、`midbackup/mid-backup`、`finalbackup/final-backup`、`DefenseMaterial/showfigures/show-figures`）。统一为 kebab-case 单一清单，`.gitkeep` 目录集从 `STANDARD_DIRS` 派生（单一事实源）；lint 命名红线补充 `draftbackup/midbackup/finalbackup/showfigures/show_figures` 旧名拦截；新增回归测试 `test_init_no_duplicate_directories`。
- **LaTeX 标准模板补全**：`ReportPaper/LaTeX/` 补齐 `img/ tables/ build/` 标准目录（build/ 为编译产物目录并加入 .gitignore）；新增 `.latexmkrc`（`bibtex8 -c utf8`，解决 Windows bibtex 读 UTF-8 中文参考文献乱码报错）；preamble 增加 `gbt7714` 参考文献宏包、`caption` 题注格式（小号加粗编号）、`\linespread{1.3}` 行距、`\graphicspath` 图片路径约定；config 增加标题/队伍编号占位与 `\keywords` 命令；摘要页 `\maketitle` + 关键词；main.tex 注释国赛 10 节结构与 `\bibliographystyle{gbt7714}`；ref.bib 示例改为英文占位（避免模板自身触发编码错误）。已在真实项目用 latexmk 全链编译验证通过（build/main.pdf 生成、零错误）。新增回归测试 `test_init_latex_standard_layout`（共 22 项测试）。
- **国赛格式规范对齐**：按 CUMCM《论文格式规范》补齐——标题体系（`\ctexset`：一级标题四号黑体居中、二级/三级小四黑体）、页眉 `fancyhdr`（"全国大学生数学建模竞赛 · 队伍编号：\teamid"）+ 页脚页码、`\teamid` 队伍编号命令（config.tex 必填）、行距 1.5 倍、参考文献五号（`\bibfont{\small}`）；真实项目 latexmk 全链编译验证通过（零错误），测试断言同步强化。

## [1.3.0] - 2026-08-19

### Changed（命名规范化——破坏性变更）

- **状态目录 `00_State` → `state`**：全部代码、文档、模板、测试同步（`state/state_utils.py`、`state/decision_log.json`、`state/reports/` 等）。
- **标准文件名去下划线/数字前缀**（kebab-case）：`Data_Log.md → DataLog.md`、`Team_Info.txt → TeamInfo.txt`、`Key_Requirements.md → KeyRequirements.md`、`Problem_Notes.md → ProblemNotes.md`、`README_项目总说明.md → README-项目总说明.md`、`README_Code.md → README-Code.md`、`README_LATEX.md → README-LaTeX.md`、`README_提交说明.txt → README-提交说明.txt`、`daily_log.md → daily-log.md`、`bug_fix_log.md → bug-fix-log.md`、`version_update.md → version-update.md`、`model_framework.md → model-framework.md`、`reference_list.md → reference-list.md`、`sensitivity_analysis.md → sensitivity-analysis.md`、`error_analysis.md → error-analysis.md`、`model_validation.md → model-validation.md`、`defense_script.md → defense-script.md`、`figure_list.md → figure-list.md`、`draft_backup/mid_backup/final_backup → draft-backup/mid-backup/final-backup`、`show_figures → show-figures`。
- **比赛模板改名**：`2025国赛论文模版PDF.pdf → 国赛论文模版PDF.pdf`、`2025国赛论文模版Word.docx → 国赛论文模版Word.docx`。
- **N0 产物路径修正**：`TimePlan.md` 明确为 `ProblemInfo/TimePlan.md`（此前根目录路径与实际生成不一致）。
- 版本统一为 1.3.0（pyproject / 脚手架 / 模板 decision_log / 两个主控 Skill frontmatter）。

### Added

- **ZCode 标准插件打包**：仓库即插件包——`.zcode-plugin/plugin.json`（兼容 `.claude-plugin/`、`.codex-plugin/`，均含 `icon: 📐` 图标标识）声明 `skills`/`agents`/`commands` 组件；命令集为 `/mm` 总控（自动识别项目现状并按描述路由全流程/单节点/接手/迭代/检查）+ `/mm-help`、`/mm-init`、`/mm-audit`、`/mm-iterate` 四个快捷命令；项目文档（README、docs/、CHANGELOG、CONTRIBUTING、SECURITY）随包携带，一次安装全部加载，Git URL 方式支持系列更新。用户级同步方式同步保持（~/.zcode/skills、~/.zcode/agents、~/.zcode/commands 已更新至 1.3.0）。
- `lint_contracts.py` 新增**插件打包契约**：三个兼容清单内容一致、组件目录存在且计数匹配（skills 34 / agents 21 / commands 5）、命令 frontmatter 必填 description；连同模拟安装自检一起构成插件发布门禁。
- `lint_contracts.py` 新增**命名红线检查**：`00_State`、下划线标准文件名、数字前缀目录（01_Problem 等）不允许出现在任何源文件中（回归防护）。
- **LaTeX 排版规范补充**（latex-guard / mm-latex-writing / LaTeX 模板）：
  - 表格尺寸一致性：宽度 ≤ `\textwidth`、全文字号统一（`\small`/`\footnotesize` 二选一）、列宽用相对 `\textwidth` 表达式，禁止同页表格宽度/字号不一致；
  - 表格与正文衔接：`\end{table}` 后必须空行，禁止字段与表格同行；
  - 图表防漂移：一律 `[htbp]` 浮动、禁止 `[H]` 硬插段落中间、图表前后空行、图表不早于首次引用；
  - 子图合并：同一对比主题的连续多图合并为一个 figure 内多个 subfigure（subcaption 包模板）；
  - 注释标注：图注/表注统一 `\footnotesize`、以"注："开头、说明数据来源/单位/缩写/显著性；
  - LaTeX 模板 preamble 补充 `subcaption/makecell/tabularx/array` 宏包与排版约定注释；sync-and-compatibility 转换后检查清单纳入图表排版质量项。
- **LaTeX 常见错误反例速查（系统联网检索整理）**：`latex-guard` 附录 A 扩充为 A.9–A.15——编译错误信息速查表（20 条常见报错消息→原因→修复，基于 Overleaf Errors / learnlatex / TeX 社区整理）、公式类反例、引用与标签类反例、中文与字体类反例（XeLaTeX+ctex）、文件与缓存类反例、表格类反例补充、浮动与图表类反例补充；`mm-latex-writing` Anti-Patterns 扩至 12 条并指向附录。

## [1.2.0] - 2026-08-19

### Added（协同能力增强）

- **PDF 题目图形处理**：`problem_guard.py figures --mode vision|human` + `figures-read` —— 有视觉能力时用 pdftoppm 把 PDF 逐页渲染为 `ProblemInfo/figures/page-*.png` 交视觉模型阅读；无视觉能力时生成 `state/problem_figure_request.md` 请求单发人工详细描述；`create --figure-mode` 声明模式，`verify` 强制校验图形已处理（vision 需图片哈希匹配且已阅读；human 需人工描述），未完成前 N1 及之后节点不得开工。
- `state_utils.py` 新增 `result-validate` / `result-ingest`：校验 Agent 结果 envelope（必填字段、状态/裁决枚举、产物路径与 SHA-256、越界路径、**审阅独立铁律**），合法结果摘要合并进 `decision_log.json` 并归档。
- **迭代报告留存**：`round-score / round-decide / result-ingest` 自动把独立审阅 Agent 实验报告（review）、决策报告（decision）、完整结果（result）归档到 `state/reports/`，`report-list` 查询；随状态一起 git 提交，跨轮复读对比。
- **项目接手**：新增 `project-audit`（题目比对/标准结构/节点首页/registry 一致性/状态-产物一致性/旧命名）与 `project-repair --apply`（只补建缺失的标准设施，不覆盖已有文件与状态；题目锁定缺失要求先 `problem_guard.py create`）。
- **全自动迭代驱动**：`orchestrator_runtime.py --plan-iteration <N4|N5|N7|N8>` 生成完整迭代序列（round-start → 执行 → round-score → round-decide × max_rounds），前置缺失返回 blocked 与缺失清单。
- `node-review` 支持 `BLOCKED` 裁决：阻断不再降级为 FAIL，门禁与记录保留 BLOCKED 语义。
- `orchestrator_runtime.py` `prepare_node(strict=True)`：上游产物缺失时返回 `status=blocked` 与 `blocked_reasons`。
- `sync_import.py` 转换协议：Markdown/PDF 接入生成 `document_to_latex` 任务（`status: BLOCKED`），脚本不再直接产出权威 LaTeX，正式转换交由专用 Agent 完成。
- `lint_contracts.py` 新增检查：NODES↔registry 双份一致、SKILL frontmatter 必填、版本单一来源对齐、**agents/skills 数量断言、压缩包禁止 git 跟踪**。
- 回归测试扩展到 20 项：N4 前置阻断、BLOCKED 审阅、result 闭环、独立审阅拒绝、项目审计与修复、迭代序列、报告留存、**PDF 图形 vision/human 双路径**。
- 新增 `docs/README.md` 导航、`CHANGELOG.md`、`CONTRIBUTING.md`、`SECURITY.md`。

### Changed

- `node-start` 强制前置门禁：注册表一致性 + 上游节点 completed + 上游产物存在，缺失时非零阻断且不置 in_progress。
- `result.schema.json` 状态枚举补 `pending/in_progress/repair_pending`，与状态工具一致。
- `problem_guard.py create` 的 `source_path` 写为相对项目路径（跨机器复制后 `verify` 仍可用）；`problem_lock.json` 增加 `figure` 字段。
- `orchestrator_runtime.py` 改用 64KB 分块 SHA-256，避免大文件一次性读入内存。
- `do_merge` 按 origin/HEAD → main → master → develop 探测主分支，merge 失败恢复原分支。
- 版本统一为 1.2.0（`pyproject.toml` / 脚手架 / 模板 decision_log / 两个主控 Skill）。
- 删除 `docs/product` 幻灯片工程与 `docs/pages.json` 等讲稿文件；`.gitignore` 覆盖 `.cloudstudio` 文件与 `*.rar`。

### Fixed

- **init 脚手架 JSON 污染**：`compatibility_manifest.json` / `claim_evidence_map.json` / `problem_lock.json` 文件尾被字面 `\n`（反斜杠+n）污染导致非法 JSON，现全部为合法 JSON（`project-audit` 触发发现）。
- `round-decide` 末尾死分支 `continue` 修正为 `repair_and_rerun` 提示。
- `templates/state/dashboard.md` 明确标注 DEPRECATED（实际由 `refresh_dashboard()` 动态生成）。
- `agents/coder.md` 重复 `python state/python state/...` 命令。
- `docs/迭代工作流说明.md` 游离代码围栏；`state/` 目录树补齐实际生成文件。
- `sync-and-compatibility/SKILL.md` frontmatter 统一为 name/description/metadata，重复章节编号修正。
- `round-score` 函数体内重复 `import math`。
- 冒烟报告与能力盘点的阶段（8→9）与数量（19/24→21/34）口径统一。

## [1.1.0] - 2026-08-15

此前版本（见 `docs/迭代工作流说明.md` 历史条目）：init 幂等、round 生命周期与决策动作、S 门禁键、claim ttl、检索地址注册表、脚本自包含落位等。
