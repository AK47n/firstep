"""ir_distance 红外测距模块：真实库 + 真实母版不变量与双平台单选生成。

与 us016/mq2 同款结构测试：manifest 形状（双平台、依赖 adc、mspm0 单角色
IR_DIST_OUT_CH3 = adc PA27——ADC12_0 sequence 八通道 MEM3）、母版 syscfg
共享事实（endAdd=7 / adcMem3chansel=CHAN_0 / adcPin0=PA27，与 adc/joystick/
us016/mq135/mq5/flame/soil 同实例）、mspm0 单选生成（syscfg 裁剪保留 ADC12_0、
模块文件落盘、main.c 调 init/读距离过静态门禁）与 stm32 单选生成（依赖 adc
展开 + uvprojx 注册，wiki-stm32-batch7/02）。换算与「无 ADC 中断」源码守卫
钉死：3.3f（无 3.5f）、60.374f、-1.16f、IR_DIST_ADC_SAMPLES 10（宏名无
ANCE、值 10）、无查表数组、全 0 防护。全程无 LLM、无服务。
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
    '#include "ir_distance.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ir_distance_init();\n"
    "    float d = ir_distance_read_distance_cm();\n"
    "    (void)d;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ir_distance_manifest_shape_mspm0():
    """ir_distance：仅 mspm0 平台条目；依赖 adc（经其 API 读 MEM3——数据所有权
    归 adc 模块）；单角色 = adc PA27（MEM3 槽位）。"""
    manifest = ModuleManifest.load(MODULES / "ir_distance")
    assert manifest.slug == "ir_distance"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ir_distance.c", "ir_distance.h"]
    for rel in mspm0.files:
        assert (MODULES / "ir_distance" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("IR_DIST_OUT_CH3", "adc", "PA27", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_ir_distance_mspm0_master_syscfg_shared_facts():
    """母版 ADC12_0 八通道共享事实（JOYSTICK 相关断言同步：endAdd 6→7（soil
    MEM7 开通道后、槽位 8/8 用满）、adcMem3=CHAN_0、adcPin0=PA27 归
    ir_distance——手册原脚；MEM4=PB20/A0_6 归 mq135、MEM5=PB24/A0_5 归 mq5
    ——wiki-modules-batch7；MEM6=PA22/A0_7 归 flame、MEM7=PA14/A0_12 归 soil
    ——wiki-modules-batch8）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'ADC12_0.samplingOperationMode      = "sequence";' in syscfg
    assert 'ADC12_0.startAdd                   = 0;' in syscfg
    assert 'ADC12_0.endAdd                     = 7;' in syscfg
    assert 'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' in syscfg
    assert 'ADC12_0.adcMem1chansel             = "DL_ADC12_INPUT_CHAN_1";' in syscfg
    assert 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' in syscfg
    assert 'ADC12_0.adcMem3chansel             = "DL_ADC12_INPUT_CHAN_0";' in syscfg
    assert 'ADC12_0.adcMem4chansel             = "DL_ADC12_INPUT_CHAN_6";' in syscfg
    assert 'ADC12_0.adcMem5chansel             = "DL_ADC12_INPUT_CHAN_5";' in syscfg
    assert 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_7";' in syscfg
    assert 'ADC12_0.adcMem7chansel             = "DL_ADC12_INPUT_CHAN_12";' in syscfg
    assert 'ADC12_0.peripheral.adcPin3.$assign = "PA24";' in syscfg
    assert 'ADC12_0.peripheral.adcPin1.$assign  = "PA26";' in syscfg
    assert 'ADC12_0.peripheral.adcPin2.$assign  = "PA25";' in syscfg
    assert 'ADC12_0.peripheral.adcPin0.$assign = "PA27";' in syscfg
    assert 'ADC12_0.peripheral.adcPin6.$assign = "PB20";' in syscfg
    assert 'ADC12_0.peripheral.adcPin5.$assign = "PB24";' in syscfg
    assert 'ADC12_0.peripheral.adcPin7.$assign = "PA22";' in syscfg
    assert 'ADC12_0.peripheral.adcPin12.$assign = "PA14";' in syscfg


def test_ir_distance_mspm0_single_select_generation(tmp_path):
    """ir_distance mspm0 单选生成：syscfg 保留 ADC12_0、ir_distance + 依赖 adc
    模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ir_distance"])
    assert {m.slug for m in resolved.manifests} == {"ir_distance", "adc"}
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
    assert 'ADC12_0.peripheral.adcPin0.$assign = "PA27";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "BH1750",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ir_distance/code/ir_distance.c").is_file()
    assert (out / "modules/ir_distance/code/ir_distance.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_ir_distance_mspm0_untouched():
    """mspm0 零改动守卫（wiki-stm32-batch7/02）：mspm0 源不含 stm32 侧宏名与
    共读通道字面量（ir_distance.c 走独立 MEM3 ADC_Channel_3）。"""
    source = (MODULES / "ir_distance" / "code" / "ir_distance.c").read_text(
        encoding="utf-8"
    )
    assert "ADC_Channel_3" in source
    assert "IR_DISTANCE_AO_CH" not in source
    assert "ADC_Channel_5" not in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch7/02：stm32 平台条目（页面 ADC 序列收敛 ml_adc + 3.3V 宏化）
# ---------------------------------------------------------------------------

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ir_distance_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ir_distance_init();\n"
    "    (void)ir_distance_read_distance_cm();\n"
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


def test_ir_distance_manifest_shape_stm32():
    """stm32 条目：单角色 IR_DISTANCE_AO = adc PA5（macros = IR_DISTANCE_AO_CH，
    ADC 共享组共读——与 us016 互替件同脚、与 flame/批 5/6 件共读页面原脚）。"""
    manifest = ModuleManifest.load(MODULES / "ir_distance")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ir_distance_stm32.c",
        "ir_distance_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ir_distance" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("IR_DISTANCE_AO", "adc", "PA5", True, ("IR_DISTANCE_AO_CH",))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/Infrared-distance-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--Infrared-distance-sensor.md",
        "3.5",
        "非线性",
        "互替",
        "未上板",
        "外部分路器",
    ):
        assert needle in stm32.notes


def test_ir_distance_stm32_macro_defined_in_pin_config():
    """stm32 接线单源：IR_DISTANCE_AO_CH 必须在母版 pin_config.h（ADC_Channel_5）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+IR_DISTANCE_AO_CH\s+ADC_Channel_5", text)


def test_ir_distance_stm32_single_select_generation(tmp_path):
    """ir_distance stm32 单选生成：依赖 adc 展开（adc 模块 stm32 条目 files=[]
    内嵌母版）、静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ir_distance"])
    assert {m.slug for m in resolved.manifests} == {"ir_distance", "adc"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ir_distance/code/ir_distance_stm32.c").is_file()
    assert (out / "modules/ir_distance/code/ir_distance_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ir_distance_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ir_distance_stm32_code_guards():
    """stm32 代码层守卫：注释里有页面缺陷清单（3.5V 宏化/0 图无查表/非线性区
    记录），剥离注释后零标准库/寄存器/演示残留；换算 = 3.3f（无 3.5f）+
    60.374f×V^(-1.16f) + IR_DIST_ADC_SAMPLES 10 + 全 0 防护。"""
    c = (MODULES / "ir_distance" / "code" / "ir_distance_stm32.c").read_text(
        encoding="utf-8"
    )
    h = (MODULES / "ir_distance" / "code" / "ir_distance_stm32.h").read_text(
        encoding="utf-8"
    )
    full = c + "\n" + h

    assert "3.5" in c  # 页面缺陷记录（注释：页面硬编码 3.5V）
    assert "非线性" in h  # 页面缺陷记录（注释：<15cm 电压跌落）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+IR_DIST_ADC_SAMPLES\s+10\b", h)
    assert re.search(r"#define\s+IR_DIST_ADC_MAX\s+4095\b", h)
    assert re.search(r"#define\s+IR_DIST_VREF_V\s+3\.3f\b", h)
    # 3.5V 常量不落码（宏化 3.3——页面 3.5 只存注释）
    assert "3.5" not in code_only
    assert "3.5f" not in code_only
    # 官方公式 + 防回写
    assert "60.374f" in code_only
    assert "-1.16f" in code_only
    assert "powf(volts, -1.16f)" in code_only
    # 无查表数组（页面 L44「下图曲线图」实为 0 图）
    assert not re.search(r"\[[0-9]+\]", code_only)
    # 全 0 防护（防 pow(0,-1.16) 溢出）
    assert "sum == 0" in code_only and "0.0f" in code_only
    # 只吃母版 ml_adc API + 引脚宏（无 ADC_Channel_5 字面量）
    assert "adc_init(ADC_1, IR_DISTANCE_AO_CH)" in code_only
    assert "adc_get(ADC_1, IR_DISTANCE_AO_CH)" in code_only
