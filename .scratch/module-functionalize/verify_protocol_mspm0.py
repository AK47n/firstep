"""module-functionalize 协议批次真机编译脚本（mspm0）：按切片生成 + gmake。

用法：python verify_protocol_mspm0.py <uwb|zigbee|key|all>
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import find_ccs_tools, find_make
from contest_generator.generator import generate
from contest_generator.platforms import PLATFORM_MSPM0
from contest_generator.selection import resolve_selection

GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"

UWB_MAIN = """#include "ti_msp_dl_config.h"
#include "uwb_uart_mspm0.h"

/* module-functionalize/06 编译验收：UWB_UART（UART2）模块内自带 IRQHandler。 */
int main(void)
{
    /* 产物编译验收门禁契约：SYSCFG_DL_init 注释，上板取消注释 */
    /* SYSCFG_DL_init(); */
    uwb_uart_init();
    while (1)
    {
        uwb_get_frame_rate();
    }
}
"""

ZIGBEE_MAIN = """#include "ti_msp_dl_config.h"
#include "zigbee_uart_mspm0.h"

/* module-functionalize/07 编译验收：ZIGBEE_UART（UART3）模块内自带 IRQHandler。 */
int main(void)
{
    /* SYSCFG_DL_init(); */
    zigbee_uart_init();
    while (1)
    {
        if (g_key_id_updated)
        {
            g_key_id_updated = 0;
        }
    }
}
"""

KEY_MAIN = """#include "ti_msp_dl_config.h"
#include "zigbee_uart_key_mspm0.h"

/* module-functionalize/08 编译验收：key 与 zigbee 共享 ZIGBEE_UART（UART3）。 */
int main(void)
{
    /* SYSCFG_DL_init(); */
    zigbee_uart_key_init();
    zigbee_uart_key_send_id(1);
    while (1)
    {
    }
}
"""

DEBUG_MAIN = """#include "ti_msp_dl_config.h"
#include "debug_uart_mspm0.h"

/* module-polish/01 编译验收：DEBUG_UART（UART2）模块内自带 IRQHandler。 */
int main(void)
{
    /* SYSCFG_DL_init(); */
    debug_uart_init();
    debug_uart_send("debug uart ok\\r\\n");
    while (1)
    {
        debug_cmd_poll();
    }
}
"""

ALL_MAIN = """#include "ti_msp_dl_config.h"
#include "digit_uart_mspm0.h"
#include "uwb_uart_mspm0.h"
#include "zigbee_uart_mspm0.h"
#include "zigbee_uart_key_mspm0.h"
#include "ball_detect.h"

/* module-functionalize 批次总验收：三个 UART 实例同工程共存。
 * UWB/UART2 与 Zigbee/UART3 的 IRQHandler 在各自模块内定义；
 * DIGIT/BALL 共享 UART1，由本文件单个 handler 聚合。 */
int main(void)
{
    /* SYSCFG_DL_init(); */
    digit_uart_init();
    uwb_uart_init();
    zigbee_uart_init();
    zigbee_uart_key_init();
    ball_detect_init();
    zigbee_uart_key_send_id(1);
    while (1)
    {
        digit_uart_parse();
        ball_detect_parse();
    }
}

void DIGIT_UART_INST_IRQHandler(void)
{
    digit_uart_rx_handler();
    ball_detect_rx_handler();
}
"""

SLICES = {
    "debug": (["debug_uart"], DEBUG_MAIN),
    "uwb": (["uwb_uart"], UWB_MAIN),
    "zigbee": (["zigbee_uart"], ZIGBEE_MAIN),
    "key": (["zigbee_uart_key"], KEY_MAIN),
    "all": (
        ["digit_uart", "uwb_uart", "zigbee_uart", "zigbee_uart_key", "ball_detect"],
        ALL_MAIN,
    ),
}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "uwb"
    if mode not in SLICES:
        print(f"未知切片 {mode}，可选：{', '.join(SLICES)}")
        return 2
    slugs, main_text = SLICES[mode]

    lib = REPO / "library"
    out = HERE / f"out_{mode}_mspm0"
    if out.exists():
        shutil.rmtree(out)

    tools = find_ccs_tools()
    if tools is None:
        print("CCS 工具链未探测到")
        return 2
    make = find_make(GMAKE)
    if make is None:
        print(f"gmake 未找到：{GMAKE}")
        return 2

    resolved = resolve_selection(lib / "modules", PLATFORM_MSPM0, slugs)
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=lib / "modules",
        master_project_dir=lib / "masters" / PLATFORM_MSPM0,
        output_dir=out,
        main_c_content=main_text,
        ccs_tools=tools,
    )

    log = out / "gmake_build.log"
    proc = subprocess.run(
        [str(make), "-C", str(out / "Debug"), "-f", "makefile", "-B", "all"],
        capture_output=True, text=True, timeout=600,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    log.write_text(text, encoding="utf-8")
    tail = text.strip().splitlines()[-6:] if text.strip() else ["无输出"]
    print(f"[{mode} gmake] exit={proc.returncode}")
    print("\n".join(tail))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
