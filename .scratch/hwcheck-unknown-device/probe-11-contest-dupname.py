# -*- coding: utf-8 -*-
"""临时诊断：`SCL` 重名缺陷在**赛题主线**（/api/generate 那条路）上也咬人吗？

判据：赛题页的生成门禁跑不跑 SysConfig CLI。跑 → 主线同样编不过；
不跑（只生成工程树、编译由用户点）→ 主线也咬，只是炸在用户机器上。
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.compile_runner import find_ccs_tools, find_make  # noqa: E402
from contest_generator.generator import generate_project  # noqa: E402
from contest_generator.pin_bindings import auto_assign_bindings  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
BASE = REPO / ".scratch" / "hwcheck-unknown-device" / "tmp-matrix" / "contest-dupname"

MAIN_C = (
    '#include "ti_msp_dl_config.h"\n'
    "int main(void)\n"
    "{\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 赛题主线最常见的两类组合：都是"板子活着 + 显示 + 一件传感器"
COMBOS = {
    "oled+mpu6050": ("led", "delay", "debug_uart", "oled", "ml_mpu6050"),
    "oled+jy61p": ("led", "delay", "debug_uart", "oled", "jy61p"),
}

for label, slugs in COMBOS.items():
    manifests = resolve_selection(MODULES, PLATFORM_MSPM0, list(slugs)).manifests
    solved = auto_assign_bindings(
        manifests, PLATFORM_MSPM0, board_for_platform(PLATFORM_MSPM0), {},
        resolve_default_conflicts=True,
    )
    out = BASE / label
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    print(f"=== {label}（自动配置解出 {solved.bindings or '无需动'}）===")
    try:
        generate_project(
            platform=PLATFORM_MSPM0, slugs=slugs, main_c_content=MAIN_C,
            output_dir=out, module_library_dir=MODULES, masters_dir=MASTERS,
            ccs_tools=find_ccs_tools(), bindings=solved.bindings or None,
        )
    except Exception as exc:
        print(f"  生成期**拦下**：{type(exc).__name__}: {str(exc).splitlines()[0]}")
        continue
    make = find_make(r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe")
    proc = subprocess.run(
        [str(make), "-C", str(out / "Debug"), "-f", "makefile", "-B", "all"],
        cwd=out, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900,
    )
    text = proc.stdout + proc.stderr
    dups = [line.strip() for line in text.splitlines() if "Duplicate name" in line]
    print(f"  生成 OK → 真编译 exit={proc.returncode}，Duplicate name {len(dups)} 条")
    for line in dups[:3]:
        print("     >>", line[:150])

