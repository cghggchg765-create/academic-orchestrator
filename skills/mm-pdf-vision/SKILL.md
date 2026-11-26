---
name: mm-pdf-vision
description: " PDF 视觉逐页阅读 + 量化排版核查：既逐页读图核查页序/页码/图表位置/正文页数/乱码/身份信息，也用脚本量化页底留白、段落是否被图表截断、图表是否先引用后出现、图表与引用页距、表格实际渲染字号、图片渲染尺寸。触发词：PDF 格式检查，渲染 PDF，逐页阅读，视觉核查，pdf pages，vision format check，页面空白，留白太多，图漂移，图文不在同一页，图表没被引用，表格字号不一致，排版检查，视觉检查"
metadata:
  version: "1.1.0"
  last_updated: "2026-09-13"
  status: active
  related_skills:
    - mm-latex-writing
    - make-pdf
    - mm-self-review
    - latex-guard
---

【范围】竞赛题目 PDF 图形识别。一般 PDF 解析请用 pdf / pdf-to-markdown 等技能。

# MM PDF Vision — PDF 视觉逐页阅读与格式核查

## 作用与适用范围

当需要对**最终 PDF（或已有 PDF 论文/材料）**做格式与版面核查，且当前模型**具备视觉能力**时，把 PDF **渲染为分页图片，逐页阅读**再判定；这与“只读 PDF 文本抽取”互补——页码居中、图表与引用段落相对位置、页面元素溢出、乱码、身份信息等只能靠视觉判定。

适用场景：

- `ReportPaper/LaTeX/build/main.pdf` 编译后的格式核查（CUMCM 2026 profile：页序/正文≤30 页/摘要≤1 页/页码/无目录/PDF≤20MB）；
- 接手已有 PDF 论文/支撑材料时的版面审阅；
- 图表与正文位置核对（图不远离引用段、图表不早于章节标题）；
- N8 终审前对最终 PDF 做视觉终检。

## 加载资格与委托守则

- 本技能可由 **latex_linter（PDF 视觉核查模式）、reviewer（join-review）、mm-viz-reviewer（版面/位置核对）、具备视觉能力的主对话模型** 加载执行。
- 主对话无视觉能力时：**不得假装已读图**，必须生成人工核查请求单并置门禁 `PENDING`（非 PASS），等人工确认后再继续。
- 本技能只做“读图 + 核查 + 报告”，不直接修改 PDF/LaTeX；修改由 writing/typesetting/visualization 按其职责执行。

## 第一步：渲染 PDF 为分页图片

```bash
# 项目内执行（先在项目根创建/激活 venv 视为可选；渲染工具为系统命令或可选包）
python scripts/pdf_render_pages.py <pdf路径> --out state/reports/pdf-pages/<版本名> --dpi 150
```

输出：

- `state/reports/pdf-pages/<版本名>/page-0001.png ... page-00NN.png`（每页一张，按页码排序）；
- `state/reports/pdf-pages/<版本名>/manifest.json`：源 PDF 路径/SHA-256、页数、dpi、引擎、每页图片路径、渲染时间。

引擎：由 **PyMuPDF** 完成渲染，脚本不调用任何外部进程（早期版本串联 pdftoppm/mutool/gs，已刻意收敛为单一可审计代码路径）。缺 PyMuPDF 时输出 `TOOL_BLOCKED` 并给出安装提示与替代解释器用法，**不写出部分 manifest**，以免下游门禁被静默放行。

```bash
# 依赖预检（本技能 5 个脚本需要 PyMuPDF；measure_figures 需要 PIL）
python -c "import fitz, PIL" 2>&1 || echo "缺依赖：pip install pymupdf pillow"
# 若项目 venv 缺依赖，用装有 PyMuPDF 的解释器运行，例如：
#   /path/to/python-with-pymupdf scripts/pdf_render_pages.py main.pdf --out state/reports/pdf-pages/<版本名> --dpi 150
```

## 第二步：先跑量化指标（🖼️ 读图之前，先拿到数字）

逐页读图只能得到"这里好像空得多"这类判断，容易漏、也无法证明修改有效。**在读图之前先跑一遍量化指标**，得到全篇的页码 + 数值基线，再带着它去读图，可以精确定位到"第几页、哪一段"。

**依赖前置检查**：三个脚本要 `PyMuPDF`，一个要 `PIL`——**项目 venv 往往两个都没装**。先探一次，缺则 `pip install pymupdf pillow`，或改用已装好的解释器（把下面的 `python` 换成对应路径）：

```bash
python -c "import fitz, PIL" 2>&1 || echo "缺依赖：pip install pymupdf pillow"
```

```bash
S=scripts   # 本技能 scripts/ 目录

# ① 页底留白 + 段落是否被图表截断（传 PDF 路径，不需要预先渲染）
python $S/check_interruptions.py main.pdf            # 全篇逐页表格 + 留白统计
python $S/check_interruptions.py main.pdf 30         # 只看前 30 页（正文），附录多时可这样收窄

# ② 图表是否先于首次引用出现（图前有没有引导句）
python $S/audit_float_citation.py main.pdf           # 必须为 0；非 0 时逐条列出 label 与页码

# ③ 图表与引用的页距（同页 / 相邻 / 漂移）
python $S/measure_drift.py main.pdf                  # 依赖 main.aux 与 PDF 同源

# ④ 浮动体落位总表（哪张图在哪一页）
python $S/list_float_pages.py main.aux

# ⑤ 图片渲染尺寸（判断是否过大 / 是否统一；需 PIL）
python $S/measure_figures.py                         # ⚠️ 脚本内 FIGDIR 与图列表是项目专属，复用前先改这两处

# ⑥ 表内实际渲染字号（发现 \resizebox 造出的字号不一致）
#    见 references/quantified-layout-checks.md §4 的片段

# ⑦ 备选：纯 PGM 留白量测（不经 PyMuPDF；① 已覆盖其功能，仅在无法装 PyMuPDF 时使用）
pdftoppm -f 1 -l 30 -gray -r 72 main.pdf /tmp/pg && python $S/measure_whitespace.py "/tmp/pg-*.pgm" 72
```

> 脚本缺依赖时会打印安装提示并以非零码退出，不会抛裸 traceback。**若某脚本报"需要 PyMuPDF"，说明用错了解释器**。

判据（完整口径见 `references/quantified-layout-checks.md`）：

- **段落被图表截断 = 0**（最伤阅读体验，优先修）
- **图表先于首次引用出现 = 0**（每个图表都必须先被正文引用）
- **页底留白 > 120pt 的页数**：目标是 0；修改前后对比这个数字
- **页距 ≥2 页 = 漂移**，必须修；=1 相邻页可接受
- **表格字号全篇一致**；**数据图统一宽度、超高结构图按高度封顶**

> ⚠️ 三项权衡：留白 / 段落截断 / 图文同页**不能同时最优**。改成 `[htbp]` 浮动可消留白，但被推到次页页顶的图会把后面那段文字拉上来、**截断段落**；`[H]` 强制就位永不截断，但图表前那页会留白。优先级：**先保段落不被截断，再压留白，最后才对个别图加同页约束**——加同页约束必须逐例核对留白代价（实践中曾因阈值过大留下 520pt / 628pt 的近乎整页空白）。
>
> ⚠️ 当排版手段都无法消除某页的大片空白时，可在该节补写分析文字作为兜底，但**这属于改动论文内容而非版面，必须先取得用户同意**（含"哪一页/空白多少/已试过哪些手段/补在哪一节"四项说明），且只能用论文已有数据。完整门禁见 `references/quantified-layout-checks.md` §3.1。

## 第三步：逐页阅读并核查（🖼️ 每页读图，禁止跳过）

按渲染页逐页读取图片，逐页记录问题；视觉类检查清单：

| # | 检查项 | 判定 |
|:-:|--------|------|
| 1 | 页序与内容 | PDF 第1页承诺书、第2页编号页、第3页摘要页、第4页起正文；正文后附录；**无目录页** |
| 2 | 页码 | 摘要页起阿拉伯数字、**页脚中部**；承诺书/编号页无页码 |
| 3 | 页数 | 摘要页≤1页；**正文从 PDF 第4页数到正文结束 ≤30 页**（以渲染页实数为准）；附录不限；PDF 文件大小≤20MB |
| 4 | 图表位置 | 每张图/表：在所属章节标题之后、正文首次引用之后；不远离引导句所在页（同页或相邻页）；表题在表上方、图题在图下方 |
| 5 | 图表内容与正文一致 | 正文关键参数（迭代次数/重启点/阈值）在图中可见且位置正确（图-文-数据三方一致的可视化部分） |
| 6 | 中文与字体 | 无乱码/缺字/重叠；字体层级一致；负号正常 |
| 7 | 身份信息 | 页眉页脚、图表水印、附录任何位置无姓名/学校/队号（匿名性） |
| 8 | 表格 | 三线表（无竖线/网格/彩色底纹）；表宽未溢出页面；列对齐一致 |
| 9 | 页面元素 | 无内容超出页边距、图片/表格被截断、大面积留白异常 |
| 10 | 页底留白（量化，见第二步①） | 单页 >120pt 记问题并给出页码与数值；报告改前/改后对比 |
| 11 | 段落被图表截断（量化，见第二步①） | 必须为 0；非 0 时给出"某页以图表开头 + 上一页末行未断句"的证据 |
| 12 | 图表先于首次引用出现（量化，见第二步②） | 必须为 0；含"图前无任何引导句"的情形 |
| 13 | 表格实际渲染字号（量化，见第二步⑥） | 全篇一致；`\resizebox` 缩放会造成不可预测的小字号 |
| 14 | 图片渲染尺寸（量化，见第二步⑤） | 数据图统一宽度；宽高比 >0.6 的结构图按高度封顶，不与数据图同宽 |

## 第四步：输出视觉核查报告

```markdown
# PDF 视觉核查报告（<版本名>）

## 元信息
- 源 PDF：<路径>
- 页数：<N>；渲染目录：state/reports/pdf-pages/<版本名>/

## 逐页发现问题
| 页码 | 图片 | 问题 | 类型 | 对应检查项 |
|------|------|------|------|:---:|

## 判定
- PASS / PENDING（无视觉能力待人工）/ FAIL
- 证据：附上 page-*.png 引用；每条问题给出页码与图片
```

- **FAIL 项**如何流转：页码/页序/页数 → writing/typesetting；图表位置/题注 → visualization（重绘或排版）；乱码/字体 → typesetting；身份信息 → 立即删除并复审；图-文-数据不一致 → visualization/writing 按实际输出重绘。
- **PENDING**：无视觉能力时输出“人工核查请求单”（检查清单 + 全部 page-*.png 路径），门禁不落 PASS，等人工确认；不得以文本抽取替代视觉判定后自行放行。

## 与 CUMCM 2026 页面 profile 的绑定

页面约束唯一来源：

- `shared/contracts/submission/cumcm_2026_format_profile.json`

核查时以此 profile 为准；年度官方规则更新只改 profile，不在本技能内重复硬编码页数。

## 参考文件

- `references/quantified-layout-checks.md` —— **量化核查口径与经验**：六项指标定义与判据、留白/截断/同页的三项权衡、常用修复手法与代价、陷阱清单（模板 cls 的 `\newpage\null`、`\resizebox` 字号失真、`\needspace` 阈值过大、并行写入、数字口径之争、Windows 下 PDF 被占用）、标准工作流。**跑量化指标前先读它**。
- `scripts/pdf_render_pages.py` —— **工作流入口**（latex_linter / reviewer / orchestrator / mm-viz-reviewer / mm-latex-writing 均按此签名调用）：渲染分页 PNG + `manifest.json`（源 PDF 路径与 SHA-256、页数、dpi、引擎、每页路径、耗时）。纯 PyMuPDF 实现，不调外部进程。
- `scripts/check_interruptions.py` —— 页底留白 + 段落是否被图表截断，**传 PDF 路径**（第二参数可限制统计页数；默认全篇）
- `scripts/audit_float_citation.py` —— 每个图表是否先被引用后出现（从 PDF 内容定位题注块）
- `scripts/measure_drift.py` —— 图表与引用的页距（依赖 `main.aux` 与 PDF 同源）
- `scripts/list_float_pages.py` —— 浮动体落位总表
- `scripts/measure_whitespace.py` —— 纯 PGM 留白量测（`check_interruptions` 的备选，仅在装不上 PyMuPDF 时使用）
- `scripts/measure_figures.py` —— 图源尺寸与渲染高宽（⚠️ 内含项目专属的 FIGDIR 与图列表，复用前先改这两处）

## 失败与降级

| 场景 | 处理 |
|------|------|
| 无渲染引擎 | `TOOL_BLOCKED`，安装 poppler-utils / mupdf-tools / pymupdf / ghostscript 后重试；不跳过视觉核查 |
| 无视觉能力 | 生成人工核查请求单，门禁 PENDING；不假装已读图 |
| PDF 损坏/无法打开 | 记录 `pdf_read_preflight` 或渲染错误，返回编译/导出处修复 SOP 后重渲染 |
| 页数不一致（manifest 页数 vs pdfinfo 页数） | 以渲染图片实际页数为准并标注差异，交上游检查 PDF 完整性 |
| `xdvipdfmx: Unable to open "main.pdf"`（Windows） | PDF 被其它进程占用。用 `latexmk -jobname=build` 备用名编译，复制 `build.pdf` 为正式产物，再用正式名重编一次使 `main.aux` 与 PDF 同源；不要在此状态下做引用审计（会读出错误页码） |
| 量化结果与上一轮不一致（同一份 PDF 两次审计不同） | 检查 `main.aux` 是否与 PDF 同源；删掉过期 aux 后重编译 |
| 留白压不下去 | 不要继续缩图（缩到能放下往往已不可读）。两类出路：① 继续试排版手段（压行距、转置表格、调浮动位置）并记录每项的留白变化；② **在该节补写分析文字**——但这改的是论文内容而非版面，**必须先取得用户同意**，且只能用论文已有数据。详见 `references/quantified-layout-checks.md` §3.1 |