# -*- coding: utf-8 -*-
"""工单 module-hwcheck/03 前置探针：**器件进工程**这条路到底通不通（真库真母版真内核）。

为什么要先探这一下：工单 03 要让「选中的器件」进生成工程（接线表才与工程 README
同源）。风险点是生成门禁——某种器件的默认脚 / 依赖 / include 形态可能在真内核上
直接被拒。先量清楚，再决定器件进不进模块集，而不是写完 UI 才发现路不通。

只读盘、只往 %TEMP% 下的临时目录写工程，跑完自删。

用法：python .scratch/module-hwcheck/probe-03-generate-with-devices.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.generator import generate_project  # noqa: E402
from contest_generator.readme import parse_pin_table  # noqa: E402

LIB = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"

# 两个平台的「框架 + 单通道 + 一件真器件」形态（mspm0 双通道默认撞脚，故只开串口）
CASES = [
    ("stm32", ["led", "delay", "debug_uart", "ml_mpu6050"]),
    ("mspm0", ["led", "delay", "debug_uart", "ml_mpu6050"]),
    ("stm32", ["led", "delay", "debug_uart", "oled", "hmc5883l"]),
    ("mspm0", ["led", "delay", "debug_uart", "sr04"]),
]


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="firstep-probe03-"))
    try:
        for platform, slugs in CASES:
            out = root / f"{platform}-{'-'.join(slugs)}"
            print(f"== {platform} slugs={slugs}")
            try:
                summary = generate_project(
                    platform=platform,
                    slugs=slugs,
                    main_c_content="/* 探针：只关心生成能不能过 */\nint main(void)\n{\n    while (1) {}\n}\n",
                    output_dir=out,
                    module_library_dir=LIB,
                    masters_dir=MASTERS,
                    tool_version="probe",
                    kind="hwcheck",
                    write_demo_script=False,
                )
            except Exception as exc:  # noqa: BLE001 —— 探针就是要看它抛什么
                print(f"   [拒] {type(exc).__name__}: {exc}\n")
                continue
            readme = (out / "README.md").read_text(encoding="utf-8")
            rows = parse_pin_table(readme)
            print(f"   [过] modules={[s for s, _ in summary.modules]}")
            print(f"   README 接线行 {len(rows)} 条：")
            for row in rows:
                print(f"     {row}")
            print()
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
