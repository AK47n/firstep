# -*- coding: utf-8 -*-
"""wiki-modules-batch1 编译矩阵通用 runner：单选生成 → gmake 真编译（0 error 硬门槛）。

用法：python run_module_matrix.py <slug>（slug ∈ joystick/hc05/nrf24l01/ir_remote）。
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

MAIN_C = {
    "joystick": (
        '#include "ti_msp_dl_config.h"\n'
        '#include "joystick.h"\n'
        "int main(void) { joystick_init(); uint16_t x = joystick_read_x_percent(); "
        "(void)x; uint16_t y = joystick_read_y_percent(); (void)y; "
        "uint8_t sw = joystick_read_sw(); (void)sw; while (1); }\n"
    ),
    "hc05": (
        '#include "ti_msp_dl_config.h"\n'
        '#include "hc05.h"\n'
        "int main(void) {\n"
        "    hc05_init();\n"
        "    hc05_send_string(\"hello\\r\\n\");\n"
        "    uint8_t buf[16]; uint16_t n = hc05_receive(buf, 16);\n"
        "    (void)n; uint16_t a = hc05_available(); (void)a;\n"
        "    (void)hc05_is_connected();\n"
        "    hc05_at_mode_exit();\n"
        "    while (1) { }\n"
        "}\n"
    ),
    "nrf24l01": (
        '#include "ti_msp_dl_config.h"\n'
        '#include "nrf24l01.h"\n'
        "int main(void) {\n"
        "    nrf24l01_init();\n"
        "    nrf24l01_set_mode(NRF24L01_MODE_TX);\n"
        "    uint8_t tx[8] = {1,2,3,4,5,6,7,8};\n"
        "    (void)nrf24l01_tx_packet(tx, 8);\n"
        "    nrf24l01_set_mode(NRF24L01_MODE_RX);\n"
        "    uint8_t rx[32];\n"
        "    (void)nrf24l01_rx_packet(rx, 32);\n"
        "    while (1) { }\n"
        "}\n"
    ),
    "ir_remote": (
        '#include "ti_msp_dl_config.h"\n'
        '#include "ir_remote.h"\n'
        "int main(void) {\n"
        "    ir_remote_init();\n"
        "    uint8_t got = ir_remote_poll();\n"
        "    (void)got;\n"
        "    (void)ir_remote_has_data();\n"
        "    (void)ir_remote_get_code();\n"
        "    (void)ir_remote_get_address();\n"
        "    ir_remote_clear();\n"
        "    while (1) { }\n"
        "}\n"
    ),
}

if len(sys.argv) < 2 or sys.argv[1] not in MAIN_C:
    print("用法：python run_module_matrix.py <slug>（可选：" + "/".join(sorted(MAIN_C)) + "）")
    sys.exit(2)
slug = sys.argv[1]

out = REPO / ".scratch" / "wiki-modules-batch1" / "matrix" / slug
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_MSPM0, [slug])
generate(
    platform=PLATFORM_MSPM0,
    manifests=resolved.manifests,
    module_library_dir=REPO / "library" / "modules",
    master_project_dir=REPO / "library" / "masters" / "mspm0",
    output_dir=out,
    main_c_content=MAIN_C[slug],
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
