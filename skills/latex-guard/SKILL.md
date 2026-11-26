---
name: latex-guard
description: LaTeX 编译防错与排版质量守护技能。专为东北大学学位论文模板(NEU-Thesis)设计，但适用于任何中文学位论文LaTeX模板。提供7类常见编译错误的快速诊断修复、表格排版规范、标准编译流程、12类PDF排版质量检测清单、编译后强制验证流程。关键词触发："编译论文"、"LaTeX报错"、"表格溢出"、"xelatex"、"tex文件"、"bibtex"、"Extra alignment"、"Overfull"、"Float too large"、任何涉及 .tex 文件编写、LaTeX 编译、表格制作、xelatex 命令执行、bibtex 引用处理、图表跨页分离、浮动体位置控制、minipage 绑定、longtable 长表格、FloatBarrier 浮动屏障 的场景均触发本技能。 新增批量浮动体修复模式：当需要系统性检查和修复整篇论文所有图表的跨页分离、位置漂移问题时触发此模式（"系统性检查浮动体"、"修复所有图表位置"、"批量优化排版"、"论文排版整体修复"）。
---

# LaTeX Guard — LaTeX 编译防错与排版质量守护技能

## 🔴 加载资格与委托守则（必须读）

本技能是 **LaTeX 质检（latex_linter）子代理** 的专项规范，**仅供 `latex_linter` 子代理加载执行**（writing 子代理在编译时也可参考本技能排查报错，但正式的质检报告由 latex_linter 出具）。

- 若你是主对话主 agent：需要论文 LaTeX 质检 / 编译验证时，派发 `subagent_type=latex_linter` 子代理；不得为了"顺便检查"而自己直接加载本技能逐条修 .tex。
- latex_linter 只报告不修改（只读审查 + 编译验证）；发现的问题由 writing 子代理按报告返修。

## 技能触发

任何涉及 .tex 文件编写、LaTeX 编译、表格制作、xelatex 命令执行、bibtex 引用处理、
图表跨页分离、浮动体位置控制、minipage 绑定、longtable 长表格、
FloatBarrier 浮动屏障 的场景均触发本技能。默认面向 NEU-Thesis 模板，但诊断方法同样适用于其他中文学位论文模板。

---

## 一、七大类常见编译错误

### 1.1 "Extra alignment tab has been changed to \cr."

**含义**：表格列数定义与实际数据列数不匹配。

**原因**：`\begin{tabular}{...}` 中定义的列数 < 数据行中 `&` 分隔符数 + 1。

**诊断**：数清列格式中 `l`/`c`/`r`/`p{}` 的个数，再数数据行中 `&` 的个数。例如 `{ccccccc}` 有7列，每行应恰好有6个 `&`。

**修复**：
- 修改 `\begin{tabular}{...}` 中的列数定义使其匹配数据行
- 或删除数据行中多余的 `&`

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 修改列数定义或删除多余 `&` 仍有错 | 进一步检查是否嵌套表格、`\multicolumn{...}` 内部列数未对齐 |
| 二线 | 报错指向嵌套 tabular 或 multirow | 改用三线表 + `booktabs`（`\toprule \midrule \bottomrule`），删除所有 `\cline` |
| 兜底 | 二线仍失败 | 用 `Tex/<filename>.log` 的具体行号定位；从最后改动处向前回溯，按行号二分定位 |

### 1.2 "Overfull \hbox" / "Float too large for page"

**含义**：表格宽度超出页面宽度。

**原因**：多列表格（≥6列）未做缩放处理。

**修复优先级（按表格宽度选择）**：

| 表格特征 | 方案 | 命令/环境 |
|---------|------|---------|
| 列数≤5 | 居中 + 五号字 | `\centering\zihao{5}` |
| 列数6-8 | 缩放适配 | `\tablefit{\begin{tabular}{...}...\end{tabular}}` |
| 列数≥9 | 横向页面 | `\begin{sidewaystable}...\end{sidewaystable}` |
| 超长表格 | 跨页表格 | `\begin{longtable}{...}...\end{longtable}` |
| 附录超大表 | 缩放 + 横向 | `sidewaystable` 内嵌 `\tablefit` |

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 套 `\tablefit{}` 或缩小字号到 `\zihao{5}`/`\zihao{-5}` 仍报 Overfull | 换 `\begin{sidewaystable}` 横向页面；或 `\resizebox{\textwidth}{!}{...}` 包裹整个 tabular |
| 二线 | 横向页仍报 Float too large（高度超页） | 拆分为多张小表，用 `\ContinuedFloat` 关联；或长表用 `\begin{longtable}{...}` + `\endhead` 重复表头 |
| 兜底 | 拆表后语义断裂 | 导出为图片 `\includegraphics[width=\textwidth]{table.png}`（最后手段，PDF 中无法复制文字） |

### 1.3 图表、文字、表格跨页分离问题（系统性解决方案）

#### 1.3.1 问题本质

LaTeX 浮动体（figure/table）默认自由漂移，自动寻找"最佳"位置放置，但这常常导致图表和描述它的文字被分隔在不同页面。三种解决思路：**限制浮动范围** / **强制内容绑定** / **调整全局规则**。以下按可靠性从高到低展开。

#### 1.3.2 浮动体位置参数详解

位置参数控制浮动体的放置偏好。`\begin{figure}[参数]` 或 `\begin{table}[参数]` 中的可选字母：

| 参数 | 含义 | 优先级 | 说明 |
|------|------|--------|------|
| `h` | here | ★ | 尽量放在当前位置（此处） |
| `t` | top | ★★ | 尽量放在页面顶部 |
| `b` | bottom | ★★ | 尽量放在页面底部 |
| `p` | page | ★ | 放在单独的浮动页 |
| `!` | 强制执行 | — | 忽略 LaTeX 对页面上浮动体数量的限制 |
| `H` | 强制在此 | ★★★ | 必须放在此处（需 `\usepackage{float}`） |

**推荐组合**：
- **通用推荐**：`[hbt!]` —— 首选此处，不行放顶部，再不行放底部，忽略数量限制
- **精确控制**：`[H]` —— 强制锁定在代码位置（但需谨慎使用，可能造成大片空白）
- **顶部偏好**：`[t!]` —— 强制放在页面顶部

> ⚠️ **`[H]` 是"核武器"**：它完全绕过 LaTeX 浮动机制，可能导致页面底部大量空白。仅在定稿阶段、确认排版无问题后使用。日常写作优先用 `[hbt!]`。

#### 1.3.3 强制内容绑定（最可靠）

当必须确保"某段文字 + 某张图/表"绝对不跨页时，用盒子环境将它们打包在一起。

**① minipage 环境（首选，最可靠）**

LaTeX 保证绝不会在 `minipage` 盒子内部进行分页，是所有方案中最可靠的：

```latex
\noindent\begin{minipage}{\textwidth}
\vspace{4pt}                                     % 上部留一点空间
关于城市轨道交通运营效率的评价指标体系见表 \ref{tab:efficiency}。
\begin{table}[H]\centering\zihao{5}
  \caption{运营效率评价指标体系}\label{tab:efficiency}
  \tablefit{
    \begin{tabular}{clc}
      \toprule
      序号 & 指标名称 & 权重 \\
      \midrule
      1 & 准点率 & 0.35 \\
      2 & 客流强度 & 0.28 \\
      \bottomrule
    \end{tabular}
  }
\end{table}
\vspace{4pt}                                     % 下部留一点空间
\end{minipage}
```

**② \vbox（更轻量）**

纯 TeX 原语，比 minipage 更轻量，但功能较少（不支持 footnote 等）：

```latex
\vbox{
关于城市轨道交通运营效率的评价指标体系如下表所示：
\begin{table}[H]\centering\zihao{5}
  \caption{运营效率评价指标体系}\label{tab:efficiency}
  ...
\end{table}
}
```

**③ \parbox（适合短内容）**

用于包裹简短的内容组合，适合"一句话 + 小图表"的场景：

```latex
\parbox{\textwidth}{
该区域土地利用变化如图 \ref{fig:landuse} 所示：
\begin{figure}[H]\centering
  \includegraphics[width=0.8\textwidth]{Img/landuse.png}
  \caption{土地利用变化图}\label{fig:landuse}
\end{figure}
}
```

**④ samepage 环境（不推荐）**

LaTeX 标准 `samepage` 环境试图阻止分页，但效果有限：

```latex
\begin{samepage}
关于...见表 \ref{tab:xxx}。
\begin{table}[H]\centering ...
\end{table}
\end{samepage}
```

> ⚠️ **警告**：CMU 官方文档明确指出 `samepage` 在很多情况下是无效的。不推荐依赖它。

#### 1.3.4 浮动屏障（\FloatBarrier）

当不需要精确绑定文字和图表，但需要确保"在某个位置之前所有浮动体都必须落位"时使用。

**基础用法**：

```latex
\usepackage{placeins}

% ... 章节内容 ...

\FloatBarrier   % 此处之前所有浮动体必须落位，不能越过此屏障
```

**带 [section] 选项（推荐）**：

```latex
\usepackage[section]{placeins}
```

加上 `[section]` 参数后，LaTeX 自动在每个 `\section` 命令前插入 `\FloatBarrier`，确保每个章节内的图表不会跑到下一个章节中去。**这是学术论文最优雅的浮动控制方案。**

> 📌 **本项目已应用**：在 `Thesis.tex` 第 27 行已添加 `\usepackage[section]{placeins}`，自动控制每章浮动体范围。

#### 1.3.5 全局参数调整

通过调整 LaTeX 内部参数，让浮动体更容易在目标位置放置，减少漂移。将以下代码放入导言区（`\begin{document}` 之前）：

```latex
% ===== 浮动体全局参数调整 =====
\renewcommand{\topfraction}{0.9}        % 页面顶部最多可被浮动体占据 90%（默认0.7）
\renewcommand{\bottomfraction}{0.9}     % 页面底部最多可被浮动体占据 90%（默认0.3）
\renewcommand{\textfraction}{0.1}       % 页面至少保留 10% 给正文（默认0.2）
\renewcommand{\floatpagefraction}{0.7}  % 浮动页上浮动体至少占 70%（默认0.5）
\setcounter{topnumber}{3}               % 页面顶部最多 3 个浮动体（默认2）
\setcounter{bottomnumber}{2}            % 页面底部最多 2 个浮动体（默认1）
\setcounter{totalnumber}{5}             % 每页最多 5 个浮动体（默认3）
\raggedbottom                           % 允许底部留白，避免拉伸填充
```

**核心参数说明**：
- `\topfraction=0.9` + `\bottomfraction=0.9`：让 LaTeX 更愿意在目标位置放置浮动体（而不是拒绝后推到后面页面）
- `\raggedbottom`：页面底部不对齐，避免为填满页面而将浮动体推远

#### 1.3.6 特殊场景处理

**① 表格标题与表格分离**

当表格标题显示在一页底部、表格内容在下一页时：

```latex
\usepackage{caption}
\captionsetup[table]{position=above}       % 标题始终在表格上方
\captionsetup[table]{skip=2pt}             % 标题与表格间距
```

对于 figure 同理：
```latex
\captionsetup[figure]{position=below}      % 图标题在下方
```

**② 长表格跨页**

超过一页的表格必须用 `longtable`，不能用 `table` 环境：

```latex
\usepackage{longtable,booktabs}

{\zihao{5}
\begin{longtable}{ccccc}
  \caption{长表格示例}\label{tab:long-example}\\
  \toprule
  列1 & 列2 & 列3 & 列4 & 列5 \\
  \midrule
  \endfirsthead                                % 首页表头
  \multicolumn{5}{c}{\tablename\ \thetable{} （续）}\\
  \midrule
  列1 & 列2 & 列3 & 列4 & 列5 \\
  \midrule
  \endhead                                     % 续页表头
  \bottomrule
  \multicolumn{5}{r}{\footnotesize 续下页}\\
  \endfoot                                     % 续页底部
  \bottomrule
  \endlastfoot                                 % 末页底部
  数据行1 & ... & ... & ... & ... \\
  数据行2 & ... & ... & ... & ... \\
  % ... 更多数据行 ...
\end{longtable}
}
```

关键元素：
- `\endfirsthead`：首页显示的表头
- `\endhead`：从第2页起每页顶部重复的表头
- `\endfoot`：非末页底部显示的内容（如"续下页"）
- `\endlastfoot`：最后一页底部显示的内容

**③ 双栏排版**

在双栏文档中使用跨双栏的图表：

```latex
\begin{figure*}[t!]                      % 跨双栏图片，强制放顶部
  \centering
  \includegraphics[width=\textwidth]{Img/wide-figure.png}
  \caption{横跨双栏的宽图}\label{fig:wide}
\end{figure*}

\begin{table*}[t!]                        % 跨双栏表格
  \centering\zihao{5}
  \caption{横跨双栏的宽表}\label{tab:wide}
  \begin{tabular}{...}
    ...
  \end{tabular}
\end{table*}
```

注意：`table*` 和 `figure*` 只能放置在页面顶部（`t`）或单独浮动页（`p`）。

**④ 延迟浮动体（afterpage）**

将浮动体精确延迟到下一页顶部：

```latex
\usepackage{afterpage}

\afterpage{
  \begin{figure}[t!]
    \centering
    \includegraphics[width=0.9\textwidth]{Img/delayed-figure.png}
    \caption{精确出现在下一页顶部的图}\label{fig:delayed}
  \end{figure}
  \FloatBarrier                           % 确保此图不会跨过下一个屏障
}
```

适用场景：当前页内容过多放不下图表，但又不想让图表飘到后面的页面。

#### 1.3.7 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `[h]` 参数无效，图表仍漂移 | `h` 只是建议，LaTeX 可以忽略 | 改为 `[h!]` 或 `[H]`；优先尝试增大 `\topfraction` 等全局参数 |
| 图表顺序错乱 | 多个浮动体互相竞争位置 | 对关键位置使用 `\FloatBarrier` 隔离；或使用 `[H]` 精确锁定顺序 |
| 图和标题分别在不同页 | `\caption` 在 `figure` 外部，或浮动体被拆分 | 确保 `\caption` 在 `\begin{figure}...\end{figure}` 内部 |
| 页面出现大片空白 | 浮动体被强制 `[H]` 锁定但当前位置放不下 | 减少 `[H]` 的使用；用 `afterpage` 延迟到下一页；调大 `\topfraction` 等参数 |

#### 1.3.8 最佳实践总结（优先级排序）

| 优先级 | 方案 | 适用场景 | 命令/配置 |
|-------|------|---------|---------|
| 1 | 位置参数 + 全局参数 | 日常写作，基础控制 | `[hbt!]` + `\topfraction=0.9` 等 |
| 2 | minipage 绑定 | 必须绑定场景 | `\begin{minipage}{\textwidth}...\end{minipage}` |
| 3 | placeins [section] | 章节级别自动控制 | `\usepackage[section]{placeins}` |
| 4 | longtable | 超过一页的表格 | `\begin{longtable}...\end{longtable}` |
| 5 | 定稿精调 | 最终排版确认 | 逐页检查，必要处用 `[H]` 或 `\FloatBarrier` |

> 📌 **黄金法则**：日常写作用 `[hbt!]` + 全局参数；章节用 `[section]{placeins}`；绑定用 `minipage`；长内容用 `longtable`。直到最后定稿时，再逐页精调分页。

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 用 `minipage{\textwidth}` 物理绑定（图+标题+说明）仍跨页分离 | 改用 `[H]` 强制浮动 + 导言区加 `\usepackage{float}` |
| 二线 | `[H]` 后图表挤压文字、版面失衡 | 检查位置参数是否用了 `[htbp]` 等弹性字符；改为 `[H]` 时同步删除弹性参数 |
| 兜底 | 二线仍失败（页面空间不足） | 调整前后段落长度让浮动体有空间；用 `\afterpage{\begin{figure}[H]...}` 延迟到下一页；接受当前分离并在定稿时手动微调 |

---

### 1.3.9 AI 生成 LaTeX 时代码提示模板

**通用提示词模板（让 AI 自动生成带分页控制的 LaTeX 代码）：**

```text
请生成以下内容的 LaTeX 代码，要求：
1. 所有表格使用 [hbt!] 位置参数，三线表格式（\toprule \midrule \bottomrule）
2. 如果某段文字直接关联一个表格/图片，请将文字和表格/图片放在同一个 minipage 环境中防止跨页分离
3. 如果表格超过30行或明确会跨页，使用 longtable 环境并设置 \endhead 重复表头
4. 每个 \section 前添加 \FloatBarrier，防止浮动体跨节漂移
5. 表格宽度用 \tablefit{} 包裹，或用 p{宽度} 指定列宽，确保不溢出页面
6. 所有宽度使用相对宽度（如 \textwidth、0.45\textwidth），不要使用绝对厘米
7. \caption 放在 \begin{table}/\begin{figure} 内部，确保与表/图绑定
8. 表格和图片前添加引导文字（如"如表 \ref{tab:xxx} 所示"）

具体需求：[在此描述你要生成的内容]
```

**修正已有代码的提示词模板：**

```text
我的 LaTeX 文件中表格和对应文字经常跨页分离，请帮我修改代码：
1. 将有"如表所示"等引导文字和对应表格放在同一个 minipage 中
2. 将 \begin{table}[htbp] 改为 \begin{table}[hbt!]
3. 在导言区添加浮动体全局参数调整：\topfraction=0.9, \bottomfraction=0.9, \textfraction=0.1
4. 将表格放在引导文字之后而非之前
5. 确保所有 \caption 在其所属环境内部

文件内容：[粘贴你的 .tex 代码]
```

### 1.4 公式与变量解释被分页切开

**含义**：公式在一页底部，它的"其中 $x$ 为..."解释文字被截到下一页顶部。

**修复**：用 `minipage` 盒子把公式和解释文字捆在一起：

```latex
\noindent\begin{minipage}{\textwidth}
\begin{equation}
  w_j = \frac{(\prod a_{ij})^{1/n}}{\sum (\prod a_{kj})^{1/n}} \tag{1}
\end{equation}
其中 $a_{ij}$ 为判断矩阵元素，$n$ 为矩阵阶数，$w_j$ 为权重向量。
\end{minipage}
```

公式太多无法避免跨页时，用 `\nopagebreak[4]` 确保编号在同一页：
```latex
\end{equation}\nopagebreak[4]   % 强烈建议此处不分页
其中 $x'_{ij}$...
```

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 用 `minipage{\textwidth}` 把公式+解释捆在一起仍跨页 | 在 `\end{equation}` 后加 `\nopagebreak[4]`（强烈建议此处不分页） |
| 二线 | `\nopagebreak[4]` 后公式区仍断裂（minipage 高度超页） | 把变量解释拆短；或将 minipage 改为 `\begin{minipage}[t]{0.9\textwidth}`（高度自适应） |
| 兜底 | 二线仍失败（页面实在放不下） | 手动断行——把变量解释拆成两段，前后各放一段：上页末尾给"其中 $a_{ij}$ 表示..."，下页开头接"具体计算公式如下" |

### 1.4.1 🔴 图表漂移（图表直接插在文段中间）

**含义**：图片/表格插在段落文字中间，把一段文字从中间截断（"文字→图→文字"的断裂版式），或图表紧贴文字无独立段落。

**判定**（编译后逐页检查 PDF）：

1. 图表是否**打断段落**：段落中间出现图/表（该段文字被截成两半分列图表上下）→ 违规；
2. 图表与前后文字是否**无空行/无独立段落**：`\end{figure}`/`\end{table}` 后直接跟文字（同一行）→ 违规；
3. 是否在正文引用位置**之前**出现（图表先于首次 `\ref{fig:xxx}` 的正文段落）→ 违规（图表必须出现在引用处之后、靠近引用处）。

**标准做法**：

- 图/表一律使用浮动环境 `\begin{figure}[htbp]` / `\begin{table}[htbp]`，**禁止** `[H]`（float 包强插）——`[H]` 会把图表硬塞进段落中间造成文字断裂；
- 图表前后各保留一个空行（独立段落），`\centering` 居中；
- 正文先用引导句引用（"如图 X 所示""见表 Y"），图表由 LaTeX 浮动到合适位置（页顶/页底/独立页均可），**不要求图表紧跟引用句**，但不得早于引用；
- 长表格用 `longtable` 或拆分为多表（表1、表2），禁止让表格跨页时把正文从中切断；
- 图表独占一行，禁止与文字并排（除非明确设计的 minipage 双栏排版）。

**验收检查**：随机抽取 5 处含图/表的页面，确认①无段落被图表截断；②图表前后有空行；③图表在正文引用之后出现。

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 图表插在段落中间（`[H]` 或浮动失败） | 改为 `[htbp]` 浮动；把图表移到段落之间（段尾空行后）；确认引用句在图表之前 |
| 二线 | `[htbp]` 后图表跑到引用句之前 | 调整浮动位置参数（`[tbp]`、`[!htbp]`），或在引用句加 `\FloatBarrier`（placeins 包）限定浮动区 |
| 兜底 | 浮动始终无法满足"引用之后、不截断段落" | 将图表放到该小节末尾独立成段，正文用"见表 X"指引 |

### 1.4.2 子图合并（同类图整理为子图，避免连续多张独立图）

**含义**：连续出现多张"同类/描述同一对象"的独立图（如 4 张不同参数下的曲线图、3 个方案的对比子图），每张单独编号（图1、图2、图3、图4），视觉碎片化、浪费版面。

**判定**：同一小节内连续 ≥2 张图，若属于同一分析对象/同一方法的不同侧面（参数对比、方案对比、时段对比），即应合并为**一个 figure 环境内的多个 subfigure**。

**标准做法**（subcaption 包）：

```latex
\begin{figure}[htbp]
  \centering
  \begin{subfigure}{0.45\textwidth}
    \centering
    \includegraphics[width=\textwidth]{fig_a.png}
    \caption{方案 A 的拟合结果}
    \label{fig:compare-a}
  \end{subfigure}
  \hfill
  \begin{subfigure}{0.45\textwidth}
    \centering
    \includegraphics[width=\textwidth]{fig_b.png}
    \caption{方案 B 的拟合结果}
    \label{fig:compare-b}
  \end{subfigure}
  \caption{不同方案拟合结果对比}
  \label{fig:compare}
\end{figure}
```

- 总图编号（图1）由外层 `\caption` 生成；子图编号（(a)(b)）由 `subfigure` 自动生成；
- 正文引用总图：`如图 \ref{fig:compare} 所示`；需要指向子图时：`图 \ref{fig:compare-a}`；
- 子图宽度统一（如各 0.45\textwidth + `\hfill` 或 `\qquad` 分隔），图片尺寸一致避免大小不一；
- 合并原则：同一对象的不同侧面/同一方法的不同方案/同一数据的多参数视角 → 合并；不同主题、不同章节用途的图 → 保持独立；
- 合并后如子图仍超过一行，可 2×2 或 3×2 网格排布（每行子图宽度按行数均分）。

**验收检查**：全文不存在"连续 3 张以上独立编号、但明显属于同一对比主题"的图。

### 1.5 段落孤行（一行只有一个字 / 一两个字）

**含义**：段落最后一行只剩下1-2个字，单独占据一整行（widow/orphan lines）。

**修复**：在 Thesis.tex 导言区（`\begin{document}` 之前）添加：

```latex
\clubpenalty=10000      % 禁止段首孤行
\widowpenalty=10000     % 禁止段尾孤行
\raggedbottom           % 允许底部留白，避免拉伸产生孤行
```

**单个段落手动修复**：段尾加 `\looseness=-1` 让 LaTeX 尝试收紧一行。

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 导言区设 `\clubpenalty=10000` + `\widowpenalty=10000` + `\raggedbottom` 后全局编译仍孤行 | 定位孤行所在段落，段尾手动加 `\looseness=-1`；或调整前一段长度 |
| 二线 | 单段修复后该段仍孤行（孤行不可避免） | 改写该段：合并短句、拆分长句、调整措辞使段落长度变化 |
| 兜底 | 二线仍失败（无法通过排版消除） | 手动 `\linebreak` 控制断行位置；接受视觉孤行（最后手段，学位论文偶有 1-2 处可接受） |

### 1.6 章节间的多余空白页

**含义**：新章从奇数页（右页）开始，上一章在奇数页结束时自动插入空白页。

**原因**：模板设定了 `openright`（学位论文正式规范）。

| 方案 | 命令 | 适用 |
|------|------|------|
| 符合规范（保留） | 不修改 | 正式提交版 |
| 消除空白页 | `\let\cleardoublepage\clearpage` | 草稿/审阅版 |

消除空白页操作（仅工作草稿）：在 `\begin{document}` 前插入 `\let\cleardoublepage\clearpage`。

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线（草稿） | 导言区加 `\let\cleardoublepage\clearpage` 后空白页消失 | 确认这是**草稿/审阅版**才用，正式提交版必须移除该指令 |
| 二线 | 一线仍报空白页（多个 `\let` 指令冲突） | 检查 `\documentclass` 是否有 `openright` 选项；临时改为 `openany`（正式提交前恢复） |
| 兜底 | 二线仍失败 | **保留空白页**——符合东北大学学位论文规范，正式版不得消除空白页；如学校未强制 `openright`，可向导师确认是否可删 `\let` 指令 |

### 1.7 "Undefined citation" / 引用显示 "[?]"

**含义**：参考文献引用无法解析。

**原因**：BibTeX 未运行，或 bib key 与 ref.bib 中不匹配，或 `\cite{}` 拼写错误。

**修复**：
1. 检查 `Biblio/ref.bib` 中是否存在该 key
2. 确认 `\cite{}` 中的 key 拼写与 bib 文件完全一致（区分大小写）
3. 重新执行完整编译链：`xelatex → bibtex → xelatex → xelatex`

#### 失败回退（if-then 三段式）

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 检查 `Biblio/ref.bib` 有该 key + `\cite{}` 拼写一致仍显示 `[?]` | 重新跑完整 4 步链：`xelatex → bibtex → xelatex → xelatex`（必须 4 步，3 步不够） |
| 二线 | 4 步链后仍 `[?]`（某次编译异常中断） | 删除 `.bbl`、`.aux`、`.bcf` 后重新生成；检查 `Thesis.aux` 中是否有 `\citation{keyname}` 记录 |
| 兜底 | 二线仍失败（bib 语法错误） | 用 `bibtex8` 或 `biber` 替代 `bibtex` 重跑；检查 bib 文件编码（必须 UTF-8）；查 CTex 论坛/StackExchange 搜 "Undefined citation NEU-thesis" |

---

## 二、表格排版完整规范

### 2.1 表格标准模板

```latex
\begin{table}[!htbp]\centering\zihao{5}
  \caption{表格标题}\label{tab:唯一标识}
  \tablefit{
    \begin{tabular}{cccccccc}
      \toprule
      列1 & 列2 & 列3 & 列4 & 列5 & 列6 & 列7 & 列8 \\
      \midrule
      数据行 & ... & ... & ... & ... & ... & ... & ... \\
      \bottomrule
    \end{tabular}
  }
\end{table}
```

### 2.2 单元格过长的处理

当某一列内容过长时，使用 `p{宽度}` 指定列宽让其自动换行：

```latex
\begin{tabular}{lp{4cm}p{3cm}cc}
```
- `p{4cm}`：该列宽度4cm，超出自动换行
- 可用表达式：`p{\dimexpr0.15\textwidth-2\tabcolsep\relax}` 精确计算

### 2.2.1 🔴 表格尺寸一致性（大小固定，全文字号统一）

表格宽度与字号必须**全文统一**，不允许出现同页两张表格宽度/字号不一致：

1. **宽度固定**：所有表格宽度不得超过 `\textwidth`；同一论文统一采用"整表宽度 = `\textwidth`"或"统一比例（如 0.8\textwidth）"中的一种，禁止混用；
2. **字号统一**：全文表格字号在 `\small` 与 `\footnotesize` 中**二选一**（推荐 `\small`），禁止同一篇论文混用多种表格字号；表头与表体字号一致；
3. **列宽固定**：列数一旦确定不再变动；长文本列用 `p{\dimexpr0.2\textwidth-2\tabcolsep\relax}` 这类**相对正文宽度**的表达式，禁止一列用 `4cm`、另一列用 `5cm` 的随意组合导致同行表格宽度漂移；
4. **对齐一致**：数值列右对齐、文本列左对齐、表头居中，全文统一；
5. 表格宽度可用 `\resizebox{\textwidth}{!}{...}` 或 `tabularx` 兜底压缩，但压缩后字号会被缩放——**优先调整列宽/换行，不优先 resizebox**（resizebox 会导致字号不一致）。

**验收检查**：同页任意两张表格，宽度差 ≤ 2mm、字号相同、表头行高一致。

### 2.2.2 表格与正文衔接（禁止字段与表格同行）

1. 表格环境结束后**必须空一行**再继续正文；`\end{table}` 后紧跟文本（同一行）会导致字段与表格视觉粘连，属于排版错误；
2. 表格前后必须有独立段落：表格前有引导句（"如表 X 所示"），表格后接分析句，不允许"表格+文字"堆在同一视觉行；
3. 表格标题 `\caption` 在表格上方、表注在表格下方，二者均不得与表格行同处一行。

### 2.3 表格注释和脚注

```latex
\begin{table}[!htbp]\centering\zihao{5}
  \caption{表格标题}\label{tab:xxx}
  \tablefit{\begin{tabular}{cccccc}
      \toprule 列1 & 列2 & 列3 \\ \midrule 数据 \\ \bottomrule
  \end{tabular}}
  \vspace{2pt}\tablefootnotesize
  注：表格脚注内容，说明数据来源、缩写等。
\end{table}
```

**注释字体规范（图注/表注统一）**：

- 表注放在表格下方，以 `注：` 开头，说明数据来源、单位、缩写、显著性标记（`* p<0.05` 等）；
- 图注/表注字体统一用 `\footnotesize`（或与正文表格字号一致的 `\small`），**全文注释字体一致**；禁止注释与正文同字号、禁止注释加粗；
- 注释文本不得与表格/图片同处一行，注释前后各保留一个空行（或 `\vspace{2pt}` 级间距）；
- 数据来源必须标注：`注：数据来源为 CUMCM 2026 A 题附件 1（原始数据，单位：万人）。`；
- 表格内的脚注标记用 `\tnote{a}`（threeparttable）或上标 `$^{a}$`，脚注内容集中到表注区。

### 2.4 LaTeX公式在表格单元格中

表格内的短公式用 `$...$` 内联，长公式用 `\makecell{$\displaystyle ...$}`：

```latex
% 需要在导言区加载 \usepackage{makecell}
& \makecell{$\displaystyle I = \frac{n}{W}\frac{\sum w_{ij}...}{\sum ...}$} &
```

---

## 三、标准编译流程

### 3.1 完整编译链（4步）

```bash
cd <你的NEU-Thesis模板目录>
xelatex -interaction=nonstopmode Thesis.tex    # 第1步：生成 .aux 文件
bibtex Thesis                                   # 第2步：生成 .bbl 引用数据
xelatex -interaction=nonstopmode Thesis.tex    # 第3步：解析引用
xelatex -interaction=nonstopmode Thesis.tex    # 第4步：确认交叉引用
```

### 3.2 快速编译（仅改正文无新增引用时）

```bash
xelatex -interaction=nonstopmode Thesis.tex
```

### 3.3 编译结果判断标准

- **成功**：生成 `Thesis.pdf`，.log 中无 `^!` 开头的 Error 行
- **警告可忽略**：`Overfull`、`Underfull`、`Font Warning` 通常不影响结果
- **必须修复**：`^!` 开头的 Error，`Float too large`，引用显示 `[?]`

### 3.3.5 🔴 编译产物复用（提效铁律，N7 多轮编译必读）

N7 链路（latex_linter 每轮验证、typesetting 排版后、反向复核）会对同一份源反复编译。
**每次编译前先判重**：

```bash
python skills/latex-guard/scripts/latex_compile_check.py --tex-dir <LaTeX目录> --check
```

- 输出 `NO_RECOMPILE`：源自上次编译未变 → **跳过重编译**，直接复用上次 PDF 继续验证；
- 输出 `NEEDS_RECOMPILE`：源有变化 → 执行标准编译（xelatex×2 + bibtex + xelatex×1，输出 `<LaTeX目录>/.build/`）。

任何 `.tex`/`.bib`（含 `sections/*.tex`）字节级变化都会改变源集哈希并触发重编译，门禁语义不变。
**禁止对未变更源反复全量重编译**；正式提交的最终 PDF 以源目录内编译产物为准。

### 3.4 🔴 编译后强制验证（重要！）

每次编译完成后**必须**执行以下步骤，漏一步即为严重错误：

#### 步骤一：验证 PDF 输出位置

编译完成后，立即确认 PDF **确实生成在项目目录下**：

```bash
ls -la "Thesis.pdf"
# 或 PowerShell: Get-Item "Thesis.pdf" | Select FullName, Length
```

- ⚠️ **经典错误**：xelatex 工作目录是模板默认路径，但实际项目在其他目录。编译前务必 `cd` 到项目根目录，编译后验证 PDF 在该目录下。
- 如果 PDF 生成到了错误路径，立即拷贝到正确位置。

#### 步骤二：重命名为论文标题

PDF **不得**以 `Thesis.pdf` 交付，必须重命名：

```bash
mv Thesis.pdf "论文完整主标题.pdf"
# Windows: Rename-Item "Thesis.pdf" "论文完整主标题.pdf"
```

- 标题从 `Tex/Frontpages.tex` 的 `\thesistitle{}` 字段获取
- 使用中文主标题，不含副标题、不含英文翻译

#### 步骤三：推送绝对路径给用户

必须向用户输出 PDF 的完整绝对路径：

```
📄 PDF 已生成：<项目目录>/<论文标题>.pdf（XX 页，X.XX MB）
```

- 使用完整绝对路径，附带页数和文件大小，不可省略。

> 📌 **反模式**：本节列出的 3 个"经典错误"在附录 A.8 反模式速查表中也有索引，详见 [附录 A](#)。

#### 诊断命令索引

```bash
rg "^!" Thesis.log                        # 统计 Error
rg "Overfull.*hbox" Thesis.log | rg "pt"  # 统计表格溢出
rg "Warning.*Citation" Thesis.log         # 查看引用问题
```

---

## 四、NEU-Thesis 模板结构速查

```
<你的NEU-Thesis模板目录>/
├── Thesis.tex          ← 主入口（不要改结构和选项）
├── Style/
│   ├── neuthesis.cls   ← 文档类（禁止修改）
│   ├── artratex.sty    ← 样式宏包（可添加 \RequirePackage）
│   └── artracom.sty    ← 用户自定义宏（可自由添加命令）
├── Tex/
│   ├── Frontpages.tex  ← 封面字段
│   ├── Abstract.tex    ← 中英文摘要
│   ├── Mainmatter.tex  ← 引用章节输入文件
│   ├── Backmatter.tex  ← 致谢 + 附录
│   ├── Chap_1.tex ~ Chap_7.tex  ← 各章节内容
│   └── Tables_Best_Practices.tex  ← 表格参考（不参与编译）
├── Biblio/
│   └── ref.bib         ← BibTeX 参考文献数据库
├── Img/                ← 图表存放目录
└── simfang.ttf, simhei.ttf, simkai.ttf, simsun.ttc ← 中文字体文件
```

### 4.1 模板修改红线

| ✅ 允许修改 | ❌ 禁止修改 |
|-----------|-----------|
| `Style/artracom.sty` 添加新命令 | `Thesis.tex` 的 `\documentclass` 和选项 |
| `Style/artratex.sty` 添加 `\RequirePackage` | `neuthesis.cls` 的格式定义 |
| `Tex/` 下各章节内容文件 | 页面布局、字体规范、页码格式 |
| `Img/` 存放新图片 | `Frontpages.tex` 的字段结构 |
| `Biblio/ref.bib` 增删条目 | 编译引擎（必须用 xelatex） |

---

## 五、自我完善机制

每次编译过程发现新的错误类型或排版技巧时，立即追加到本文档对应章节。

### 5.1 添加新错误的格式

```markdown
### [错误关键字]
- **出现场景**：
- **诊断方法**：
- **修复步骤**：
- **模板修复位置**（如适用）：
```

### 5.2 添加新表格技巧的格式

追加到第二章"表格排版完整规范"中，保持编号递增。

### 5.3 已累积的教训

1. **列对齐错误(Extra alignment tab)**：数 `&` + 1 = 列数，两者必须匹配
2. **宽表溢出(Overfull)**：`\tablefit` 缩放是最通用方案
3. **巨型表格(Float too large)**：`\resizebox{\textwidth}{!}` 包裹整个 tabular
4. **引用缺失(Undefined citation)**：完整4步编译链是最可靠方案
5. **中文乱码**：必须用 `xelatex`，不要用 `pdflatex`
6. **空白页**：模板 `openright` 规范；草稿用 `\let\cleardoublepage\clearpage`
7. **图表跨页**：浮动体用 `[H]` 强制锁定位置，或用 `\FloatBarrier` 屏障
8. **公式与解释分离**：用 `minipage` 捆在一起，或用 `\nopagebreak[4]` 阻断开裂
9. **段尾孤行**：导言区设 `\clubpenalty=10000` + `\widowpenalty=10000` + `\raggedbottom`
10. **三线表缺失**：只用 `\toprule` `\midrule` `\bottomrule`
11. **表格跨页割裂**：用 `longtable` + `\endhead` 重复表头
12. **英文期刊名未斜体**：BibTeX 的 `journal` 字段自动处理
13. **单位与数字无空格**：用 `\Unit{cm}` 宏
14. **公式变量未斜体**：变量用 `$x$`，单位用 `\mathrm{m}`
15. **图题分离**：`\begin{figure}[H]` 锁定图片位置
16. **图片模糊**：导出时设 `dpi=300`
17. **占位符残留**：编译后用脚本扫描 `(作者姓名)` 等关键字
18. **目录页码不匹配**：必须2次 xelatex 解析交叉引用
19. **PDF 路径错误**：编译前 cd 到项目根目录；编译后 verify PDF 落在项目目录下
20. **PDF 文件名不规范**：输出文件必须重命名为论文中文标题，不能保留 "Thesis.pdf"
21. **编译后未告知用户路径**：完成编译和重命名后，必须推送 PDF 的完整绝对路径 + 页数 + 文件大小
22. **minipage 捆绑法**：将文字+图/表放入 `minipage` 环境是最可靠的防跨页手段（优于 float 包 [H]）
23. **全局参数调整**：\topfraction=0.9 + \bottomfraction=0.9 + \textfraction=0.1 让 LaTeX 更愿意在目标位置放置浮动体
24. **\FloatBarrier + [section] 选项**：自动在每个 \section 处插入浮动屏障，是学术论文最优雅的方案
25. **longtable 替代 table**：长表格不能用 table 环境，必须用 longtable + \endhead 重复表头
26. **afterpage 延迟浮动**：用 `\afterpage{\begin{figure}[t!]...}` 将浮动体精确延迟到下一页顶部
27. **\nopagebreak[4]**：在表格前导文字末尾添加，确保"引用文字-表格"视觉连贯性（惩罚值10000，99%不断页）

---

## 六、常用工具宏

以下宏已在 `Style/artracom.sty` 中定义，所有章节文件可直接使用：

| 宏命令 | 作用 | 用法 |
|-------|------|------|
| `\tablefit{...}` | 表格缩放到页面宽度 | `\tablefit{\begin{tabular}...\end{tabular}}` |
| `\tablefootnotesize` | 表格脚注字号 | `\tablefootnotesize 注：...` |
| `\Vector{...}` | 数学向量（粗斜体） | `\Vector{x}` |
| `\Matrix{...}` | 数学矩阵（粗正体） | `\Matrix{A}` |
| `\Unit{...}` | 单位（正体） | `\Unit{kg/m^3}` |
| `\nopagebreak[4]` | 强烈建议在此不分页 | 公式后紧跟 `\nopagebreak[4]` |
| `\looseness=-1` | 尝试将段落收紧一行 | 段落末尾 `\looseness=-1` |

---

## 七、PDF 排版质量全面检测清单

论文编译完成后，按以下12大类逐项检查生成的 PDF。

### 7.1 封面与题名页

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 学位类型错误 | 硕士标"博士" | `Tex/Frontpages.tex` 中 `\thesislevel{}` |
| 校名断字 | N O R T H E A S T | 校名用 `\textbf` 包裹 |
| 标题断行混乱 | 多余空格、重复 | 用 `\\` 精确控制换行 |
| 信息缺失 | `(xx)` 占位符 | 逐字段填入真实内容 |

### 7.2 页码与页眉

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 页眉重复叠加 | 标题重复N次 | 检查 `\pagestyle` 定义 |
| 页码混用 | 前言阿拉伯/正文罗马 | `\frontmatter`(罗马) `\mainmatter`(阿拉伯) |
| 页码偏移 | I,II,III,IV 重复 | 删除多余 `\pagenumbering{}` |
| 目录页码不匹配 | 标注与实际不符 | 必须 2 次 xelatex |

### 7.3 目录结构

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 章节编号错乱 | 5.3 在 5.1 前 | 检查 `\section` 顺序 |
| 层级异常 | 三级标题缩进错 | `\subsection` 嵌套在 `\section` 内 |
| 引导点不齐 | 点线缺失 | 模板自动生成，不需改 |
| 图表索引缺失 | 图号后无标题 | 每个 `\caption{}` 有文字内容 |

### 7.4 正文结构

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 标题重复 | 同一章出现多次 | 删除重复 `\chapter{}` |
| 层级混乱 | 3.2.1 缺 3.2 | `\subsubsection` 在 `\subsection` 内 |
| 段首空格 | 空格混用 | LaTeX 自动缩进，不手动加 |
| 多余空行 | 连续空行 | 删除 `.tex` 中多余空行 |

### 7.5 公式与数学符号

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 上下标错误 | cm2 应为 cm² | 用 `cm$^2$` / `\textsuperscript{2}` |
| 变量未斜体 | x 应为 $x$ | 变量用 `$x$` 包裹 |
| 正斜体混排 | 单位 m 需正体 | `\Unit{m}` / `\mathrm{m}` |
| 编号不对齐 | 编号偏离 | 用 `\begin{equation}` |
| 公式引用残缺 | `[3]` 写成 `(3)` | `\label{eq:xxx}` + `\eqref{eq:xxx}` |

### 7.6 表格排版

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 三线表缺失 | 有竖线/多余横线 | 只用 `\toprule` `\midrule` `\bottomrule` |
| 跨页割裂 | 无表头续页 | `longtable` + `\endhead` |
| 表题分离 | 不在同一页 | `\begin{table}[H]` 锁定 |
| 列宽不均 | 溢出或过空 | 用 `p{3cm}` 固定列宽 |
| 表注缺失 | 无数据来源 | `\tablefootnotesize 注：...` |

### 7.7 图片与插图

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 图题缺失 | 图号后无文字 | 每个 `\caption{}` 填标题 |
| 图号不连续 | 缺图3.2 | 检查 `\label` 和引用 |
| 图题分离 | 图题跨页 | `\begin{figure}[H]` |
| 分辨率低 | 模糊/锯齿 | 导出 dpi=300，PNG/PDF |
| 引用格式错误 | 图2-1 → 图2.1 | `\ref{fig:xxx}` |

### 7.8 文字与标点符号

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 全角半角混排 | 中文夹英文标点 | 中文后用全角 `，。：；` |
| 引号不配对 | `"xxx"` → `"xxx"` | 直接输入 `""` |
| 破折号错误 | `--` 代 `—` | 用 `——` 或 `---` |
| 单位无空格 | 25cm → 25 cm | `\Unit{cm}` |
| 特殊符号 | ℃ % ± 错位 | `$^\circ$C` `\%` `$\pm$` |

### 7.9 参考文献与引用

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 上标位置 | 正文[1] 应为上标 | `\cite{}` 自动上标 |
| 序号不连续 | [1][2][5] | 检查 bib 条目完整性 |
| 英文未斜体 | 期刊名正体 | BibTeX `journal` 自动处理 |
| 条目不齐 | 悬挂缩进缺失 | `.bst` 自动处理 |
| 格式不统一 | 中英文混排混乱 | `ref.bib` 统一管理 |

### 7.10 固定模版页

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 声明页污染 | 页眉在声明页 | `\thispagestyle{empty}` |
| 摘要标题重复 |"摘 要"×3 | 删除多余 `\chapter*{摘要}` |
| 中英文不对应 | 段数不一致 | 确保一一对应 |
| 关键词格式 | 逗号分隔 | 统一用 `；` |

### 7.11 格式统一性

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 字体混用 | 宋/黑/楷随机 | 宋体正文+黑体标题 |
| 字号混乱 | 同级字数不同 | 模板自动统一 |
| 行距/段距不一致 | 间距差异 | 模板 `\linespread{}` |
| 中英文间距 | 无空格或过大 | XeLaTeX 自动处理 |

### 7.12 内容冗余与乱码

| 检查点 | 关键词 | 修复 |
|-------|--------|------|
| 乱码字符 |"宝""男士" | 替换为正确中文 |
| 占位符残留 |"(作者姓名)" | 替换为真实信息 |
| 代码残留 |"pip install" | 删除非论文内容 |
| 重复段落 | 同一段×2 | 删除重复内容 |

---

## 八、编译后一键排版检查

将 `scripts/check_latex_quality.ps1` 放到模板根目录，编译后运行即可批量扫描。

**使用方法**：

```powershell
# 默认扫描（Tex/ + Thesis.log）
.\scripts\check_latex_quality.ps1

# 自定义路径
.\scripts\check_latex_quality.ps1 -TexDir "Tex" -LogFile "Thesis.log"

# 输出 JSON（CI 集成用）
.\scripts\check_latex_quality.ps1 -OutputFormat json

# 输出 Markdown（嵌入交接记录）
.\scripts\check_latex_quality.ps1 -OutputFormat markdown
```

**检测项**：5 类源文件问题（占位符/绝对宽度/竖线表格/单[h]/samepage）+ 5 类编译日志问题（Error/Float too large/Overfull>50pt/Undefined citation/Undefined reference），详见脚本注释。

---

## 九、批量浮动体修复工作流（攻击模式）

当需要对一篇**已完成写作**的论文进行系统性的浮动体位置修复时，按以下工作流从粗到细、分层推进。

### 9.1 总流程

```
系统性扫描 → 全局参数调整 → 位置参数统一 → 脆弱点绑定 → 编译验证 → 遗留处理
```

### 9.2 Step 1：系统性扫描

用 grep/ripgrep 扫描所有 `.tex` 文件中的浮动体声明：

```bash
rg "\\\\begin\\{(figure|table)\\}" Tex/ --line-number
rg "\\\\begin\\{(figure|table)\\}" --include="*.tex" .
```

**检查每个浮动体的当前位置参数**（`[htbp]`、`[h]`、`[t]`、`[H]` 等），记录数量。目标：建立完整清单。

### 9.3 Step 2：全局参数调整（优先级 2）

在 `Thesis.tex` 导言区（`\begin{document}` 之前）添加或补全全局浮动体参数：

```latex
% ===== 浮动体全局参数 =====
\renewcommand{\topfraction}{0.9}        % 页面顶部最多 90% 给浮动体
\renewcommand{\bottomfraction}{0.9}     % 页面底部最多 90% 给浮动体
\renewcommand{\textfraction}{0.1}       % 正文至少保留 10%
\renewcommand{\floatpagefraction}{0.7}  % 浮动页至少占 70%
\setcounter{topnumber}{3}               % 顶部最多 3 个浮动体
\setcounter{bottomnumber}{2}            % 底部最多 2 个浮动体
\setcounter{totalnumber}{5}             % 每页最多 5 个浮动体
```

如果已存在 `\clubpenalty`、`\widowpenalty`、`\raggedbottom`、`\let\cleardoublepage\clearpage` 则保留不重复添加。

### 9.4 Step 3：位置参数统一（优先级 1）

将 Step 1 扫描到的所有浮动体位置参数统一修改为 `[hbt!]`：

```bash
# 批量替换（谨慎使用，先确认范围）
rg -l "\\\\begin\\{figure\\}\\[htbp\\]" Tex/ | xargs sed -i "s/\\\\begin{figure}\\[htbp\\]/\\\\begin{figure}[hbt!]/g"
rg -l "\\\\begin\\{table\\}\\[htbp\\]" Tex/ | xargs sed -i "s/\\\\begin{table}\\[htbp\\]/\\\\begin{table}[hbt!]/g"
```

> ⚠️ **重要**：执行前必须用 `rg` 确认所有目标，避免误改非标准格式的浮动体。推荐逐文件手动修改以确保精确性。

**参数说明**：
- `h` = here（首选此处）
- `b` = bottom（次选页面底部）
- `t` = top（再次选页面顶部）
- `!` = 忽略 LaTeX 内部限制

### 9.5 Step 4：脆弱点绑定（优先级 4+5）

**4a. `\nopagebreak[4]` 绑定（优先级 4）**

在直接引用图表编号的段落后添加分页禁止指令。当某段文字中包含 `如图\ref{fig:xxx}所示` 或 `见表\ref{tab:xxx}` 且该图表紧接其后时：

```latex
...这一延迟消化周期的形成机制如图\ref{fig:cumulative_returns_path}所示。\nopagebreak[4]
\begin{figure}[hbt!]
  ...
\end{figure}
```

**定位方法**：
```bash
rg "\\\\ref\\{fig:|\\\\ref\\{tab:" Tex/ --line-number
```

为每处引用对应段落的末尾添加 `\nopagebreak[4]`。

**4b. minipage 强绑定（优先级 5，最后手段）**

当 `[hbt!]` + `\nopagebreak[4]` 仍然无法阻止跨页分离时，用 minipage 进行物理绑定：

```latex
\noindent\begin{minipage}{\textwidth}
引导文字如图\ref{fig:xxx}所示。
\begin{figure}[H]\centering
  \includegraphics[width=0.85\textwidth]{Img/xxx.png}
  \caption{...}\label{fig:xxx}
\end{figure}
\end{minipage}
```

> ⚠️ minipage 内的浮动体必须使用 `[H]`（需 `\usepackage{float}`），否则浮动体会脱离盒子。

### 9.6 Step 5：编译验证

执行完整四步编译链：

```bash
cd <项目目录>
xelatex -interaction=nonstopmode Thesis.tex    # 第1步
bibtex Thesis                                   # 第2步（有新增引用时）
xelatex -interaction=nonstopmode Thesis.tex    # 第3步
xelatex -interaction=nonstopmode Thesis.tex    # 第4步
```

**验证标准**：

| 检查项 | 阈值 | 命令 |
|--------|------|------|
| 编译错误 (`^!`) | 必须为 0 | `rg "^!" Thesis.log` |
| 未定义引用 | 必须为 0 | `rg "undefined" Thesis.log` |
| Float too large | 必须为 0 | `rg "Float too large" Thesis.log` |
| Overfull hbox (>50pt) | 尽可能为 0 | `rg "Overfull.*hbox.*\\([5-9][0-9]" Thesis.log` |

### 9.7 Step 6：遗留处理

对于 Step 5 中发现的 `Float too large` 问题：
1. 缩放图片：`width=0.85\textwidth` → `0.78\textwidth`
2. 或降低表格字号：添加 `\zihao{5}` 或 `\footnotesize`
3. 或使用 `\tablefit{}` 包裹 tabular 环境

#### 9.7.1 批量修复失败回退

跑完 §9.1-§9.6 后，若仍存在遗留问题，按以下三段式逐层回退：

| 阶段 | 触发条件 | 修复 |
|------|---------|------|
| 一线 | 跑完 §9.1-§9.6 后 `rg "^!" Thesis.log` 仍 > 0（编译错误未清零） | 重跑完整 4 步编译链：`xelatex → bibtex → xelatex → xelatex`（§9.6 残留常因未跑全 4 步） |
| 二线 | 仍有 `Float too large` 报错 | 缩图片到 `0.78\textwidth`；或换 `longtable` 横向；或 `\resizebox{\textwidth}{!}{...}` 包裹整个 tabular |
| 兜底 | 仍有 `Overfull \hbox > 50pt` 顽固溢出 | 局部用 `\tablefit{}` 包裹；用 `minipage{\textwidth}` 单图锁定；接受最后 1-2 处小溢出（>50pt 才需要处理，<50pt 可接受） |

### 9.8 优先级决策表

| 优先级 | 方案 | 适用场景 | 侵入性 | 何时使用 |
|--------|------|---------|--------|---------|
| 1 | `[hbt!]` 位置参数 | 所有浮动体 | 低（安全） | 第一步，全局统一 |
| 2 | 全局参数调整 | 导言区一次性 | 低（安全） | 第一步，为后续提供宽容环境 |
| 3 | `\FloatBarrier [section]` | 章级别控制 | 低（安全） | 章间浮动体不跨越 |
| 4 | `\nopagebreak[4]` | 引用文字-图表之间 | 中（局部） | 引用段落末，逐处添加 |
| 5 | minipage 绑定 | 必须绝对绑定 | 高（锁死） | 仅当 1-4 全部无效时 |
| 6 | longtable | 超长表格 | 中（换环境） | 表格超过一页时 |

### 9.9 完整示例：一次典型修复的指令序列

```bash
# Step 1: 扫描
rg "\\begin{(figure|table)}" Tex/ --line-number > float_scan.txt

# Step 2: 全局参数（手动编辑 Thesis.tex 导言区）

# Step 3: 位置参数批量修改
rg -l "\\begin{figure}\[htbp\]" Tex/ | while read f; do
  sed -i "s/\\begin{figure}\[htbp\]/\\begin{figure}[hbt!]/g" "$f"
done
rg -l "\\begin{table}\[htbp\]" Tex/ | while read f; do
  sed -i "s/\\begin{table}\[htbp\]/\\begin{table}[hbt!]/g" "$f"
done

# Step 4: 脆弱点扫描
rg "\\ref\{(fig|tab):" Tex/Chap_Format.tex Tex/Backmatter.tex --line-number
# → 手动在每处段落末尾添加 \nopagebreak[4]

# Step 5: 编译验证
xelatex -interaction=nonstopmode Thesis.tex && \
bibtex Thesis && \
xelatex -interaction=nonstopmode Thesis.tex && \
xelatex -interaction=nonstopmode Thesis.tex

# Step 6: 遗留检查
rg "^!" Thesis.log            # 应为 0
rg "Float too large" Thesis.log  # 应为 0
```

---

## 附录 A：❌ 常见错误做法（反模式黑名单）

> 🚫 **本附录列出 LaTeX 论文写作中最常见的错误做法。遇到这些场景，**直接绕开**，使用正确方案。**

### A.1 ❌ 用 `pdflatex` 编译含中文的论文

| 项目 | 内容 |
|------|------|
| 错误做法 | `pdflatex Thesis.tex` |
| 触发后果 | 编译报 `Package inputenc Error: Unicode character ... not set up`、中文字符全部变方框、参考文献乱码 |
| 正确方案 | 强制使用 `xelatex` 编译。NEU-Thesis 模板已预配置 fontset，无需额外 fontspec 设置 |
| 检测命令 | `rg "pdflatex" *.log` 应为 0 命中 |

### A.2 ❌ 用 `samepage` 环境防止图表分页

| 项目 | 内容 |
|------|------|
| 错误做法 | `\begin{samepage}...引导文字...图表...\end{samepage}` |
| 触发后果 | 看似生效但实际分页，CMU 官方文档已确认 samepage 在多数场景无效 |
| 正确方案 | 用 `minipage{\textwidth}` 物理绑定文字+图/表（§1.3.3 ①），或用 `[H]` 强制浮动（需 `float` 包）|
| 检测命令 | `rg "\\\\begin\\{samepage\\}" Tex/` 应为 0 命中 |

### A.3 ❌ 表格用绝对宽度（如 `8cm`）

| 项目 | 内容 |
|------|------|
| 错误做法 | `\begin{tabular}{p{8cm}p{5cm}}` |
| 触发后果 | 切换页面尺寸/纸张方向后表格错位，无法适配不同模板 |
| 正确方案 | 改用相对宽度：`p{0.3\textwidth}` 或 `\tablefit{}` 自动缩放 |
| 检测命令 | `rg "p\\{[0-9]+cm\\}" Tex/` 应为 0 命中（全部改为相对宽度）|

### A.4 ❌ 表格用竖线/多余横线（如 `|c|c|c|`、`\hline\hline`）

| 项目 | 内容 |
|------|------|
| 错误做法 | `\begin{tabular}{|c|c|c|} \hline 数据 \\ \hline \end{tabular}` |
| 触发后果 | 学术论文规范禁止（非三线表），评审会要求重排 |
| 正确方案 | 三线表格式：只用 `\toprule` `\midrule` `\bottomrule`（需 `booktabs` 包）|
| 检测命令 | `rg "\\{|\\\\hline" Tex/` 应为 0 命中 |

### A.5 ❌ 用单一位置参数 `[h]` 期望精确控制

| 项目 | 内容 |
|------|------|
| 错误做法 | `\begin{figure}[h]...` |
| 触发后果 | LaTeX 经常忽略 `h`，图表漂移到其他位置 |
| 正确方案 | 日常写作用 `[hbt!]`（首选 h，不行 b，再不行 t，忽略数量限制）|
| 检测命令 | `rg "\\\\begin\\{figure\\}\\[h[^b]\\]" Tex/` 应为 0 命中（除 `[hbt!]`）|

### A.6 ❌ bibtex 引擎与 xelatex 不匹配

| 项目 | 内容 |
|------|------|
| 错误做法 | 跑 `latex` 而非 `bibtex`；或 `biber` 而非 `bibtex`（NEU-Thesis 默认 bibtex）|
| 触发后果 | 参考文献无法解析，显示 `[?]`，或报 `I found no \citation commands` |
| 正确方案 | 严格按 4 步链：`xelatex → bibtex → xelatex → xelatex`（NEU-Thesis 用 bibtex，不用 biber）|
| 检测命令 | `rg "I found no \\\\citation" Thesis.log` 应为 0 |

### A.7 ❌ 直接编辑 `neuthesis.cls` 修改格式

| 项目 | 内容 |
|------|------|
| 错误做法 | 打开 `Style/neuthesis.cls` 改字号、改页边距 |
| 触发后果 | 升级模板时所有改动丢失；与论文规范冲突导致格式审查不通过 |
| 正确方案 | 模板特定修改放到 `Style/artracom.sty`（用户自定义层），通用修改用 `\usepackage` 在导言区追加 |
| 检测命令 | `git diff Style/neuthesis.cls` 应为 0 行（提交前验证）|

### A.8 反模式速查表

| ❌ 反模式 | ✅ 正确做法 | 章节 |
|----------|------------|------|
| `pdflatex` 编译 | `xelatex` 编译 | A.1 |
| `samepage` 防分页 | `minipage` 或 `[H]` | A.2 |
| 绝对宽度 `8cm` | 相对宽度 `0.3\textwidth` | A.3 |
| 竖线 `\hline` 三线表 | `\toprule \midrule \bottomrule` | A.4 |
| 单参数 `[h]` | `[hbt!]` | A.5 |
| `biber` 引擎 | `bibtex`（NEU 模板）| A.6 |
| 改 `neuthesis.cls` | 改 `artracom.sty` | A.7 |
| 编译前不 `cd` 项目根 | `cd <项目目录>` 后编译 | §3.4 |
| PDF 不重命名 | 改为论文中文主标题 | §3.4 |
| 不告知用户 PDF 路径 | 推送绝对路径+页数+大小 | §3.4 |

### A.9 编译错误信息速查（系统检索整理：Overleaf Errors / learnlatex / TeX 常见问答）

遇到 `^!` 开头的报错先读 `Thesis.log` 中报错行**上方 3 行**的源码定位，按下表逐一修复：

| # | 报错消息（.log 原文） | 原因 | 修复 |
|---|----------------------|------|------|
| 1 | `Undefined control sequence.` | 命令拼写错误，或宏包未加载 | 检查拼写；在导言区 `\usepackage{...}` 加载对应宏包 |
| 2 | `Missing $ inserted.` | 正文文本中用了 `^`、`_`、`\frac` 等数学命令 | 放入 `$...$` 或数学环境 |
| 3 | `Double subscript.` | 写了 `x_1_2` 未加括号的下标嵌套 | 改为 `x_{1_2}` 或 `x_{1_{2}}` |
| 4 | `Display math should end with $$.` | `$$...$$` 首尾不匹配 | 补全/删除多余的 `$$`（更推荐 `\[...\]`） |
| 5 | `Extra alignment tab has been changed to \cr.` | 一行中 `&` 数量超过列定义 | 增加列数（`{ccc}`）或删除多余 `&` |
| 6 | `Misplaced alignment tab character &.` | 在正文文本中使用 `&` | 正文中写 `\&`；`&` 仅用于表格/对齐环境 |
| 7 | `Missing number, treated as zero.` | 长度/位置参数缺数值（如 `\hspace{}`） | 补数值：`\hspace{1cm}` |
| 8 | `Illegal unit of measure (pt inserted).` | 长度写了数字缺单位（如 `\hspace{10}`） | 加单位：`10pt`、`2em`、`3cm` |
| 9 | `LaTeX Error: Environment xxx undefined.` | 使用的环境未加载宏包（align→amsmath、tikzpicture→tikz、algorithm→algorithm） | 导言区加载对应宏包 |
| 10 | `LaTeX Error: File 'xxx' not found.` | `\input`/`\includegraphics` 文件不存在或路径错 | 核对文件名与相对路径；图片确认格式（PDF/PNG/JPG） |
| 11 | `Package pdftex.def Error: File 'xxx' not found.` | 图片文件缺失或扩展名错误 | 检查图片路径或转换格式 |
| 12 | `LaTeX Error: Can be used only in preamble.` | 命令（如 `\usepackage`）写在 `\begin{document}` 之后 | 移到导言区 |
| 13 | `` `h' float specifier changed to `ht'. `` | `[h]` 无法精确满足，LaTeX 自动放宽 | 直接用 `[hbt!]` / `[htbp]` |
| 14 | `No positions in optional float specifier.` | 浮动参数为空（`\begin{figure}[]`） | 补至少一个位置字母 |
| 15 | `There were undefined references.` / `Reference xxx undefined on input line y.` | `\ref`/`\cite` 指向不存在的标签，或编译次数不足 | 检查标签拼写；按 4 步链重跑（xelatex→bibtex→xelatex→xelatex） |
| 16 | `There were multiply-defined labels.` | 两个 `\label` 同名 | 改为唯一标签名 |
| 17 | `I found no \citation commands.` | bibtex 未找到引用命令（`.aux` 过期或引擎不匹配） | 先 xelatex 生成 `.aux` 再 bibtex；确认引擎（bibtex，不用 biber） |
| 18 | `Float too large for page.` | 图表/表格超出页面可放区域 | 缩小 `\includegraphics[width=...]`、拆分长表格、缩短表注 |
| 19 | `Overfull \hbox (...) too wide.` | 一行内容超出页宽 | 缩短该行（换词/断句）；表格过宽则按 §2.2.1 处理 |
| 20 | `Underfull \hbox` / `Underfull \vbox` | 空白过多（警告级） | 通常可忽略；影响观感时用 `\sloppy` 或调整断行 |

### A.10 数学公式类反例

| ❌ 反例 | 问题 | ✅ 正确写法 |
|--------|------|------------|
| `$x_1_2$` | 双重下标报错 | `$x_{1_2}$` |
| `$a<b$` 期望显示 `a<b` | 未转义关系符被当作标签 | `$a\textless b$` 或 `$a < b$`（数学模式内 `<` 合法） |
| `\begin{equation}...\end{equation}` 内用 `\\` 换行 | equation 不支持换行 | 用 `aligned`/`split` 环境（需 amsmath） |
| 行内 `$\frac{...}{...}$` 使行距被撑大 | 行内大公式挤压行距 | 用 `\dfrac` 或 `\tfrac` 按需；大公式独立成 `\[...\]` |
| `$$...$$` 裸定界 | 间距/编号不可控 | `\[...\]` 或 `equation` 环境 |
| 正文中直接写 `%`、`#`、`_`、`&` | 特殊字符被解析 | `\%`、`\#`、`\_`、`\&`（文本模式） |

### A.11 引用与标签类反例

| ❌ 反例 | 问题 | ✅ 正确做法 |
|--------|------|------------|
| `\label` 写在 `\caption` 之前 | 引用指向上一编号 | `\label` 必须紧跟 `\caption` 之后 |
| 同一 `\label{fig:result}` 用两次 | multiply-defined | 每个标签唯一；图 `fig:`、表 `tab:`、公式 `eq:`、节 `sec:` 前缀命名 |
| 只编译一次就交付 | 交叉引用显示 `??` | 完整 4 步链：xelatex→bibtex→xelatex→xelatex |
| `\cite{key}` 但 ref.bib 无此条目 | 显示 `[?]` | 补 bib 条目并重跑 bibtex |
| 引用了未列出的图/表编号（手写"图5"） | 编号漂移 | 一律用 `\ref{fig:xxx}`，禁止手写编号 |
| 图表先出现、正文引用在后 | 读者看到"图X"却无指引 | 正文先引用（"如图 X 所示"），图表浮动到引用之后 |

### A.12 中文与字体类反例（XeLaTeX + ctex）

| ❌ 反例 | 问题 | ✅ 正确做法 |
|--------|------|------------|
| `pdflatex` 编译含中文文档 | 中文乱码/缺字 | 用 `xelatex` 或 `lualatex` 编译（见 A.1） |
| `\documentclass{article}` + 中文 | 标题/目录仍是英文"Abstract/Contents" | 用 `ctexart`（或 `\usepackage{ctex}`），标题自动中文化 |
| 未配置 CJK 字体 | PDF 中部分汉字不显示（空白方框） | `\setCJKmainfont{...}`（如 FandolSong、SimSun）；确认字体含所需字形 |
| 中文引号被替换成西文引号 | 标点不规范 | 用中文引号 ""'' 原样输入（xelatex 直接支持 UTF-8），或 `\usepackage{csquotes}` |
| 中文与英文/公式混排无间隔 | 中英文粘连、行距不均 | xelatex 下直接混排即可；正文留自然空格；`\setlength{\parskip}` 控制段距 |
| 用 `\\` 手动换行模拟段距 | 段落结构错误 | 段落用空行分隔，`\\` 只用于表格/诗歌等 |

### A.13 文件与缓存类反例

| ❌ 反例 | 问题 | ✅ 正确做法 |
|--------|------|------------|
| 图片用 `.eps` 且引擎是 xelatex | 找不到/无法嵌入 | xelatex 用 PDF/PNG/JPG；EPS 需 `epstopdf` 转换 |
| `\includegraphics{fig}` 无扩展名 | 引擎按自己的顺序找文件 | 显式写扩展名或确认路径；图片放同一相对路径 |
| 修改 ref.bib 后只跑一次 xelatex | 引用仍是旧数据/`[?]` | 按 4 步链重跑；改完 `.bib` 必须重跑 bibtex |
| 删除了 `.aux` 后直接 bibtex | `I found no \citation` | 先 xelatex 生成 `.aux` 再 bibtex |
| 宏包重复加载（同一包两个版本） | Option clash / 冲突报错 | 每个包只 `\usepackage` 一次；用 `\PassOptionsToPackage` 传选项 |
| 修改模板 `.cls` 文件 | 升级丢失/格式违规 | 修改放用户层（artracom.sty / 导言区） |

### A.14 表格类反例补充（配合 §2 表格规范）

| ❌ 反例 | 问题 | ✅ 正确做法 |
|--------|------|------------|
| `{ccccc}` 5 列但某行只写 4 个 `&` | Extra alignment tab / 缺列 | 每行 `&` 数 = 列数-1 |
| `\begin{tabular}{cccccccc}` 8 列且全文本列 | 表格过宽 Overfull、字号被压 | 合并列/精简内容；长文本列用 `p{\dimexpr0.2\textwidth-2\tabcolsep\relax}` |
| 不同表格用不同字号/宽度 | 同页表格大小不一致 | 全文统一 `\small` 或 `\footnotesize`；宽度 ≤ `\textwidth`（§2.2.1） |
| `\end{table}` 后紧跟正文 | 字段与表格同行视觉粘连 | 表格后空一行再写正文（§2.2.2） |
| 表格跨页把正文从中切断 | 正文断裂 | 长表用 `longtable`（`\endfirsthead/\endhead/\endfoot`）或拆分多表 |
| 表注与表格同字号 | 注释不显著 | 表注统一 `\footnotesize`，以"注："开头（§2.3） |

### A.15 浮动与图表类反例补充（配合 §1.4.1/1.4.2）

| ❌ 反例 | 问题 | ✅ 正确做法 |
|--------|------|------------|
| `\begin{figure}[H]`（float 包强插） | 图表硬插进段落中间截断文字 | `[hbt!]`/`[htbp]` 浮动，段落之间放置（§1.4.1） |
| 连续 3 张同类独立图（图1/图2/图3） | 版面碎片化、编号膨胀 | 合并为 subfigure 子图（§1.4.2） |
| 图表未引用就出现 | 读者无指引 | 正文先"如图 X 所示"，再让浮动体放置 |
| `\caption` 与 `\includegraphics` 同行 | 排版混乱 | caption 独立一行，位于图下方/表上方 |
| 图注用正文字号/加粗 | 注释字体不统一 | 图注/表注统一 `\footnotesize`（§2.3） |

> ⚠️ **配套工具声明**：本 Skill 引用的 `templates/*.md`、`scripts/*.py|.ps1|.ts`、`docs/design/*.md`、`docs/images/` 等为外部配套工具/示例，仓库未内置这些文件；引用仅作规范说明，实际使用需按需自备或从上游来源获取（不构成仓库内可访问的承诺）。
