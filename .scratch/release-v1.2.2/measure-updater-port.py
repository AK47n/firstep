# -*- coding: utf-8 -*-
"""从**沙箱自己的** updater.log 里切出今天这一轮（20260919-133228），核对它停的是哪个端口。

判据：这一轮必须停 **8020**（沙箱自己的端口）。它若停 8000，说明「发起更新的那一代」
端口没传下去——那正是 `update-restart-stale-service/01` 在 v1.1.1 上要修的那条，
而沙箱起点就是 v1.1.1，所以这一格同时也是那条修复的**真机复核**。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG = Path(r"C:\Users\luoji\.contest_generator_sim\updates\updater.log")
STAMP = "20260919-133228"


def main() -> int:
    lines = LOG.read_bytes().decode("utf-8", errors="replace").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("=== firstep 更新开始")]
    print(f"updater.log 共 {len(lines)} 行 / {len(starts)} 轮")
    block: list[str] = []
    for index, begin in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        chunk = lines[begin:end]
        if STAMP in chunk[0]:
            block = chunk
            break

    if not block:
        print(f"**找不到 {STAMP} 那一轮**——最后几轮的时间戳：")
        for begin in starts[-4:]:
            print(f"  {lines[begin][:80]}")
        return 2

    print(f"\n## 本轮（{STAMP}）的关键行")
    markers = ("更新包", "工具根", "校验", "停", "端口", "备份", "落位", "删除", "重装",
               "标记", "记录", "重启", "完成")
    for line in block:
        if any(marker in line for marker in markers) and "删除已废弃文件" not in line:
            print(f"  {line}")

    print("\n## 判据")
    stopped_8020 = any("8020" in line for line in block)
    stopped_8000 = any("8000" in line for line in block)
    print(f"  日志里出现 8020：{stopped_8020}")
    print(f"  日志里出现 8000：{stopped_8000}")
    ok = stopped_8020 and not stopped_8000
    print(f"  停的是沙箱自己的端口（8020）、不是真身的 8000：{'✓' if ok else '✗'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
