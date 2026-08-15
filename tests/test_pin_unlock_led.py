"""工单 pin-unlock-stm32/03 母版 ml_led.h 双 LED 定义修复守卫（红证先行）。

旧 ml_led.h 写死 `LED_GPIO GPIO_A` / `LED_RED_Pin Pin_11` / `LED_GREEN_Pin
Pin_12`——PA11/PA12 是蓝药丸 USB DM/DP，生成骨架调 LED_RED_ON() 点的是
USB 脚（编译全绿、灯不亮），与 pin_config.h 的 PC13-15 板载 LED 定义并存。
修复：include "pin_config.h" 派生（LED_GPIO=LED_PORT、旧名=新名宏）+ 板载
LED 低电平点亮（ON=set 0 / OFF=set 1）。测试直接读仓库内真实
library/masters/stm32/ml_libs/ml_led.h（磁盘目录即数据库，同
test_master_embedded.py 先例），防定义漂移回 USB 脚。
"""

import re
from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parents[1] / "library"
ML_LED_H = LIBRARY_DIR / "masters" / "stm32" / "ml_libs" / "ml_led.h"


def _read() -> str:
    return ML_LED_H.read_text(encoding="utf-8", errors="replace")


def test_ml_led_h_has_no_gpio_a_hardcode():
    """红证：GPIO_A 硬编码（旧 USB 脚定义）不得出现——修前此断言必红。"""
    text = _read()
    assert "GPIO_A" not in text, "ml_led.h 仍写死 GPIO_A（PA11 = USB DM）"


def test_ml_led_h_derives_from_pin_config():
    """派生自接线单源：include pin_config.h + 旧名宏 = pin_config 新名宏。

    LED_YELLOW_Pin 别名一并钉（与红/绿旧名同族）；全库 grep 无
    LED_YELLOW_ON/OFF 消费方（debug_uart.c 直用 pin_config.h 宏），
    ON/OFF 宏不补（工单 grep 消费方定：有则必补，无则不补）。
    """
    text = _read()
    assert '#include "pin_config.h"' in text, "未 include 接线单源"
    for old, new in (
        ("LED_GPIO", "LED_PORT"),
        ("LED_RED_Pin", "LED_RED_PIN"),
        ("LED_YELLOW_Pin", "LED_YELLOW_PIN"),
        ("LED_GREEN_Pin", "LED_GREEN_PIN"),
    ):
        assert re.search(
            rf"#define\s+{old}\s+{new}\b", text
        ), f"{old} 应派生自 {new}"


def test_ml_led_h_active_low_levels():
    """低电平点亮翻转：ON() = set 0、OFF() = set 1（板载 LED 灌电流）。"""
    text = _read()
    for color in ("LED_RED", "LED_GREEN"):
        on = re.search(
            rf"#define\s+{color}_ON\(\)\s+gpio_set\(LED_GPIO,\s*{color}_Pin,"
            rf"\s*(\d)\)",
            text,
        )
        off = re.search(
            rf"#define\s+{color}_OFF\(\)\s+gpio_set\(LED_GPIO,\s*{color}_Pin,"
            rf"\s*(\d)\)",
            text,
        )
        assert on is not None, f"{color}_ON() 缺失"
        assert off is not None, f"{color}_OFF() 缺失"
        assert on.group(1) == "0", f"{color}_ON() 应 set 0（低电平点亮）"
        assert off.group(1) == "1", f"{color}_OFF() 应 set 1（高电平熄灭）"
