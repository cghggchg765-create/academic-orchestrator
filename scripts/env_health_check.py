#!/usr/bin/env python3
"""运行环境健康检查（防止"大 Agent 占用巨量资源"类问题复发）。

背景：`~/.zcode/cli/exec` 会话输出日志曾膨胀至 13GB（单个子代理会话目录即占 13GB），
导致后续子代理（如 tuner）因磁盘/内存压力 OOM。本脚本在任务开工前（/mm-boot 第 0 步）或
定期执行，检查三类资源风险并给出清理建议/直接清理。

用法：
  python scripts/env_health_check.py            # 检查并输出健康/警告（exit 0=健康, 1=警告, 2=严重）
  python scripts/env_health_check.py --clean    # 检查 + 清理历史会话日志（保留当前会话）与 Temp 残留
  python scripts/env_health_check.py --quiet    # 仅输出结论一行
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

HOME = Path.home()
EXEC_DIR = HOME / ".zcode" / "cli" / "exec"
TEMP = Path(os.environ.get("TEMP", "/tmp"))
CURRENT_SESSION = os.environ.get("ZCODE_SESSION_ID", "")

# 阈值（可调）：exec 日志 >2GB 警告，>5GB 严重；Temp/mm_* 测试残留 >50 个警告
EXEC_WARN_MB = 2048
EXEC_CRIT_MB = 5120
TEMP_WARN_COUNT = 50
DISK_WARN_GB = 10


def dir_size_mb(p: Path) -> float:
    total = 0
    for f in p.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def count_temp_mm() -> int:
    if not TEMP.exists():
        return 0
    return sum(1 for p in TEMP.glob("mm_*") if p.is_dir())


def disk_free_gb() -> float:
    try:
        total, _, free = shutil.disk_usage(HOME)
        return free / (1024 ** 3)
    except OSError:
        return -1.0


def clean_exec_logs(dry: bool = True) -> int:
    """删除非当前会话的历史 exec 日志目录（保留当前会话与 bash-startup）。"""
    if not EXEC_DIR.exists():
        return 0
    removed = 0
    for d in EXEC_DIR.iterdir():
        if not d.is_dir() or not d.name.startswith("sess_"):
            continue
        if CURRENT_SESSION and d.name == CURRENT_SESSION:
            continue
        if dry:
            removed += 1
        else:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return removed


def clean_temp_mm(dry: bool = True) -> int:
    if not TEMP.exists():
        return 0
    removed = 0
    for p in TEMP.glob("mm_*"):
        if p.is_dir():
            if dry:
                removed += 1
            else:
                shutil.rmtree(p, ignore_errors=True)
                removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="运行环境健康检查（exec 日志/Temp 残留/磁盘）")
    ap.add_argument("--clean", action="store_true", help="检查后执行清理（历史会话日志 + Temp 残留）")
    ap.add_argument("--quiet", action="store_true", help="仅输出结论")
    args = ap.parse_args()

    issues: list[str] = []
    critical = False

    exec_mb = dir_size_mb(EXEC_DIR) if EXEC_DIR.exists() else 0.0
    if exec_mb > EXEC_CRIT_MB:
        issues.append(f"[严重] ~/.zcode/cli/exec 会话日志 {exec_mb:.0f}MB（> {EXEC_CRIT_MB}MB）——大 Agent 输出累积，建议立即清理")
        critical = True
    elif exec_mb > EXEC_WARN_MB:
        issues.append(f"[警告] ~/.zcode/cli/exec 会话日志 {exec_mb:.0f}MB（> {EXEC_WARN_MB}MB），建议清理历史会话日志")
    elif exec_mb > 256:
        issues.append(f"[提示] exec 会话日志 {exec_mb:.0f}MB，属正常范围")

    n_temp = count_temp_mm()
    if n_temp > TEMP_WARN_COUNT:
        issues.append(f"[警告] 测试临时项目残留 {n_temp} 个（Temp/mm_*），建议清理")

    free_gb = disk_free_gb()
    if 0 <= free_gb < DISK_WARN_GB:
        issues.append(f"[严重] 磁盘剩余仅 {free_gb:.1f}GB（< {DISK_WARN_GB}GB）")
        critical = True

    clean_log: list[str] = []
    if args.clean:
        n_log = clean_exec_logs(dry=False)
        n_tmp = clean_temp_mm(dry=False)
        clean_log.append(f"[已清理] 历史会话日志 {n_log} 个目录、Temp 残留 {n_tmp} 个")
        # 清理后：exec/Temp 相关条目视为已处理（保留磁盘等其余风险）
        issues = [i for i in issues if not ("exec 会话日志" in i or "测试临时" in i)]

    if args.quiet:
        print("健康" if not issues else ("严重" if critical else "警告"))
        return 0 if not issues else (2 if critical else 1)

    print("=== 运行环境健康检查 ===")
    for i in clean_log:
        print("  " + i)
    if not issues:
        print("状态: 健康 ✓（exec 日志 / Temp 残留 / 磁盘均正常）")
        print(f"  exec 会话日志: {exec_mb:.0f}MB  |  测试临时残留: {n_temp} 个  |  磁盘剩余: {free_gb:.1f}GB")
        return 0
    print("状态:", "严重（建议立即处理）" if critical else "警告")
    for i in issues:
        print("  " + i)
    print("清理命令: python scripts/env_health_check.py --clean")
    return 2 if critical else 1


if __name__ == "__main__":
    sys.exit(main())
