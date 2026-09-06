"""s12sd 紫外线传感器模块：真实库 + 真实母版不变量与双平台单选生成。

与 mq2 同款结构测试：manifest 形状（双平台、依赖 adc、mspm0 单角色
S12SD_AO_CH0 = adc PA24——与 adc/us016/mq2 共享 ADC12_0 MEM0 槽位薄封装，
无新 ADC 通道；stm32 单角色 S12SD_AO = adc PA5——ADC 共享组共读（页面原脚
即共读点））、mspm0 单选生成（syscfg 裁剪保留 ADC12_0、s12sd + 依赖 adc
模块文件落盘、main.c 调 init/read_uv_index 过静态门禁）与 stm32 单选生成。
UV 指数阈值表（页面 Get_Ultraviolet_Intensity 原式：0-11 级 12 档——非百分
比）与「无 ADC 中断」源码守卫钉死（页面 ADC 中断改轮询——共享实例
IRQHandler 强符号唯一）。全程无 LLM、无服务。
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
    '#include "s12sd.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    s12sd_init();\n"
    "    uint8_t idx = s12sd_read_uv_index();\n"
    "    (void)idx;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_s12sd_manifest_shape_mspm0():
    """s12sd：仅 mspm0 平台条目；依赖 adc；单角色 = adc PA24（MEM0 槽位）。"""
    manifest = ModuleManifest.load(MODULES / "s12sd")
    assert manifest.slug == "s12sd"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["s12sd.c", "s12sd.h"]
    for rel in mspm0.files:
        assert (MODULES / "s12sd" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("S12SD_AO_CH0", "adc", "PA24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # UV-A 波段/量程与档位标定限制必须写入 notes
    assert "240-370nm" in mspm0.notes
    assert "UV-A" in mspm0.notes
    assert "11" in mspm0.notes


def test_s12sd_mspm0_single_select_generation(tmp_path):
    """s12sd mspm0 单选生成：syscfg 保留 ADC12_0（adc 消费实例）、s12sd + 依赖
    adc 模块文件落盘、静态门禁过；无独立 GPIO 实例（薄封装）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["s12sd"])
    assert {m.slug for m in resolved.manifests} == {"s12sd", "adc"}
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
    assert "const S12SD = " not in syscfg  # 薄封装：无独立 GPIO 实例
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/s12sd/code/s12sd.c").is_file()
    assert (out / "modules/s12sd/code/s12sd.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_s12sd_uv_index_threshold_guard():
    """UV 指数阈值表与轮询守卫（防回潮）：页面 Get_Ultraviolet_Intensity
    原式 12 档（0-11 级——抽查首/中/末档阈值常量）、ADC_Channel_0（MEM0
    薄封装）、无 ADC 中断（共享实例 IRQHandler 强符号唯一——页面 IRQHandler
    不可回潮）。"""
    source = (MODULES / "s12sd" / "code" / "s12sd.c").read_text(encoding="utf-8")
    header = (MODULES / "s12sd" / "code" / "s12sd.h").read_text(encoding="utf-8")
    assert "S12SD_ADC_SAMPLES" in header
    for threshold in ("227u", "318u", "795u", "1079u", "1170u"):
        assert threshold in source, threshold
    assert "ADC_Channel_0" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch5/06：stm32 平台条目（页面 ADC 序列收敛 ml_adc + 档位表）
# ---------------------------------------------------------------------------

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "s12sd_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    s12sd_init();\n"
    "    (void)s12sd_read_uv_index();\n"
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
    (r"IRtracking", "IRtracking 串台字面量（仅 notes 记录）"),
]


def test_s12sd_manifest_shape_stm32():
    """stm32 条目：单角色 S12SD_AO = adc PA5（macros = S12SD_AO_CH，ADC 共享组
    共读——与 flame/本批 8 件默认共读页面原脚 PA5）；notes 记录档位表与
    IRtracking 串台。"""
    manifest = ModuleManifest.load(MODULES / "s12sd")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "s12sd_stm32.c",
        "s12sd_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "s12sd" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("S12SD_AO", "adc", "PA5", True, ("S12SD_AO_CH",))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/s12sd-uv-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--s12sd-uv-sensor.md",
        "档位表",
        "IRtracking",
        "未上板",
        "外部分路器",
    ):
        assert needle in stm32.notes


def test_s12sd_stm32_macro_defined_in_pin_config():
    """stm32 接线单源：S12SD_AO_CH 必须在母版 pin_config.h（ADC_Channel_5）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+S12SD_AO_CH\s+ADC_Channel_5", text)


def test_s12sd_stm32_single_select_generation(tmp_path):
    """s12sd stm32 单选生成：依赖 adc 展开、静态门禁通过、模块文件落盘、
    uvprojx 注册 s12sd_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["s12sd"])
    assert {m.slug for m in resolved.manifests} == {"s12sd", "adc"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/s12sd/code/s12sd_stm32.c").is_file()
    assert (out / "modules/s12sd/code/s12sd_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("s12sd_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_s12sd_stm32_code_guards():
    """stm32 代码层守卫：档位表上界常量逐档（227…1170——页面阈值表原式，
    非百分比）+ 5 次快平均；剥离注释后零标准库/寄存器/演示残留/IRtracking
    字面量（串台仅 notes 记录）；只吃母版 ml_adc API。"""
    c = (MODULES / "s12sd" / "code" / "s12sd_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "s12sd" / "code" / "s12sd_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+S12SD_ADC_SAMPLES\s+5u", h)
    for boundary in ("227u", "318u", "408u", "503u", "606u", "696u",
                     "795u", "881u", "976u", "1079u", "1170u"):
        assert boundary in code_only, f"档位表缺上界 {boundary}"
    # 档位表为 if 链（非百分比公式——无 * 100.0f 字面量）
    assert "* 100.0f" not in code_only
    # 只吃母版 ml_adc API + 引脚宏（无 ADC_Channel_5 字面量）
    assert "adc_init(ADC_1, S12SD_AO_CH)" in code_only
    assert "adc_get(ADC_1, S12SD_AO_CH)" in code_only
