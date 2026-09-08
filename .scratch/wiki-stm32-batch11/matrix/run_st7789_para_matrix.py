# -*- coding: utf-8 -*-
"""st7789_para stm32 编译矩阵（wiki-stm32-batch11/02）：单选生成 → UV4 真编译
（0 error/0 warning 硬门槛 = exit 0）。产物在
.scratch/wiki-stm32-batch11/matrix/st7789_para/。"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log,
    compile_passed,
    find_uv4,
)
from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C = (
    '#include "headfile.h"\n'
    '#include "st7789_para_stm32.h"\n'
    "int main(void)\n"
    "{\n"
    "    st7789_para_init(ST7789_PARA_DIR_DEFAULT);\n"
    "    (void)st7789_para_get_width();\n"
    "    (void)st7789_para_get_height();\n"
    "    st7789_para_clear(BLACK);\n"
    "    st7789_para_fill(0, 0, 40, 20, RED);\n"
    "    st7789_para_draw_point(10, 10, GREEN);\n"
    "    st7789_para_draw_line(0, 0, 30, 20, BLUE);\n"
    "    st7789_para_draw_rectangle(1, 1, 20, 10, YELLOW);\n"
    "    st7789_para_draw_circle(50, 40, 6, WHITE);\n"
    "    st7789_para_show_char(0, 0, 'A', WHITE, BLACK, 16, 0);\n"
    "    st7789_para_show_string(8, 20, (const uint8_t *)\"OK\", WHITE, BLACK, 16, 1);\n"
    "    st7789_para_show_num(0, 40, 123, 3, WHITE, BLACK, 16);\n"
    "    st7789_para_show_float(0, 60, 3.14f, 4, WHITE, BLACK, 16);\n"
    "    uint8_t hz[2] = {0xD6, 0xD0};\n"
    "    st7789_para_show_chinese16x16(0, 80, hz, WHITE, BLACK, 0);\n"
    "    uint8_t pic[8] = {0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0xFF, 0xFF};\n"
    "    st7789_para_show_picture(0, 100, 2, 2, pic);\n"
    "    while (1);\n"
    "}\n"
)

uv4 = find_uv4()
print("uv4:", uv4)
if uv4 is None:
    print("FAIL: 未找到 UV4")
    sys.exit(2)

out = REPO / ".scratch" / "wiki-stm32-batch11" / "matrix" / "st7789_para"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_STM32, ["st7789_para"])
generate(
    platform=PLATFORM_STM32,
    manifests=resolved.manifests,
    module_library_dir=REPO / "library" / "modules",
    master_project_dir=REPO / "library" / "masters" / "stm32",
    output_dir=out,
    main_c_content=MAIN_C,
)
log = collect_build_log(PLATFORM_STM32, out, uv4=uv4, timeout=300)
output = log.run.output or ""
(out / "build.log").write_text(output, encoding="utf-8", errors="replace")
passed = compile_passed(PLATFORM_STM32, log.run.exit_code) is True
print("compile_passed:", passed)
print("exit_code:", log.run.exit_code)
print(output[-3000:])
sys.exit(0 if passed else 1)
