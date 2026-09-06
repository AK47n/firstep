"""mq135 空气质量传感器模块：真实库 + 真实母版不变量与双平台单选生成。

与 ir_distance 同款结构测试：manifest 形状（双平台、依赖 adc、mspm0 单角色
MQ135_AO_CH4 = adc PB20——ADC12_0 sequence 八通道 MEM4 独立通道，与 mq2
的 MEM0 薄封装不同：多路气体同选时物理通道独立、无共读冲突；stm32 单角色
MQ135_AO = adc PA5——ADC 共享组共读（页面原脚即共读点））、mspm0 单选
生成（syscfg 裁剪保留 ADC12_0、mq135 + 依赖 adc 模块文件落盘、main.c 调
init/read_percent 过静态门禁）与 stm32 单选生成。百分比公式与「无 ADC
中断」源码守卫钉死（页面 ADC 中断改轮询——共享实例 IRQHandler 强符号唯一）。
全程无 LLM、无服务。
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
    '#include "mq135.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    mq135_init();\n"
    "    float percent = mq135_read_percent();\n"
    "    (void)percent;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_mq135_manifest_shape_mspm0():
    """mq135：仅 mspm0 平台条目；依赖 adc；单角色 = adc PB20（MEM4 独立
    通道——与 mq2 的 MEM0 薄封装不同：多路气体同选时物理通道独立）。"""
    manifest = ModuleManifest.load(MODULES / "mq135")
    assert manifest.slug == "mq135"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["mq135.c", "mq135.h"]
    for rel in mspm0.files:
        assert (MODULES / "mq135" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MQ135_AO_CH4", "adc", "PB20", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # MQ 系相对值非 ppm 精标说明 + 与 mq2 通道方案差异必须写入 notes
    assert "相对值" in mspm0.notes
    assert "ppm" in mspm0.notes
    assert "MEM0" in mspm0.notes


def test_mq135_mspm0_master_syscfg_shared_facts():
    """母版 ADC12_0 八通道共享事实（endAdd 6→7（soil MEM7 开通道后）、
    adcMem4chansel=CHAN_6、adcPin6=PB20 归 mq135——ir_distance/joystick/mq5
    相关断言同步）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'ADC12_0.endAdd                     = 7;' in syscfg
    assert 'ADC12_0.adcMem4chansel             = "DL_ADC12_INPUT_CHAN_6";' in syscfg
    assert 'ADC12_0.peripheral.adcPin6.$assign = "PB20";' in syscfg


def test_mq135_mspm0_single_select_generation(tmp_path):
    """mq135 mspm0 单选生成：syscfg 保留 ADC12_0（八通道 + mq135 通道行）、
    mq135 + 依赖 adc 模块文件落盘、静态门禁过；无独立 GPIO 实例。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["mq135"])
    assert {m.slug for m in resolved.manifests} == {"mq135", "adc"}
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
    assert 'ADC12_0.adcMem4chansel             = "DL_ADC12_INPUT_CHAN_6";' in syscfg
    assert 'ADC12_0.peripheral.adcPin6.$assign = "PB20";' in syscfg
    assert "const MQ135 = " not in syscfg  # 无独立 GPIO 实例（独立 ADC 通道）
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/mq135/code/mq135.c").is_file()
    assert (out / "modules/mq135/code/mq135.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_mq135_percent_formula_guard():
    """百分比公式与轮询守卫（防回潮）：value/4095×100（页面原式）、
    ADC_Channel_4（MEM4 独立通道）、无 ADC 中断（共享实例 IRQHandler 强符号
    唯一——页面 IRQHandler 不可回潮）、adc 模块 API 通道守卫已扩展至 MEM5
    （adc_get 支持 mq135/mq5 两件）。"""
    source = (MODULES / "mq135" / "code" / "mq135.c").read_text(encoding="utf-8")
    header = (MODULES / "mq135" / "code" / "mq135.h").read_text(encoding="utf-8")
    assert "MQ135_ADC_MAX" in header
    assert "4095u" in header
    assert "* 100.0f" in source
    assert "/ (float)MQ135_ADC_MAX" in source
    assert "ADC_Channel_4" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch5/02：stm32 平台条目（页面 ADC 序列收敛 ml_adc）
# ---------------------------------------------------------------------------

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "mq135_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    mq135_init();\n"
    "    (void)mq135_read_percent();\n"
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


def test_mq135_manifest_shape_stm32():
    """stm32 条目：单角色 MQ135_AO = adc PA5（macros = MQ135_AO_CH，ADC 共享组
    共读——与 flame/本批 8 件默认共读页面原脚 PA5）。"""
    manifest = ModuleManifest.load(MODULES / "mq135")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "mq135_stm32.c",
        "mq135_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "mq135" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("MQ135_AO", "adc", "PA5", True, ("MQ135_AO_CH",))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/mq-135-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--mq-135-sensor.md",
        "SAMPLES 30",
        "酒精值",
        "未上板",
        "外部分路器",
    ):
        assert needle in stm32.notes


def test_mq135_stm32_macro_defined_in_pin_config():
    """stm32 接线单源：MQ135_AO_CH 必须在母版 pin_config.h（ADC_Channel_5）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+MQ135_AO_CH\s+ADC_Channel_5", text)


def test_mq135_stm32_single_select_generation(tmp_path):
    """mq135 stm32 单选生成：依赖 adc 展开、静态门禁通过、模块文件落盘、
    uvprojx 注册 mq135_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["mq135"])
    assert {m.slug for m in resolved.manifests} == {"mq135", "adc"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/mq135/code/mq135_stm32.c").is_file()
    assert (out / "modules/mq135/code/mq135_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("mq135_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_mq135_stm32_code_guards():
    """stm32 代码层守卫：注释里有页面缺陷清单（SAMPLES 30/酒精值串台记录），
    剥离注释后零标准库/寄存器/演示残留/delay_1ms/IRQHandler；只吃母版
    ml_adc API（adc_init/adc_get + MQ135_AO_CH 宏）；源码零「酒精值」字面量
    （页面串台仅 notes 记录）。"""
    c = (MODULES / "mq135" / "code" / "mq135_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "mq135" / "code" / "mq135_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "SAMPLES 30" in c  # 页面缺陷记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"
    assert "酒精值" not in code_only  # 串台仅 notes 记录

    assert re.search(r"#define\s+MQ135_ADC_MAX\s+4095u", h)
    assert re.search(r"#define\s+MQ135_ADC_SAMPLES\s+5u", h)
    # 正向映射原式（页面 Get_MQ135_Percentage_value）
    assert "* 100.0f" in code_only and "/ (float)MQ135_ADC_MAX" in code_only
    assert "1.0f - " not in code_only
    # 只吃母版 ml_adc API + 引脚宏（无 ADC_Channel_5 字面量）
    assert "adc_init(ADC_1, MQ135_AO_CH)" in code_only
    assert "adc_get(ADC_1, MQ135_AO_CH)" in code_only
    adc_source = (MODULES / "adc" / "code" / "adc_mspm0.c").read_text(
        encoding="utf-8"
    )
    assert "> ADC_Channel_7" in adc_source  # adc_get 守卫扩展至 MEM7
