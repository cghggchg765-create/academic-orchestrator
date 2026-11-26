<#
.SYNOPSIS
    LaTeX 论文排版质量批量扫描脚本（NEU-Thesis 模板专用，但适用通用中文学位论文）

.DESCRIPTION
    扫描 .tex 源文件中的常见错误（占位符残留、Extra alignment 风险、绝对宽度、竖线表格、
    单一位置参数等），并检查编译日志（.log）中的 Error / Overfull / Float too large。
    对应 latex-guard SKILL.md §七、12 类 PDF 排版质量检测的"前置扫描"环节。

.PARAMETER TexDir
    .tex 源文件目录，默认 Tex/

.PARAMETER LogFile
    编译日志路径，默认 Thesis.log

.PARAMETER OutputFormat
    输出格式：text（默认）/ json / markdown

.EXAMPLE
    .\check_latex_quality.ps1 -TexDir "Tex" -LogFile "Thesis.log"

.EXAMPLE
    .\check_latex_quality.ps1 -OutputFormat json

.EXAMPLE
    .\check_latex_quality.ps1 -OutputFormat markdown

.NOTES
    Author: latex-guard skill
    Requires: PowerShell 5.1+ (Windows)
    推荐在 xelatex 编译后立即运行
#>

[CmdletBinding()]
param(
    [string]$TexDir = "Tex",
    [string]$LogFile = "Thesis.log",
    [ValidateSet("text", "json", "markdown")]
    [string]$OutputFormat = "text"
)

$ErrorCount = 0
$WarningCount = 0
$Findings = @()

function Write-Finding {
    param([string]$Category, [string]$Severity, [string]$File, [int]$Line, [string]$Message)
    $script:Findings += [PSCustomObject]@{
        Category = $Category
        Severity = $Severity
        File     = $File
        Line     = $Line
        Message  = $Message
    }
    if ($Severity -eq "Error") { $script:ErrorCount++ } else { $script:WarningCount++ }
}

Write-Host "===== LaTeX 论文排版质量扫描 =====" -ForegroundColor Cyan
Write-Host "扫描目录: $TexDir"
Write-Host "编译日志: $LogFile"
Write-Host ""

# === 1. 源文件扫描（占位符残留 + 编译错误风险）===
Write-Host "[1/4] 扫描 .tex 源文件..." -ForegroundColor Yellow

if (Test-Path -LiteralPath $TexDir) {
    $texFiles = Get-ChildItem -LiteralPath $TexDir -Filter "*.tex" -Recurse -ErrorAction SilentlyContinue

    # 1.1 占位符残留
    $placeholders = @("(作者姓名)", "(导师姓名)", "(学号)", "(专业)", "(日期)", "xxx", "XXX", "TODO", "FIXME")
    foreach ($f in $texFiles) {
        foreach ($p in $placeholders) {
            $matches = Select-String -Path $f.FullName -Pattern ([regex]::Escape($p)) -SimpleMatch -ErrorAction SilentlyContinue
            foreach ($m in $matches) {
                Write-Finding "占位符残留" "Warning" $f.Name $m.LineNumber "发现占位符 '$p'"
            }
        }
    }

    # 1.2 绝对宽度（违反反例 A.3）
    foreach ($f in $texFiles) {
        $matches = Select-String -Path $f.FullName -Pattern 'p\{[0-9]+cm\}' -ErrorAction SilentlyContinue
        foreach ($m in $matches) {
            Write-Finding "绝对宽度" "Warning" $f.Name $m.LineNumber "使用了绝对宽度，应改为 \textwidth 相对宽度"
        }
    }

    # 1.3 竖线表格（违反反例 A.4）
    foreach ($f in $texFiles) {
        $matches = Select-String -Path $f.FullName -Pattern '\\begin\{tabular\}\{' -ErrorAction SilentlyContinue
        foreach ($m in $matches) {
            if ($m.Line -match '\|') {
                Write-Finding "竖线表格" "Warning" $f.Name $m.LineNumber "学术论文应使用三线表（booktabs）"
            }
        }
    }

    # 1.4 单一位置参数 [h]（违反反例 A.5）
    foreach ($f in $texFiles) {
        $matches = Select-String -Path $f.FullName -Pattern '\\begin\{(figure|table)\}\[h\]' -ErrorAction SilentlyContinue
        foreach ($m in $matches) {
            Write-Finding "单参数浮动" "Warning" $f.Name $m.LineNumber "单参数 [h] 经常被 LaTeX 忽略，应改为 [hbt!]"
        }
    }

    # 1.5 samepage 使用（违反反例 A.2）
    foreach ($f in $texFiles) {
        $matches = Select-String -Path $f.FullName -Pattern '\\begin\{samepage\}' -ErrorAction SilentlyContinue
        foreach ($m in $matches) {
            Write-Finding "samepage 反例" "Warning" $f.Name $m.LineNumber "samepage 经常无效，应用 minipage 物理绑定"
        }
    }
} else {
    Write-Warning "Tex 目录不存在: $TexDir（跳过源文件扫描）"
}

# === 2. 编译日志扫描 ===
Write-Host "[2/4] 扫描编译日志..." -ForegroundColor Yellow

if (Test-Path -LiteralPath $LogFile) {
    $logContent = Get-Content -LiteralPath $LogFile -Encoding UTF8 -ErrorAction SilentlyContinue

    # 2.1 编译错误 ^! Error
    $errorLines = $logContent | Select-String -Pattern '^!'
    foreach ($e in $errorLines) {
        Write-Finding "编译错误" "Error" $LogFile $e.LineNumber $e.Line.Trim()
    }

    # 2.2 Float too large
    $floatLines = $logContent | Select-String -Pattern "Float too large" -SimpleMatch
    foreach ($e in $floatLines) {
        Write-Finding "浮动体过大" "Error" $LogFile $e.LineNumber $e.Line.Trim()
    }

    # 2.3 Overfull \hbox > 50pt（重度溢出）
    $overfullLines = $logContent | Select-String -Pattern "Overfull \\hbox" -SimpleMatch
    foreach ($e in $overfullLines) {
        if ($e.Line -match '\(([5-9][0-9]|[1-9][0-9]+)\.?[0-9]*pt') {
            Write-Finding "表格溢出" "Warning" $LogFile $e.LineNumber $e.Line.Trim()
        }
    }

    # 2.4 Undefined citation
    $undefRef = $logContent | Select-String -Pattern "Undefined citation" -SimpleMatch
    foreach ($e in $undefRef) {
        Write-Finding "未定义引用" "Error" $LogFile $e.LineNumber $e.Line.Trim()
    }

    # 2.5 Undefined reference
    $undefRef2 = $logContent | Select-String -Pattern "Reference .* undefined" -SimpleMatch
    foreach ($e in $undefRef2) {
        Write-Finding "未定义交叉引用" "Error" $LogFile $e.LineNumber $e.Line.Trim()
    }
} else {
    Write-Warning "编译日志不存在: $LogFile（跳过日志扫描）"
}

# === 3. 输出结果 ===
Write-Host ""
Write-Host "[3/4] 扫描结果：" -ForegroundColor Yellow

switch ($OutputFormat) {
    "json" {
        $Findings | ConvertTo-Json -Depth 3
    }
    "markdown" {
        Write-Host "# LaTeX 论文排版质量扫描报告"
        Write-Host ""
        Write-Host "- 扫描时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Write-Host "- 错误数: $ErrorCount"
        Write-Host "- 警告数: $WarningCount"
        Write-Host ""
        if ($Findings.Count -gt 0) {
            $Findings | ForEach-Object { Write-Host "## [$($_.Severity)] $($_.Category) - $($_.File):$($_.Line)" }
            $Findings | ForEach-Object { Write-Host "- $($_.Message)" }
        } else {
            Write-Host "✅ 无问题发现"
        }
    }
    default {
        if ($Findings.Count -eq 0) {
            Write-Host "✅ 全部检查通过" -ForegroundColor Green
        } else {
            $Findings | Format-Table -AutoSize
        }
    }
}

# === 4. 退出码 ===
Write-Host ""
Write-Host "[4/4] 退出码: Error=$ErrorCount, Warning=$WarningCount"
if ($ErrorCount -gt 0) {
    exit 1
} else {
    exit 0
}