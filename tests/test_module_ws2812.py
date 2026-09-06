"""ws2812 幻彩灯模块：真实库 + 真实母版不变量与双平台单选生成。

与 ir_beam / zigbee_link 同款结构测试：manifest 形状（双平台文件齐、stm32
引脚宏在母版 pin_config.h）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、
mspm0 单选生成（syscfg 裁剪保留 WS2812 实例 + 模块文件落盘）。页面缺陷
清单守卫（反写循环 ×4 防回潮 / LedId 越界 >= / 12MHz 时序弃用按 72MHz 重写 /
.h 声明无定义不落码——setLedCount/RGB_LED_Write1 残留守卫）。全程无 LLM、
无服务：main.c 手写，直驱 generate()。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "ws2812.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ws2812_init();\n"
    "    ws2812_set_color(0, WS2812_RED);\n"
    "    ws2812_refresh();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ws2812_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ws2812_init();\n"
    "    ws2812_set_led_count(8);\n"
    "    ws2812_set_color(0, WS2812_RED);\n"
    "    ws2812_refresh();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bTIM[234]\b", "TIMx（不占定时器）"),
    (r"\bPWM\b", "PWM（不占 PWM 外设）"),
    (r"\bIRQHandler\b", "IRQHandler（不注册中断）"),
    (r"\bsetLedCount\b|\bgetLedCount\b|\bRGB_LED_Write1\b", "页面声明无定义残留"),
    # 页面反写延时循环（条件 i < 0 恒假——0 次迭代脉宽全丢）防回潮
    (r"for\s*\(\s*\w+\s*=\s*0\s*;\s*\w+\s*<\s*0\s*;", "页面反写延时循环"),
    # 页面越界比较（LedId > ledsCount —— off-by-one）防回潮
    (r"LedId\s*>\s*", "页面越界比较"),
]


def test_ws2812_manifest_shape_both_platforms():
    """ws2812：双平台文件齐；stm32 单角色 WS2812_DIN = gpio_out PA8（macros =
    WS2812_GPIO/WS2812_PIN，依赖 delay 顶层已有）；mspm0 条目原样（IN PA14）。"""
    manifest = ModuleManifest.load(MODULES / "ws2812")
    assert manifest.slug == "ws2812"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ws2812_stm32.c",
        "ws2812_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ws2812" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("WS2812_DIN", "gpio_out", "PA8", True, ("WS2812_GPIO", "WS2812_PIN"))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/control/ws2812-color-rgb-led.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/control--ws2812-color-rgb-led.md",
        "for(k = 0; i < 0; i++);",
        "LedId > ledsCount",
        "12MHz",
        "setLedCount",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ws2812.c", "ws2812.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("WS2812_IN", "gpio_out", "PA14", True, ())
    ]
    assert mspm0.kit and mspm0.source_url


def test_ws2812_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：WS2812_GPIO / WS2812_PIN 必须在母版 pin_config.h。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+WS2812_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+WS2812_PIN\s+Pin_8", text)


def test_ws2812_mspm0_syscfg_instance():
    """mspm0 母版必须有 WS2812 输出实例（IN = PA14），方向 OUTPUT。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const WS2812 = GPIO.addInstance();" in syscfg
    assert 'WS2812.associatedPins[0].$name        = "IN";' in syscfg
    assert 'WS2812.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'WS2812.associatedPins[0].pin.$assign  = "PA14";' in syscfg


def test_ws2812_stm32_single_select_generation(tmp_path):
    """ws2812 stm32 单选生成：静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ws2812"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ws2812/code/ws2812_stm32.c").is_file()
    assert (out / "modules/ws2812/code/ws2812_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ws2812_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ws2812_mspm0_single_select_generation(tmp_path):
    """ws2812 mspm0 单选生成：syscfg 只留 WS2812、模块文件落盘、main.c 调用
    过静态门禁（ws2812_init/set_color/refresh 与头文件声明一致）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ws2812"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_MSPM0,
    )
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const WS2812 = GPIO.addInstance();" in syscfg
    assert 'WS2812.associatedPins[0].pin.$assign  = "PA14";' in syscfg
    for drop in ("KEY", "HUIDU", "DIGIT_UART", "LED_BEEP", "STEP_MOTOR", "IR_BEAM"):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ws2812/code/ws2812.c").is_file()
    assert (out / "modules/ws2812/code/ws2812.h").is_file()


def test_ws2812_stm32_code_guards():
    """stm32 代码层守卫（页面缺陷 4 条防回潮 + 换算残留）：
    注释里有页面缺陷记录（for(k=0;i<0;i++);/LedId > ledsCount/12MHz/
    setLedCount），剥离注释后零标准库/寄存器/演示残留、零页面反写循环/
    越界比较/无定义声明残留；只吃母版 ml_* API（gpio_init OUT_PP /
    gpio_set / delay_us）+ 忙等 NOP 宏。"""
    c = (MODULES / "ws2812" / "code" / "ws2812_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ws2812" / "code" / "ws2812_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    for needle in ("for(k = 0; i < 0; i++);", "LedId > ledsCount", "12MHz"):
        assert needle in full  # 页面缺陷记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+WS2812_MAX\s+8", h)
    assert re.search(r"#define\s+WS2812_RED\s+0xFF0000u", h)
    # GRB 缓冲序（页面「将绿和红色进行颠倒」在 set_color 换位）
    assert "G" in code_only and "0x80 >> i" in code_only
    # 时序：delay_us 出现 + 忙等 0.25us（18×NOP——12MHz 标注弃用按 72MHz 重写）
    assert "delay_us(1)" in code_only and "delay_us(285)" in code_only
    assert "WS2812_DELAY_QUARTER_US()" in code_only
    assert "gpio_init(WS2812_GPIO, WS2812_PIN, OUT_PP)" in code_only
    assert "gpio_set(WS2812_GPIO, WS2812_PIN" in code_only
    # API 对齐语义：越界 >= + 越界忽略
    assert "led_id >= s_count" in code_only
