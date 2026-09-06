# -*- coding: utf-8 -*-
"""tcs34725 stm32 编译矩阵（wiki-stm32-batch3/03）：单选生成 → UV4 真编译
（0 error/0 module warning 硬门槛 = exit 0）。照 wiki-stm32-batch2
run_aht10_matrix.py 配方改 slug；产物在 .scratch/wiki-stm32-batch3/matrix/tcs34725/。"""
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
    '#include "tcs34725_stm32.h"\n'
    "int main(void)\n"
    "{\n"
    "    TCS34725_RGBC rgb;\n"
    "    TCS34725_HSL hsl;\n"
    "    (void)tcs34725_init();\n"
    "    (void)tcs34725_read_rgb(&rgb);\n"
    "    tcs34725_rgb_to_hsl(&rgb, &hsl);\n"
    "    tcs34725_set_integration_time(TCS34725_INTEGRATIONTIME_24MS);\n"
    "    tcs34725_set_gain(TCS34725_GAIN_1X);\n"
    "    tcs34725_enable();\n"
    "    tcs34725_disable();\n"
    "    while (1);\n"
    "}\n"
)

uv4 = find_uv4()
print("uv4:", uv4)
if uv4 is None:
    print("FAIL: 未找到 UV4")
    sys.exit(2)

out = REPO / ".scratch" / "wiki-stm32-batch3" / "matrix" / "tcs34725"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_STM32, ["tcs34725"])
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
