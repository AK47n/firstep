"""microwave_radar 微波多普勒雷达模块：真实库 + 真实母版不变量与双平台单选生成。

与 human_ir / ir_beam 同款结构测试：manifest 形状（双平台文件齐、stm32 引脚
宏在母版 pin_config.h）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、
mspm0 单选生成（syscfg 裁剪保留 MICROWAVE + 模块文件落盘）。极性（按页面
自一致：检测到=输出低——页面注释 + main 演示同口径）以 MICROWAVE_TRIGGER_LEVEL
单点反相宏守卫钉死；页面演示开/关门时序归生成骨架（ADR 0009）以「无演示
时序」守卫。全程无 LLM、无服务。
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
    '#include "microwave_radar.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    microwave_radar_init();\n"
    "    uint8_t detected = microwave_radar_read();\n"
    "    (void)detected;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "microwave_radar_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    microwave_radar_init();\n"
    "    (void)microwave_radar_read();\n"
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
    (r"\bEXTI_|NVIC|IRQHandler", "中断相关调用（本件轮询）"),
]

# 额外断言：页面演示时序（flag/time 开门关门）不得落码
DEMO_TOKENS = ("flag", "close", "open")


def test_microwave_radar_manifest_shape_both_platforms():
    """microwave_radar：双平台文件齐；stm32 单角色 gpio_in PA4（macros =
    MICROWAVE_GPIO/MICROWAVE_PIN）；mspm0 条目原样（syscfg gpio_in PA31）。"""
    manifest = ModuleManifest.load(MODULES / "microwave_radar")
    assert manifest.slug == "microwave_radar"
    assert manifest.dependencies == ()

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "microwave_radar_stm32.c",
        "microwave_radar_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "microwave_radar" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (
            "MICROWAVE_OUT",
            "gpio_in",
            "PA4",
            True,
            ("MICROWAVE_GPIO", "MICROWAVE_PIN"),
        )
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/microwave-doppler-radar-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--microwave-doppler-radar-sensor.md",
        "MICROWAVE_ 前缀",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == [
        "microwave_radar.c",
        "microwave_radar.h",
    ]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MICROWAVE_OUT", "gpio_in", "PA31", True, ())
    ]
    assert "归生成骨架" in mspm0.notes


def test_microwave_radar_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：MICROWAVE_GPIO / MICROWAVE_PIN 必须在母版 pin_config.h。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+MICROWAVE_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+MICROWAVE_PIN\s+Pin_4", text)


def test_microwave_radar_mspm0_syscfg_instances():
    """mspm0 母版：MICROWAVE GPIO 实例（OUT 输入，内部上拉，默认 PA31）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const MICROWAVE = GPIO.addInstance();" in syscfg
    assert 'MICROWAVE.associatedPins[0].$name            = "OUT";' in syscfg
    assert 'MICROWAVE.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'MICROWAVE.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'MICROWAVE.associatedPins[0].pin.$assign      = "PA31";' in syscfg


def test_microwave_radar_stm32_single_select_generation(tmp_path):
    """microwave_radar stm32 单选生成：静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["microwave_radar"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/microwave_radar/code/microwave_radar_stm32.c").is_file()
    assert (out / "modules/microwave_radar/code/microwave_radar_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("microwave_radar_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_microwave_radar_mspm0_single_select_generation(tmp_path):
    """microwave_radar mspm0 单选生成：syscfg 只留 MICROWAVE、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["microwave_radar"])
    assert {m.slug for m in resolved.manifests} == {"microwave_radar"}
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
    assert "const MICROWAVE = GPIO.addInstance();" in syscfg
    assert 'MICROWAVE.associatedPins[0].pin.$assign      = "PA31";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "IR_REMOTE", "NRF24L01", "HUMAN_IR",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/microwave_radar/code/microwave_radar.c").is_file()
    assert (out / "modules/microwave_radar/code/microwave_radar.h").is_file()


def test_microwave_radar_polarity_and_no_demo_guards():
    """页面极性（检测到=输出低）与单点反相宏守卫（防回潮）：
    MICROWAVE_TRIGGER_LEVEL 默认 0u（页面注释+演示自一致——低=检测到）、read
    返回 level == 宏（1=检测到移动）、页面演示时序不落码（开/关门 flag/time
    逻辑归生成骨架——ADR 0009）、无页面残留命名（OUTPIN_Scanf/OUT_IN 不落码）。"""
    source = (MODULES / "microwave_radar" / "code" / "microwave_radar.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "microwave_radar" / "code" / "microwave_radar.h").read_text(
        encoding="utf-8"
    )
    assert "MICROWAVE_TRIGGER_LEVEL 0u" in header
    assert "level == MICROWAVE_TRIGGER_LEVEL" in source
    assert "MICROWAVE_OUT_PIN" in source
    assert "OUTPIN_Scanf" not in source  # 页面命名残留守卫
    assert "GPIO_OUT_PIN" not in source
    assert "flag" not in source and "time" not in source  # 演示时序归骨架
    assert "1=检测到移动" in header  # read 语义守卫


def test_microwave_radar_stm32_code_guards():
    """stm32 代码层守卫：注释里有页面极性/命名记录，剥离注释后零标准库/
    寄存器/演示残留/中断调用；只吃母版 ml_* API（gpio_init IU / gpio_get）。"""
    c = (MODULES / "microwave_radar" / "code" / "microwave_radar_stm32.c").read_text(
        encoding="utf-8"
    )
    h = (MODULES / "microwave_radar" / "code" / "microwave_radar_stm32.h").read_text(
        encoding="utf-8"
    )
    full = c + "\n" + h

    assert "MICROWAVE_ 前缀" in h or "MICROWAVE_ 前缀" in c  # 宏名前缀记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"
    for token in DEMO_TOKENS:
        assert token not in code_only, f"演示时序残留 {token}"

    assert re.search(r"#define\s+MICROWAVE_TRIGGER_LEVEL\s+0u", h)
    assert "gpio_init(MICROWAVE_GPIO, MICROWAVE_PIN, IU)" in code_only
    assert "gpio_get(MICROWAVE_GPIO, MICROWAVE_PIN)" in code_only
    assert "level == MICROWAVE_TRIGGER_LEVEL" in code_only
