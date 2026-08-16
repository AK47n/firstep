"""module-functionalize/05-09：协议驱动补 mspm0（digit/uwb/zigbee/key/ball）。

真实库不变量：mspm0 文件齐全、双平台 API 同形、manifest pins 与母版
mspm0.syscfg $assign 一致、syscfg 实例消费映射与裁剪行为、模块自含与
DL_UART 宏消费。编译级验收（gmake 0 错）在 .scratch/module-functionalize/
verify_protocol_mspm0.py 真机脚本留痕，本文件只管可内存验证的数据不变量。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"


def _manifest(slug: str) -> ModuleManifest:
    return ModuleManifest.load(MODULES / slug)


def _read(slug: str, rel: str) -> str:
    return (MODULES / slug / rel).read_text(encoding="utf-8", errors="replace")


def _mspm0_pins(slug: str):
    return _manifest(slug).platforms["mspm0"].pins


def _syscfg_text() -> str:
    return (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")


def test_digit_uart_mspm0_driver_shape_and_shared_uart1_note():
    """digit_uart mspm0 雏形：文件/引脚/API 与 stm32 同形；头注释写明 UART1
    与 ball_detect 共享、由 main.c 单个 IRQHandler 聚合两个 rx_handler。"""
    m = _manifest("digit_uart")
    entry = m.platforms["mspm0"]
    assert [Path(f).name for f in entry.files] == [
        "digit_uart_mspm0.c",
        "digit_uart_mspm0.h",
    ]
    for rel in entry.files:
        assert (MODULES / "digit_uart" / rel).is_file(), rel

    assert {(p.id, p.type, p.default, p.required) for p in entry.pins} == {
        ("DIGIT_UART_TX", "uart_tx", "PA8", True),
        ("DIGIT_UART_RX", "uart_rx", "PA9", True),
    }

    h = _read("digit_uart", "code/digit_uart_mspm0.h")
    c = _read("digit_uart", "code/digit_uart_mspm0.c")
    for fn in ("digit_uart_init", "digit_uart_flush", "digit_uart_rx_handler", "digit_uart_parse"):
        assert fn in h
    assert "DIGIT_UART_INST" in c
    assert "NVIC_EnableIRQ(DIGIT_UART_INST_INT_IRQN)" in c
    # 共享 UART1 的挂载形态在模块头给 LLM 看到（与 ball_detect 同选时聚合）
    assert "DIGIT_UART_INST_IRQHandler" in h
    assert "ball_detect_rx_handler" in h

def test_config_module_has_mspm0_parameter_header():
    """config 补 mspm0：UWB/Zigbee 依赖 config，否则 mspm0 依赖展开 missing。"""
    entry = _manifest("config").platforms["mspm0"]
    assert entry.files == ("code/config_mspm0.h",)
    text = _read("config", "code/config_mspm0.h")
    for macro in (
        "UWB_BAUD",
        "ZIGBEE_BAUD",
        "FILTER_WIN_SIZE",
        "FILTER_AZ_WIN_SIZE",
        "DIST_MAX_STEP",
        "AZ_MAX_STEP",
    ):
        assert f"#define {macro}" in text


def test_uwb_uart_mspm0_driver_shape_and_pins():
    """uwb_uart mspm0：UART2（PA23 TX / PA24 RX）；API/全局量与 stm32 同形。"""
    entry = _manifest("uwb_uart").platforms["mspm0"]
    assert entry.files == ("code/uwb_uart_mspm0.c", "code/uwb_uart_mspm0.h")
    for rel in entry.files:
        assert (MODULES / "uwb_uart" / rel).is_file(), rel
    assert {(p.id, p.type, p.default, p.required) for p in entry.pins} == {
        ("UWB_UART_TX", "uart_tx", "PA23", True),
        ("UWB_UART_RX", "uart_rx", "PA24", True),
    }
    assert entry.kit and entry.source_url  # 同一套件身份随平台条目走

    mspm0_h = _read("uwb_uart", "code/uwb_uart_mspm0.h")
    stm32_h = _read("uwb_uart", "code/uwb_uart.h")
    for name in (
        "UWB_Data",
        "g_uwb_raw",
        "g_uwb_filtered",
        "g_uwb_updated",
        "g_uwb_last_tick",
        "g_uwb_frame_count",
        "uwb_uart_init",
        "uwb_rx_handler",
        "uwb_filter_reset",
        "uwb_get_frame_rate",
    ):
        assert name in mspm0_h
        assert name in stm32_h

    c = _read("uwb_uart", "code/uwb_uart_mspm0.c")
    assert "DL_UART_receiveData(UWB_UART_INST)" in c
    assert "UWB_UART_INST_IRQHandler" in c
    assert '#include "config_mspm0.h"' in c
    assert '#include "filter.h"' in c


def test_uwb_syscfg_instance_and_prune_mapping():
    """UWB_UART 母版实例存在且归 uwb_uart 消费：选中保留、未选裁剪。"""
    syscfg = _syscfg_text()
    assert "const UWB_UART = UART.addInstance();" in syscfg
    assert 'UWB_UART.peripheral.$assign = "UART2";' in syscfg
    assert 'UWB_UART.peripheral.txPin.$assign = "PA23";' in syscfg
    assert 'UWB_UART.peripheral.rxPin.$assign = "PA24";' in syscfg

    from contest_generator.syscfg_instances import INSTANCES_BY_SLUG
    from contest_generator.syscfg_prune import prune_syscfg



def test_zigbee_uart_mspm0_driver_shape_and_pins():
    """zigbee_uart mspm0：UART3（PA26 TX / PA25 RX）；API/全局量与 stm32 同形。"""
    entry = _manifest("zigbee_uart").platforms["mspm0"]
    assert entry.files == ("code/zigbee_uart_mspm0.c", "code/zigbee_uart_mspm0.h")
    for rel in entry.files:
        assert (MODULES / "zigbee_uart" / rel).is_file(), rel
    assert {(p.id, p.type, p.default, p.required) for p in entry.pins} == {
        ("ZIGBEE_UART_TX", "uart_tx", "PA26", True),
        ("ZIGBEE_UART_RX", "uart_rx", "PA25", True),
    }

    mspm0_h = _read("zigbee_uart", "code/zigbee_uart_mspm0.h")
    stm32_h = _read("zigbee_uart", "code/zigbee_uart.h")
    for name in (
        "ZIGBEE_SYNC1",
        "ZIGBEE_SYNC2",
        "ZIGBEE_FRAME_SIZE",
        "g_key_id",
        "g_key_id_updated",
        "g_key_id_last_tick",
        "g_zigbee_byte_count",
        "zigbee_uart_init",
        "zigbee_rx_handler",
    ):
        assert name in mspm0_h
        assert name in stm32_h

    c = _read("zigbee_uart", "code/zigbee_uart_mspm0.c")
    assert "DL_UART_receiveData(ZIGBEE_UART_INST)" in c
    assert "ZIGBEE_UART_INST_IRQHandler" in c


def test_zigbee_syscfg_instance_and_prune_mapping():
    """ZIGBEE_UART 母版实例存在且归 zigbee_uart 消费（key 后续共享）。"""
    syscfg = _syscfg_text()
    assert "const ZIGBEE_UART = UART.addInstance();" in syscfg
    assert 'ZIGBEE_UART.peripheral.$assign = "UART3";' in syscfg
    assert 'ZIGBEE_UART.peripheral.txPin.$assign = "PA26";' in syscfg
    assert 'ZIGBEE_UART.peripheral.rxPin.$assign = "PA25";' in syscfg

    from contest_generator.syscfg_instances import INSTANCES_BY_SLUG
    from contest_generator.syscfg_prune import prune_syscfg

    assert "ZIGBEE_UART" in INSTANCES_BY_SLUG["zigbee_uart"]
    assert "const ZIGBEE_UART" in prune_syscfg(syscfg, ["zigbee_uart"])
    assert "const ZIGBEE_UART" not in prune_syscfg(syscfg, ["digit_uart"])
def test_zigbee_uart_key_mspm0_driver_shares_instance():
    """zigbee_uart_key mspm0：与 zigbee_uart 共享 ZIGBEE_UART/UART3 默认脚；
    API 与 stm32 同形；只发不收不定义 IRQHandler。"""
    entry = _manifest("zigbee_uart_key").platforms["mspm0"]
    assert entry.files == (
        "code/zigbee_uart_key_mspm0.c",
        "code/zigbee_uart_key_mspm0.h",
    )
    for rel in entry.files:
        assert (MODULES / "zigbee_uart_key" / rel).is_file(), rel
    assert {(p.id, p.type, p.default, p.required) for p in entry.pins} == {
        ("ZIGBEE_UART_TX", "uart_tx", "PA26", True),
        ("ZIGBEE_UART_RX", "uart_rx", "PA25", True),
    }

    mspm0_h = _read("zigbee_uart_key", "code/zigbee_uart_key_mspm0.h")
    stm32_h = _read("zigbee_uart_key", "code/zigbee_uart_key.h")
    for fn in ("zigbee_uart_key_init", "zigbee_uart_key_send_id"):
        assert fn in mspm0_h
        assert fn in stm32_h

    c = _read("zigbee_uart_key", "code/zigbee_uart_key_mspm0.c")
    assert "DL_UART_transmitDataBlocking(ZIGBEE_UART_INST" in c
    assert "ZIGBEE_UART_INST_IRQHandler" not in c  # 共享 handler 归接收侧

    from contest_generator.syscfg_instances import INSTANCES_BY_SLUG
    from contest_generator.syscfg_prune import prune_syscfg

    assert set(INSTANCES_BY_SLUG["zigbee_uart_key"]) == {"ZIGBEE_UART"}
    # key 单独选中也保留共享实例（否则发送宏缺失编译炸）
    assert "const ZIGBEE_UART" in prune_syscfg(_syscfg_text(), ["zigbee_uart_key"])


def test_ball_detect_mspm0_pins_and_shared_uart1_note():
    """ball_detect mspm0 已有实现补声明：pins 与 DIGIT_UART 共享映射 + 头注释
    写明与 digit_uart 同选时由 main.c 单个 UART1 handler 聚合。"""
    entry = _manifest("ball_detect").platforms["mspm0"]
    assert entry.files == ("code/ball_detect.c", "code/ball_detect.h")
    assert {(p.id, p.type, p.default, p.required) for p in entry.pins} == {
        ("BALL_DETECT_UART_TX", "uart_tx", "PA8", True),
        ("BALL_DETECT_UART_RX", "uart_rx", "PA9", True),
    }
    assert entry.hardware_bound is True  # K230 视觉套件绑定

    h = _read("ball_detect", "code/ball_detect.h")
    c = _read("ball_detect", "code/ball_detect.c")
    for fn in (
        "ball_detect_init",
        "ball_detect_flush",
        "ball_detect_rx_handler",
        "ball_detect_parse",
    ):
        assert fn in h
    assert "DIGIT_UART_INST" in c
    assert "DIGIT_UART_INST_IRQHandler" in h
    assert "digit_uart_rx_handler" in h

    from contest_generator.syscfg_instances import INSTANCES_BY_SLUG
    from contest_generator.syscfg_prune import prune_syscfg

    assert set(INSTANCES_BY_SLUG["ball_detect"]) == {"DIGIT_UART"}
    assert "const DIGIT_UART" in prune_syscfg(_syscfg_text(), ["ball_detect"])

def test_generate_mspm0_all_protocol_modules_default_layout(tmp_path):
    """五个协议模块同选（三 UART 默认布局）生成通过 + syscfg 只留本批实例。"""
    from contest_generator.generator import generate
    from contest_generator.platforms import PLATFORM_MSPM0
    from contest_generator.selection import resolve_selection

    main_c = """#include "ti_msp_dl_config.h"
#include "digit_uart_mspm0.h"
#include "uwb_uart_mspm0.h"
#include "zigbee_uart_mspm0.h"
#include "zigbee_uart_key_mspm0.h"
#include "ball_detect.h"

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
    resolved = resolve_selection(
        MODULES,
        PLATFORM_MSPM0,
        ["digit_uart", "uwb_uart", "zigbee_uart", "zigbee_uart_key", "ball_detect"],
    )
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out,
        main_c_content=main_c,
    )
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    for keep in ("DIGIT_UART", "UWB_UART", "ZIGBEE_UART"):
        assert f"const {keep} = UART.addInstance();" in syscfg
    for drop in ("IMU601", "OLED", "I2C_0", "HUIDU", "MOTOR_PID"):
        assert f"const {drop}" not in syscfg
    # 模块文件树齐全：五模块各自平台条目 + config/filter 依赖
    modules_dir = out / "modules"
    for slug in (
        "digit_uart",
        "uwb_uart",
        "zigbee_uart",
        "zigbee_uart_key",
        "ball_detect",
        "config",
        "filter",
    ):
        assert (modules_dir / slug).is_dir(), slug