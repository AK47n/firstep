"""key / uart 补 stm32（module-functionalize/04）：双平台 API 与真实库不变量。"""

import json
from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"


def _manifest(slug: str) -> dict:
    return json.loads((MODULES / slug / "manifest.json").read_text(encoding="utf-8"))


def _read(slug: str, rel: str) -> str:
    return (MODULES / slug / rel).read_text(encoding="utf-8", errors="replace")


def test_key_module_has_stm32_files_and_uniform_no_arg_api():
    """key 双平台：get_key_state(void)；stm32 用 pin_config.h 宏 + 上拉低电平按下。"""
    m = _manifest("key")
    assert "stm32" in m["platforms"]
    for rel in m["platforms"]["stm32"]["files"]:
        assert (MODULES / "key" / rel).is_file(), rel
    stm32_c = _read("key", "code/key_stm32.c")
    stm32_h = _read("key", "code/key_stm32.h")
    mspm0_h = _read("key", "code/key.h")
    assert "uint8_t get_key_state(void)" in stm32_h
    assert "uint8_t get_key_state(void)" in mspm0_h
    assert "gpio_get(KEY_GPIO, KEY_PIN)" in stm32_c
    assert "低电平按下" in stm32_c or "低电平" in stm32_c


def test_key_stm32_pin_declaration_pb3():
    """key stm32 引脚声明：KEY_START 默认 PB3（JTDO 复位后可用）。"""
    m = _manifest("key")
    pins = m["platforms"]["stm32"]["pins"]
    assert pins[0]["id"] == "KEY_START"
    assert pins[0]["default"] == "PB3"
    assert set(pins[0]["macros"]) == {"KEY_GPIO", "KEY_PIN"}


def test_key_mspm0_uses_syscfg_key_start_pin():
    """mspm0 key.c 用 SysConfig 生成的 KEY_PORT / KEY_START_PIN。"""
    c = _read("key", "code/key.c")
    assert "KEY_PORT" in c and "KEY_START_PIN" in c


def test_uart_module_has_stm32_files_with_uartn_enum_api():
    """uart 双平台：stm32 版用 UARTn_enum（UART_1/2/3），函数名与 mspm0 相同。"""
    m = _manifest("uart")
    assert "stm32" in m["platforms"]
    for rel in m["platforms"]["stm32"]["files"]:
        assert (MODULES / "uart" / rel).is_file(), rel
    stm32_h = _read("uart", "code/uart_stm32.h")
    for fn in ("UART_send_string", "UART_send_char", "UART_send_buffer"):
        assert fn in stm32_h
    assert "UARTn_enum" in stm32_h
    stm32_c = _read("uart", "code/uart_stm32.c")
    assert "uart_sendbyte" in stm32_c and "uart_sendstr" in stm32_c


def test_uart_manifest_description_dual_platform():
    assert "stm32" in _manifest("uart")["description"] or "双平台" in _manifest("uart")["description"]
