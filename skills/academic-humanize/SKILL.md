---
name: academic-humanize
description: "学术文本去AI化——展开缩写、删除过渡词拐杖、被动转主动、同义词替换，适用于论文、学位论文、期刊投稿、报告等任何学术文本。需配合 humanizer skill 检测 AI-ness Score。触发词：humanize, 去AI化, 去AI味, 降低AI率, 学术润色, 论文润色, 语言润色, 表达自然化, academic text polishing。若目标是审查论文整体质量而非语言风格，用 academic-paper-reviewer。"
---

# Academic Humanize — 论文去AI化与学术精炼表达

## 🔴 加载资格与委托守则（必须读）

本技能是 **去 AI 化（humanize）子代理** 的专项工具，**仅供 `humanize` 子代理加载执行**（与 `humanizer` 配合测量 AI-ness）。

- 若你是主对话主 agent：需要对论文做去 AI 化/学术精炼时，派发 `subagent_type=humanize` 子代理；**不得自己加载本技能直接改写论文正文**。
- 检测报告落 `state/reports/`；发现 AI 痕迹 → writing 子代理按报告修订 → 复审。

> **版本**: 1.0.0 | **更新**: 2026-06-15 | **类型**: 学术写作润色
> 
> **核心工具**: `gh_grep_searchGitHub`（GitHub代码搜索）+ 规则检测

## 概述

本技能通过 **GitHub 真实人类写作文本搜索** 和 **AI写作模式检测**，帮助将学术论文从AI生成痕迹中解脱出来，使其表达更自然、更接近人类学者风格。

## 触发条件

以下任一场景触发本技能：

| 场景 | 示例 |
|------|------|
| 论文去AI化 | "帮我去掉论文里的AI味"、"humanize这段" |
| 学术精炼 | "润色这段学术表达"、"写得更像人写的" |
| 检测AI痕迹 | "检查这段有没有AI痕迹"、"detect AI patterns" |
| 中文学术润色 | "让这段中文更像学者写的" |
| 引用真实语料 | "搜一下GitHub上真实项目怎么描述这个概念的" |

## 核心原理

### 1. AI写作的典型痕迹（源自 Hexis 引擎，当前实现 36 种；下表为常见高频示例）

基于 QuixiAI/Hexis 项目的 AI pattern 检测引擎，以下是最常见的 AI 写作信号：

| # | 模式 | 中文示例 | 英文示例 | 修复建议 |
|---|------|---------|---------|---------|
| 1 | **公式化开头** | "值得注意的是"、"在当今社会" | "It's worth noting"、"In today's world" | 直入主题，从具体观点开始 |
| 2 | **过渡词拐杖** | "此外"、"而且"、"然而"、"因此" | "Moreover"、"Furthermore"、"Additionally" | 让思想自然流动，少用过渡标记 |
| 3 | **模糊限制堆叠** | "似乎"、"某种程度上"、"可以说" | "it seems"、"arguably"、"to some extent" | 减少模糊词，增强确定性 |
| 4 | **副词膨胀** | "极其"、"非常"、"显著地" | "incredibly"、"significantly"、"remarkably" | 用具体数据替代空洞副词 |
| 5 | **"delve"** | "深入探究" (过度使用) | "delve into" | 用 explore/examine/investigate 替代 |
| 6 | **抽象名词填充** | "在...的景观/领域/范畴中" | "the landscape/tapestry/realm of" | 直接说明具体指什么 |
| 7 | **"not only...but also"** | "不仅...而且..." | "not only...but also" | 直接并列陈述，不要用这个结构 |
| 8 | **"leverage/utilize"** | "利用/运用" (滥用) | "leverage/utilize" | 用 use/make use of/apply |
| 9 | **破折号滥用** | — 在段落中出现>2次 | em dash overuse | 用逗号、句号或括号替代 |
| 10 | **隐喻陈词** | "双刃剑"、"冰山一角"、"范式转移" | "double-edged sword"、"tip of the iceberg" | 用新鲜、具体的语言 |

### 2. 中文学术AI特征

除了通用的AI模式，中文学术写作还有特有的AI痕迹：

| AI特征 | 典型例句 | 更自然的写法 |
|--------|---------|-------------|
| 四字成语堆砌 | "综上所述，这一研究不仅...而且..." | 直接总结核心发现 |
| 过度连接词 | "首先...其次...再次...最后..." | 用自然段落过渡 |
| 模板化段落 | "随着...的发展，...已成为..." | 从具体问题或数据切入 |
| 被动滥用 | "被认为...被广泛接受..." | 主动语态，明确主体 |
| 模糊范围 | "在一定程度上"、"从某种角度来说" | 精确限定范围或直接断言 |

## 工作流

> **双档执行模式（提效铁律）**：N7 每轮修订后仅轻量 `compute_ai_score()` 评分；36 模式全量扫描 + C1-C7 中文风险提示 + GitHub 语料对照只在 **N8 前专项执行一次**（humanize Agent 报告落 `state/reports/`）。禁止每轮迭代重复全量检测同一稿。

### Phase 1: GitHub 搜索真实语料

使用 `gh_grep_searchGitHub` 搜索真实人类写作文本：

```
# 搜索真实学术评论中的自然表达
搜索: "we propose" "we present" "we introduce"  → 找到真实论文代码中的自然学术开头

# 搜索中文技术文档中的学术表达
搜索: "本文提出" "实验结果表明" "实验分析" → 找到真实中文技术写作

# 对比AI和人类表达
搜索: "our approach" "our method" compare
搜索: "该方法" "本方法" "本工作"
```

**搜索策略**：
- 搜索真实代码注释中的学术语言
- 搜索 README、文档中的技术描述
- 搜索学术项目中的论文摘要、引言
- 对比搜索结果与AI生成文本的差异

### Phase 2: AI模式检测

对目标文本运行 `detect_ai_patterns()` 36 种 AI 模式检测（`skills/humanizer/src/humanizer_tools.py`）：

1. 逐段扫描
2. 标记所有匹配的AI模式
3. 计算 AI-ness Score (0.0~1.0)
4. 输出检测报告

### Phase 3: 对比与替换

对每个AI模式，在GitHub搜索结果中找到对应的**人类自然表达**：

```
AI写法: "In this paper, we delve into the intricate landscape of..."
GitHub搜索: "we study" "we analyze" "we investigate" language:Python
人类写法: "We study the effect of X on Y using Z."
```

### Phase 4: 精炼表达

根据人类语料库进行精炼：
1. 替换AI模式为自然表达
2. 调整句式结构
3. 精简冗余词汇
4. 统一术语
5. 重新计算 AI-ness Score

## GitHub搜索策略库

### 英文搜索

```python
# 搜索真实论文代码中的摘要/引言
gh_grep_searchGitHub(query="we present a novel", language=["Python", "TypeScript"])
gh_grep_searchGitHub(query="In this paper we", language=["Markdown"])
gh_grep_searchGitHub(query="experimental results demonstrate", language=["Python", "Markdown"])

# 搜索真实的方法描述
gh_grep_searchGitHub(query="our approach consists of", language=["Python"])
gh_grep_searchGitHub(query="the main contribution of this work", language=["Markdown"])

# 搜索自然的结果描述
gh_grep_searchGitHub(query="achieve state-of-the-art", path="README.md")
gh_grep_searchGitHub(query="we observe that", language=["Python"])
```

### 中文搜索

```python
# 搜索中文技术写作中的自然表达
gh_grep_searchGitHub(query="本文提出了一种", language=["Markdown", "Python"])
gh_grep_searchGitHub(query="实验结果表明该", language=["Python", "Markdown"])

# 搜索真实中文注释
gh_grep_searchGitHub(query="该函数用于计算", language=["Python"])
gh_grep_searchGitHub(query="注意：这里需要", language=["Python"])
```

## AI-ness Score 计算

基于 Hexis 项目的评分算法：

```
Score = min((density × 0.3 + diversity_factor × 0.7), 1.0)

其中:
- density = 检测到的模式总数 / 总词数 × 100
- diversity_factor = min(检测到的不同模式数 / 10, 1.0)
- 0.0 = 完全人类写作
- 1.0 = 完全AI写作
```

### 评分解读

| 分数区间 | 含义 | 建议 |
|---------|------|------|
| 0.0~0.2 | 自然人类写作 | 无需处理 |
| 0.2~0.4 | 轻微AI痕迹 | 选择性修复明显模式 |
| 0.4~0.6 | 中等AI痕迹 | 建议全面humanize |
| 0.6~0.8 | 较强AI痕迹 | 必须全面重写 |
| 0.8~1.0 | 明显AI生成 | 大幅重写 |

## 规则引擎后端（英文 AcademicHumanizer）

> 原 `academic-humanizer`（兼容 wrapper 子集）已于 1.8.0 物理并入本技能，规则引擎源码随迁：
> `src/academic_humanizer.py`（`AcademicHumanizer` 类）。英文文本可直接走确定性规则引擎，中文走上面的人工语料+检测流程或由 `skills/humanizer/src/backends/chinese.py` 处理。

### 类与主入口

```python
class AcademicHumanizer:
    def __init__(self, model_name='paraphrase-MiniLM-L6-v2', seed=None)
    def humanize(self, text, use_synonyms=False, ai_score=0.0) -> str  # 主入口：按 ai_score 调侵略性
    def expand_contractions(self, sentence) -> str                     # 缩写展开: don't -> do not
    def remove_transitions(self, sentence) -> str                      # 句首过渡词拐杖（Moreover/Furthermore...）
    def remove_ai_openers(self, sentence) -> str                       # AI 公式化开场白（It is worth noting...）
    def convert_to_active(self, sentence) -> str                       # 被动转主动（仅含 by 施动者）
    def replace_with_synonyms(self, sentence) -> str                   # 同义词替换（语义保持，可选）
```

使用示例：

```python
import sys
sys.path.insert(0, "<本插件目录>/skills/academic-humanize")
from src.academic_humanizer import AcademicHumanizer

h = AcademicHumanizer()  # 依赖预检失败时须走 humanize Agent 的规则降级，禁止自动下载
result = h.humanize(
    "Moreover, the experiment was conducted by the researchers and it's shown that...",
    use_synonyms=True, ai_score=0.72,
)
```

### 侵略性分级（aggressiveness = min(ai_score × 1.5, 1.0)）

| 区间 | 执行操作 |
|------|---------|
| 0.0 ~ 0.3 | 仅缩写展开（始终执行） |
| 0.3 ~ 0.4 | + 删除过渡词 + 删除开场白 |
| 0.4 ~ 0.5 | + 被动→主动 |
| 0.5 ~ 1.0 | + 同义词替换（若启用） |

### 依赖预检与失败模式

- **spaCy + en_core_web_sm 未装**：构造即抛 RuntimeError → 由 humanize Agent 决定规则降级（仅缩写展开+正则删除）或 BLOCKED；**禁止 import 时自动下载模型**。
- **sentence-transformers 未装**：`model_name=''` 走纯规则处理，自动禁用同义词替换。
- **极短文本**（< 5 词）原样返回；**被动模式无法匹配**保留原句式。
- **已知缺陷（Round 1 实测残留）**：`convert_to_active` 对 "was conducted by" 可能输出 "the the conduct..."（正则式局限，建议改 spaCy 依存句法 `nsubjpass`→`nsubj`）；`Moreover,` 删除后句首字母小写已做 capitalize 修正；`It is worth noting` 删除后产生 "That..." 句首的情况需人工审视。规则引擎输出一律由 humanizer 二次检测验证 AI-ness 已下降，未下降则不采信。

### 回归保护

规则引擎回归测试：`tests/test_academic_humanizer_regressions.py`（段落分隔符保持、被动时态保持、首空格不重复大写）。

## 质量检查清单

完成润色后，逐一检查：

| # | 检查项 | 标准 |
|---|--------|------|
| 1 | 过渡词密度 | 每段不超过1个显式过渡词 (Moreover/Furthermore等) |
| 2 | "delve/landscape"检查 | 全文0次 |
| 3 | "not only...but also" | 全文≤1次 |
| 4 | 破折号密度 | 每段≤1个 |
| 5 | 四字成语堆砌 | 中文每段≤1个 |
| 6 | 连接词多样性 | 不重复使用相同连接词 |
| 7 | 主被动平衡 | 主动语态占>70% |
| 8 | 模糊限制词 | 每句≤1个 (seems/perhaps/可能等) |
| 9 | AI-ness Score重算 | 修复后 < 0.3 |
| 10 | GitHub对比验证 | 至少3处表达有真实人类写法对照 |

## 参考项目

- [QuixiAI/Hexis](https://github.com/QuixiAI/Hexis) — AI写作模式检测引擎（当前实现 36 种模式），含 AI-ness Score 算法
- [DadaNanjesha/AI-Text-Humanizer-App](https://github.com/DadaNanjesha/AI-Text-Humanizer-App) — 学术文本人性化，含 AcademicTextHumanizer 类
- [causify-ai/helpers](https://github.com/causify-ai/helpers) — humanize_text 工具函数
- [aadya940/autoresume](https://github.com/aadya940/autoresume) — AI痕迹移除后处理

## 反模式

| 禁止行为 | 原因 | 正确做法 |
|---------|------|---------|
| 只替换词汇不调整句式 | 治标不治本，AI味仍在 | 重构整句结构 |
| 盲目增加学术词汇 | 使文本更生硬 | 用真实人类语料对照 |
| 完全依赖LLM重写 | 可能引入新的AI模式 | GitHub真实语料 + 规则检测双验证 |
| 忽略中英文差异 | 中文AI特征不同于英文 | 使用独立的中文检测规则 |
