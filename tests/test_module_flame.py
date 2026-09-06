"""flame 红外火焰传感器模块：真实库 + 真实母版不变量与双平台单选生成。

与 mq135 / ir_beam 同款结构测试：manifest 形状（双平台文件齐、stm32 引脚
宏在母版 pin_config.h）、stm32 单选生成（依赖 adc 展开 + uvprojx 注册 +
静态门禁过）、mspm0 单选生成（syscfg 裁剪保留 ADC12_0 + flame + 依赖 adc
模块文件落盘）。百分比公式（页面原式**反向映射**（1 − value/4095）×100）与
「无 ADC 中断」源码守卫钉死（页面 ADC 中断改轮询——共享实例 IRQHandler
强符号唯一）。全程无 LLM、无服务。
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
    '#include "flame.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    flame_init();\n"
    "    float percent = flame_read_percent();\n"
    "    (void)percent;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "flame_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    flame_init();\n"
    "    (void)flame_read_percent();\n"
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


def test_flame_manifest_shape_both_platforms():
    """flame：双平台文件齐；stm32 单角色 FLAME_AO = adc PA5（macros =
    FLAME_AO_CH，依赖 adc 顶层已有）；mspm0 条目原样（MSPM0 MEM6 PA22）。"""
    manifest = ModuleManifest.load(MODULES / "flame")
    assert manifest.slug == "flame"
    assert manifest.dependencies == ("adc",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "flame_stm32.c",
        "flame_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "flame" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("FLAME_AO", "adc", "PA5", True, ("FLAME_AO_CH",))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/flame-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--flame-sensor.md",
        "delay_1ms",
        "SAMPLES 30",
        "反向映射",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["flame.c", "flame.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("FLAME_AO_CH6", "adc", "PA22", True, ())
    ]
    assert "反向映射" in mspm0.notes


def test_flame_stm32_macro_defined_in_pin_config():
    """stm32 接线单源：FLAME_AO_CH 必须在母版 pin_config.h（ADC_Channel_5）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+FLAME_AO_CH\s+ADC_Channel_5", text)


def test_flame_mspm0_master_syscfg_shared_facts():
    """母版 ADC12_0 八通道共享事实（endAdd 6→7（soil MEM7 开通道后）、
    adcMem6chansel=CHAN_7、adcPin7=PA22 归 flame——ir_distance/joystick/mq135
    相关断言同步）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'ADC12_0.endAdd                     = 7;' in syscfg
    assert 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_7";' in syscfg
    assert 'ADC12_0.peripheral.adcPin7.$assign = "PA22";' in syscfg


def test_flame_stm32_single_select_generation(tmp_path):
    """flame stm32 单选生成：依赖 adc 展开（adc 模块 stm32 条目 files=[] 内嵌
    母版）、静态门禁通过、模块文件落盘、uvprojx 注册 flame_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["flame"])
    assert {m.slug for m in resolved.manifests} == {"flame", "adc"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/flame/code/flame_stm32.c").is_file()
    assert (out / "modules/flame/code/flame_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("flame_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_flame_mspm0_single_select_generation(tmp_path):
    """flame mspm0 单选生成：syscfg 保留 ADC12_0（八通道 + flame 通道行）、
    flame + 依赖 adc 模块文件落盘、静态门禁过；无独立 GPIO 实例。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["flame"])
    assert {m.slug for m in resolved.manifests} == {"flame", "adc"}
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
    assert 'ADC12_0.endAdd                     = 7;' in syscfg
    assert 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_7";' in syscfg
    assert 'ADC12_0.peripheral.adcPin7.$assign = "PA22";' in syscfg
    assert "const FLAME = " not in syscfg  # 无独立 GPIO 实例（独立 ADC 通道）
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/flame/code/flame.c").is_file()
    assert (out / "modules/flame/code/flame.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_flame_percent_formula_guard():
    """百分比公式与轮询守卫（防回潮）：页面原式**反向映射**
    （1 − value/4095）×100（红外光越强 ADC 值越小、百分比越高）、
    ADC_Channel_6（MEM6 独立通道）、无 ADC 中断（共享实例 IRQHandler 强符号
    唯一——页面 IRQHandler 不可回潮）、adc 模块 API 通道守卫已扩展至 MEM6
    （adc_get 支持 flame）。"""
    source = (MODULES / "flame" / "code" / "flame.c").read_text(encoding="utf-8")
    header = (MODULES / "flame" / "code" / "flame.h").read_text(encoding="utf-8")
    assert "FLAME_ADC_MAX" in header
    assert "4095u" in header
    assert "* 100.0f" in source
    assert "1.0f - " in source  # 反向映射（火焰 = 页面原式，非 mq2/soil 正向）
    assert "/ (float)FLAME_ADC_MAX" in source
    assert "ADC_Channel_6" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source
    adc_source = (MODULES / "adc" / "code" / "adc_mspm0.c").read_text(
        encoding="utf-8"
    )
    assert "> ADC_Channel_7" in adc_source  # adc_get 守卫扩展至 MEM7


def test_flame_stm32_code_guards():
    """stm32 代码层守卫：注释里有页面缺陷清单（delay_1ms/SAMPLES 30/反向映射），
    剥离注释后零标准库/寄存器/演示残留/delay_1ms/IRQHandler；只吃母版
    ml_* API（adc_init/adc_get + FLAME_AO_CH 宏）。"""
    c = (MODULES / "flame" / "code" / "flame_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "flame" / "code" / "flame_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "delay_1ms" in c and "SAMPLES 30" in c  # 页面缺陷记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+FLAME_ADC_MAX\s+4095u", h)
    assert re.search(r"#define\s+FLAME_ADC_SAMPLES\s+5u", h)
    # 反向映射原式（页面 Get_FLAME_Percentage_value）
    assert "1.0f - " in code_only and "FLAME_ADC_MAX" in code_only
    # 只吃母版 ml_adc API + 引脚宏（无 ADC_Channel_5 字面量）
    assert "adc_init(ADC_1, FLAME_AO_CH)" in code_only
    assert "adc_get(ADC_1, FLAME_AO_CH)" in code_only
