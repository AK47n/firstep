# -*- coding: utf-8 -*-
"""lcd 编译矩阵：单选生成 → SysConfig CLI 校验 → gmake 真编译（0 error 硬门槛）。

照 run_mq3_matrix.py 先例（批次 11）：generate 单选 lcd（依赖 delay 展开）→
collect_build_log 真编译。批次 12/01 打样件（ST7735 0.96 寸 80×160）。
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log, compile_passed, find_ccs_tools, find_make,
)
from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
MAIN_C = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "lcd.h"\n'
    "int main(void)\n"
    "{\n"
    "    lcd_init(LCD_MODEL_096, LCD_DIR_DEFAULT);\n"
    "    lcd_clear(BLACK);\n"
    "    lcd_fill(0, 0, 40, 20, RED);\n"
    "    lcd_draw_point(10, 10, GREEN);\n"
    "    lcd_draw_line(0, 0, 30, 20, BLUE);\n"
    "    lcd_draw_rectangle(1, 1, 20, 10, YELLOW);\n"
    "    lcd_draw_circle(50, 40, 6, WHITE);\n"
    "    lcd_show_char(0, 0, 'A', WHITE, BLACK, 16, 0);\n"
    "    lcd_show_string(8, 20, (const uint8_t *)\"OK\", WHITE, BLACK, 16, 1);\n"
    "    lcd_show_num(0, 40, 123, 3, WHITE, BLACK, 16);\n"
    "    lcd_show_float(0, 60, 3.14f, 4, WHITE, BLACK, 16);\n"
    "    uint8_t hz[2] = {0xD6, 0xD0};\n"
    "    lcd_show_chinese16x16(0, 80, hz, WHITE, BLACK, 0);\n"
    "    while (1);\n"
    "}\n"
)

out = REPO / ".scratch" / "wiki-modules-batch12" / "matrix" / "lcd"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_MSPM0, ["lcd"])
generate(
    platform=PLATFORM_MSPM0,
    manifests=resolved.manifests,
    module_library_dir=REPO / "library" / "modules",
    master_project_dir=REPO / "library" / "masters" / "mspm0",
    output_dir=out,
    main_c_content=MAIN_C,
    ccs_tools=find_ccs_tools(),
)
log = collect_build_log(
    PLATFORM_MSPM0, out,
    make=find_make(GMAKE),
    timeout=300,
)
print("compile_passed:", compile_passed(PLATFORM_MSPM0, log.run.exit_code))
print("exit_code:", log.run.exit_code)
print(log.run.output[-4000:])
