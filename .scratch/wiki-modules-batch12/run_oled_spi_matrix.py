# -*- coding: utf-8 -*-
"""oled SPI 总线变体编译矩阵：单选生成 → SysConfig CLI 校验 → gmake 真编译。

照 run_lcd_matrix.py 先例（批次 12/01）：generate 单选 oled（依赖 delay
展开）→ collect_build_log 真编译。批次 12/07 决策 B（0.96 SPI 单色屏
SSD1306 SPI 变体——OLED_SPI_Init 软 SPI 位操作 5 脚）。
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
    '#include "oled.h"\n'
    "int main(void)\n"
    "{\n"
    "    OLED_SPI_Init();\n"
    "    OLED_Clear();\n"
    "    OLED_ShowString(0, 0, (u8 *)\"SPI OK!\", 16);\n"
    "    OLED_Refresh();\n"
    "    while (1);\n"
    "}\n"
)

out = REPO / ".scratch" / "wiki-modules-batch12" / "matrix" / "oled_spi"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_MSPM0, ["oled"])
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
