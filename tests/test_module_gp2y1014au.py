"""gp2y1014au 粉尘传感器模块：真实库 + 真实母版不变量与双平台单选生成。

与 mq2 同款结构测试：manifest 形状（双平台、依赖 adc+delay、mspm0 双角色——
GP2Y1014_AO_CH0 = adc PA24（与 adc/us016/mq2 共享 ADC12_0 MEM0 槽位薄封装，
无新 ADC 通道）+ GP2Y1014_LED = gpio_out PA1（**器件必需例外**——LED 驱动
脉冲）；stm32 双角色——GP2Y1014_AO = adc PA5（ADC 共享组共读，页面原脚即
共读点）+ GP2Y1014_LED = gpio_out **PB5**（页面原脚 PA2=DEBUG_UART TX 不
照抄））、mspm0 单选生成（syscfg 裁剪保留 ADC12_0 + 新 GPIO 实例 GP2Y1014、
gp2y1014au + 依赖 adc/delay 模块文件落盘、main.c 调 init/read_dust 过静态
门禁）与 stm32 单选生成。换算公式（0.17×value−0.1）、LED 脉冲时序常量
（280/40/9680us）、滑动平均窗口（10）与「无 ADC 中断」源码守卫钉死（页面
ADC 中断改轮询——共享实例 IRQHandler 强符号唯一）。全程无 LLM、无服务。
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
from contest_generator.platforms import (  # noqa: E402
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "gp2y1014au.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    gp2y1014_init();\n"
    "    float dust = gp2y1014_read_dust();\n"
    "    (void)dust;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_gp2y1014au_manifest_shape_mspm0():
    """gp2y1014au：仅 mspm0 平台条目；依赖 adc+delay；双角色 = adc PA24
    （MEM0 槽位）+ gpio_out PA1（LED 驱动——器件必需例外）。"""
    manifest = ModuleManifest.load(MODULES / "gp2y1014au")
    assert manifest.slug == "gp2y1014au"
    assert manifest.dependencies == ("adc", "delay")
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["gp2y1014au.c", "gp2y1014au.h"]
    for rel in mspm0.files:
        assert (MODULES / "gp2y1014au" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("GP2Y1014_AO_CH0", "adc", "PA24", True, ()),
        ("GP2Y1014_LED", "gpio_out", "PA1", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 非精标、LED 时序、滑动平均内嵌必须写入 notes
    assert "非精标" in mspm0.notes
    assert "LED" in mspm0.notes
    assert "滑动平均" in mspm0.notes


def test_gp2y1014au_mspm0_single_select_generation(tmp_path):
    """gp2y1014au mspm0 单选生成：syscfg 保留 ADC12_0（adc 消费实例）+ 新 GPIO
    输出实例 GP2Y1014（LED）、gp2y1014au + 依赖 adc/delay 模块文件落盘、静态
    门禁过；无其它 GPIO 实例。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["gp2y1014au"])
    assert {m.slug for m in resolved.manifests} == {"gp2y1014au", "adc", "delay"}
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
    assert "const ADC12_0 = ADC12.addInstance();" in syscfg
    assert 'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' in syscfg
    assert "const GP2Y1014 = GPIO.addInstance();" in syscfg
    assert 'GP2Y1014.associatedPins[0].pin.$assign      = "PA1";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "HUMAN_IR", "MICROWAVE",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/gp2y1014au/code/gp2y1014au.c").is_file()
    assert (out / "modules/gp2y1014au/code/gp2y1014au.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


def test_gp2y1014au_formula_and_timing_guard():
    """换算公式、LED 脉冲时序与轮询守卫（防回潮）：0.17×value−0.1（页面原式）、
    280/40/9680us 时序常量、10 点滑动平均窗口、delay_us 调用（依赖 delay）、
    ADC_Channel_0（MEM0 薄封装）、无 ADC 中断（共享实例 IRQHandler 强符号
    唯一——页面 IRQHandler 不可回潮）。"""
    source = (MODULES / "gp2y1014au" / "code" / "gp2y1014au.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "gp2y1014au" / "code" / "gp2y1014au.h").read_text(
        encoding="utf-8"
    )
    assert "0.17f * (float)value - 0.1f" in source
    assert "GP2Y1014_FILTER_WINDOW" in header
    assert "10u" in header
    assert "GP2Y1014_LED_SETTLE_US 280u" in header
    assert "GP2Y1014_LED_SAMPLE_TAIL_US 40u" in header
    assert "GP2Y1014_LED_CYCLE_TAIL_US 9680u" in header
    assert "delay_us(GP2Y1014_LED_SETTLE_US)" in source
    assert "delay_us(GP2Y1014_LED_SAMPLE_TAIL_US)" in source
    assert "delay_us(GP2Y1014_LED_CYCLE_TAIL_US)" in source
    assert "ADC_Channel_0" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch5/08：stm32 平台条目（页面 ADC 序列收敛 ml_adc + LED 时序）
# ---------------------------------------------------------------------------

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "gp2y1014au_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    gp2y1014_init();\n"
    "    (void)gp2y1014_read_dust();\n"
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
    (r"\bdelay_1ms\b", "delay_1ms（ml_delay 无此 API）"),
    (r"\bIRQHandler\b", "IRQHandler（页面 ADC 中断改轮询）"),
    (r"stdio\.h", "stdio 残余 include"),
    (r"\bGPIO_WriteBit\b", "GPIO_WriteBit（走母版 ml_gpio gpio_set）"),
]


def test_gp2y1014au_manifest_shape_stm32():
    """stm32 条目：双角色——GP2Y1014_AO = adc PA5（macros = GP2Y1014_AO_CH，
    ADC 共享组共读）+ GP2Y1014_LED = gpio_out **PB5**（macros 双宏——页面原脚
    PA2=DEBUG_UART TX 不照抄）；notes 记录 SAMPLES/周期矛盾修正与 LED 必需性。"""
    manifest = ModuleManifest.load(MODULES / "gp2y1014au")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "gp2y1014au_stm32.c",
        "gp2y1014au_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "gp2y1014au" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("GP2Y1014_AO", "adc", "PA5", True, ("GP2Y1014_AO_CH",)),
        ("GP2Y1014_LED", "gpio_out", "PB5", True,
         ("GP2Y1014_LED_GPIO", "GP2Y1014_LED_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/gp2y1014au-dust-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--gp2y1014au-dust-sensor.md",
        "SAMPLES 30",
        "10ms",
        "PB5",
        "未上板",
        "外部分路器",
    ):
        assert needle in stm32.notes


def test_gp2y1014au_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：GP2Y1014_AO_CH（ADC_Channel_5）+ LED 双宏
    （GPIO_B/Pin_5）必须在母版 pin_config.h。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+GP2Y1014_AO_CH\s+ADC_Channel_5", text)
    assert re.search(r"#define\s+GP2Y1014_LED_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+GP2Y1014_LED_PIN\s+Pin_5", text)


def test_gp2y1014au_stm32_single_select_generation(tmp_path):
    """gp2y1014au stm32 单选生成：依赖 adc+delay 展开（delay 模块 stm32 条目
    files=[] 内嵌母版）、静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["gp2y1014au"])
    assert {m.slug for m in resolved.manifests} == {"gp2y1014au", "adc", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/gp2y1014au/code/gp2y1014au_stm32.c").is_file()
    assert (out / "modules/gp2y1014au/code/gp2y1014au_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("gp2y1014au_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_gp2y1014au_stm32_code_guards():
    """stm32 代码层守卫：LED 脉冲时序常量（280u/40u/9680u）、5 次快平均
    （无 30 次）、0.17f 系数、Filter 收敛 static、LED 走母版 ml_gpio
    （gpio_init OUT_PP + gpio_set——零 GPIO_WriteBit）；剥离注释后零标准库/
    寄存器/演示残留/delay_1ms/IRQHandler；只吃母版 ml_adc API。"""
    c = (MODULES / "gp2y1014au" / "code" / "gp2y1014au_stm32.c").read_text(
        encoding="utf-8"
    )
    h = (MODULES / "gp2y1014au" / "code" / "gp2y1014au_stm32.h").read_text(
        encoding="utf-8"
    )
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+GP2Y1014_ADC_SAMPLES\s+5u", h)
    assert re.search(r"#define\s+GP2Y1014_FILTER_WINDOW\s+10u", h)
    assert re.search(r"#define\s+GP2Y1014_LED_SETTLE_US\s+280u", h)
    assert re.search(r"#define\s+GP2Y1014_LED_SAMPLE_TAIL_US\s+40u", h)
    assert re.search(r"#define\s+GP2Y1014_LED_CYCLE_TAIL_US\s+9680u", h)
    # 5 次快平均（无页面 30 次字面量残留）
    assert "GP2Y1014_ADC_SAMPLES" in code_only
    assert "> 30" not in code_only and "SAMPLES 30" not in code_only
    # LED 脉冲序列 + 0.17 系数（页面原式）
    assert "gpio_set(GP2Y1014_LED_GPIO, GP2Y1014_LED_PIN, 0)" in code_only
    assert "gpio_set(GP2Y1014_LED_GPIO, GP2Y1014_LED_PIN, 1)" in code_only
    assert "delay_us(GP2Y1014_LED_SETTLE_US)" in code_only
    assert "delay_us(GP2Y1014_LED_SAMPLE_TAIL_US)" in code_only
    assert "delay_us(GP2Y1014_LED_CYCLE_TAIL_US)" in code_only
    assert "0.17f * (float)value - 0.1f" in code_only
    # 只吃母版 ml_adc API + 引脚宏（无 ADC_Channel_5 字面量）
    assert "adc_init(ADC_1, GP2Y1014_AO_CH)" in code_only
    assert "adc_get(ADC_1, GP2Y1014_AO_CH)" in code_only
    assert "static int gp2y1014_filter" in code_only  # Filter 收敛 static
