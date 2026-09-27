# -*- coding: utf-8 -*-
"""发版 v1.3.1 的读数落盘：复用 `hwcheck-hygiene/readings.py`（同一条纪律：
收全量、剥 ANSI、UTF-8、带命令/时间/退出码头），只把输出目录换成本目录。

用法：`python .scratch/release-v1.3.1/_reading.py <读数名> -- <命令…>`
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hwcheck-hygiene"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import readings  # noqa: E402 —— 路径就位后才能导入

readings.OUT_DIR = HERE
sys.exit(readings.main(sys.argv[1:]))
