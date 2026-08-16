"""led / beep 拆分（module-functionalize/01）：真实库数据/代码不变量。

led 与 beep 独立成模块（双平台），led_beep 保留为组合模块（依赖二者）。
"""

from pathlib import Path

from contest_generator.library import list_modules
from contest_generator.syscfg_instances import INSTANCES_BY_SLUG

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"


def _manifest(slug: str):
    return next(m for m in list_modules(MODULES) if m.slug == slug)


def _read(slug: str, rel: str) -> str:
    return (MODULES / slug / rel).read_text(encoding="utf-8", errors="replace")


def test_led_module_dual_platform_with_uniform_api():
    """led 模块双平台，API 统一：led_init/led_on/led_off/led_toggle；通道宏在
    led_instances.h（生成器多实例渲染产物——stm32 母版默认三通道、mspm0 库内
    默认单通道，module-multi-instance/03）。

    stm32 实现内嵌母版 ml_led（空条目先例 oled/delay），mspm0 实现随模块。"""
    led = _manifest("led")
    assert set(led.platforms) == {"stm32", "mspm0"}
    assert led.platforms["stm32"].files == ()  # 内嵌母版
    for rel in led.platforms["mspm0"].files:
        assert (MODULES / "led" / rel).is_file(), rel
    mspm0_h = _read("led", "code/led.h")
    stm32_ml_led_h = (LIBRARY_ROOT / "masters" / "stm32" / "ml_libs" / "ml_led.h").read_text(
        encoding="utf-8", errors="replace"
    )
    for h in (stm32_ml_led_h, mspm0_h):
        for fn in ("led_init", "led_on", "led_off", "led_toggle"):
            assert fn in h
        assert "led_instances.h" in h  # 通道宏经 led_instances.h 进入接口
    stm32_channels = (LIBRARY_ROOT / "masters" / "stm32" / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    )
    mspm0_channels = _read("led", "code/led_instances.h")
    for text in (stm32_channels, mspm0_channels):
        assert "LED_RED" in text and "LED_CHANNEL_COUNT" in text


def test_led_stm32_uses_pin_config_macros_and_source_polarity():
    """stm32 led 默认通道引脚取 pin_config.h 宏（接线单源，单实例下
    config.LED_* 绑定照旧驱动三内置灯）；1=亮（拉电流）封装在 led_on 内部。"""
    ml_led_h = (LIBRARY_ROOT / "masters" / "stm32" / "ml_libs" / "ml_led.h").read_text(
        encoding="utf-8", errors="replace"
    )
    ml_led_c = (LIBRARY_ROOT / "masters" / "stm32" / "ml_libs" / "ml_led.c").read_text(
        encoding="utf-8", errors="replace"
    )
    channels = (LIBRARY_ROOT / "masters" / "stm32" / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "pin_config.h" in ml_led_h  # 引脚宏单源
    assert "LED_RED_PIN" in channels and "LED_YELLOW_PIN" in channels
    assert "LED_GREEN_PIN" in channels and "LED_PORT" in channels
    assert "高电平点亮" in ml_led_c  # 拉电流极性封装在实现内


def test_beep_module_dual_platform_with_uniform_api():
    """beep 模块双平台，API 统一：beep_init/on/off/toggle/beep_beep。"""
    beep = _manifest("beep")
    assert set(beep.platforms) == {"stm32", "mspm0"}
    for p, entry in beep.platforms.items():
        for rel in entry.files:
            assert (MODULES / "beep" / rel).is_file(), rel
    for h in ("code/beep_stm32.h", "code/beep.h"):
        text = _read("beep", h)
        for fn in ("beep_init", "beep_on", "beep_off", "beep_toggle", "beep_beep"):
            assert fn in text


def test_beep_stm32_uses_pin_config_buzzer_macros():
    """stm32 beep 用 pin_config.h 的 BUZZER 宏。"""
    beep_c = _read("beep", "code/beep_stm32.c")
    assert "pin_config.h" in beep_c
    assert "BUZZER_GPIO" in beep_c and "BUZZER_PIN" in beep_c


def test_led_beep_is_combo_depending_on_led_and_beep():
    """led_beep 保留为组合模块，依赖 led + beep，只做同时控制。"""
    led_beep = _manifest("led_beep")
    assert led_beep.dependencies == ("led", "beep", "delay")
    for p, entry in led_beep.platforms.items():
        for rel in entry.files:
            assert (MODULES / "led_beep" / rel).is_file(), rel
    combo_c = _read("led_beep", "code/led_beep.c")
    assert "led_on" in combo_c and "beep_on" in combo_c


def test_syscfg_led_beep_instance_consumed_by_led_module():
    """LED_BEEP syscfg 实例消费者 = led（组合模块不直接消费）。"""
    assert "led" in INSTANCES_BY_SLUG
    assert "LED_BEEP" in INSTANCES_BY_SLUG["led"]
    assert "led_beep" not in INSTANCES_BY_SLUG.get("led_beep", ())
