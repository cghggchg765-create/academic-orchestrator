"""MM state_utils —— 模板脚手架与项目初始化命令（init/脚手架/交接）（由 state_utils.py 拆分而来，勿手改结构；逻辑见各模块）。"""
from state_defs import *  # noqa: F401,F403

GITIGNORE = """# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
dist/
build/

# LaTeX 中间文件
*.aux
*.log
*.out
*.toc
*.synctex.gz
*.fdb_latexmk
*.fls
*.bbl
*.blg
*.xdv
*.lof
*.lot
ReportPaper/LaTeX/*.aux
ReportPaper/LaTeX/*.log
ReportPaper/LaTeX/*.out
ReportPaper/LaTeX/*.toc
ReportPaper/LaTeX/*.synctex.gz
ReportPaper/LaTeX/*.bbl
ReportPaper/LaTeX/*.blg
ReportPaper/LaTeX/*.pdf
ReportPaper/LaTeX/build/

# IDE / OS
.idea/
.vscode/
.DS_Store
Thumbs.db

# 环境变量（密钥不入库）
.env

# 说明: Data/raw 原始数据建议入库保证可复现; 若数据过大可在下方手动追加忽略规则。
"""

README_PROJECT = """# {name} 项目总说明

## 项目概述
- 竞赛: {name} {year} {problem}
- 语言: {language}
- 状态统一节点: `state/`（decision_log.json + 状态工作栏 + 9 个节点首页 + 检索地址注册表，由 AI 编排系统维护）

## 目录结构
见 `state/dashboard.md` 与 mm-iteration-engine Skill §1 标准项目结构。

## 运行环境
- Python 3.9~3.11（避免 3.12+ 兼容问题）
- 🔴 **必须创建虚拟环境（venv）后运行代码**：
  - Windows: `python -m venv .venv` → `.venv\\Scripts\\activate`
  - macOS/Linux: `python3 -m venv .venv` → `source .venv/bin/activate`
  - 激活后安装依赖: `pip install -r Code/requirements.txt`
  - `.venv/` 已加入 .gitignore，不入库

## 复现步骤
1. 激活虚拟环境（见上）后运行: `python Code/main.py --problem 1`
2. 输出统一落在 `Code/output/`（tables/figures/txt_result/model_save）

## 团队分工
| 成员 | 角色 | 负责节点 |
|------|------|---------|
| - | 建模 | N1/N3 |
| - | 编程 | N4/N5/N6 |
| - | 写作 | N7/N8 |

## Git 协作
- 迭代分支命名: `round{{N}}_{{任务}}_{{slug}}`（每轮算法/论文迭代一个分支）
- 评分 ≥ pass 才 merge 回 main; 提交信息含 Round/Agent/Gate/Score/State-Sha trailer
- 请创建远端 GitHub 仓库后执行: `git remote add origin <url>` 并自行推送（AI 不代做推送）

## 目录与文件命名规范
- 项目根目录用项目名（如 `2026_CUMCM_Problem_A` / `MathModel_Contest`）
- 🔴 禁止 `xxx-main` / `xxx-master` 后缀目录名（GitHub zip 解压产物形态），禁止在项目内再嵌套同名子目录
- 🔴 项目名/目录名/文件名禁止纯数字（如 `01`、`000`）；文件一律语义命名（如 `fig1_results_comparison.png`、`main_round1.pdf`、`p1_solver.py`）
"""

REQUIREMENTS = """numpy>=1.24
pandas>=2.0
scipy>=1.10
scikit-learn>=1.3
matplotlib>=3.7
seaborn>=0.12
"""

CONFIG_PY = '''"""config.py — 全局参数、路径、超参配置（占位模板）

铁律: 所有参数集中在此，禁止在业务代码中硬编码 magic number。
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "Data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")          # 唯一输出口
FIG_DIR = os.path.join(OUTPUT_DIR, "figures")
TAB_DIR = os.path.join(OUTPUT_DIR, "tables")
TXT_DIR = os.path.join(OUTPUT_DIR, "txt_result")
MODEL_DIR = os.path.join(OUTPUT_DIR, "model_save")

RANDOM_SEED = 42
'''

MAIN_PY = '''"""main.py — 统一入口（占位模板）

运行: python main.py --problem 1
各题求解逻辑在 problem_1~4/pX_solver.py 中实现，本入口负责串联与输出。
"""
import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="数学建模统一入口")
    parser.add_argument("--problem", type=int, default=1, help="题号 1-4")
    args = parser.parse_args()
    print(f"[main.py] 占位模板: 请在 Code/problem_{args.problem} 下实现 p{args.problem}_solver.py。")
    sys.exit(0)


if __name__ == "__main__":
    main()
'''

UTIL_TPL = '''"""{name}.py — 占位模块

职责: {desc}
"""
'''


def solver_placeholder(name, desc):
    return f'''"""{name}.py — 占位模块（每问一文件，独立可运行）

职责: {desc}
规范: 核心函数 docstring 必须引用 ModelDocs/formula.md 中对应公式编号（如"对应公式 (3.1)"）。
      np.random.seed(42) / 数据路径用 config.py 中相对路径，禁止硬编码绝对路径。
"""
import numpy as np

np.random.seed(42)


def solve() -> None:
    raise NotImplementedError("请按 ModelDocs/formula.md 实现本问求解逻辑")


if __name__ == "__main__":
    solve()
'''


LATEX_MAIN = r"""\documentclass[12pt,a4paper]{ctexart}
\input{preamble}
\input{config}
\begin{document}

% ===== PDF 第 1 页：承诺书（无页码） =====
\IfFileExists{frontmatter/commitment.tex}{\input{frontmatter/commitment}}{\thispagestyle{empty}\null}
\thispagestyle{empty}\clearpage

% ===== PDF 第 2 页：编号专用页（无页码） =====
\IfFileExists{frontmatter/team_number.tex}{\input{frontmatter/team_number}}{\thispagestyle{empty}\null}
\thispagestyle{empty}\clearpage

% ===== PDF 第 3 页：摘要页（摘要≤1页；页码从此处记 1） =====
\pagenumbering{arabic}
\setcounter{page}{1}
\input{sections/abstract}
\clearpage

% ===== PDF 第 4 页起：正文（正文从第4页计，≤30页；附录不限） =====
% 正文章节按 current-year CUMCM profile 组织；不要插入目录。
%   \input{sections/problem_restatement}   % 问题重述
%   \input{sections/problem_analysis}      % 问题分析
%   \input{sections/model_assumptions}     % 模型假设
%   \input{sections/symbols}               % 符号说明
%   \input{sections/model_solution}        % 模型建立与求解
%   \input{sections/model_verification}    % 模型检验
%   \input{sections/model_evaluation}      % 模型评价

% ===== 正文结束后：参考文献与附录（附录页数不限） =====
\bibliographystyle{gbt7714}
\bibliography{ref}
%   \input{sections/appendix}              % 代码/数据/补充推导

\end{document}
"""

LATEX_PREAMBLE = r"""% preamble.tex — 宏包与全局设置（国赛标准模板）
% 编译：latexmk -xelatex -outdir=build -interaction=nonstopmode main.tex
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{array}
\usepackage{tabularx}
\usepackage{makecell}
\usepackage{subcaption}
\usepackage{caption}
\captionsetup{font=small,labelfont=bf,labelsep=quad}   % 图注/表注：小号（约五号）、加粗编号（CJK 下映射黑体）
\usepackage{algorithm,algpseudocode}
\usepackage[super]{gbt7714}                             % 参考文献 GB/T 7714（TeX Live 自带；
                                                        % 若环境缺失改用 natbib + gb7714-2015 样式）
\renewcommand{\bibfont}{\small}                         % 参考文献五号字
\usepackage{fancyhdr}                                   % 页眉/页脚：队伍编号 + 页码（国赛要求论文中出现队伍编号）
\pagestyle{fancy}
\fancyhf{}
\fancyhead[C]{\zihao{-5}全国大学生数学建模竞赛\;\;队伍编号：\teamid}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\usepackage[colorlinks=true]{hyperref}
\usepackage{geometry}
\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}
\linespread{1.5}                                        % 行距 1.5 倍（国赛常见；页数紧张可调回 1.3）
% 标题字体（国赛规范：一级标题四号黑体居中，二级/三级小四黑体）
\ctexset{
  section     = {format = {\zihao{4}\heiti\centering}},
  subsection  = {format = {\zihao{-4}\heiti}},
  subsubsection = {format = {\zihao{-4}\heiti}},
}
\graphicspath{{img/}{../../ResultFigures/}}             % 图片路径约定：本目录 img/ 与论文级图库 ResultFigures/
% 表格/图表排版约定（详见 latex-guard Skill）：
% 1) 表格统一使用 booktabs 三线表，禁止竖线与全框线；
% 2) 表格宽度不超过 \textwidth，列宽用 p{...} 或 tabularx 控制，全文字号统一（\small 或 \footnotesize 二选一）；
% 3) 图/表必须放在浮动环境（figure/table）中，禁止 [H] 硬插到段落中间；
% 4) 同一类的多张图合并为一个 figure 环境内的多个 subfigure（subcaption 包）；
% 5) 图注/表注统一用 \footnotesize，以"注："开头说明数据来源与缩写。
"""

LATEX_CONFIG = r"""% config.tex — 论文全局配置：队伍编号/标题/关键词命令（写作时填写）
% 队伍编号（必填：竞赛报名号，全文唯一身份标识；填错将导致成绩无法匹配）
\newcommand{\teamid}{2026XXXX}

\title{论文题目（写作时填写）}
\author{队伍编号：\teamid}
\date{\today}

% 关键词命令（摘要页末尾使用）：\keywords{关键词一；关键词二}
\newcommand{\keywords}[1]{\par\vspace{6pt}\noindent{\bfseries 关键词：}#1}
"""

LATEX_ABSTRACT = r"""% sections/abstract.tex — 摘要（第 1 页，≤1 页；最后写）
\maketitle
\begin{abstract}
摘要正文（占位）：问题重述（1-2 句）→ 方法概述（3-5 句，含模型名与关键公式引用）→ 主要结论（2-3 句，每问至少 1 个数字，与正文/代码输出一致）。
\keywords{关键词一；关键词二；关键词三；关键词四}
\end{abstract}
"""

LATEX_BIB = """% ref.bib — 参考文献（GB/T 7714）
% 正文用 \\cite{key} 引用；示例条目（英文占位，写作时替换为真实文献，中文文献直接 UTF-8 书写即可）：
% @article{key1,
%   author  = {Author A and Author B},
%   title   = {Paper title},
%   journal = {Journal Name},
%   year    = {2024},
%   volume  = {40},
%   number  = {3},
%   pages   = {567--578},
% }
"""

FIGURE_LIST = """# 图片编号与用途（ResultFigures/figure-list.md）

> 由 visualization agent 维护：图片编号、用途、对应论文章节。论文级图片从 Code/output/figures 精选入库，去冗余。
> `data_class` 取 `contest_provided` / `external_public` / `model_simulation` / `survey_field`；内部代码路径只作 scope evidence，不写入论文题注。

| 编号 | 文件名 | 分类目录 | 用途 | 对应论文章节 | data_class | source_ref | citation_ref | accessed_at | sample_size | seed | reproducibility_ref |
|------|--------|---------|------|-------------|------------|------------|--------------|-------------|-------------|------|---------------------|
| - | - | - | - | - | - | - | - | - | - | - | - |
"""

DATA_PROVENANCE_TEMPLATE = """## 数据来源与可复现性登记

| 数据对象/文件 | data_class | source_ref | citation_ref | accessed_at | sample_size | seed | reproducibility_ref |
|---|---|---|---|---|---:|---|---|
| - | contest_provided / external_public / model_simulation / survey_field | - | - | - | - | - | - |

> 外部公开数据必须填写机构/数据集/日期或访问时间、GB/T 7714 引用和支撑材料；模型仿真必须填写参数、随机种子和完整代码；问卷/实测必须填写时间、方式和有效样本量；赛题自带数据不得伪称外部资料。
"""

SUBMISSION_CHECKLIST = """# 参赛提交清单（SubmissionPackage/参赛提交清单.md）

> 由 reviewer（N8 终审）核对生成。

| 材料 | 要求 | 状态 |
|------|------|------|
| 论文.pdf | PDF ≤20MB；第1承诺书/第2编号页/第3摘要/第4起正文；正文从第4页计 ≤30页；无目录 | 待核对 |
| 代码 | 可运行、有 README、可复现 | 待核对 |
| 数据 | raw 原始数据 + provenance/处理说明；外部数据按要求纳入支撑材料 | 待核对 |
| 支撑材料包 | 代码/数据压缩包 ≤20MB，与论文 PDF 分开 | 待核对 |
| 附件 | Appendix_附件.pdf / 支撑材料清单 | 待核对 |
"""

VERSION_UPDATE = """# 版本迭代记录（LogRecord/version-update.md）

> 由迭代引擎每轮自动追加（与 git commit trailer 对齐）。

| 时间 | 节点 | 轮次 | 分支 | 评分 | 决策 | feedback / 下轮 goal |
|------|------|:----:|------|:----:|------|----------------------|
"""

HUMAN_CHECKPOINT = """# 人工在环检查点（state/human_checkpoint.md）

> 当 H1/H2/H3 需要人工确认而用户不在时，流水线在本文件登记挂起记录并暂停。
> 用户确认后，orchestrator 将确认结果与时间戳写入 decision_log.json 的对应 H 门禁，然后继续。

## 挂起记录

| 时间 | 检查点 | 待确认内容 | 产物位置 | 状态 |
|------|--------|-----------|---------|------|

## 确认模板

- H1（题型判定/隐性约束）: 确认"问题类型判定是否正确？隐性约束有无遗漏？" 不通过 → 纠正 → 重跑 M1。
- H2（数值量级）: 确认"结果数量级是否合理？有无明显荒谬的输出？" 不通过 → 回 N4/N5。
- H3（论文整体）: 确认"摘要是否每问量化？结论是否自洽？整体印象是否达到省一水平？" 不通过 → 回 N7。
"""

NODE_DASHBOARD_TEMPLATE = """# 节点首页：{NODE_ID}-{NODE_NAME}

> 本页为节点独立状态页，由执行 Agent 与配对审阅 Agent 在每次执行/审阅后刷新（`state_utils.py node-finish / node-review`）。
> 机器事实源为 `state/decision_log.json`（以 JSON 为准，本页为可读视图）。

## 1. 基本信息

| 项 | 值 |
|----|----|
| 节点 | {NODE_ID}-{NODE_NAME} |
| 执行 Agent | {EXECUTOR} |
| 配对审阅 Agent | {REVIEWER} |
| 审阅前必读 Skill | {SKILLS} |
| 产物目录 | {ARTIFACT_DIR} |
| 门禁 | {GATES} |
| 状态 | pending |
| 最近更新 | - |

## 2. 本节点 goal

- （本节点当前迭代目标，与 decision_log.json 中 nodes.{NODE_ID}.goal 及 rounds[n].goal 对应；goal 插件写入，达成后清空）

## 3. 产物清单

| 路径 | sha256 | 备注 |
|------|--------|------|
| - | - | - |

## 4. 迭代记录（round → 评分 → 决策 → feedback → goal）

| round | 分支 | 评分 | 决策 | feedback / 下轮 goal |
|:-----:|------|:----:|------|----------------------|
| - | - | - | - | - |

## 5. 审阅记录

| 时间 | 审阅 Agent | 声明已读 Skill | 结论 | 问题清单 |
|------|-----------|---------------|------|---------|
| - | - | - | - | - |

## 6. 门禁状态

| 门禁 | 状态 | 结果 |
|------|------|------|
| - | pending | - |

## 7. 回退与备注

- （回退原因、人工确认记录、abandoned 分支说明）

## 8. 执行小步骤与任务清单

- 小步骤时间线：`state/nodes/{NODE_DIR}/steps.md`（由执行 Agent 用 `state_utils.py node-log <节点> --step <小步骤>` 逐条追加，完成节点后再 `node-finish` 标记完成）
- 项目任务清单：`state/todo.md`（`state_utils.py todo add / done / list` 动态更新；完成条目标记 [x]）

## 9. 交叉审阅与数据一致性（🔴 节点产物必须过独立审阅）

| 环节 | 要求 |
|------|------|
| 交叉审阅 | 本节点产物完成后，必须派发配对**独立审阅 Agent**（审阅≠执行，见第 5 节审阅记录）：N1-N3/N7-N8 → reviewer（节点/论文评审模式），N4/N5 → mm-code-reviewer（五维评分），N6 → mm-viz-reviewer（5 个前置门禁 + 20 项编号质量核对） |
| 审阅前置 | 审阅 Agent 必须先加载配对 Skill 并声明（node-review --skills 强制校验）；FAIL/BLOCKED 必须附 --evidence |
| 数据一致性 | 论文/图表/代码中的关键数字必须与 `Code/output/tables/`、运行日志**同源可追溯**（"代码输出 = 论文数据"；支撑材料与论文不符可能取消评奖资格），审阅 Agent 抽查核对 |
| 修复循环 | 审阅 FAIL → 执行 Agent 按 feedback 返修（≤2 次，空返修打回）→ 复审；超限转 BLOCKED/ESCALATE |
| 门禁 | 审阅通过后门禁落盘（N4→P2、N5→T1、N6→V1、N7→W2 等），迭代节点由 round-score/round-decide 裁决 |
"""


# ---------------------------------------------------------------- init


STANDARD_DIRS = [
    f"{STATE_DIR}/agents", f"{STATE_DIR}/cases", f"{STATE_DIR}/reviews", f"{STATE_DIR}/scopes",
    "ProblemInfo",
    "Data/raw", "Data/processed", "Data/feature", "Data/test_result",
    "Code/utils", "Code/visualization/utils",
    "Code/output/tables", "Code/output/figures", "Code/output/txt_result", "Code/output/model_save",
    "ResultFigures/schematic", "ResultFigures/curve", "ResultFigures/heatmap", "ResultFigures/comparison",
    "ReportPaper/LaTeX/frontmatter", "ReportPaper/LaTeX/sections", "ReportPaper/LaTeX/img",
    "ReportPaper/LaTeX/tables", "ReportPaper/LaTeX/build",
    "ModelDocs",
    "SubmissionPackage",
    "Material/similar_papers", "Material/template",
    "LogRecord",
    "BackupArchive/draft-backup", "BackupArchive/mid-backup", "BackupArchive/final-backup",
    "DefenseMaterial/show-figures",
]

STANDARD_FILES = {
    ".gitignore",
    "README-项目总说明.md",
    "ProblemInfo/ProblemNotes.md",
    "ProblemInfo/KeyRequirements.md",
    "ProblemInfo/TeamInfo.txt",
    "ProblemInfo/TimePlan.md",
    "Data/raw/readme.txt",
    "Data/DataLog.md",
    "Code/config.py",
    "Code/main.py",
    "Code/requirements.txt",
    "Code/README-Code.md",
    "ResultFigures/figure-list.md",
    "ReportPaper/LaTeX/main.tex",
    "ReportPaper/LaTeX/preamble.tex",
    "ReportPaper/LaTeX/config.tex",
    "ReportPaper/LaTeX/ref.bib",
    "ReportPaper/LaTeX/sections/abstract.tex",
    "ReportPaper/LaTeX/README-LaTeX.md",
    "ModelDocs/model-framework.md",
    "ModelDocs/formula.md",
    "ModelDocs/assumption.md",
    "ModelDocs/reference-list.md",
    "ModelDocs/sensitivity-analysis.md",
    "ModelDocs/error-analysis.md",
    "ModelDocs/model-validation.md",
    "SubmissionPackage/README-提交说明.txt",
    "SubmissionPackage/参赛提交清单.md",
    "LogRecord/daily-log.md",
    "LogRecord/bug-fix-log.md",
    "LogRecord/version-update.md",
    "DefenseMaterial/defense-script.md",
    f"{STATE_DIR}/todo.md",
}


def standard_files_content(name="", year="", problem="", language="zh"):
    """标准占位文件内容（init 与 project-repair 共用；不覆盖已存在文件）。"""
    return {
        ".gitignore": GITIGNORE,
        "README-项目总说明.md": README_PROJECT.format(name=name, year=year, problem=problem, language=language),
        f"{STATE_DIR}/compatibility_manifest.json": json.dumps({"version": "1.0", "status": "pending", "inputs": {"existing_code": [], "existing_data": [], "existing_paper": []}, "gates": {"code": "pending", "data": "pending", "paper": "blocked_until_code_and_data"}}, ensure_ascii=False, indent=2) + "\n",
        f"{STATE_DIR}/source_inventory.md": "# 现有材料清单\\n\\n接入已有论文、代码和数据后填写；未完成代码与数据审阅前不得改写论文。\\n",
        f"{STATE_DIR}/claim_evidence_map.json": json.dumps({"version": "1.0", "claims": []}, ensure_ascii=False, indent=2) + "\n",
        f"{STATE_DIR}/problem_lock.json": json.dumps({"version": "1.0", "status": "pending", "source_path": "", "source_sha256": "", "objectives": [], "constraints": [], "preconditions": [], "data_requirements": [], "evaluation_metrics": [], "drift_policy": "题目原文、目标、约束、数据或指标变化时必须重新锁定"}, ensure_ascii=False, indent=2) + "\n",
        "ProblemInfo/ProblemNotes.md": "# ProblemNotes（题目拆解，selector 产物占位）\n\n待 N1 选题拆解后填写。\n",
        "ProblemInfo/KeyRequirements.md": "# KeyRequirements（核心约束、评分点、禁忌项，selector 产物占位）\n",
        "ProblemInfo/TeamInfo.txt": "成员: \n分工: 建模- / 编程- / 写作-\n",
        "ProblemInfo/TimePlan.md": "# TimePlan（比赛时间轴、节点任务）\n\n| 时间 | 节点任务 | 状态 |\n|------|---------|------|\n",
        "Data/raw/readme.txt": "原始数据目录：禁止修改。数据来源与说明写入 Data/DataLog.md。\n",
        "Data/DataLog.md": "# DataLog（数据处理日志，dataprep 产物占位）\n\n待 N2 数据处理后填写。\n\n" + DATA_PROVENANCE_TEMPLATE,
        "Code/config.py": CONFIG_PY,
        "Code/main.py": MAIN_PY,
        "Code/requirements.txt": REQUIREMENTS,
        "Code/README-Code.md": "# README-Code（代码运行说明、依赖版本）\n\n🔴 运行前必须创建并激活虚拟环境:\n  Windows: python -m venv .venv && .venv\\\\Scripts\\\\activate\n  Linux/macOS: python3 -m venv .venv && source .venv/bin/activate\n安装依赖: pip install -r requirements.txt\n运行: `python main.py --problem 1`（输出只落 output/）\n",
        "Code/utils/__init__.py": "",
        "Code/utils/data_io.py": UTIL_TPL.format(name="data_io", desc="数据读写"),
        "Code/utils/preprocess.py": UTIL_TPL.format(name="preprocess", desc="预处理"),
        "Code/utils/metrics.py": UTIL_TPL.format(name="metrics", desc="指标计算"),
        "Code/utils/logger.py": UTIL_TPL.format(name="logger", desc="日志"),
        "Code/utils/model_utils.py": UTIL_TPL.format(name="model_utils", desc="模型通用工具、保存加载"),
        "Code/visualization/__init__.py": "",
        "Code/visualization/utils/__init__.py": "",
        "Code/visualization/utils/plot_base.py": UTIL_TPL.format(name="plot_base", desc="绘图基础设置（中文/300dpi/配色）"),
        "ResultFigures/figure-list.md": FIGURE_LIST,
        "ReportPaper/LaTeX/main.tex": LATEX_MAIN,
        "ReportPaper/LaTeX/frontmatter/commitment.tex": "% 承诺书占位页（正式提交前由队伍按当年模板填写）\n\\thispagestyle{empty}\\begin{center}承诺书\\end{center}\n",
        "ReportPaper/LaTeX/frontmatter/team_number.tex": "% 编号专用页占位（正式提交前由队伍按当年模板填写）\n\\thispagestyle{empty}\\begin{center}编号专用页\\end{center}\n",
        "ReportPaper/LaTeX/preamble.tex": LATEX_PREAMBLE,
        "ReportPaper/LaTeX/config.tex": LATEX_CONFIG,
        "ReportPaper/LaTeX/ref.bib": LATEX_BIB,
        "ReportPaper/LaTeX/sections/abstract.tex": LATEX_ABSTRACT,
        "ReportPaper/LaTeX/README-LaTeX.md": "# README-LaTeX\n\n唯一文档源为 LaTeX；PDF 仅为编译产物，不作为源文件维护。\n\n编译（产物进 build/，工作区干净）：\n\n    latexmk -xelatex -outdir=build -interaction=nonstopmode main.tex\n\nWindows 下中文参考文献（UTF-8）由项目内 .latexmkrc 自动使用 bibtex8 -c utf8；\n交叉引用/引用变化后自动重跑，最终 PDF 位于 build/main.pdf。\n",
        "ReportPaper/LaTeX/.latexmkrc": "$bibtex = 'bibtex8 -c utf8';\n# 中文参考文献（UTF-8）在 Windows bibtex 下需 utf8 编码；TeX Live 自带 bibtex8\n",
        "ModelDocs/model-framework.md": "# model-framework（模型框架，modeler 产物占位）\n",
        "ModelDocs/formula.md": "# formula（公式推导，modeler 产物占位）\n",
        "ModelDocs/assumption.md": "# assumption（假设清单，modeler 产物占位）\n",
        "ModelDocs/reference-list.md": "# reference-list（参考文献清单）\n",
        "ModelDocs/sensitivity-analysis.md": "# sensitivity-analysis（灵敏度分析，tuner 产物占位）\n",
        "ModelDocs/error-analysis.md": "# error-analysis（误差分析，tuner 产物占位）\n",
        "ModelDocs/model-validation.md": "# model-validation（模型验证与鲁棒性，tuner 产物占位）\n",
        "SubmissionPackage/README-提交说明.txt": "提交说明（占位）\n",
        "SubmissionPackage/参赛提交清单.md": SUBMISSION_CHECKLIST,
        "Material/training_notes.md": "# training_notes（训练笔记）\n",
        "Material/contest_experience.md": "# contest_experience（赛题经验、避坑总结）\n",
        "LogRecord/daily-log.md": "# daily-log（每日进度、问题、解决方案）\n\n| 日期 | 进度 | 问题 | 解决方案 |\n|------|------|------|---------|\n",
        "LogRecord/bug-fix-log.md": "# bug-fix-log（代码 bug、模型问题修复记录）\n\n| 时间 | 现象 | 根因 | 修复 | 关联分支 |\n|------|------|------|------|---------|\n",
        f"{STATE_DIR}/todo.md": "# 任务清单（To-Do）\n\n- [ ] （在节点执行过程中动态更新：`state_utils.py todo add <待办> [--node N4]` 新增、`todo done <匹配文本>` 标记完成、`todo list` 查看）\n",
        "LogRecord/version-update.md": VERSION_UPDATE,
        "DefenseMaterial/defense-script.md": "# defense-script（答辩话术、问答预案）\n",
    }


def scaffold(root, competition, force=False, sync_runtime=False, runtime_source=None):
    """创建项目结构；runtime 模块仅在显式 sync_runtime 时更新，状态文件仍幂等。"""
    name, year, problem, language = (competition.get(k, "") for k in ("name", "year", "problem", "language"))
    dirs = STANDARD_DIRS
    for d in dirs:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    for d in (info["dir"] for nid, info in NODES.items()):
        os.makedirs(os.path.join(root, STATE_DIR, "nodes", d), exist_ok=True)

    files = standard_files_content(name, year, problem, language)
    for path, text in files.items():
        full = os.path.join(root, path)
        if force or not os.path.exists(full):
            save_text_atomic(full, text)
    for q in range(1, 5):
        pdir = os.path.join(root, f"Code/problem_{q}")
        os.makedirs(pdir, exist_ok=True)
        for fn, desc in (("__init__.py", ""), (f"p{q}_solver.py", f"第 {q} 问核心求解代码"),
                         (f"p{q}_analysis.py", f"第 {q} 问结果分析、误差分析"), (f"p{q}_param.py", f"第 {q} 问专属参数配置")):
            full = os.path.join(pdir, fn)
            if force or not os.path.exists(full):
                save_text_atomic(full, solver_placeholder(fn.replace(".py", ""), desc) if fn != "__init__.py" else "")
    for q in range(1, 5):
        full = os.path.join(root, f"Code/visualization/vis_p{q}.py")
        if force or not os.path.exists(full):
            save_text_atomic(full, solver_placeholder(f"vis_p{q}", f"第 {q} 问可视化（输出到 output/figures）"))
    # .gitkeep 目录清单从 STANDARD_DIRS 派生（单一事实源，禁止另写一份目录清单导致重复目录）
    gitkeep_dirs = [d for d in STANDARD_DIRS if d.endswith(("raw", "tables", "figures", "txt_result", "model_save",
                                                             "schematic", "curve", "heatmap", "comparison",
                                                             "LaTeX", "similar_papers", "template",
                                                             "draft-backup", "mid-backup", "final-backup",
                                                             "show-figures", "agents", "cases"))]
    for d in gitkeep_dirs:
        full = os.path.join(root, d, ".gitkeep")
        if force or not os.path.exists(full):
            save_text_atomic(full, "")

    # ---- 状态目录全量预建（前期工作；已存在时跳过，防止覆盖已推进状态）
    if force or not os.path.exists(os.path.join(root, STATE_FILE)):
        decision_log = {
            "_schema": "2.0",
            "_comment": "=== mm-iteration-engine 状态统一节点 (schema 2.0) === orchestrator 单写；动态门禁键 S<轮次>-<节点>（如 S1-N4）由 round-score 创建。",
            "competition": {"name": name, "year": year, "problem": problem, "language": language},
            "stages": {},
            "scopes": [],
            "nodes": {nid: {"name": info["name"], "status": "pending",
                            "homepage": f"{STATE_DIR}/nodes/{info['dir']}/dashboard.md", "goal": ""}
                      for nid, info in NODES.items()},
            "gates": {},
            "rounds": [],
            "decisions": [],
            "termination": {
                "code": {"pass": 7.0, "target": 8.0, "max_rounds": 5, "plateau": {"window": 2, "epsilon": 0.3},
                         "budget": {"deadline": None}},
                "paper": {"pass": 6.5, "target": 7.5, "max_rounds": 4, "plateau": {"window": 2, "epsilon": 0.3},
                          "budget": {"deadline": None}},
            },
            "meta": {"created_at": now_iso(), "updated_at": now_iso(), "seq": 0, "skill_version": "2.0.0",
                     "platform_mode": "", "current_round": None, "current_stage": None, "state_git_sha": None,
                     "generator": "state_utils.py init"},  # 状态真实性标记：audit 据此识别"手工伪造状态（绕过 CLI）"
        }
        for nid, info in NODES.items():
            stage = {"status": "pending", "completed_at": None, "artifacts": [], "decisions": {}}
            if info["stage"] == "4_solving":
                stage["random_seed"] = None
            if info["stage"] == "8_review":
                stage["final_score"] = None
                stage["passed"] = False
            decision_log["stages"][info["stage"]] = stage
        for gate in ("M1", "D1", "P1", "P2", "A1", "T1", "V1", "W1", "A2", "W2", "A3"):
            decision_log["gates"][gate] = {"status": "pending", "agent": None, "timestamp": None, "result": None}
        for gate in ("H1", "H2", "H3"):
            decision_log["gates"][gate] = {"status": "pending", "note": None}
        save_state(root, decision_log, bump=False)

    if force or not os.path.exists(os.path.join(root, REGISTRY_FILE)):
        registry = {"_comment": "调用路由注册表：任务→执行 Agent→审阅 Agent→必读 Skill→门禁→产物。任何委派必须与本表匹配。迭代动态门禁 S<n>-<节点> 未列于此（运行时由 round-score 创建）。",
                    "version": "1.0", "nodes": []}
        for nid, info in NODES.items():
            if nid == "N0":
                continue
            entry = {"id": nid, "name": info["name"], "trigger_phrases": info["phrases"],
                     "executor": info["executor"], "reviewer": info["reviewer"], "review_mode": info["review_mode"],
                     "required_skills": info["skills"], "gates": info["gates"], "artifact_dir": info["artifact"],
                     "homepage": f"{STATE_DIR}/nodes/{info['dir']}/dashboard.md",
                     "upstream": [up for up, _ in UPSTREAM.get(nid, [])]}
            # 2.0.0：次要审阅者（如 B1 门禁的图表对标审阅）随节点透传进项目 registry
            if info.get("secondary_reviewers"):
                entry["secondary_reviewers"] = info["secondary_reviewers"]
            registry["nodes"].append(entry)
        save_json_atomic(os.path.join(root, REGISTRY_FILE), registry)

    if force or not os.path.exists(os.path.join(root, CASES_INDEX)):
        save_json_atomic(os.path.join(root, CASES_INDEX), {"version": "1.0", "cases": []})

    if force or not os.path.exists(os.path.join(root, SEARCH_SOURCES_FILE)):
        save_json_atomic(os.path.join(root, SEARCH_SOURCES_FILE), SEARCH_SOURCES)

    if force or not os.path.exists(os.path.join(root, STATE_DIR, "human_checkpoint.md")):
        save_text_atomic(os.path.join(root, STATE_DIR, "human_checkpoint.md"), HUMAN_CHECKPOINT)

    for nid, info in NODES.items():
        home = node_homepage(root, nid)
        if force or not os.path.exists(home):
            text = NODE_DASHBOARD_TEMPLATE.format(
                NODE_ID=nid, NODE_NAME=info["name"], NODE_DIR=info["dir"], EXECUTOR=info["executor"],
                REVIEWER=info["reviewer"] or "-", SKILLS=", ".join(info["skills"]) or "-",
                ARTIFACT_DIR=info["artifact"], GATES=" / ".join(info["gates"]) or "-")
            save_text_atomic(home, text)

    # 脚本落位：复制进项目（项目自包含，统一用 `python state/state_utils.py`）
    # 🔴 必须复制同目录门面 state_utils.py，而不能用 __file__：cmd_init 定义在本模块，
    # __file__ 会指向 state_scaffold.py，导致项目内 state/state_utils.py 被 scaffold 内容覆盖，
    # 缺失 round-*/node-*/scope-* 等全部 argparse 分发命令。
    _module_dir = os.path.abspath(runtime_source) if runtime_source else os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(_module_dir, "state_utils.py")):
        raise ValueError(f"runtime_source 必须包含 state_utils.py: {_module_dir}")
    copied = os.path.join(root, STATE_DIR, "state_utils.py")
    src = os.path.join(_module_dir, "state_utils.py")
    tgt = os.path.abspath(copied)
    if src == tgt:
        pass  # 已在项目内运行 init：源=目标，跳过
    elif os.path.isfile(src) and (force or sync_runtime or not os.path.exists(copied)):
        shutil.copyfile(src, tgt)
    # 配套模块同步复制（state_defs/state_scaffold 等被 state_utils 拆分的兄弟模块与 legacy_names 等被模块级导入；
    # 缺失会导致项目内 CLI 全部崩溃）。与本文件同目录的全部 .py 均为运行态模块（state_utils.py 本体 + 各分模块 + 配套脚本），
    # 一并复制保证项目自包含；__pycache__/测试等不在此目录，随仓库维护。
    for module in sorted(
        p for p in os.listdir(_module_dir)
        if p.endswith(".py") and p != "state_utils.py"
    ):
        m_src = os.path.join(_module_dir, module)
        m_tgt = os.path.join(root, STATE_DIR, module)
        if os.path.isfile(m_src) and (force or sync_runtime or not os.path.exists(m_tgt)):
            shutil.copyfile(m_src, m_tgt)

    # 技能路由层落位：能力词表 + 发现/匹配模块复制进项目 state/skill-routing/，
    # 使 `python state/state_utils.py skill-plan <节点>` 在项目内可独立运行。
    routing_src = os.path.abspath(os.path.join(_module_dir, "..", "skill-routing"))
    if os.path.isdir(routing_src):
        routing_tgt = os.path.join(root, STATE_DIR, "skill-routing")
        os.makedirs(routing_tgt, exist_ok=True)
        for fname in ("capability_taxonomy.json", "skill_discovery.py", "skill_matcher.py"):
            f_src = os.path.join(routing_src, fname)
            f_tgt = os.path.join(routing_tgt, fname)
            if os.path.isfile(f_src) and (force or sync_runtime or not os.path.exists(f_tgt)):
                shutil.copyfile(f_src, f_tgt)

    refresh_dashboard(root)

    if competition.get("git"):
        do_git_init(root)


def do_git_init(root):
    if not os.path.exists(os.path.join(root, ".git")):
        r = git(["init"], cwd=root)
        if r.returncode != 0:
            print(f"[state_utils] git init 失败: {r.stderr.strip()}")
            return
        git(["branch", "-M", "main"], cwd=root)
    git(["add", "-A"], cwd=root)
    r = git(["commit", "-m", "chore: 初始化标准项目结构与状态统一节点（状态目录全量预建）"], cwd=root)
    print("[state_utils] 首次提交: " + (r.stdout.strip().splitlines()[-1] if r.returncode == 0 else r.stderr.strip()))
    print("[state_utils] 提醒: 请在 GitHub 创建远端仓库后由用户自行执行:")
    print("    git remote add origin <仓库URL> && git push -u origin main   （AI 不代做推送）")


def refresh_dashboard(root):
    state = load_state(root)
    c = state.get("competition", {})
    nodes = state.get("nodes", {})
    gates = state.get("gates", {})
    rounds = state.get("rounds", [])
    rows = []
    for nid in NODES:
        home = node_homepage(root, nid)
        last_review = "-"
        if os.path.exists(home):
            with open(home, "r", encoding="utf-8") as f:
                in_review = False
                for ln in f:
                    if ln.startswith("## 5. 审阅记录"):
                        in_review = True
                        continue
                    if in_review and ln.startswith("## "):
                        break
                    if in_review and ln.startswith("|") and "声明已读" not in ln and "审阅 Agent" not in ln \
                            and not ln.startswith("|------") and not _is_placeholder_row(ln):
                        cells = [x.strip() for x in ln.strip().strip("|").split("|")]
                        if len(cells) >= 4:
                            last_review = f"{cells[3]}" + (f" | {cells[4][:30]}" if len(cells) >= 5 and cells[4] else "")
                        break
        s_keys = sorted(g for g in gates if g.startswith("S") and g.endswith(f"-{nid}"))
        gate_label = " / ".join(NODES[nid]["gates"]) or "-"
        if s_keys:
            gate_label += " / " + ",".join(s_keys)
        rows.append(f"| {nid} {NODES[nid]['name']} | {nodes.get(nid, {}).get('status', 'pending')} | {NODES[nid]['artifact']} | {last_review} | {gate_label} |")
    round_rows = []
    for r in rounds:
        sc = r.get("score") or {}
        dec = r.get("decision") or {}
        round_rows.append(
            f"| {r.get('node')} | {r.get('round')} | {r.get('branch') or '-'} | {sc.get('total', '-')} | {dec.get('action', '-')} | {dec.get('feedback') or r.get('goal') or '-'} |")
    pending_h = [g for g in ("H1", "H2", "H3") if gates.get(g, {}).get("status") not in ("confirmed",)]
    auto_h = [g for g in ("H1", "H2", "H3") if gates.get(g, {}).get("status") == "auto_passed"]
    next_node = "-"
    for nid in ("N0", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"):
        if nodes.get(nid, {}).get("status") == "pending":
            next_node = f"{nid} {NODES[nid]['name']}"
            break
    text = f"""# 状态工作栏（state/dashboard.md）

> 本页为总状态工作栏，由 orchestrator 通过 `python state/state_utils.py dashboard-refresh` 维护。
> 机器事实源为 `state/decision_log.json`（以 JSON 为准，本页为可读视图）。

## 竞赛信息

| 竞赛 | 年份 | 题号 | 语言 | 当前分支 | 最近提交 |
|------|------|------|------|---------|---------|
| {c.get('name', '-')} | {c.get('year', '-')} | {c.get('problem', '-')} | {c.get('language', '-')} | {git_current_branch(root)} | {git_last_commit(root)} |

## 节点卡片

| 节点 | 状态 | 产物 | 最近审阅结论 | 门禁 |
|------|------|------|-------------|------|
{chr(10).join(rows)}

## 迭代轮次总览

| 节点 | 轮次 | 分支 | 总分 | 决策 | feedback / 下轮 goal |
|------|:----:|------|:----:|------|----------------------|
{chr(10).join(round_rows) if round_rows else '| - | - | - | - | - | - |'}

## 待办

- next node: {next_node}
- 待人工确认: {', '.join(pending_h) if pending_h else '无'}{'（自动核查通过待追认: ' + ', '.join(auto_h) + '）' if auto_h else ''}
"""
    save_text_atomic(os.path.join(root, DASHBOARD_FILE), text)


# ---------------------------------------------------------------- 命令实现


def cmd_init(args):
    root = os.path.abspath(args.dir)
    # 目录名规范化：去除 GitHub zip 解压后缀（-main/-master），避免 `xxx-main\xxx-main` 嵌套形态
    base = os.path.basename(root.rstrip("/\\"))
    for suf in ("-main", "-master"):
        if base.endswith(suf):
            root = os.path.join(os.path.dirname(root.rstrip("/\\")), base[: -len(suf)])
            print(f"[state_utils] 目录名 {base} 含 GitHub 解压后缀 {suf}，已规范化为 {os.path.basename(root)}（禁止 xxx-main 嵌套目录）")
            base = os.path.basename(root)
            break
    # 命名红线：项目名/目录名禁止纯数字（如 01 / 000）
    if base.isdigit():
        sys.exit("[state_utils] 项目目录名不能为纯数字（如 01 / 000）。请使用有意义名称，如 2026_CUMCM_Problem_A 或 MathModel_Contest")
    if args.name and args.name.strip().isdigit():
        sys.exit("[state_utils] --name 项目名不能为纯数字（如 01 / 000）。请使用有意义名称，如 CUMCM_2026_A")
    os.makedirs(root, exist_ok=True)
    state_file = os.path.join(root, STATE_FILE)
    if os.path.exists(state_file) and not args.force and not args.sync_runtime:
        sys.exit("[state_utils] 项目已初始化（state/decision_log.json 已存在）。"
                 "如需重建请加 --force（⚠ 将清空全部 rounds/gates 状态，请先确认已备份）；"
                 "仅同步运行模块请使用 --sync-runtime")
    if args.force and os.path.exists(state_file):
        print("[state_utils] ⚠ --force: 将重建 decision_log/registry/cases/节点首页，已有状态会被清空")
    competition = {"name": args.name or os.path.basename(root), "year": args.year or "",
                   "problem": args.problem or "", "language": args.language or "zh", "git": args.git}
    scaffold(root, competition, force=args.force, sync_runtime=args.sync_runtime,
             runtime_source=args.runtime_source)
    print(f"[state_utils] init 完成: {root}")
    print("[state_utils] 已预建: decision_log / dashboard / registry / search_sources / cases / 9 份节点首页")
    print("[state_utils] 脚本已复制到 state/state_utils.py（项目内统一用: python state/state_utils.py <命令>）")


def cmd_dump(args):
    state = load_state(os.path.abspath(args.dir))
    print(json.dumps(state, ensure_ascii=False, indent=2))


def cmd_stage_set(args):
    root = os.path.abspath(args.dir)
    state = load_state(root)
    stage = state["stages"].get(args.key)
    if stage is None:
        sys.exit(f"[state_utils] 未知 stage key: {args.key}")
    stage["status"] = args.status
    if args.artifact:
        if args.artifact not in stage.setdefault("artifacts", []):
            stage["artifacts"].append(args.artifact)
    if args.decision:
        stage.setdefault("decisions", {})[now_iso()] = args.decision
    state["meta"]["current_stage"] = args.key
    save_state(root, state)
    print(f"[state_utils] stage {args.key} -> {args.status}")


def cmd_gate_set(args):
    root = os.path.abspath(args.dir)
    state = load_state(root)
    gate = state["gates"].setdefault(args.gate, {"status": "pending"})
    gate["status"] = args.status
    if args.agent:
        gate["agent"] = args.agent
    if args.result:
        gate["result"] = args.result
    gate["timestamp"] = now_iso()
    save_state(root, state)
    print(f"[state_utils] gate {args.gate} -> {args.status}")


def write_handoff(root, node):
    """生成/刷新节点交接文件 handoff.md：上游状态/门禁/产物哈希 + 本节点输入输出约定 + 待办 + 就绪判定。
    单独拉出某阶段执行时先读本文件自检（缺上游 → PREREQ-REQUEST）。"""
    state = load_state(root)
    info = NODES[node]
    nodes, gates = state.get("nodes", {}), state.get("gates", {})
    lines = [f"# {node}-{info['name']} 阶段交接文件（handoff）", "",
             f"> 生成时间: {now_iso()} ｜ 作用：本阶段独立拉出执行时的自检入口；机器事实源为 state/decision_log.json",
             "", "## 1. 本阶段信息", "",
             "| 项 | 值 |", "|----|----|",
             f"| 执行 Agent | {info['executor']} |",
             f"| 配对审阅 Agent | {info['reviewer'] or '-'} |",
             f"| 必读 Skill | {', '.join(info['skills']) or '-'} |",
             f"| 产物目录 | {info['artifact']} |",
             f"| 门禁 | {', '.join(info['gates']) or '-'} |",
             f"| 本节点状态 | {(nodes.get(node) or {}).get('status', 'pending')} |",
             "", "## 2. 上游交接（读入）", "",
             "| 上游节点 | 状态 | 审阅门禁 | 交接产物（sha256 前 12 位） |",
             "|---------|------|---------|---------------------------|"]
    ready = True
    for up_node, up_name in UPSTREAM.get(node, []):
        up_status = (nodes.get(up_node) or {}).get("status", "pending")
        up_gate = REVIEW_GATE.get(up_node)
        gate_status = (gates.get(up_gate) or {}).get("status", "pending") if up_gate else "-"
        if up_status != "completed":
            ready = False
        if up_gate and gate_status not in {"PASS", "auto_passed", "confirmed"}:
            ready = False
        arts = []
        for p in [x.strip() for x in NODES[up_node].get("artifact", "").split(",") if x.strip()]:
            full = os.path.join(root, p)
            arts.append(f"{p}" + (f"({sha256_of(full)[:12]})" if os.path.isfile(full) else "(缺失)"))
        lines.append(f"| {up_node} {up_name} | {up_status} | {up_gate or '-'}={gate_status} | {', '.join(arts) or '-'} |")
    lines += ["", "## 3. 本阶段输入与输出约定", "",
              f"- 输入：上游产物（上表所列文件，读取时以 sha256 校验）；题目事实：state/problem_lock.json",
              f"- 输出：{info['artifact']}（唯一输出口；论文级图片/表格按各 Skill 约定）",
              "- 完成标准：产物齐备 + 独立审阅 PASS（门禁落盘）；迭代节点由 round-decide 裁决", "",
              "## 4. 待办与小步骤", "",
              "- 本节点待办：见 state/todo.md 中 [Nx] 条目（todo plan 自动维护）",
              "- 小步骤时间线：state/nodes/<本节点>/steps.md（node-log 追加）", "",
              "## 5. 就绪判定", "",
              f"- 就绪: {'✅ ready（可开工）' if ready else '❌ blocked（缺上游：状态未 completed 或审阅门禁未过）'}"]
    if not ready:
        lines.append("- 处理：先补跑上游（派发上游执行 Agent 完成'审阅→修改→再审阅'循环），再回来开工本阶段；"
                     "或输出 [PREREQ-REQUEST]")
    handoff = os.path.join(root, STATE_DIR, "nodes", info["dir"], "handoff.md")
    save_text_atomic(handoff, "\n".join(lines) + "\n")
    return handoff


def cmd_handoff(args):
    root = os.path.abspath(args.dir)
    require_node(args.node)
    handoff = write_handoff(root, args.node)
    print(f"[state_utils] handoff: 交接文件已生成 -> {os.path.relpath(handoff, root)}")


def cmd_handover_review(args):
    """接手复核（加载/完整阅读已有项目后必跑）：先按 9 个阶段逐节点检查；
    已完成节点不直接信任——生成"复核→修改→复审"序列（门禁未过或产物漂移者强制复核）；
    in_progress 节点补完审阅-修改循环；pending 节点列为待执行。同步修改用 cascade-invalidate --apply 联动。"""
    root = os.path.abspath(args.dir)
    if not os.path.exists(os.path.join(root, STATE_FILE)):
        sys.exit(f"[state_utils] 项目未初始化：{root}；请先运行 init")
    state = load_state(root)
    nodes, gates = state.get("nodes", {}), state.get("gates", {})
    plan = {"project": root, "checked_at": now_iso(), "nodes": {}, "summary": {}}
    for nid, info in NODES.items():
        if nid == "N0":
            continue
        status = (nodes.get(nid) or {}).get("status", "pending")
        entry = {"status": status, "executor": info["executor"], "reviewer": info["reviewer"] or "-",
                 "gates": info["gates"]}
        if status == "completed":
            gate_id = REVIEW_GATE.get(nid)
            gate_status = (gates.get(gate_id) or {}).get("status", "pending") if gate_id else "N/A"
            recorded = (nodes.get(nid) or {}).get("artifact_hash") or {}
            current = artifact_snapshot(root, nid)
            drift = current != recorded
            entry["gate"] = f"{gate_id or '-'}={gate_status}"
            entry["artifact_drift"] = drift
            if gate_status not in {"PASS", "auto_passed", "confirmed"} or drift:
                entry["action"] = "🔴 强制复核：审阅→修改→再审阅（门禁未过或产物漂移）"
            else:
                entry["action"] = "复核确认：配对审阅 Agent 审阅已过内容（发现问题→修改→复审）"
        elif status in {"in_progress", "review_pending"}:
            entry["action"] = "继续执行：补完'审阅→修改→再审阅'循环"
        else:
            entry["action"] = "待执行：前置（上游 completed + 门禁 PASS）就绪后开工"
        plan["nodes"][nid] = entry
    forced = [nid for nid, e in plan["nodes"].items() if "强制复核" in e["action"]]
    plan["summary"] = {
        "completed_nodes": sum(1 for e in plan["nodes"].values() if e["status"] == "completed"),
        "forced_review": forced,
        "note": ("已完成 ≠ 跳过：全部 completed 节点必须过配对审阅复核；发现问题的按"
                 "'审阅→修改→再审阅'循环修改，修改后运行 cascade-invalidate --apply 同步联动下游并复验"
                 "（state_utils.py handover-review → 逐节点复核 → cascade-invalidate → project-audit 复检）"),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))


