---
name: mm-data-preprocessing
description: "CUMCM数据预处理SOP：探查Checklist、清洗规则（缺失值/异常值/重复值）、特征工程方法、Python代码模板、产物落 Data/DataLog.md + 三级数据目录。触发词：数据预处理, 数据清洗, data preprocessing, 缺失值, 异常值"
metadata:
  version: "1.1.0"
  last_updated: "2026-08-15"
  status: active
  related_skills:
    - mathematical-modeling
    - mm-algorithm-dev
    - mm-iteration-engine
---

【范围】竞赛数据预处理与可复现性。通用数据清洗与特征工程按项目既有流程执行。

# MM Data Preprocessing — 数据预处理 SOP

国赛数学建模数据预处理标准操作流程，覆盖数据探查、清洗规则、特征工程与代码模板。**产物落 `Data/`**（DataLog.md 写报告 + raw/processed/feature/test_result 三级数据）。

---

## Quick Start

```
处理这组数据
```
```
数据清洗，有缺失值和异常值
```
```
数据预处理 SOP
```

---

## Trigger Conditions

### Trigger Keywords

- **中文**: 数据预处理, 数据清洗, 缺失值, 异常值, 特征工程, 数据探查, 数据处理
- **English**: data preprocessing, data cleaning, missing values, outliers, feature engineering

### Does NOT Trigger

| Scenario | Use Instead |
|----------|-------------|
| 纯统计分析（不做清洗） | 直接使用 pandas/numpy |
| 建模阶段 | `mm-model-library` |

---

## Phase 1: 数据探查 Checklist

### 1.1 基础信息

| 检查项 | 命令 | 输出 |
|-------|------|------|
| 行数 / 列数 | `df.shape` | (rows, cols) |
| 列名与数据类型 | `df.dtypes` | 各列类型 |
| 前 5 行预览 | `df.head()` | 样本数据 |
| 基础统计量 | `df.describe()` | count/mean/std/min/max/四分位 |
| 分类列分布 | `df[col].value_counts()` | 各类别频次 |

### 1.2 缺失分析

```python
# 缺失值统计
missing_report = pd.DataFrame({
    '列名': df.columns,
    '缺失数': df.isnull().sum().values,
    '缺失率': (df.isnull().sum() / len(df) * 100).round(2).values
}).sort_values('缺失率', ascending=False)

# 缺失模式
import missingno as msno
msno.matrix(df)  # 可视化缺失模式
```

**缺失率决策阈值（仅作风险提示，不是机械删行规则）：**

| 缺失率 | 默认候选策略 | 必须记录的判断依据 |
|:------:|---------|---------|
| < 5% | 根据变量类型和缺失机制选择插补或删除 | 删除是否改变样本量/分布；插补是否引入偏差 |
| 5% - 20% | 中位数/众数/KNN/时序插值等插补 | MCAR/MAR/MNAR 判断、验证集影响 |
| 20% - 50% | 插补 + 缺失标志位，必要时做敏感性对照 | 缺失机制、样本代表性、对结果的影响 |
| > 50% | 评估删除列、保留为特殊特征或补采数据 | 删除/保留的模型影响和可复现理由 |

🔴 不得仅凭“低于 5%”直接删除记录；删除、插补或保留必须由变量类型、缺失机制、样本影响和赛题语义共同决定，并写入 DataLog。

### 1.3 重复值检查

```python
# 重复行统计
dup_count = df.duplicated().sum()
dup_rate = dup_count / len(df) * 100

# 查看重复行
df[df.duplicated(keep=False)]
```

---

## Phase 2: 清洗规则

### 2.1 缺失值处理策略表

| 数据类型 | 缺失率低 (<20%) | 缺失率高 (>=20%) | 时序数据 |
|---------|----------------|-----------------|---------|
| **数值型** | 中位数填充 | KNN 插补 / 多重插补 | 时间插值 (`interpolate()`) |
| **分类型** | 众数填充 | 新增"未知"类别 | 前向填充 (`ffill()`) |
| **日期型** | 前后值推断 | 删除该行 | 时间插值 |

```python
# 数值型 - 中位数填充
df['col'].fillna(df['col'].median(), inplace=True)

# 数值型 - KNN 插补
from sklearn.impute import KNNImputer
imputer = KNNImputer(n_neighbors=5)
df[num_cols] = imputer.fit_transform(df[num_cols])

# 分类型 - 众数填充
df['col'].fillna(df['col'].mode()[0], inplace=True)

# 时序 - 插值
df['col'] = df['col'].interpolate(method='linear')
```

### 2.2 异常值检测与处理

#### 方法一：IQR 法（推荐用于偏态分布）

```python
def detect_outliers_iqr(series, factor=1.5):
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - factor * IQR
    upper = Q3 + factor * IQR
    return (series < lower) | (series > upper)
```

#### 方法二：3-sigma 法（适用于正态/近似正态分布）

```python
def detect_outliers_3sigma(series, threshold=3):
    mean = series.mean()
    std = series.std()
    return abs(series - mean) > threshold * std
```

#### 方法三：Z-score 法

```python
from scipy import stats
z_scores = stats.zscore(df[num_cols].dropna())
outliers = abs(z_scores) > 3  # 阈值可调
```

#### 异常值处理策略

| 场景 | 处理方法 |
|------|---------|
| 明确的录入错误 | 修正或删除 |
| 极端但真实的值 | 截断（winsorize）到 1%/99% 分位数 |
| 分布严重偏态 | 对数变换 `np.log1p()` |
| 不确定是否为异常 | 保留并标注，建模时用鲁棒模型 |

### 2.3 重复值处理

```python
# 完全重复 → 删除
df = df.drop_duplicates()

# 部分列重复 → 按关键列去重
df = df.drop_duplicates(subset=['id', 'date'], keep='last')
```

---

## Phase 3: 特征工程

### 常用方法速查

| 方法 | 适用场景 | Python 实现 |
|------|---------|------------|
| 标准化 | 数值特征量纲差异大 | `StandardScaler()` |
| 归一化 | 需要 [0,1] 区间 | `MinMaxScaler()` |
| 独热编码 | 无序分类特征 | `pd.get_dummies()` / `OneHotEncoder()` |
| 标签编码 | 有序分类特征 | `LabelEncoder()` |
| 多项式特征 | 需要交互项 | `PolynomialFeatures()` |
| 分箱 | 连续变量离散化 | `pd.cut()` / `pd.qcut()` |
| 对数变换 | 右偏分布 | `np.log1p()` |
| 时间特征 | 日期列提取 | `.dt.year/month/weekday` |
| 文本向量化 | 文本特征 | `TfidfVectorizer()` |

### 特征选择方法

| 方法 | 适用场景 | 实现 |
|------|---------|------|
| 相关系数过滤 | 高相关特征去除 | `df.corr()` |
| 方差过滤 | 低方差特征去除 | `VarianceThreshold()` |
| 互信息 | 非线性关系 | `mutual_info_classif/regression()` |
| L1 正则化 | 自动特征选择 | `Lasso(alpha=...)` |
| 树模型重要性 | 非线性特征评估 | `RandomForest.feature_importances_` |

---

## 代码模板

### 完整预处理流水线

```python
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import KNNImputer

def preprocess_pipeline(df, target_col=None):
    """国赛数据预处理标准流水线"""
    report = {}

    # 1. 基础信息
    report['shape'] = df.shape
    report['dtypes'] = df.dtypes.to_dict()

    # 2. 缺失值处理
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

    # 数值列：KNN 插补
    if num_cols:
        imputer = KNNImputer(n_neighbors=5)
        df[num_cols] = imputer.fit_transform(df[num_cols])

    # 分类列：众数填充
    for col in cat_cols:
        if df[col].isnull().any():
            df[col].fillna(df[col].mode()[0], inplace=True)

    # 3. 异常值检测（IQR）
    outlier_info = {}
    for col in num_cols:
        Q1, Q3 = df[col].quantile([0.25, 0.75])
        IQR = Q3 - Q1
        mask = (df[col] < Q1 - 1.5*IQR) | (df[col] > Q3 + 1.5*IQR)
        outlier_info[col] = mask.sum()
    report['outliers'] = outlier_info

    # 4. 重复值
    report['duplicates'] = df.duplicated().sum()

    # 5. 标准化
    scaler = StandardScaler()
    df[num_cols] = scaler.fit_transform(df[num_cols])

    report['cleaned_shape'] = df.shape
    return df, report
```

---

## 产出物规范

数据预处理完成后产出 **`Data/DataLog.md`**（数据处理日志与可复现记录），必须包含：

1. **数据概览**：行列数、数据类型、统计量（与 `Data/raw/` 原始数据一致）
2. **缺失分析**：各列缺失率、处理方法与理由
3. **异常值报告**：检测方法、异常数量、处理方式
4. **重复值处理**：去重前后行数对比
5. **特征工程**：新增/变换特征说明（落 `Data/feature/`）
6. **数据集划分**：训练/验证/测试集拆分（落 `Data/processed/` 与 `test_result/`）
7. **处理前后对比**：关键统计量变化

> 配套产物：`Data/processed/`（清洗后标准化数据）、`Data/feature/`（特征工程数据集）、`Data/test_result/`（模型验证/测试数据集）。运行代码只写 `Code/output/`（唯一输出口）。

---

## Anti-Patterns

| # | 反模式 | 后果 | 正确做法 |
|---|--------|------|---------|
| 1 | 不看分布直接用均值填充 | 偏态数据填充偏差大 | 偏态用中位数 |
| 2 | 删除所有缺失行 | 数据大量丢失 | 按缺失率选择策略 |
| 3 | 标准化后才发现异常值 | 异常值影响标准化 | 先检测异常值 |
| 4 | 对所有列统一处理 | 分类列被数值化 | 区分数值/分类列 |
| 5 | 不记录处理过程 | 结果不可复现 | 产出数据报告 |

---

## References

| 资源 | 说明 |
|------|------|
| pandas 官方文档 | 数据处理 API |
| scikit-learn preprocessing | 特征工程模块 |
| `mm-algorithm-dev/SKILL.md` | 代码开发规范（含 `Code/output/` 唯一输出口约定） |
| `mm-iteration-engine/SKILL.md` | 状态统一节点（D1 门禁、节点首页 N2） |
| `mathematical-modeling/SKILL.md` | 全流程总控 |

---

## Pro 知识库融合（v1.7.0）：数据工作流与泄漏防护

> 融合自 math-modeling-skill-pro（作者授权）：数据清单/字典、质量审计、清洗决策、特征工程与结构化切分规范。

### 资产位置
- `skills/mm-data-preprocessing/assets/pro/data-workflow.md`：数据清单与字段字典、质量审计、清洗决策表、特征工程（机制先行）、泄漏审计清单、可复现交付

### 使用时机
N2 数据预处理全程：①资产清单+字段字典（含「是否可用于预测」按预测时信息集判断）→ ②质量审计（结构/缺失 MCAR-MAR-MNAR/异常/分布）→ ③清洗决策留痕 → ④特征工程（每个特征写现实含义/公式/单位/可获得时间）→ ⑤结构化切分与泄漏审计 → ⑥可复现交付（DataLog.md 引用）。

### 与既有流程的关系
- 本技能已有的清洗流程负责执行；Pro 资产补充「决策必须可回溯」的强制项：任何处理保存原始列和处理标记，预处理规则在查看最终测试结果前确定。
- 泄漏审计清单逐项核对：特征可获得性、预处理只在训练折拟合、同一主体不跨训练测试、时序不用未来值、空间/网络邻接不泄漏、调参不看测试集。
- 小样本：限制自由度、重复 CV/留一/Bootstrap；不把数据增强当独立信息；深网只在迁移/共享/强先验时进入候选并与简单基线对比。

### 回退
题目数据不足时按优先级：题意/机制推导可识别量 → 权威外部数据 → 区间/情景 → 量纲/边界/敏感性 → 条件性结论；禁止虚构精确参数。
