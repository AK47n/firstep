"""工单 pin-unlock-stm32/03 母版 LED 定义修复守卫（红证先行）——通道表迁移后
守卫点随 module-multi-instance/03 迁移：ml_led.h 与母版默认 led_instances.h。

旧 ml_led.h 写死 `LED_GPIO GPIO_A` / `LED_RED_Pin Pin_11` / `LED_GREEN_Pin
Pin_12`——PA11/PA12 是蓝药丸 USB DM/DP，生成骨架调 LED_RED_ON() 点的是
USB 脚（编译全绿、灯不亮），与 pin_config.h 的 PC13-15 板载 LED 定义并存。
修复：include "pin_config.h" 派生（LED_GPIO=LED_PORT、旧名=新名宏）+ 板载
LED 高电平点亮（ON=set 1 / OFF=set 0，拉电流接法）。
module-multi-instance/03 起通道表移出 ml_led.h：通道宏 / (port, pin) 表 /
便捷宏在母版根 led_instances.h（默认三通道 PC13/14/15，引脚取 pin_config.h
宏——接线单源不变），ml_led.c 读它建表。测试直接读仓库内真实
library/masters/stm32/ 文件（磁盘目录即数据库，同 test_master_embedded.py
先例），防定义漂移回 USB 脚。
"""

import re
from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parents[1] / "library"
ML_LED_H = LIBRARY_DIR / "masters" / "stm32" / "ml_libs" / "ml_led.h"
ML_LED_C = LIBRARY_DIR / "masters" / "stm32" / "ml_libs" / "ml_led.c"
LED_INSTANCES_H = LIBRARY_DIR / "masters" / "stm32" / "led_instances.h"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_led_definitions_have_no_gpio_a_hardcode():
    """红证：GPIO_A 硬编码（旧 USB 脚定义）不得出现在 ml_led.h 与母版默认
    led_instances.h——修前此断言必红。"""
    for path in (ML_LED_H, LED_INSTANCES_H):
        assert "GPIO_A" not in _read(path), (
            f"{path.name} 仍写死 GPIO_A（PA11 = USB DM）"
        )


def test_default_channels_derive_from_pin_config():
    """默认通道引脚派生自接线单源：led_instances.h 默认三通道的 (port, pin)
    取 pin_config.h 宏（LED_PORT / LED_RED_PIN / LED_YELLOW_PIN /
    LED_GREEN_PIN——单实例下 config.LED_* 绑定照旧驱动三内置灯）。"""
    text = _read(LED_INSTANCES_H)
    assert re.search(r"#define\s+LED_CHANNEL_0_PORT\s+LED_PORT\b", text)
    for channel, macro in (
        ("LED_CHANNEL_0_PIN", "LED_RED_PIN"),
        ("LED_CHANNEL_1_PIN", "LED_YELLOW_PIN"),
        ("LED_CHANNEL_2_PIN", "LED_GREEN_PIN"),
    ):
        assert re.search(
            rf"#define\s+{channel}\s+{macro}\b", text
        ), f"{channel} 应派生自 {macro}"


def test_led_active_high_levels():
    """高电平点亮保持：led_on 实现内 gpio_set(..., 1)（LED 一脚接地、一脚接
    引脚，拉电流接法——2026-08-15 用户更正，原灌电流 0=亮 的假设作废）；
    三色 ON/OFF 便捷宏仍在（led_instances.h，led_on/led_off 形态）。"""
    c_text = _read(ML_LED_C)
    assert "高电平点亮" in c_text
    assert re.search(r"gpio_set\(led\.port,\s*led\.pin,\s*1\)", c_text)

    text = _read(LED_INSTANCES_H)
    for color in ("LED_RED", "LED_YELLOW", "LED_GREEN"):
        assert re.search(rf"#define\s+{color}_ON\(\)\s+led_on\(LED", text), (
            f"{color}_ON() 缺失"
        )
        assert re.search(rf"#define\s+{color}_OFF\(\)\s+led_off\(LED", text), (
            f"{color}_OFF() 缺失"
        )


def test_ml_led_c_reads_channel_table_from_led_instances():
    """ml_led.c 泛型化：读 LED_CHANNEL_COUNT + LED_PIN_TABLE 建表，越界钳回
    首通道（module-multi-instance/03 契约）。"""
    c_text = _read(ML_LED_C)
    assert "LED_CHANNEL_COUNT" in c_text
    assert "LED_PIN_TABLE" in c_text
    assert "channel >= LED_CHANNEL_COUNT" in c_text
