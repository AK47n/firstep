# -*- coding: utf-8 -*-
"""tp_xpt2046 编译矩阵：单选生成 → SysConfig CLI 校验 → gmake 真编译。

照 run_lcd_matrix.py 先例（批次 12/01）：generate 单选 tp_xpt2046（依赖
delay 展开）→ collect_build_log 真编译。批次 12/06（XPT2046 电阻触摸独立件）。
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
    '#include "tp_xpt2046.h"\n'
    "int main(void)\n"
    "{\n"
    "    xpt2046_init();\n"
    "    uint16_t x = 0, y = 0;\n"
    "    if (xpt2046_is_pressed()) {\n"
    "        xpt2046_read_xy(&x, &y);\n"
    "    }\n"
    "    (void)x;\n"
    "    (void)y;\n"
    "    while (1);\n"
    "}\n"
)

out = REPO / ".scratch" / "wiki-modules-batch12" / "matrix" / "tp_xpt2046"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(
    REPO / "library" / "modules", PLATFORM_MSPM0, ["tp_xpt2046"]
)
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
