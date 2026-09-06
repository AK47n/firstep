# -*- coding: utf-8 -*-
"""dht11 stm32 编译矩阵（wiki-stm32-batch4/03）：单选生成 → UV4 真编译
（0 error/0 module warning 硬门槛 = exit 0）。照 run_sht30_matrix.py 改 slug；
产物在 .scratch/wiki-stm32-batch4/matrix/dht11/。"""
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
    '#include "dht11_stm32.h"\n'
    "int main(void)\n"
    "{\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    dht11_init();\n"
    "    (void)dht11_read(&t, &h);\n"
    "    (void)dht11_read_temperature();\n"
    "    (void)dht11_read_humidity();\n"
    "    while (1);\n"
    "}\n"
)

uv4 = find_uv4()
print("uv4:", uv4)
if uv4 is None:
    print("FAIL: 未找到 UV4")
    sys.exit(2)

out = REPO / ".scratch" / "wiki-stm32-batch4" / "matrix" / "dht11"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_STM32, ["dht11"])
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
