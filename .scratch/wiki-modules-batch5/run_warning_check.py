# -*- coding: utf-8 -*-
"""批次 5 编译矩阵 warning 核查（硬门槛 0 error / 0 warning）：串行重跑 4 件。"""
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
MAIN_C = {
    "ads1115": (
        '#include "ti_msp_dl_config.h"\n#include "ads1115.h"\n'
        "int main(void) { ads1115_init(); ads1115_set_gain(ADS1115_PGA_4_096V); "
        "ads1115_set_data_rate(ADS1115_DR_128SPS); (void)ads1115_set_address(0x48); "
        "(void)ads1115_read(0); (void)ads1115_read_voltage(1); while (1); }\n"
    ),
    "tcs34725": (
        '#include "ti_msp_dl_config.h"\n#include "tcs34725.h"\n'
        "int main(void) { tcs34725_init(); TCS34725_RGBC rgb = {0}; "
        "TCS34725_HSL hsl = {0}; if (tcs34725_read_rgb(&rgb)) { "
        "tcs34725_rgb_to_hsl(&rgb, &hsl); } tcs34725_disable(); while (1); }\n"
    ),
    "mlx90614": (
        '#include "ti_msp_dl_config.h"\n#include "mlx90614.h"\n'
        "int main(void) { mlx90614_init(); float obj = 0.0f; "
        "(void)mlx90614_read_object_temp(&obj); "
        "(void)mlx90614_read_ambient_temp(&obj); while (1); }\n"
    ),
    "at24c02": (
        '#include "ti_msp_dl_config.h"\n#include "at24c02.h"\n'
        "int main(void) { at24c02_init(); at24c02_write_byte(0, 48); "
        "at24c02_wait_write_done(); (void)at24c02_read_byte(0); "
        "uint8_t page[AT24C02_PAGE_SIZE] = {0}; "
        "(void)at24c02_write_page(0, page, AT24C02_PAGE_SIZE); "
        "at24c02_wait_write_done(); uint8_t buf[4] = {0}; "
        "(void)at24c02_read_block(0, buf, 4); while (1); }\n"
    ),
}

ok = True
for slug, main_c in MAIN_C.items():
    out = REPO / ".scratch" / "wiki-modules-batch5" / "matrix" / slug
    if out.exists():
        import shutil
        shutil.rmtree(out)
    out.mkdir(parents=True)
    resolved = resolve_selection(
        REPO / "library" / "modules", PLATFORM_MSPM0, [slug]
    )
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=REPO / "library" / "modules",
        master_project_dir=REPO / "library" / "masters" / "mspm0",
        output_dir=out,
        main_c_content=main_c,
        ccs_tools=find_ccs_tools(),
    )
    log = collect_build_log(
        PLATFORM_MSPM0, out, make=find_make(GMAKE), timeout=300
    )
    passed = compile_passed(PLATFORM_MSPM0, log.run.exit_code)
    warns = [ln for ln in log.run.output.splitlines() if "warning" in ln.lower()]
    print(f"[{slug}] passed={passed} exit={log.run.exit_code} warnings={len(warns)}")
    for ln in warns[:8]:
        print("   WARN:", ln.strip()[:160])
    ok = ok and passed and not warns
print("ALL_OK:", ok)
