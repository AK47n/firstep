"""us016 模拟量超声波模块：真实库 + 真实母版不变量与双平台单选生成。

与 mq2 同款结构测试：manifest 形状（双平台、依赖 adc、mspm0 单角色
US016_OUT_CH0 = adc PA24——与 adc 模块共享 ADC12_0 MEM0 槽位薄封装，
wiki-modules-batch2/02；stm32 单角色 US016_AO = adc PA5——**ADC 共享组共读**
（页面原脚即共读点，与 ir_distance 互替件同脚），wiki-stm32-batch7/01）、
mspm0 单选生成（syscfg 裁剪保留 ADC12_0、us016 + 依赖 adc 模块文件落盘、
main.c 调 init/读距离过静态门禁）与 stm32 单选生成（依赖 adc 展开 + uvprojx
注册）。换算与「无 ADC 中断」源码守卫钉死：US016_ADC_SAMPLES 5、
US016_RANGE_1M 双量程宏（0=3m 档 0.75 系数/1=1m 档 0.25 系数——0.25f/0.75f
双档在场）、出参 cm、无 0.769/3096 式。全程无 LLM、无服务。
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
    '#include "us016.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    us016_init();\n"
    "    float d = us016_read_distance_cm();\n"
    "    (void)d;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_us016_manifest_shape_mspm0():
    """us016：仅 mspm0 平台条目；依赖 adc；单角色 = adc PA24（MEM0 槽位）。"""
    manifest = ModuleManifest.load(MODULES / "us016")
    assert manifest.slug == "us016"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["us016.c", "us016.h"]
    for rel in mspm0.files:
        assert (MODULES / "us016" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("US016_OUT_CH0", "adc", "PA24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_us016_mspm0_single_select_generation(tmp_path):
    """us016 mspm0 单选生成：syscfg 保留 ADC12_0（adc 消费实例）、us016 + 依赖
    adc 模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["us016"])
    assert {m.slug for m in resolved.manifests} == {"us016", "adc"}
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
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/us016/code/us016.c").is_file()
    assert (out / "modules/us016/code/us016.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_us016_mspm0_untouched():
    """mspm0 零改动守卫（wiki-stm32-batch7/01）：mspm0 源不含 stm32 侧宏名与
    通道字面量（us016.c 走 MEM0 薄封装 ADC_Channel_0）。"""
    source = (MODULES / "us016" / "code" / "us016.c").read_text(encoding="utf-8")
    assert "ADC_Channel_0" in source
    assert "US016_AO_CH" not in source
    assert "ADC_Channel_5" not in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch7/01：stm32 平台条目（页面 ADC 序列收敛 ml_adc）
# ---------------------------------------------------------------------------

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "us016_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    us016_init();\n"
    "    (void)us016_read_distance_cm();\n"
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


def test_us016_manifest_shape_stm32():
    """stm32 条目：单角色 US016_AO = adc PA5（macros = US016_AO_CH，ADC 共享组
    共读——与 ir_distance 互替件同脚、与 flame/批 5/6 件共读页面原脚 PA5）。"""
    manifest = ModuleManifest.load(MODULES / "us016")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "us016_stm32.c",
        "us016_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "us016" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("US016_AO", "adc", "PA5", True, ("US016_AO_CH",))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/us-016-ultrasonic-ranging-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--us-016-ultrasonic-ranging-sensor.md",
        "3096",
        "500ms",
        "互替",
        "未上板",
        "外部分路器",
    ):
        assert needle in stm32.notes


def test_us016_stm32_macro_defined_in_pin_config():
    """stm32 接线单源：US016_AO_CH 必须在母版 pin_config.h（ADC_Channel_5）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+US016_AO_CH\s+ADC_Channel_5", text)


def test_us016_stm32_single_select_generation(tmp_path):
    """us016 stm32 单选生成：依赖 adc 展开（adc 模块 stm32 条目 files=[] 内嵌
    母版）、静态门禁通过、模块文件落盘、uvprojx 注册 us016_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["us016"])
    assert {m.slug for m in resolved.manifests} == {"us016", "adc"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/us016/code/us016_stm32.c").is_file()
    assert (out / "modules/us016/code/us016_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("us016_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_us016_stm32_code_guards():
    """stm32 代码层守卫：注释里有页面缺陷清单（3096/3072、500ms 记录），剥离
    注释后零标准库/寄存器/演示残留；只吃母版 ml_adc API（adc_init/adc_get +
    US016_AO_CH 宏）；换算 = 双量程宏 0.25f/0.75f 系数 + Vref/Vcc 修正 + mm/10
    出 cm。"""
    c = (MODULES / "us016" / "code" / "us016_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "us016" / "code" / "us016_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "3096" in c  # 页面缺陷记录（注释）
    assert "出参 cm" in c  # 出参 cm 注释（页面 main /10 归入 API）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+US016_ADC_SAMPLES\s+5\b", h)
    assert re.search(r"#define\s+US016_RANGE_1M\s+0\b", h)
    assert re.search(r"#define\s+US016_VREF_V\s+3\.3f", h)
    assert re.search(r"#define\s+US016_VCC_V\s+3\.3f", h)
    # 双量程系数（页面正文 3096 vs 代码 3072——按代码 0.75；1m 档 0.25 双档在场）
    assert "0.25f" in code_only and "0.75f" in code_only
    # 无 0.769 式（3072/4096 = 0.75 而非 0.769）与 3096 字面量
    assert "0.769" not in code_only
    assert "3096" not in code_only
    # 只吃母版 ml_adc API + 引脚宏（无 ADC_Channel_5 字面量）
    assert "adc_init(ADC_1, US016_AO_CH)" in code_only
    assert "adc_get(ADC_1, US016_AO_CH)" in code_only
