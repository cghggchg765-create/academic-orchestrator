#!/usr/bin/env python3
"""旧版命名迁移映射（升级自愈专用）。

本文件包含旧版命名（00_State、Data_Log.md 等），命名红线检查对其豁免——
这些旧名是迁移目标，必须保留以识别并修复旧版项目。除本文件与 CHANGELOG 外，
任何源文件出现旧名都会被 lint_contracts 拦截。
"""
from __future__ import annotations

LEGACY_STATE_DIR = "00_State"

# 旧文件名 → 新文件名（kebab-case/语义命名）
LEGACY_RENAME = {
    "Data/Data_Log.md": "Data/DataLog.md",
    "ProblemInfo/Team_Info.txt": "ProblemInfo/TeamInfo.txt",
    "ProblemInfo/Key_Requirements.md": "ProblemInfo/KeyRequirements.md",
    "ProblemInfo/Problem_Notes.md": "ProblemInfo/ProblemNotes.md",
    "README_项目总说明.md": "README-项目总说明.md",
    "Code/README_Code.md": "Code/README-Code.md",
    "ReportPaper/LaTeX/README_LATEX.md": "ReportPaper/LaTeX/README-LaTeX.md",
    "SubmissionPackage/README_提交说明.txt": "SubmissionPackage/README-提交说明.txt",
    "LogRecord/version_update.md": "LogRecord/version-update.md",
    "LogRecord/daily_log.md": "LogRecord/daily-log.md",
    "LogRecord/bug_fix_log.md": "LogRecord/bug-fix-log.md",
    "ModelDocs/model_framework.md": "ModelDocs/model-framework.md",
    "ModelDocs/reference_list.md": "ModelDocs/reference-list.md",
    "ModelDocs/sensitivity_analysis.md": "ModelDocs/sensitivity-analysis.md",
    "ModelDocs/error_analysis.md": "ModelDocs/error-analysis.md",
    "ModelDocs/model_validation.md": "ModelDocs/model-validation.md",
    "DefenseMaterial/defense_script.md": "DefenseMaterial/defense-script.md",
    "ResultFigures/figure_list.md": "ResultFigures/figure-list.md",
}

# 旧版近义重复空目录（统一命名后遗留）
LEGACY_EMPTY_DIRS = [
    "BackupArchive/draftbackup", "BackupArchive/midbackup", "BackupArchive/finalbackup",
    "DefenseMaterial/showfigures",
]
