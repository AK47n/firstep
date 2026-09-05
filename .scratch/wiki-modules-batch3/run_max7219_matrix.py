# -*- coding: utf-8 -*-
"""max7219 编译矩阵：单选生成 → gmake 真编译（0 error 硬门槛）。"""
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
    '#include "max7219.h"\n'
    "int main(void) { max7219_init(MAX7219_FORM_DIGIT, 3); "
    "max7219_write_digit(1, 3); max7219_write_digit(2, 0x0F); "
    "max7219_init(MAX7219_FORM_MATRIX, 1); "
    "uint8_t rows[8] = {0x3C,0x42,0x42,0x42,0x42,0x42,0x66,0x38}; "
    "max7219_write_matrix(rows, 1); max7219_clear(); "
    "max7219_write_reg(0, 0x0A, 5); while (1); }\n"
)

out = REPO / ".scratch" / "wiki-modules-batch3" / "matrix" / "max7219"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_MSPM0, ["max7219"])
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
