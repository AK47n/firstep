"""rain 雨滴传感器模块：真实库 + 真实母版不变量与双平台单选生成。

与 mq2 同款结构测试：manifest 形状（双平台、依赖 adc、mspm0 单角色
RAIN_AO_CH0 = adc PA24——与 adc/us016/mq2 共享 ADC12_0 MEM0 槽位薄封装，
无新 ADC 通道；stm32 单角色 RAIN_AO = adc PA5——ADC 共享组共读（页面原脚
即共读点））、mspm0 单选生成（syscfg 裁剪保留 ADC12_0、rain + 依赖 adc
模块文件落盘、main.c 调 init/read_percent 过静态门禁）与 stm32 单选生成。
百分比公式（**正向映射**——雨越大百分比越高；页面逆式（1−value/4095）×100
与正文矛盾已修正，守卫防回潮——**「1.0f - 」不得出现**，与 photoresistance
的必须出现对仗）与「无 ADC 中断」源码守卫钉死（页面 ADC 中断改轮询——共享
实例 IRQHandler 强符号唯一）。全程无 LLM、无服务。
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
    '#include "rain.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    rain_init();\n"
    "    float percent = rain_read_percent();\n"
    "    (void)percent;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_rain_manifest_shape_mspm0():
    """rain：仅 mspm0 平台条目；依赖 adc；单角色 = adc PA24（MEM0 槽位）。"""
    manifest = ModuleManifest.load(MODULES / "rain")
    assert manifest.slug == "rain"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["rain.c", "rain.h"]
    for rel in mspm0.files:
        assert (MODULES / "rain" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("RAIN_AO_CH0", "adc", "PA24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 正向映射修正、非线性/干净度与毫米级实体测量限制必须写入 notes
    assert "正向映射" in mspm0.notes
    assert "实体测量" in mspm0.notes
    assert "非线性" in mspm0.notes


def test_rain_mspm0_single_select_generation(tmp_path):
    """rain mspm0 单选生成：syscfg 保留 ADC12_0（adc 消费实例）、rain + 依赖
    adc 模块文件落盘、静态门禁过；无独立 GPIO 实例（薄封装）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["rain"])
    assert {m.slug for m in resolved.manifests} == {"rain", "adc"}
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
    assert "const RAIN = " not in syscfg  # 薄封装：无独立 GPIO 实例
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/rain/code/rain.c").is_file()
    assert (out / "modules/rain/code/rain.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_rain_percent_formula_guard():
    """百分比公式与轮询守卫（防回潮）：value/4095×100（**正向映射**——雨越大
    百分比越高，页面正文「雨水越大→ADC 值越大」取证；页面逆式
    (1−value/4095)×100 与正文矛盾已修正——`1.0f - ` 不得出现在换算中）、
    ADC_Channel_0（MEM0 薄封装）、无 ADC 中断（共享实例 IRQHandler 强符号
    唯一——页面 IRQHandler 不可回潮）。"""
    source = (MODULES / "rain" / "code" / "rain.c").read_text(encoding="utf-8")
    header = (MODULES / "rain" / "code" / "rain.h").read_text(encoding="utf-8")
    assert "RAIN_ADC_MAX" in header
    assert "4095u" in header
    assert "* 100.0f" in source
    assert "/ (float)RAIN_ADC_MAX" in source
    assert "1.0f - " not in source  # 正向映射（页面逆式已修正——防回潮）
    assert "ADC_Channel_0" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch5/05：stm32 平台条目（页面 ADC 序列收敛 ml_adc + 方向修正）
# ---------------------------------------------------------------------------

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "rain_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    rain_init();\n"
    "    (void)rain_read_percent();\n"
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
]


def test_rain_manifest_shape_stm32():
    """stm32 条目：单角色 RAIN_AO = adc PA5（macros = RAIN_AO_CH，ADC 共享组
    共读——与 flame/本批 8 件默认共读页面原脚 PA5）——**方向修正核心件**：
    notes 必须记录正文取证修正与防回潮说明。"""
    manifest = ModuleManifest.load(MODULES / "rain")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "rain_stm32.c",
        "rain_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "rain" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("RAIN_AO", "adc", "PA5", True, ("RAIN_AO_CH",))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/rain-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--rain-sensor.md",
        "方向修正",
        "正向映射",
        "1.0f - ",
        "GPIOC",
        "未上板",
        "外部分路器",
    ):
        assert needle in stm32.notes


def test_rain_stm32_macro_defined_in_pin_config():
    """stm32 接线单源：RAIN_AO_CH 必须在母版 pin_config.h（ADC_Channel_5）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+RAIN_AO_CH\s+ADC_Channel_5", text)


def test_rain_stm32_single_select_generation(tmp_path):
    """rain stm32 单选生成：依赖 adc 展开、静态门禁通过、模块文件落盘、
    uvprojx 注册 rain_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["rain"])
    assert {m.slug for m in resolved.manifests} == {"rain", "adc"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/rain/code/rain_stm32.c").is_file()
    assert (out / "modules/rain/code/rain_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("rain_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_rain_stm32_code_guards():
    """stm32 代码层守卫：**正向映射防回潮**——percent 公式不得出现 `1.0f - `
    （与 photoresistance 的必须出现对仗）；注释里记录方向修正确据与页面缺陷
    （delay_1ms/SAMPLES/GPIOC 串台）；剥离注释后零标准库/寄存器/演示残留/
    delay_1ms/IRQHandler；只吃母版 ml_adc API（adc_init/adc_get + RAIN_AO_CH
    宏）。"""
    c = (MODULES / "rain" / "code" / "rain_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "rain" / "code" / "rain_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "delay_1ms" in c  # 页面缺陷记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+RAIN_ADC_MAX\s+4095u", h)
    assert re.search(r"#define\s+RAIN_ADC_SAMPLES\s+5u", h)
    # 正向映射原式（正文取证修正——页面反向式不得回潮）
    assert "* 100.0f" in code_only and "/ (float)RAIN_ADC_MAX" in code_only
    assert "1.0f - " not in code_only
    # 只吃母版 ml_adc API + 引脚宏（无 ADC_Channel_5 字面量）
    assert "adc_init(ADC_1, RAIN_AO_CH)" in code_only
    assert "adc_get(ADC_1, RAIN_AO_CH)" in code_only
