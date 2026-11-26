---
name: mm-algorithm-dev
description: "CUMCM算法开发规范：Code 标准目录结构、Python环境要求、代码注释规范（与ModelDocs/formula.md公式对应）、运行验证Checklist、requirements.txt模板、唯一输出口 output/。触发词：代码开发, 算法实现, algorithm development, 写代码, 代码规范"
metadata:
  version: "1.2.0"
  last_updated: "2026-08-19"
  status: active
  related_skills:
    - mathematical-modeling
    - mm-iteration-engine
    - mm-model-library
    - mm-model-tuning
---

【范围】竞赛算法实现与公式核对。一般软件开发用 coder 通用开发模式或 TDD 流程。

# MM Algorithm Development — 算法开发规范

国赛数学建模竞赛代码开发的规范标准，覆盖**Code 标准目录结构**、环境配置、注释规范（与 ModelDocs/formula.md 公式对应）与验证流程。

---

## Quick Start

```
帮我写代码实现这个模型
```
```
代码怎么组织？
```
```
国赛代码规范
```

---

## Trigger Conditions

### Trigger Keywords

- **中文**: 代码开发, 算法实现, 写代码, 代码规范, 项目结构, requirements
- **English**: algorithm development, code implementation, coding standard, project structure

### Does NOT Trigger

| Scenario | Use Instead |
|----------|-------------|
| 模型选型 | `mm-model-library` |
| 模型调参 | `mm-model-tuning` |
| 画图 | `mm-visualization` |

---

## 竞赛代码目录结构规范（Code 标准，对齐 mm-iteration-engine §1）

```
Code/                            # 代码根（标准项目结构，由 state_utils.py init 生成）
├── config.py                    # 全局参数、路径、超参配置（铁律：禁硬编码，所有参数集中此处）
├── main.py                      # 统一入口：串联全流程，输出只落 output/
├── requirements.txt             # 依赖清单
├── README-Code.md               # 代码运行说明、依赖版本
│
├── utils/                       # 通用工具库
│   ├── __init__.py
│   ├── data_io.py               # 数据读写（从 Data/raw/ 读，处理后写 Data/processed/）
│   ├── preprocess.py            # 数据清洗与特征工程
│   ├── metrics.py               # 指标计算
│   ├── logger.py                # 日志
│   └── model_utils.py           # 模型通用工具（保存/加载/交叉验证）
│
├── problem_1~4/                 # 分题求解模块（每问独立可运行）
│   ├── __init__.py
│   ├── pX_solver.py             # 核心求解代码（注释引用 ModelDocs/formula.md 公式编号）
│   ├── pX_analysis.py           # 结果分析、误差分析
│   └── pX_param.py              # 单题专属参数配置
│
├── visualization/               # 可视化模块（输出到 output/figures/）
│   ├── __init__.py
│   ├── vis_p1~4.py
│   └── utils/plot_base.py       # 绘图基础设置（中文 SimHei / 300dpi / 配色）
│
└── output/                      # 🔴 唯一输出口（运行表格/图片/文本/模型只写此目录）
    ├── tables/                  # 输出表格 csv/excel
    ├── figures/                 # 输出图片（PDF/PNG，≥300dpi，语义命名 figN_描述.png）
    ├── txt_result/              # 运行日志、关键数字文本
    └── model_save/              # 训练好的模型权重/文件
```

> **铁律**：① 代码只写 `Code/output/`（唯一输出口）；② 论文级图片由 visualization agent 精选到 `ResultFigures/`；③ `Data/raw/` 原始数据只读不修改；④ **文件名禁止纯数字**（如 `000.png`、`main_v000.pdf`、`01.csv`），一律语义命名（`fig1_results.png`、`p1_solver.py`）；⑤ 运行前必须建 venv（见下）。

---

## Python 环境要求

### 推荐版本
- Python 3.9 ~ 3.11（国赛机房常见版本）
- 避免使用 3.12+ 新语法（兼容性风险）

### 🔴 虚拟环境（venv）铁律
- **运行任何代码前必须创建并激活虚拟环境**，禁止直接使用系统 Python 全局环境：
  - Windows: `python -m venv .venv` → `.venv\Scripts\activate`
  - macOS/Linux: `python3 -m venv .venv` → `source .venv/bin/activate`
- 激活后安装依赖：`pip install -r Code/requirements.txt`
- `.venv/` 已加入 .gitignore（不入库）；换机/换人必须重新建 venv 再复现

### 核心依赖库

| 类别 | 库名 | 用途 | 最低版本 |
|------|------|------|---------|
| **基础计算** | numpy | 数值计算 | 1.21+ |
| **数据处理** | pandas | 表格数据处理 | 1.3+ |
| **科学计算** | scipy | 优化/统计/插值 | 1.7+ |
| **机器学习** | scikit-learn | 分类/回归/聚类 | 1.0+ |
| **统计模型** | statsmodels | 时序分析/统计检验 | 0.13+ |
| **线性优化** | pulp | 线性/整数规划 | 2.5+ |
| **约束优化** | ortools | 组合优化/调度 | 9.0+ |
| **绘图** | matplotlib | 基础绑图 | 3.5+ |
| **统计绘图** | seaborn | 统计可视化 | 0.11+ |
| **中文显示** | matplotlib 内置 | SimHei/SimSun 字体 | - |

### 可选依赖

| 库名 | 用途 |
|------|------|
| torch / tensorflow | 深度学习（LSTM/CNN等） |
| xgboost | 梯度提升树 |
| prophet | Facebook 时序预测 |
| networkx | 图论算法 |
| deap | 遗传算法 |
| missingno | 缺失值可视化 |

---

## requirements.txt 模板

```txt
# CUMCM 数学建模 - 依赖清单
# Python 3.9+

# 基础计算
numpy>=1.21.0
pandas>=1.3.0
scipy>=1.7.0

# 机器学习
scikit-learn>=1.0.0
statsmodels>=0.13.0

# 优化求解
pulp>=2.5.0
ortools>=9.0.0

# 可视化
matplotlib>=3.5.0
seaborn>=0.11.0

# 可选（按需启用）
# torch>=1.12.0
# xgboost>=1.5.0
# networkx>=2.6.0
# deap>=1.3.0
```

---

## 代码注释与公式对应规范

### 注释层级

```python
"""
模块级注释：说明本模块的数学背景和算法原理
例如：本模块实现灰色预测 GM(1,1) 模型
参考：邓聚龙《灰色系统理论》
"""

# === 第一步：级比检验 ===
# 公式：lambda(k) = x^(0)(k-1) / x^(0)(k), k=2,...,n
# 判据：所有 lambda(k) 属于 (e^(-2/(n+1)), e^(2/(n+1)))
def step1_grade_ratio_test(data):
    """
    级比检验
    输入: data - 原始数据序列 x^(0)
    输出: bool - 是否通过级比检验
    数学公式: lambda(k) = x^(0)(k-1) / x^(0)(k)
    """
    # ...实现...
    pass
```

### 注释规范表

| 层级 | 格式 | 示例 |
|------|------|------|
| 模块 | `"""..."""` 三引号 | 数学背景、算法来源 |
| 函数 | `"""..."""` docstring | 输入/输出/公式 |
| 关键步骤 | `# === 步骤名 ===` | `# === 灰色生成 ===` |
| 公式 | `# 公式: ...` | `# 公式: y = wx + b` |
| 行内 | `# 说明` | `# 防止除零` |

### 变量命名规则

| 类型 | 命名规则 | 示例 |
|------|---------|------|
| 矩阵 | 大写或 `mat_` 前缀 | `A`, `mat_distance` |
| 向量 | 小写或 `vec_` 前缀 | `b`, `vec_weights` |
| 标量 | 语义命名 | `learning_rate`, `alpha` |
| 数据框 | `df_` 前缀 | `df_raw`, `df_clean` |
| 函数 | 动词+名词 | `calculate_distance`, `build_model` |
| 类 | PascalCase | `GreyPrediction`, `NetworkOptimizer` |

---

## 运行验证 Checklist

### 代码层面

- [ ] **已创建并激活虚拟环境（`python -m venv .venv` + 激活）**，依赖装于 venv 内
- [ ] 无语法错误（`python -m py_compile main.py`）
- [ ] 所有 import 可用（venv 内 `pip install -r requirements.txt` 后测试）
- [ ] 无硬编码路径（使用相对路径 `os.path.join`）
- [ ] 无 `print` 调试语句残留（改用 `logging`）
- [ ] 数值计算有防零/防溢出保护

### 结果层面

- [ ] 输出结果数量级合理
- [ ] 与论文中描述一致
- [ ] 运行时间可接受（< 30 分钟）
- [ ] 随机种子已固定（`np.random.seed(42)`）
- [ ] 多次运行结果一致（随机种子生效）

### 性能与实现时间层面（🔴 写完代码必须自审，见下节"算法性能与实现时间自审"）

- [ ] 已实测关键步骤运行时间并记录（`time` / `timeit` / 代码内计时，写入 `Code/output/txt_result/`）
- [ ] 已做复杂度分析（大 O 注释或报告说明）
- [ ] 热点已定位并说明优化收益（预计提速 vs 预计实现时间）
- [ ] 若使用 GPU：验证了正确加载（cuda 检查/device 统一/无逐元素同步）与正确搜索（faiss/topk/cKDTree 选型），且与 CPU 基线结果一致
- [ ] 运行已达标时不强行过度优化；未达标时已按"优化阶梯"逐级优化

### 可复现性

- [ ] `requirements.txt` 完整
- [ ] 数据文件路径正确（相对路径）
- [ ] 随机种子设置
- [ ] 关键参数有注释说明
- [ ] 运行环境说明（Python 版本、操作系统）

---

## main.py 标准模板

```python
"""
CUMCM 数学建模 - [题目名称]
主入口文件：串联数据预处理 → 模型训练 → 评估 → 可视化。
所有路径与参数从 config.py 读取，运行结果只写 output/（唯一输出口）。

参考：`ModelDocs/formula.md` 中对应公式编号（写入核心函数 docstring）。
"""

import os
import sys
import numpy as np
import pandas as pd
import config
from utils.data_io import load_data, save_output
from problem_1.p1_solver import solve_problem_1
from problem_1.p1_analysis import analyze_problem_1

# 固定随机种子，确保可复现
np.random.seed(config.RANDOM_SEED)


def main() -> None:
    """统一入口：按题号分题求解 + 输出到 output/。"""
    # 1. 数据加载与预处理（路径来自 config.py）
    df = load_data(os.path.join(config.DATA_DIR, "raw", "raw_data.csv"))
    # ... 调用 problem_*/p*_preprocess ...

    # 2. 模型构建与求解（每题独立模块）
    results_1 = solve_problem_1(df)
    # ... results_2/3/4 ...

    # 3. 结果分析与可视化
    analyze_problem_1(results_1)
    # ... visualization/vis_p* ...

    # 4. 输出落 Code/output/
    save_output(results_1, os.path.join(config.OUTPUT_DIR, "txt_result", "problem_1.txt"))
    # 产物示例路径：
    #   Code/output/tables/         ← 表格 csv/excel
    #   Code/output/figures/        ← 图片（PDF/PNG，论文级图由 visualization 精选到 ResultFigures/）
    #   Code/output/txt_result/     ← 文本/运行日志
    #   Code/output/model_save/     ← 训练好的模型


if __name__ == "__main__":
    main()
```

---

## 算法性能与实现时间自审（🔴 写完代码必须执行，纳入 result.json 报告）

**目的**：除了查错，还要兼顾"算法跑得快不快"与"优化花了多少实现时间"。竞赛 72 小时，时间就是分数：运行太慢 → 迭代/敏感性分析跑不动；优化过度 → 浪费写作与建模时间。写完代码立即自审，把结论写进 `state/agents/coder/result.json` 的 `performance_review` 字段。

### 1. 时间预算（先定预算再优化）

| 环节 | 建议预算 |
|------|---------|
| 单题求解器单次运行 | ≤ 5 分钟（含读取数据） |
| 全流程 main.py 一次跑通 | ≤ 30 分钟 |
| 敏感性/参数扫描 | ≤ 2 小时（超预算 → 换更快的代理模型或并行） |
| 每项优化投入的实现时间 | ≤ 1 小时（超过则降级方案） |

### 2. 性能审查流程（先测后优，禁止凭感觉优化）

1. **计时**：先测后改——记录每个关键函数耗时（`time.perf_counter()` 包裹 / `timeit` / 运行 `python -m cProfile main.py`），输出到 `Code/output/txt_result/perf_report.txt`；
2. **定位热点**：耗时占比 > 20% 的函数就是热点（cProfile 的 tottime / cumtime）；小数据量测试正确性，大数据量测性能；
3. **复杂度分析**：为热点函数标注大 O（如 `O(n²)` → 能降到 `O(n log n)` 就值得做）；
4. **优化阶梯**：从便宜到昂贵逐级尝试，**每级先确认是否已达标，达标即停**：

| 级别 | 手段 | 适用场景 | 成本 |
|:----:|------|---------|------|
| 1 | 算法级：剪枝 / 提前终止 / 缓存（`functools.lru_cache`）/ 避免重复计算 | 循环里重复算同一结果 | 低 |
| 2 | 向量化：numpy 广播 / 矩阵运算替代 for 循环 | 数值计算热点 | 低 |
| 3 | 编译加速：numba `@njit`（纯数值函数）/ Cython | 无法向量化的逐元素循环 | 中 |
| 4 | 多核并行：`multiprocessing` / `joblib` | 独立子任务（参数扫描、多题并行） | 中 |
| 5 | GPU：torch / cupy（见下节） | 矩阵运算为主 / 数据量大 / 深度学习 | 高（仅在确实需要时） |

5. **验证不破坏正确性**：每级优化后重跑，与优化前结果对比（数值误差 < 1e-6 或与公式一致），保证"优化 ≠ 改错"。

### 3. GPU 加速规范（能用才用，用就要用对）

**何时用 GPU**：矩阵运算为主、数据量 ≥ 10⁵ 行/样本、或使用深度学习模型（LSTM/CNN/Transformer）；**何时不用**：数据量小（< 10⁴）、瓶颈在 I/O 或单次小矩阵调用——GPU 的显存搬运/内核启动开销大于收益，盲目用反而更慢（CPU 秒级完成的任务不要上 GPU）。

**正确加载（"正确地加载"）**：

```python
import torch

# ① 检查可用性 + device 统一管理（禁止写死 cuda）
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# ② 数据与模型统一 .to(device)，一次搬运批量计算，禁止循环内来回搬
X = torch.as_tensor(df.values, dtype=torch.float32, device=device)
# ③ 大批量数据用 DataLoader 正确加载：num_workers 多进程预读 + pin_memory 加快拷贝
from torch.utils.data import DataLoader, TensorDataset
loader = DataLoader(TensorDataset(X, y), batch_size=1024, shuffle=True,
                    num_workers=os.cpu_count() // 2, pin_memory=device.type == "cuda")
# ④ 推理/评估用 torch.no_grad()，关掉梯度图省显存与时间
with torch.no_grad():
    pred = model(batch)
# ⑤ 禁止逐元素 CPU-GPU 同步（.item()/numpy() 进循环会卡死性能）——统计先 torch 内归约，最后一次性取出
```

**正确搜索（"正确地搜索"）**：

- **大规模最近邻 / 相似度搜索**（数据点 ≥ 10⁵）：用 `faiss`（`faiss.IndexFlatL2`/`IndexIVFFlat`，支持 GPU：`faiss.index_cpu_to_all_gpus`）或 `torch.cdist(x, y).topk(k)` 批量计算，禁止写双重 for 循环；
- **中小规模**（< 10⁵）：`scipy.spatial.cKDTree`（`O(n log n)` 建树 + 快速 query）或 numpy 向量化 `topk`；
- **距离矩阵避免全量 O(n²)**：能只查最近 k 个邻居就不要算完整矩阵（内存也从 O(n²) 降到 O(nk)）；
- **组合优化 / 网格搜索**：把候选方案并行批量评估（GPU 一次 forward 评估 N 个候选），而不是逐个循环；
- **选型理由写进代码注释与自审报告**（用了什么、为什么、结果与 CPU 基线是否一致）。

### 4. 实现时间权衡（优化 ROI 决策）

| 场景 | 决策 |
|------|------|
| 运行已达标（≤ 预算） | **不再优化**，直接交付；把省下的时间给建模/写作 |
| 热点明确 + 优化成本低（向量化/剪枝） | 立即做（投入 ≤ 30 分钟） |
| 需要 GPU/重写（成本高） | 先估算：预计提速 ≥ 5 倍且能跑通 → 做；否则记录"建议项"留给后续轮次 |
| 优化引入新 bug / 结果不一致 | 回退优化，恢复可交付版本，绝不带病提交 |
| 迭代轮次剩余时间不足 | 停止优化，保住正确结果（正确性 > 性能 > 炫技） |

### 5. 自审报告（写入 result.json）

```json
"performance_review": {
  "baseline_seconds": 312,
  "optimized_seconds": 45,
  "speedup": 6.9,
  "hot_spots": ["distance_matrix O(n^2) -> faiss IndexFlatL2"],
  "gpu_used": false,
  "gpu_note": "数据量 2e4 小于阈值，CPU 向量化已达标，无需 GPU",
  "optimization_roi": [{"change": "numpy 广播", "impl_minutes": 15, "speedup": 8.3}],
  "result_unchanged": true,
  "next_candidates": ["参数扫描并行化（预算充足时）"]
}
```

> 该字段是 mm-code-reviewer 效率维度评分（efficiency）的证据来源之一；缺失 = 效率维度按证据不足给分。

---

## Anti-Patterns

| # | 反模式 | 后果 | 正确做法 |
|---|--------|------|---------|
| 1 | 全部代码写在一个文件 | 难以调试和维护 | 按功能分模块 |
| 2 | 不固定随机种子 | 每次结果不同 | `np.random.seed(42)` |
| 3 | 硬编码绝对路径 | 换电脑就报错 | 相对路径 + `os.path` |
| 4 | 不写注释直接提交 | 评委无法理解 | 每步对应公式注释 |
| 5 | 不处理异常 | 运行中断 | try-except + 日志 |
| 6 | print 代替 logging | 调试信息混乱 | 使用 `logging` 模块 |
| 7 | 不建 venv 直接用系统 Python | 依赖污染、不可复现 | 先 `python -m venv .venv` 再装依赖 |

---

## References

| 资源 | 说明 |
|------|------|
| `mm-iteration-engine/SKILL.md` | 状态统一节点 + 迭代循环（SEARCH 案例搜索 / commit trailer / 评分） |
| `mm-model-library/SKILL.md` | 模型选型 |
| `mm-model-tuning/SKILL.md` | 调参规范（三份报告落 `ModelDocs/`） |
| `mm-visualization/SKILL.md` | 可视化规范 |
| `ModelDocs/formula.md` | 公式推导（代码核心函数 docstring 必引用对应公式编号） |
| `mathematical-modeling/SKILL.md` | 全流程总控 |
| PEP 8 | Python 编码规范 |

---

## Pro 知识库融合（v1.7.0）：代码骨架库

> 融合自 math-modeling-skill-pro（作者授权）：8 类可运行 Python 起始骨架，输入→预处理→拟合/求解→评估→输出的模块化分层。

### 资产位置
- `skills/mm-algorithm-dev/assets/pro/code-skeletons/`：prediction（泄漏安全预测流水线+朴素基线）、evaluation（多指标综合评价 MCDA）、optimization（优化问题结构+约束断言）、clustering、machine-learning（监督学习）、network（网络模型）、mechanism（ODE 机理模型）、simulation（Monte Carlo）

### 使用时机
N4 代码实现：选最接近问题结构的骨架作为起点，按实际 schema 与假设适配；每个骨架保留随机种子固定、防泄漏切分、配置记录、维度/单位/边界/可行性断言。

### 与既有流程的关系
- 本技能已有的实现规范（公式-代码一致性、`Code/output/` 唯一输出口、运行验证）不变；骨架仅提供起始模板，不替代规范。
- 骨架中的基线（如 LastValueForecast）是竞赛最低对比要求，不得删除以省事。

### 回退
骨架与具体赛题结构不符时，以本技能既有实现规范为准自行组织代码，不得为了套骨架而扭曲问题结构。
