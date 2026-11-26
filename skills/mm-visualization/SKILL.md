---
name: mm-visualization
description: "CUMCM竞赛图表规范：分辨率/格式/中文字体要求、图表类型选型指南、matplotlib配置代码、图注/坐标轴模板、常见错误黑名单、产物 output/figures → ResultFigures 精选入库。触发词：画图, 可视化, visualization, matplotlib, 图表, 生成图表"
metadata:
  version: "1.2.0"
  last_updated: "2026-08-19"
  status: active
  related_skills:
    - mathematical-modeling
    - mm-algorithm-dev
    - mm-iteration-engine
---

【范围】仅用于竞赛论文图表规范（CUMCM 分辨率/中文字体/入库要求）。若只是普通论文、报告、演示文稿需要绘图，用 visualization（出版级 APA 标准）或对应交付 skill；不要套用竞赛入库规则。

# MM Visualization — 竞赛图表规范

## 🔴 加载资格与委托守则（必须读）

本技能是 **可视化（visualization）子代理** 的专项规范，**仅供 `visualization` 子代理加载执行**。

- 若你是主对话主 agent：需要生成/修改竞赛图表时，派发 `subagent_type=visualization` 子代理；**不得自己加载本技能直接画图**。
- 图表完成 → `mm-viz-reviewer` 核对（V1 门禁）→ 精选入库 `ResultFigures/`。

国赛(CUMCM)数学建模竞赛图表制作规范，覆盖格式要求、类型选型、代码模板与常见错误。**产物**：`Code/output/figures/`（唯一输出口）→ 论文级图片精选入库 `ResultFigures/` + `figure-list.md` 维护（与 visualization agent + mm-viz-reviewer 配合）。

---

## Quick Start

```
帮我画个图
```
```
生成结果可视化
```
```
国赛图表规范
```

---

## Trigger Conditions

### Trigger Keywords

- **中文**: 画图, 可视化, 图表, 生成图, 画柱状图, 画折线图, matplotlib, 绑图
- **English**: visualization, plot, chart, figure, matplotlib, generate chart

### Does NOT Trigger

| Scenario | Use Instead |
|----------|-------------|
| 代码实现（非画图） | `mm-algorithm-dev` |
| 论文排版 | `mm-latex-writing` |

---

## 国赛图表硬性规范

### 🔴 可视化前置决策链（模型/数据→检索→定型→绘图）

可视化不是先画图再寻找解释。必须按以下顺序执行：

1. **需求与证据**：结合实际研究需求、已确定的数学模型和实际数据，明确要展示的对象、比较关系、趋势/分布/空间结构和评价指标；模型或数据未锁定时不得绘图。
2. **学术方案检索**：调用论文搜索 MCP，必要时用 Tavily/WebSearch/Context7，检索同类模型和数据的学术可视化方案；记录检索式、来源、候选图形、优缺点和适用条件，沉淀知识卡片与调用留痕。
3. **方案定型**：由 orchestrator/visualization 根据数据类型、模型含义、竞赛版式、可读性和复现成本确定图形类型、编码变量、颜色、子图布局、标题和注释；形成可视化清单后才允许绘图。
4. **绘图与复核**：按定型方案生成图，输出到 `Code/output/figures/`，再精选到 `ResultFigures/`；mm-viz-reviewer 核对数据同源、分辨率、字体、编号、题注和可读性。禁止先生成“好看但无模型/数据依据”的图。

### 🔴 图-文-数据三方一致性自检（绘制后必做，防"图与算法/数据脱钩"）

图必须**严格由算法实际运行输出直接绘制**：读取输出文件的完整记录生成（如 PSO 150 代 → 150 个点），禁止用估算/手写/仅取头部片段冒充完整轨迹，禁止先画图再倒推解释。绘制完成后逐项自检，任何一项不过即修复后再交 V1：

| 检查项 | 判定 |
|---|---|
| **坐标轴范围 = 数据/正文声称范围** | 正文称最大迭代 K=150，横轴必须覆盖 0~150；若只展示前 10 代，标题/题注必须显式标注"前 N 代/局部"并删除与完整长度冲突的表述，否则 FAIL |
| **关键事件标记存在且位置正确** | 正文声称重启点 k=41、k=81，图中必须有对应竖线/星标/分段标记且落位正确（在本轴上可见）；声称的收敛阈值、切换点同理 |
| **曲线形态符合算法预期** | 收敛曲线应随迭代下降/按算法定义演化；曲线平直、贴 0、无变化时必须核对数据是否只含局部片段或读取错误，不得直接放行 |
| **图例-曲线-正文一致性** | 图例项数 = 曲线/系列实际数；图例名称与正文术语一致（如 "Fitness(F)"、"Adaptive restart(k=41)"）；无正文未提及的悬空图例 |
| **数据点/行数与输出文件一致** | 点密度/行数与输出记录行数对应（150 行 ↔ 150 点）；抽样比对图中数值与输出文件逐行一致 |
| **标题不含未标注的"完整/全程/收敛轨迹"字样** | 实际为片段时不得标"完整收敛轨迹"；确需展示局部须改题为 "…(前 N 代)" 并在正文同步去掉与完整长度冲突的表述 |

> 自检结果随图写入 `figure-list.md` 的对应列并在 scope evidence（`state/reviews/`）留痕；mm-viz-reviewer 对未通过项 FAIL 并返回 visualization 按实际输出重绘后复审。

### 数据来源四类判定（🔴 图表和正文必须一致）

| 数据类别 | 图表/正文标注 | 支撑材料与引用要求 |
|---|---|---|
| 赛题直接给出的原始数据 | 通常不重复写“数据来源”；不得伪称外部公开数据 | 按当年竞赛要求处理；不要把赛题原始数据冒充外部资料放入参考文献或附录 |
| 外部公开/文献/网页/数据库数据 | 必须写机构/数据集/报告/日期或访问时间的简短图注/表注，并在正文引用、文末按 GB/T 7714 著录；禁止“来源于网络” | 原始数据集或可复现下载说明纳入支撑材料压缩包 |
| 代码仿真/模型输出数据 | 必须说明“本文模型计算/仿真得到”，不能伪装成真实观测或公开数据 | 附录提供完整可运行代码、参数和随机种子；不作为外部文献引用 |
| 问卷/实地调研一手数据 | 写明调研时间、地点/方式和有效样本量 | 保留调查设计、匿名原始数据或可核验汇总及处理说明 |

🔴 图表注释禁止直接暴露 `Code/output/`、`ModelDocs/`、`*.txt`、`*.xlsx`、`*.log` 等内部路径；内部路径只作为 scope evidence 留在 `state/reviews/`，不得进入论文题注、表注或正文。

🔴 **图注“少而精”**：同源数据在首次或正文统一说明一句即可，后续同源图不再逐图重复；不得出现"完整代码见附件、按式(x)复核、图示位置按代码输出绘制、不在本文重复"等重复/内务话术；多数图可不带"数据来源"字样。行数/子图/曲目按该图实际表达的数据实体组织，不为凑对齐补空项。

### 官方格式约束（全国大学生数学建模竞赛组委会《论文格式规范》）

| 项目 | 要求 |
|------|------|
| 摘要页 | 电子版论文首个内容页为摘要专用页；摘要（含标题和关键词）不超过一页；承诺书/编号页如需提交由提交版本单独处理 |
| 正文页数 | 采用 `shared/contracts/submission/cumcm_2026_format_profile.json`：正文从 PDF 第4页起计 ≤30 页；摘要页单独≤1页，附录不限；年度官方规则更新时只改 profile，不在各 Skill 中分散改数字 |
| 页面设置 | A4 白纸，页边距上下左右至少 2.5cm，左侧装订 |
| 电子版 | 单独 PDF/Word 文件，≤20MB，第一页为摘要专用页，与纸质版完全一致 |
| 匿名性 | 摘要/正文/附录及**图表中**不得出现参赛者身份、学校、赛区信息（注意水印/文件名） |
| 支撑材料 | RAR/ZIP ≤20MB，须含全部可运行源程序代码；**支撑材料与论文不符、缺程序或程序不可运行 → 可能取消评奖资格**（图表数字与代码输出不一致即触碰此红线） |

### 竞赛图表硬性规范（经验共识 + 出版级惯例）

| 项目 | 要求 |
|------|------|
| 分辨率 | >= 300 dpi（印刷级；位图 PNG；线稿可更高） |
| 输出格式 | PDF（矢量，LaTeX 首选）或 PNG（位图 ≥300dpi） |
| 中文字体 | SimHei（黑体）或 SimSun（宋体），`axes.unicode_minus=False` |
| 图号 | 连续编号：图1, 图2, 图3 ...（正文按序引用，不得断号/跳号） |
| 表号 | 连续编号：表1, 表2, 表3 ... |
| 图注 | 图下方居中，格式："图N 对象+内容"；简洁直接，数据来源/补充说明另列左对齐“注：”行 |
| 表注 | 表上方居中，格式："表N 对象+内容"；数据来源另列简短“注：”行，不把内部文件路径写入论文 |
| 坐标轴 | 必须有轴标签和单位（"时间 (天)"、"产量 (吨)"） |
| 图幅 | 单栏 ~8cm / 双栏 ~16cm（Nature 标准 90/180mm），高度 6-10cm；像素 = 英寸 × dpi |
| 图表数量 | 无官方规定；经验：全文 15-25 张图，正文平均每页 0.5-1 张，避免整页堆图或全程无图 |
| 自明性 | 每张图不读正文也能理解：图注交代内容与结论、坐标轴含单位、图例区分系列 |

---

## matplotlib 中文配置代码

```python
import matplotlib.pyplot as plt
import matplotlib

# ========== 方案一：SimHei（最常用） ==========
plt.rcParams['font.sans-serif'] = ['SimHei']      # 中文显示
plt.rcParams['axes.unicode_minus'] = False         # 负号显示

# ========== 方案二：Windows 系统字体路径 ==========
import matplotlib.font_manager as fm
font_path = 'C:/Windows/Fonts/simhei.ttf'
fm.fontManager.addfont(font_path)
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ========== 方案三：通用配置（兼容性最好） ==========
plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'Microsoft YaHei', 'DejaVu Sans'],
    'axes.unicode_minus': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'lines.linewidth': 1.5,
    'axes.linewidth': 0.8,
})

# ========== 方案四：出版级 rcParams（批量出图统一风格，放 plot_base.py 共享） ==========
plt.rcParams.update({
    'font.size': 10,                 # 全局基准字号
    'axes.labelsize': 11,            # 轴标签 10-12pt
    'xtick.labelsize': 9,            # 刻度标签 8-10pt
    'ytick.labelsize': 9,
    'axes.titlesize': 13,            # 标题 12-14pt
    'legend.fontsize': 10,           # 图例 9-10pt
    'lines.linewidth': 1.5,          # 数据线宽
    'lines.markersize': 6,           # marker 大小
    'axes.grid': False,              # 网格默认关，需要时 ax.grid(True, alpha=0.3)
    'figure.figsize': (6.4, 4.8),    # 英寸；出图宽度 = 目标印刷宽度(cm)/2.54 × 300dpi
})
```

---

## 图表类型选型指南

### 选型速查表

| 数据关系 | 推荐图表 | 适用场景 | 示例 |
|---------|---------|---------|------|
| 趋势变化 | **折线图** | 时间序列、连续变化 | 股价走势、温度变化 |
| 类别对比 | **柱状图** | 离散类别数值对比 | 各方案成本对比 |
| 分布特征 | **直方图/箱线图** | 数据分布、异常值 | 评分分布、收入分布 |
| 相关关系 | **散点图** | 两变量关系 | 面积与价格关系 |
| 矩阵关系 | **热力图** | 相关系数、混淆矩阵 | 特征相关性 |
| 占比构成 | **饼图/环形图** | 少量类别占比（<6） | 能源结构占比 |
| 多维对比 | **雷达图** | 多指标综合评价 | 方案综合评分 |
| 空间分布 | **地理图/3D图** | 空间数据 | 污染物分布 |
| 流程关系 | **流程图** | 算法流程、系统架构 | 建模流程 |
| 层次结构 | **思维导图** | 问题分解、方案层次 | 问题分析结构 |
| 网络关系 | **网络图** | 节点连接关系 | 交通网络 |

### 选型决策树

```
你的数据要表达什么？
│
├─ 变化趋势？ → 折线图
│   └─ 多条趋势？ → 多系列折线图 + 图例
│
├─ 类别对比？ → 柱状图
│   └─ 堆叠？ → 堆叠柱状图
│
├─ 分布？ → 直方图（连续）/ 饼图（分类）
│
├─ 两变量关系？ → 散点图
│   └─ 第三维？ → 散点图 + 颜色/大小映射
│
├─ 矩阵数据？ → 热力图
│
├─ 多指标评价？ → 雷达图
│
└─ 流程/架构？ → 流程图/架构图
```

---

## 图表代码模板

### 模板 1：折线图

```python
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(8, 5))

x = np.arange(1, 11)
ax.plot(x, y1, marker='o', label='方案一', linewidth=1.5)
ax.plot(x, y2, marker='s', label='方案二', linewidth=1.5, linestyle='--')

ax.set_xlabel('时间 (天)', fontsize=11)
ax.set_ylabel('产量 (吨)', fontsize=11)
ax.set_title('不同方案产量对比', fontsize=13)
ax.legend(loc='upper left')
ax.grid(True, alpha=0.3)
ax.set_xticks(x)

plt.tight_layout()
plt.savefig('output/figures/fig1_line.pdf', dpi=300, bbox_inches='tight')
plt.savefig('output/figures/fig1_line.png', dpi=300, bbox_inches='tight')
plt.close()
```
> 注意：实际项目内路径为 `Code/output/figures/figN_xxx.png`（与 `config.py` 中 `FIG_DIR` 一致）；论文级图由 visualization agent 精选到 `ResultFigures/<分类>/` 并登记到 `figure-list.md`。

### 模板 2：柱状图

```python
fig, ax = plt.subplots(figsize=(8, 5))

categories = ['方案A', '方案B', '方案C', '方案D']
values = [85, 92, 78, 88]
colors = ['#2196F3', '#4CAF50', '#FF9800', '#F44336']

bars = ax.bar(categories, values, color=colors, edgecolor='black', linewidth=0.5)

# 在柱子上方标注数值
for bar, val in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f'{val}', ha='center', va='bottom', fontsize=10)

ax.set_ylabel('评分', fontsize=11)
ax.set_title('各方案综合评分对比', fontsize=13)
ax.set_ylim(0, 100)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('output/figures/fig2_bar.pdf', dpi=300, bbox_inches='tight')
plt.close()
```

### 模板 3：热力图

```python
import seaborn as sns
import pandas as pd

fig, ax = plt.subplots(figsize=(8, 6))

# 相关系数热力图
corr_matrix = df.corr()
sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='RdYlBu_r',
            center=0, vmin=-1, vmax=1, ax=ax,
            square=True, linewidths=0.5)

ax.set_title('特征相关系数热力图', fontsize=13)
plt.tight_layout()
plt.savefig('output/figures/fig3_heatmap.pdf', dpi=300, bbox_inches='tight')
plt.close()
```

### 模板 4：散点图 + 拟合线

```python
fig, ax = plt.subplots(figsize=(8, 5))

ax.scatter(x_data, y_data, s=30, alpha=0.6, label='观测数据')

# 线性拟合
z = np.polyfit(x_data, y_data, 1)
p = np.poly1d(z)
x_fit = np.linspace(x_data.min(), x_data.max(), 100)
ax.plot(x_fit, p(x_fit), 'r--', linewidth=1.5, label=f'拟合: y={z[0]:.2f}x+{z[1]:.2f}')

ax.set_xlabel('自变量 X', fontsize=11)
ax.set_ylabel('因变量 Y', fontsize=11)
ax.set_title('变量相关性分析', fontsize=13)
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('output/figures/fig4_scatter.pdf', dpi=300, bbox_inches='tight')
plt.close()
```

### 模板 5：雷达图

```python
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

categories = ['准确性', '效率', '成本', '可扩展性', '鲁棒性']
N = len(categories)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

# 方案数据
values1 = [85, 70, 90, 75, 80]
values1 += values1[:1]
ax.plot(angles, values1, 'o-', linewidth=2, label='方案一')
ax.fill(angles, values1, alpha=0.15)

values2 = [75, 85, 70, 90, 85]
values2 += values2[:1]
ax.plot(angles, values2, 's--', linewidth=2, label='方案二')
ax.fill(angles, values2, alpha=0.15)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=11)
ax.set_ylim(0, 100)
ax.set_title('方案综合评价雷达图', fontsize=13, pad=20)
ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

plt.tight_layout()
plt.savefig('output/figures/fig5_radar.pdf', dpi=300, bbox_inches='tight')
plt.close()
```

---

## 图注/坐标轴标注规范

### 标准图注格式

```
图 N: [图表说明文字，简明扼要描述图表内容]

示例：
图 1: 2020-2024年GDP增长率趋势
图 2: 各方案成本-效益对比
图 3: 特征相关系数热力图
图 4: 模型预测值与真实值对比
```

### 坐标轴标注规范

| 要素 | 格式 | 示例 |
|------|------|------|
| 轴标签 | `变量名 (单位)` | `时间 (天)`, `产量 (吨)` |
| 刻度 | 数值均匀分布 | 0, 20, 40, 60, 80, 100 |
| 图例 | 右上或左上 | `ax.legend(loc='upper left')` |
| 网格 | 淡色辅助线 | `ax.grid(True, alpha=0.3)` |

### 坐标轴进阶规则

| 场景 | 规则 |
|------|------|
| y 轴不从 0 开始 | 必须显式说明或使用截断轴，避免误导比例（柱状图必须从 0 起） |
| 数据跨数量级（1~1e6） | 用对数轴，并标注底数（如 log10） |
| 离群点压缩主体 | 截断轴：双子图 `sharex=True` 分别 `set_ylim`、隐藏中间 spines、`subplots_adjust(hspace=0.05)` |
| 出图尺寸 | 像素 = 英寸 × dpi；目标印刷宽度(单栏 8cm) → figsize ≈ (3.15, 2.4) 英寸 @300dpi |
| 裁剪留白 | `savefig(..., bbox_inches='tight', pad_inches=0.05)` |

---

## 统计标注规范（结果图必做）

```python
# 误差棒（均值 ± 标准差；std 用 ddof=1 样本标准差）
plt.errorbar(x, y_mean, yerr=y_std, fmt='o-', capsize=3, label='方案A')
# 连续趋势带（不重复画线）
ax.fill_between(x, mean - std, mean + std, alpha=0.2)

# 显著性星号惯例：* p<0.05, ** p<0.01, *** p<0.001（柱顶或对比线两端标注）
ax.text(x_i, top, '**', ha='center', va='bottom')

# 样本量：图注或图内标注 n=...（小样本尤其必须）
```

- 随机性数据（采样/噪声）必须 `np.random.seed(...)` 保证图可复现；
- 对比图的每条曲线用"颜色 + 线型 + 标记"三重区分（`o-`、`s--`），黑白打印也可读。

---

## 图表脚本效率与数据一致性（🔴 出图脚本工程化）

1. **数据同源（官方红线）**：图表数字必须直接从 `Code/output/tables/` 或结果文件读取，**禁止手抄/二次录入**——"代码输出 = 论文数据"；支撑材料与论文不符可能取消评奖资格；
2. **批量统一风格**：所有图共用 `Code/visualization/utils/plot_base.py` 的 `setup_plot_style()`（统一 rcParams），禁止每张图散落写参数；同类型图封装为函数（入参数据 + 输出路径）；
3. **循环出图必须 `plt.close()`**（防内存泄漏）；批量生成用脚本一次性产出全部图，逐图单独渲染；
4. **输出只落 `Code/output/figures/`**（唯一输出口），论文级图精选到 `ResultFigures/<分类>/` 并登记 `figure-list.md`；
5. **绘制效率**：数据量过大时先抽样/聚合再画（散点 >10^5 用 alpha/hexbin），避免渲染卡死；矢量 PDF 优先（缩放不失真、体积小）。

---

## 图表自查清单（出图后必查，mm-viz-reviewer 将逐项核对）

- [ ] 图号/表号全文连续，与正文引用（\ref{fig:*}）一致
- [ ] 中文无乱码（SimHei + unicode_minus=False）
- [ ] 分辨率 ≥300dpi（或矢量 PDF）
- [ ] 每图有标题 + 坐标轴标签（含单位）+ 图例
- [ ] 🔴 数字与 `output/tables/` 同源（代码输出 = 论文数据）
- [ ] 统计标注完整（误差棒/显著性/样本量 n=）
- [ ] 色盲友好（不红绿并用；序列数据用 viridis/plasma 等感知均匀色板，禁用 jet）
- [ ] 黑白打印可读（线型/标记区分）
- [ ] 柱状图从 0 起；非 0 起点有说明或截断轴
- [ ] 配色 ≤5 种；饼图切片 ≤6
- [ ] 字体字号统一（轴标签 ≥10pt、刻度 ≥8pt、标题 ≥12pt、图例 ≥9pt）
- [ ] 图注在图下方/表注在表上方居中
- [ ] 命名语义化（figN_描述，禁 chart1.png）
- [ ] 官方格式 profile（PDF 第4页起正文≤30页、摘要≤1页、附录不限、页边距≥2.5cm、PDF≤20MB、支撑材料包≤20MB且分离、无身份信息）

---

## 常见错误黑名单

| # | 错误 | 后果 | 正确做法 |
|---|------|------|---------|
| 1 | 中文显示为方框 | 无法阅读 | 设置 SimHei 字体 |
| 2 | 分辨率 < 150 dpi | 打印模糊 | `dpi=300` |
| 3 | 没有坐标轴标签 | 信息不完整 | 必须标注轴名和单位 |
| 4 | 图表无编号 | 论文无法引用 | 连续编号"图N" |
| 5 | 颜色过多（>7） | 视觉混乱 | 控制在 5 色以内 |
| 6 | 3D 图滥用 | 信息失真 | 默认 2D（理工科三维曲面等例外需注明视角） |
| 7 | 饼图切片过多（>6） | 难以区分 | 用柱状图替代 |
| 8 | 不关闭 figure | 内存泄漏 | `plt.close()` |
| 9 | 图表和论文不一致 | 结果不可信 | 代码输出 = 论文数据 |
| 10 | 图注放在图表内部 | 遮挡数据 | 放在图表下方居中 |

---

## References

| 资源 | 说明 |
|------|------|
| `mm-iteration-engine/SKILL.md` | 状态统一节点 + 图表门禁 V1（5 个前置门禁 + mm-viz-reviewer 20 项编号质量核对） |
| matplotlib 官方文档 | 绑图 API 参考 |
| seaborn 官方文档 | 统计可视化 |
| `mm-latex-writing/SKILL.md` | LaTeX 图表插入（`ReportPaper/LaTeX/img/` 相对 `ResultFigures/`） |
| `mathematical-modeling/SKILL.md` | 全流程总控 |
