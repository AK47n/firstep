"""module-polish 批次：debug_uart mspm0 / OLED 共同 API / delay_us。"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"


def _manifest(slug: str) -> ModuleManifest:
    return ModuleManifest.load(MODULES / slug)


def _read(slug: str, rel: str) -> str:
    return (MODULES / slug / rel).read_text(encoding="utf-8", errors="replace")


def _syscfg_text() -> str:
    return (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")


def test_debug_uart_mspm0_driver_and_pins():
    """debug_uart mspm0：DEBUG_UART/UART2、PA23 TX / PA22 RX；API 与 stm32 同形。"""
    entry = _manifest("debug_uart").platforms["mspm0"]
    assert entry.files == ("code/debug_uart_mspm0.c", "code/debug_uart_mspm0.h")
    for rel in entry.files:
        assert (MODULES / "debug_uart" / rel).is_file(), rel
    assert {(p.id, p.type, p.default, p.required) for p in entry.pins} == {
        ("DEBUG_UART_TX", "uart_tx", "PA23", True),
        ("DEBUG_UART_RX", "uart_rx", "PA22", True),
    }

    mspm0_h = _read("debug_uart", "code/debug_uart_mspm0.h")
    stm32_h = _read("debug_uart", "code/debug_uart.h")
    for fn in ("debug_uart_init", "debug_uart_send", "debug_uart_rx_handler", "debug_cmd_poll"):
        assert fn in mspm0_h
        assert fn in stm32_h
    assert "DEBUG_PRINTF" in mspm0_h

    c = _read("debug_uart", "code/debug_uart_mspm0.c")
    assert "DL_UART_transmitDataBlocking(DEBUG_UART_INST" in c
    assert "DEBUG_UART_INST_IRQHandler" in c


def test_debug_uart_syscfg_instance_and_prune():
    """DEBUG_UART 实例存在且归 debug_uart 消费；与 UWB 默认同 UART2 属显式重叠。"""
    syscfg = _syscfg_text()
    assert "const DEBUG_UART = UART.addInstance();" in syscfg
    assert 'DEBUG_UART.peripheral.$assign = "UART2";' in syscfg
    assert 'DEBUG_UART.peripheral.txPin.$assign = "PA23";' in syscfg
    assert 'DEBUG_UART.peripheral.rxPin.$assign = "PA22";' in syscfg

    from contest_generator.syscfg_instances import INSTANCES_BY_SLUG
    from contest_generator.syscfg_prune import prune_syscfg

    assert "DEBUG_UART" in INSTANCES_BY_SLUG["debug_uart"]
    assert "const DEBUG_UART" in prune_syscfg(syscfg, ["debug_uart"])
    assert "const DEBUG_UART" not in prune_syscfg(syscfg, ["digit_uart"])

def test_oled_common_api_exists_on_both_platforms():
    """三件套 oled_show_text / oled_show_number / oled_refresh 双平台都在；旧 API 保留。"""
    stm32_h = (STM32_MASTER / "ml_libs" / "ml_oled.h").read_text(
        encoding="utf-8", errors="replace"
    )
    mspm0_h = _read("oled", "code/oled.h")
    for fn in ("oled_show_text", "oled_show_number", "oled_refresh"):
        assert fn in stm32_h
        assert fn in mspm0_h
    for old in ("OLED_ShowString", "OLED_ShowNum", "OLED_Init"):
        assert old in stm32_h
        assert old in mspm0_h

    stm32_c = (STM32_MASTER / "ml_libs" / "ml_oled.c").read_text(
        encoding="utf-8", errors="replace"
    )
    mspm0_c = _read("oled", "code/oled.c")
    assert "OLED_ShowString(Line, Column, (char *)String)" in stm32_c
    assert "OLED_ShowString((u8)(column * 8), (u8)(line * 16), (u8 *)text, 16)" in mspm0_c

def test_delay_us_exists_on_mspm0():
    """mspm0 delay 补 delay_us（stm32 母版已有，双平台集合趋同）。"""
    h = _read("delay", "code/delay.h")
    c = _read("delay", "code/delay.c")
    assert "void delay_us(uint32_t us)" in h
    assert "(CPUCLK_FREQ / 1000000)" in c
    stm32_h = (STM32_MASTER / "ml_libs" / "ml_delay.h").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "delay_us" in stm32_h

def test_led_convenience_macros_aligned_both_platforms():
    """三色 ON/OFF 便捷宏双平台一致（module-polish/05）——通道表迁移后宏在
    led_instances.h（stm32 母版默认 / mspm0 库内默认，module-multi-instance/03）。"""
    mspm0_h = _read("led", "code/led_instances.h")
    stm32_h = (STM32_MASTER / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    )
    for macro in (
        "LED_RED_ON",
        "LED_RED_OFF",
        "LED_YELLOW_ON",
        "LED_YELLOW_OFF",
        "LED_GREEN_ON",
        "LED_GREEN_OFF",
    ):
        assert f"#define {macro}" in mspm0_h
        assert f"#define {macro}" in stm32_h


def test_motor_notes_mark_legacy_api():
    """motor 双平台 notes 明确旧 API 兼容遗留、新工程用统一 API。"""
    entry_m = _manifest("motor").platforms["mspm0"]
    entry_s = _manifest("motor").platforms["stm32"]
    assert "limit_duty 为兼容遗留" in entry_m.notes
    assert "请用 motor_set_duty" in entry_m.notes
    assert "旧 API（motorA_duty/motorB_duty/encoder_init）仅作兼容遗留" in entry_s.notes
    assert "新工程请用 motor_* 统一 API" in entry_s.notes
