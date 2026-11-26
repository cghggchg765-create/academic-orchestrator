---
name: mm-model-tuning
description: "CUMCM迭代调优规范：调优循环流程、超参搜索方法对比、敏感性分析方法、鲁棒性检验方法；产物落 ModelDocs/ 三份报告（sensitivity-analysis.md / error-analysis.md / model-validation.md）。触发词：模型调优, 超参搜索, model tuning, 参数优化, 敏感性分析"
metadata:
  version: "1.1.0"
  last_updated: "2026-08-15"
  status: active
  related_skills:
    - mathematical-modeling
    - mm-algorithm-dev
    - mm-model-library
    - mm-iteration-engine
    - mm-self-review
---

【范围】竞赛模型的调参与敏感性分析。通用机器学习调参请按项目框架（如 sklearn/Optuna）常规做法执行。

# MM Model Tuning — 迭代调优规范

国赛数学建模模型迭代调优的标准流程，覆盖超参搜索、敏感性分析与鲁棒性检验。**产物落 `ModelDocs/` 三份报告**（sensitivity-analysis.md / error-analysis.md / model-validation.md），并纳入迭代引擎轮次评分（mm-code-reviewer 审 N5，T1 门禁）。

---

## Quick Start

```
帮我调优这个模型
```
```
模型精度不够，怎么优化？
```
```
做一下敏感性分析
```

---

## Trigger Conditions

### Trigger Keywords

- **中文**: 模型调优, 超参搜索, 参数优化, 敏感性分析, 鲁棒性检验, 交叉验证, 调参
- **English**: model tuning, hyperparameter search, sensitivity analysis, robustness check

### Does NOT Trigger

| Scenario | Use Instead |
|----------|-------------|
| 还没实现模型 | `mm-algorithm-dev` |
| 模型选型 | `mm-model-library` |
| 只是画图 | `mm-visualization` |

---

## 调优循环流程图

```
┌─────────────────────────────────────────────────────┐
│                    调优循环                           │
│                                                       │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│   │ 基线建立  │ → │ 误差分析  │ → │ 超参搜索  │       │
│   │ Baseline │    │  Error   │    │  Search  │       │
│   └──────────┘    └──────────┘    └──────────┘       │
│        ↑                              │               │
│        │         ┌──────────┐         │               │
│        └──────── │ 鲁棒性   │ ← ┌─────┴─────┐        │
│                  │ 检验     │   │ 敏感性     │        │
│                  │Robustness│   │ 分析       │        │
│                  └──────────┘   │Sensitivity │        │
│                       │         └───────────┘        │
│                       ↓                              │
│                 ┌──────────┐                         │
│                 │ 调优报告  │                         │
│                 │ Report   │                         │
│                 └──────────┘                         │
└─────────────────────────────────────────────────────┘
```

### 循环终止条件

| 条件 | 说明 |
|------|------|
| 性能指标达标 | 达到预设阈值（如准确率 > 90%） |
| 提升饱和 | 连续两轮提升 < 1% |
| 迭代次数上限 | 最多 5 轮调优 |
| 时间限制 | 国赛时间有限，单轮调优 < 30 分钟 |

---

## 超参搜索方法对比

### 选型表

| 方法 | 搜索空间 | 时间复杂度 | 适用场景 | Python 实现 |
|------|---------|-----------|---------|------------|
| **GridSearchCV** | 离散网格 | O(n^d)，d 为维度 | 参数少（<=3 个）、空间小 | `sklearn.model_selection.GridSearchCV` |
| **RandomizedSearchCV** | 连续/离散 | O(n)，n 为迭代次数 | 参数多、空间大 | `sklearn.model_selection.RandomizedSearchCV` |
| **Optuna** | 连续/离散/条件 | 自适应采样 | 复杂空间、条件参数 | `optuna` |
| **贝叶斯优化** | 连续 | 自适应采样 | 评估代价高 | `scikit-optimize` |

### 方法选择决策

```
参数数量 <= 3 且每个参数取值少（<10）？
├─ 是 → GridSearchCV
└─ 否 → 参数数量 > 3 ？
    ├─ 是 → 有 Optuna？→ Optuna
    │        无 → RandomizedSearchCV
    └─ 否 → 单次评估时间长？
        ├─ 是 → 贝叶斯优化 / Optuna
        └─ 否 → RandomizedSearchCV
```

### GridSearchCV 示例

```python
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [3, 5, 7, 10],
    'min_samples_split': [2, 5, 10]
}

grid_search = GridSearchCV(
    RandomForestClassifier(random_state=42),
    param_grid,
    cv=5,               # 5 折交叉验证
    scoring='accuracy',
    n_jobs=-1,          # 并行
    verbose=1
)
grid_search.fit(X_train, y_train)
print(f"最优参数: {grid_search.best_params_}")
print(f"最优分数: {grid_search.best_score_:.4f}")
```

### Optuna 示例

```python
import optuna
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import GradientBoostingClassifier

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 300),
        'max_depth': trial.suggest_int('max_depth', 2, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0)
    }
    model = GradientBoostingClassifier(**params, random_state=42)
    score = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy').mean()
    return score

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50)
print(f"最优参数: {study.best_params}")
print(f"最优分数: {study.best_value:.4f}")
```

---

## 敏感性分析方法

### 方法一：单因素扰动法

固定其他参数，逐一变动目标参数，观察结果变化。

```python
def sensitivity_single_param(model_class, base_params, param_name, 
                              param_range, X, y, metric):
    """单因素敏感性分析"""
    results = []
    for value in param_range:
        params = base_params.copy()
        params[param_name] = value
        model = model_class(**params)
        score = cross_val_score(model, X, y, cv=5, scoring=metric).mean()
        results.append({'param': param_name, 'value': value, 'score': score})
    return pd.DataFrame(results)
```

### 方法二：正交实验法

多因素同时变动，用正交表安排实验，高效识别关键因素。

| 因素 | 水平1 | 水平2 | 水平3 |
|------|------|------|------|
| A: n_estimators | 50 | 100 | 200 |
| B: max_depth | 3 | 5 | 10 |
| C: learning_rate | 0.01 | 0.1 | 0.3 |

使用 L9(3^3) 正交表安排 9 次实验。

### 方法三：蒙特卡洛模拟

对参数施加随机扰动，统计结果分布。

```python
def monte_carlo_sensitivity(model_class, base_params, n_simulations=100,
                             noise_std=0.1, X=None, y=None):
    """蒙特卡洛敏感性分析"""
    scores = []
    for _ in range(n_simulations):
        # 对每个参数添加正态随机扰动
        perturbed = {
            k: v * (1 + np.random.normal(0, noise_std))
            if isinstance(v, (int, float)) else v
            for k, v in base_params.items()
        }
        model = model_class(**perturbed)
        score = cross_val_score(model, X, y, cv=5).mean()
        scores.append(score)
    return {
        'mean': np.mean(scores),
        'std': np.std(scores),
        'cv': np.std(scores) / np.mean(scores)  # 变异系数
    }
```

---

## 鲁棒性检验方法

### 方法一：交叉验证

```python
from sklearn.model_selection import cross_val_score, KFold

# 5 折交叉验证（推荐）
kf = KFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(model, X, y, cv=kf, scoring='accuracy')
print(f"均值: {scores.mean():.4f} ± {scores.std():.4f}")
```

### 方法二：Bootstrap 置信区间

```python
def bootstrap_confidence_interval(model, X, y, n_bootstrap=1000, 
                                   confidence=0.95, metric='accuracy'):
    """Bootstrap 置信区间估计"""
    scores = []
    n = len(X)
    for _ in range(n_bootstrap):
        indices = np.random.choice(n, size=n, replace=True)
        X_boot, y_boot = X[indices], y[indices]
        model.fit(X_boot, y_boot)
        score = model.score(X, y)
        scores.append(score)
    
    lower = np.percentile(scores, (1-confidence)/2 * 100)
    upper = np.percentile(scores, (1+confidence)/2 * 100)
    return np.mean(scores), lower, upper
```

### 方法三：训练集/测试集稳定性

```python
from sklearn.model_selection import train_test_split

# 多次随机划分验证稳定性
stability_scores = []
for seed in range(10):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed)
    model.fit(X_train, y_train)
    stability_scores.append(model.score(X_test, y_test))

print(f"稳定性: {np.mean(stability_scores):.4f} ± {np.std(stability_scores):.4f}")
```

---

## 调优报告模板（落 `ModelDocs/` 三份文档）

### `ModelDocs/sensitivity-analysis.md`

```markdown
# 敏感性分析

## 关键参数（top 3-5）
- [param1, param2, ...]

## 扰动实验结果表（±20% / ±10% / 基准）
| 参数 \ 扰动幅度 | -20% | -10% | 0% | +10% | +20% |
| param1          | 0.85 | 0.89 | 0.92 | 0.90 | 0.86 |
| param2          | 0.88 | 0.90 | 0.92 | 0.91 | 0.89 |

## 敏感性指标
- 绝对敏感性 / 相对敏感性 / 排序敏感性（具体值）

## 热力图数据矩阵
## 敏感性结论（哪些参数高敏感，哪些低敏感）
```

### `ModelDocs/error-analysis.md`

```markdown
# 误差分析

## 基线结果
- 模型：[模型名称]
- 评估指标：[指标名] = [基线值]
- 运行时间：[时间]
- 代码路径：`Code/output/txt_result/` 关联

## 误差来源分解（偏差/方差/不可约误差）
## 残差分析（正态性/异方差/自相关）
## 改进建议（基于误差分析的调优方向）

## 超参搜索对比表
| 排名 | 参数组合 | 训练指标 | 验证指标 | 训练时间 | 过拟合度 |
|------|---------|---------|---------|---------|---------|

## 最优参数组合
```

### `ModelDocs/model-validation.md`

```markdown
# 模型验证与鲁棒性

## K-Fold CV
- 均值：[指标均值]
- 标准差：[指标标准差]
- 评分：/10

## Bootstrap
- 95% CI：[下界, 上界]
- 评分：/10

## 蒙特卡洛
- 变异系数：CV 值
- 评分：/10

## 鲁棒性综合评分（加权平均，/10）

## 调优总结
- 基线 → 调优后提升幅度
- 关键发现
- 建议
```

> 调优报告触发 **T1 门禁**（mm-code-reviewer 审 N5 时核对基线/对比/敏感性/鲁棒性四齐备），并进入迭代引擎轮次评分。

---

## Anti-Patterns

| # | 反模式 | 后果 | 正确做法 |
|---|--------|------|---------|
| 1 | 只在训练集调优 | 过拟合，泛化差 | 必须用交叉验证 |
| 2 | 搜索空间太大 | 调优耗时过长 | 先粗搜再细搜 |
| 3 | 不做敏感性分析 | 不知道参数影响 | 单因素扰动法 |
| 4 | 不报告方差 | 只看均值误导 | 报告 mean ± std |
| 5 | 调优轮数无上限 | 时间浪费 | 最多 5 轮 |

---

## References

| 资源 | 说明 |
|------|------|
| `mm-iteration-engine/SKILL.md` | 状态统一节点 + 迭代循环（termination.code pass 7.0 / target 8.0 / ≤5 轮；T1 门禁） |
| `mm-self-review/SKILL.md` | 五维自检 Checklist（硬上限 + 仲裁） |
| `mm-algorithm-dev/SKILL.md` | 代码实现规范 |
| `mm-model-library/SKILL.md` | 模型选型 |
| `mm-visualization/SKILL.md` | 敏感性分析图表 |
| `mathematical-modeling/SKILL.md` | 全流程总控 |
| scikit-learn 调参指南 | 官方调优文档 |

---

## Pro 知识库融合（v1.7.0）：验证、敏感性与稳健性

> 融合自 math-modeling-skill-pro（作者授权）：从主张出发的验证协议、切分与泄漏防护、敏感性/稳健性、最低验证包。

### 资产位置
- `skills/mm-model-tuning/assets/pro/validation-methods.md`：主张→证据映射、数据切分协议、按任务验证、局部/全局敏感性、不确定性传播、消融与统计判断、误差与失败情景
- `skills/mm-model-tuning/assets/pro/templates/validation-plan.md`：验证计划模板（建模前填写验收规则，看完结果不得换主指标）

### 使用时机
N5 调优/验证前必须完成：①验证从主张开始（映射主张→证据→不足证据）→ ②声明切分/扰动/指标/阈值/重复次数 → ③四层验证（内部正确性/预测或解释证据/基线对比/不确定性）→ ④误差与失败情景 → ⑤最低验证包逐项核对。

### 与既有流程的关系
- 本技能已有的敏感性/误差/稳健性三份报告为产物骨架；Pro 资产约束其证据强度：单参数扰动不得称「稳健」；训练拟合优度不得验证预测；`p < 0.05` 不等于实际重要。
- 切分必须匹配数据结构（时序滚动/GroupKFold/空间阻断/嵌套验证），预处理器只在训练折拟合。
- 仿真必须报告重复次数、随机种子、置信区间、暖机/收敛；单条漂亮轨迹不是证据。
- 每子问至少：一个匹配任务的基线、一个正确切分/小规模精确检查、主辅指标各一、关键参数敏感性、一项误差/失败情景；有创新模块加消融，有随机算法加多种子。

### 回退
验证篇幅不足时优先覆盖核心主张与高风险假设，不机械塞满所有方法；无法验证的结论降低强度或改写为条件性结论。
