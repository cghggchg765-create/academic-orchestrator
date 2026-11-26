---
name: make-pdf
preamble-tier: 1
version: 1.0.0
description: |
  Turn any markdown file into a publication-quality PDF. Proper 1in margins,
  intelligent page breaks, page numbers, cover pages, running headers, curly
  quotes and em dashes, clickable TOC, diagonal DRAFT watermark. Not a draft
  artifact — a finished artifact. Use when asked to "make a PDF", "export to
  PDF", "turn this markdown into a PDF", or "generate a document".
  Voice triggers (speech-to-text aliases): "make this a pdf", "make it a pdf", "export to pdf", "turn this into a pdf", "turn this markdown into a pdf", "generate a pdf", "make a pdf from", "pdf this markdown".
triggers:
  - markdown to pdf
  - generate pdf
  - make pdf
  - export pdf
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

> 维护说明：本文件是 make-pdf 的权威来源（上游 SKILL.md.tmpl 生成工具未随本插件分发，原 "AUTO-GENERATED" 标记已失效，改为手工维护）。

## 前置检查（对本仓库而言）

```bash
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
```

本插件**不内置** gstack 运行时（`~/.claude/skills/gstack/` 二进制与 `make-pdf` 的 TS 源码均已剥离）。PDF 生成二进制只在安装了 gstack 上游的机器上可用；未安装时——
- **竞赛论文**（国赛 10 节 LaTeX 稿）走 `latex-guard` + pdflatex 正规链路，不走本技能；
- **临时 Markdown 快速导出**使用下面的便携回退（pandoc 或 pdflatex），或明确告知用户需自行构建 gstack 二进制后再重试。

## MAKE-PDF SETUP（执行任何 make-pdf 命令前先跑）

```bash
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
P=""
[ -n "$MAKE_PDF_BIN" ] && [ -x "$MAKE_PDF_BIN" ] && P="$MAKE_PDF_BIN"
if [ -n "$_ROOT" ] && [ -x "$_ROOT/.claude/skills/gstack/make-pdf/dist/pdf" ]; then
  P="$_ROOT/.claude/skills/gstack/make-pdf/dist/pdf"
fi
[ -z "$P" ] && [ -x "$HOME/.claude/skills/gstack/make-pdf/dist/pdf" ] && P="$HOME/.claude/skills/gstack/make-pdf/dist/pdf"
if [ -x "$P" ]; then
  echo "MAKE_PDF_READY: $P"
  export P   # 同一技能调用内的后续命令可用 $P
else
  echo "MAKE_PDF_NOT_AVAILABLE: gstack 二进制未安装，走便携回退"
fi
```

若输出 `MAKE_PDF_NOT_AVAILABLE`，对竞赛论文：走 LaTeX 正规链路（`latex-guard` + pdflatex），并在提交清单中登记为 LaTeX 编译产物；对临时 Markdown 导出，用以下便携回退生成：

```bash
# 回退一（推荐）：pandoc + LaTeX 引擎
pandoc input.md -o output.pdf --pdf-engine=xelatex -V CJKmainfont="SimSun" -V geometry:margin=1in -V lang=zh-CN
# 回退二：LaTeX 直接转换
pandoc input.md -o output.tex && xelatex output.tex
```

> 竞赛提交的 PDF 一律以 `ReportPaper/LaTeX/` 正规编译产物为准，make-pdf 仅用于非论文类 Markdown 快速导出，避免绕过格式门禁。

若输出 `MAKE_PDF_READY`：`$P` 为二进制路径，后续命令统一用 `$P`（保持可移植）。

Core commands（二进制可用时）:
- `$P generate <input.md> [output.pdf]` — render markdown to PDF (80% use case)
- `$P generate --cover --toc essay.md out.pdf` — full publication layout
- `$P generate --watermark DRAFT memo.md draft.pdf` — diagonal DRAFT watermark
- `$P preview <input.md>` — render HTML and open in browser (fast iteration)
- `$P setup` — verify browse + Chromium + pdftotext and run a smoke test
- `$P --help` — full flag reference

Output contract:
- `stdout`: ONLY the output path on success. One line.
- `stderr`: progress (`Rendering HTML... Generating PDF...`) unless `--quiet`.
- Exit 0 success / 1 bad args / 2 render error / 3 Paged.js timeout / 4 browse unavailable.

## 核心用法（二进制可用时）

### 80% case — memo/letter

One command, no flags. Gets a clean PDF with running header + page numbers
+ CONFIDENTIAL footer by default.

```bash
$P generate letter.md                 # writes /tmp/letter.pdf
$P generate letter.md letter.pdf      # explicit output path
```

### Publication mode — cover + TOC + chapter breaks

```bash
$P generate --cover --toc --author "Garry Tan" --title "On Horizons" \
  essay.md essay.pdf
```

Each top-level H1 in the markdown starts a new page. Disable with
`--no-chapter-breaks` for memos that happen to have multiple H1s.

### Draft-stage watermark

```bash
$P generate --watermark DRAFT memo.md draft.pdf
```

Diagonal 10% opacity DRAFT across every page. When the draft is final, drop
the flag and regenerate.

### Fast iteration via preview

```bash
$P preview essay.md
```

Renders HTML with the same print CSS and opens it in your browser. Refresh
as you edit the markdown. Skip the PDF round trip until you're ready.

### Brand-free (no CONFIDENTIAL footer)

```bash
$P generate --no-confidential memo.md memo.pdf
```

## Common flags（二进制可用时）

```
Page layout:
  --margins <dim>            1in (default) | 72pt | 2.54cm | 25mm
  --page-size letter|a4|legal

Structure:
  --cover                    Cover page (title, author, date, hairline rule)
  --toc                      Clickable TOC with page numbers
  --no-chapter-breaks        Don't start a new page at every H1

Branding:
  --watermark <text>         Diagonal watermark ("DRAFT", "CONFIDENTIAL")
  --header-template <html>   Custom running header
  --footer-template <html>   Custom footer (mutex with --page-numbers)
  --no-confidential          Suppress the CONFIDENTIAL right-footer

Output:
  --page-numbers             "N of M" footer (default on)
  --tagged                   Accessible PDF (default on)
  --outline                  PDF bookmarks from headings (default on)
  --quiet                    Suppress progress on stderr
  --verbose                  Per-stage timings

Network:
  --allow-network            Fetch external images. Off by default
                             (blocks tracking pixels).

Metadata:
  --title "..."              Document title (defaults to first H1)
  --author "..."             Author for cover + PDF metadata
  --date "..."               Date for cover (defaults to today)
```

## When Claude should run it

Watch for markdown-to-PDF intent. Any of these patterns → run `$P generate`:

- "Can you make this markdown a PDF"
- "Export it as a PDF"
- "Turn this letter into a PDF"
- "I need a PDF of the essay"
- "Print this as a PDF for me"

If the user has a `.md` file open and says "make it look nice", propose
`$P generate --cover --toc` and ask before running.

## Debugging（二进制可用时）

- Output looks empty / blank → check browse daemon is running: `$P status`.
- Fragmented text on copy-paste → highlight.js output (Phase 4). Retry with
  `--no-syntax` once that flag exists. For now, remove fenced code blocks
  and regenerate.
- Paged.js timeout → probably no headings in the markdown. Drop `--toc`.
- External image missing → add `--allow-network` (understand you're giving
  the markdown file permission to fetch from its image URLs).
- Generated PDF too tall/wide → `--page-size a4` or `--margins 0.75in`.

## Output contract（二进制可用时）

```
stdout: /tmp/letter.pdf          ← just the path, one line
stderr: Rendering HTML...        ← progress spinner (unless --quiet)
        Generating PDF...
        Done in 1.5s. 43 words · 22KB · /tmp/letter.pdf

exit code: 0 success / 1 bad args / 2 render error / 3 Paged.js timeout
           / 4 browse unavailable
```

Capture the path: `PDF=$($P generate letter.md)` — then use `$PDF`.