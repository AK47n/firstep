"""key / uart 补 stm32（module-functionalize/04）：双平台 API 与真实库不变量。"""

import json
from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"


def _manifest(slug: str) -> dict:
    return json.loads((MODULES / slug / "manifest.json").read_text(encoding="utf-8"))


def _read(slug: str, rel: str) -> str:
    return (MODULES / slug / rel).read_text(encoding="utf-8", errors="replace")


def test_key_module_has_stm32_files_and_uniform_channel_api():
    """key 双平台：get_key_state(uint8_t channel) + key_init；stm32 用 pin_config.h
    宏 + 上拉低电平按下（通道表 key_instances.h，key-multi-instance/02 泛型化）。"""
    m = _manifest("key")
    assert "stm32" in m["platforms"]
    for rel in m["platforms"]["stm32"]["files"]:
        assert (MODULES / "key" / rel).is_file(), rel
    stm32_c = _read("key", "code/key_stm32.c")
    stm32_h = _read("key", "code/key_stm32.h")
    mspm0_h = _read("key", "code/key.h")
    assert "uint8_t get_key_state(uint8_t channel)" in stm32_h
    assert "uint8_t get_key_state(uint8_t channel)" in mspm0_h
    assert "void key_init(void)" in stm32_h and "void key_init(void)" in mspm0_h
    assert "gpio_get(KEY_PINS" in stm32_c
    assert "低电平" in stm32_c
    assert "KEY_CHANNEL_COUNT" in stm32_h and "KEY_PIN_TABLE" in stm32_h


def test_key_stm32_pin_declaration_pb3():
    """key stm32 引脚声明：KEY_START 默认 PB3（JTDO 复位后可用）。"""
    m = _manifest("key")
    pins = m["platforms"]["stm32"]["pins"]
    assert pins[0]["id"] == "KEY_START"
    assert pins[0]["default"] == "PB3"
    assert set(pins[0]["macros"]) == {"KEY_GPIO", "KEY_PIN"}


def test_key_mspm0_uses_syscfg_key_start_pin():
    """mspm0 通道表（模块 code/key_instances.h）用 SysConfig 生成的
    KEY_PORT / KEY_START_PIN；manifest mspm0 files 含通道表。"""
    m = _manifest("key")
    assert "code/key_instances.h" in m["platforms"]["mspm0"]["files"]
    instances_h = _read("key", "code/key_instances.h")
    assert "KEY_PORT" in instances_h and "KEY_START_PIN" in instances_h
    assert "KEY_CHANNEL_COUNT 1" in instances_h


def test_key_default_channel_table_single_channel_both_platforms():
    """默认通道表 = 1 通道单实例：模块侧（mspm0）与母版根（stm32）都有默认表，
    KEY_START=0 + KEY_PIN_TABLE 形态一致。"""
    mspm0_table = _read("key", "code/key_instances.h")
    assert "KEY_START 0" in mspm0_table
    assert "KEY_PIN_TABLE" in mspm0_table
    masters = Path(__file__).resolve().parents[1] / "library" / "masters"
    stm32_table = (masters / "stm32" / "key_instances.h").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "KEY_CHANNEL_COUNT 1" in stm32_table
    assert "KEY_START 0" in stm32_table
    assert "KEY_GPIO" in stm32_table and "KEY_PIN" in stm32_table


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
