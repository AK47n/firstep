"""max7219 数码管/点阵模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / hx711 / aht10 / sr04 / joystick / dht11 同款结构测试：manifest
形状（仅 mspm0、无依赖、三角色 DIN/CLK/CS = 母版 syscfg 由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 MAX7219、模块
文件落盘、main.c 调 init/write_digit/write_matrix 过静态门禁）。单模块
双形态（数码管 BCD / 点阵行直通），软 SPI 位操作不占硬件 SPI 外设。
全程无 LLM、无服务。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "max7219.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    max7219_init(MAX7219_FORM_DIGIT, 3);\n"
    "    max7219_write_digit(1, 3);\n"
    "    uint8_t rows[8] = {0x3C, 0x42, 0x42, 0x42, 0x42, 0x42, 0x66, 0x38};\n"
    "    max7219_init(MAX7219_FORM_MATRIX, 1);\n"
    "    max7219_write_matrix(rows, 1);\n"
    "    max7219_clear();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_max7219_manifest_shape_mspm0():
    """max7219：仅 mspm0 平台条目；无依赖；三角色 DIN/CLK/CS = gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "max7219")
    assert manifest.slug == "max7219"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["max7219.c", "max7219.h"]
    for rel in mspm0.files:
        assert (MODULES / "max7219" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MAX7219_DIN", "gpio_out", "PB9", True, ()),
        ("MAX7219_CLK", "gpio_out", "PA18", True, ()),
        ("MAX7219_CS", "gpio_out", "PB18", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_max7219_mspm0_syscfg_instances():
    """mspm0 母版：MAX7219 GPIO 实例（DIN/CLK/CS 三输出，CS 初始高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const MAX7219 = GPIO.addInstance();" in syscfg
    assert 'MAX7219.associatedPins[0].$name        = "DIN";' in syscfg
    assert 'MAX7219.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'MAX7219.associatedPins[0].pin.$assign  = "PB9";' in syscfg
    assert 'MAX7219.associatedPins[1].pin.$assign  = "PA18";' in syscfg
    assert 'MAX7219.associatedPins[2].$name        = "CS";' in syscfg
    assert 'MAX7219.associatedPins[2].initialValue = "SET";' in syscfg
    assert 'MAX7219.associatedPins[2].pin.$assign  = "PB18";' in syscfg


def test_max7219_mspm0_single_select_generation(tmp_path):
    """max7219 mspm0 单选生成：syscfg 只留 MAX7219、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["max7219"])
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
    assert "const MAX7219 = GPIO.addInstance();" in syscfg
    assert 'MAX7219.associatedPins[2].pin.$assign  = "PB18";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "DC_MOTOR",
        "PWMAB", "SERVO_PWM", "IR_REMOTE", "PCA9685", "IR_TX",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/max7219/code/max7219.c").is_file()
    assert (out / "modules/max7219/code/max7219.h").is_file()


# ---------------------------------------------------------------------------
# 批次 10（wiki-stm32-batch10/01）：stm32 平台条目
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "max7219_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    max7219_init(MAX7219_FORM_DIGIT, 3);\n"
    "    max7219_write_digit(1, 3);\n"
    "    uint8_t rows[8] = {0x3C, 0x42, 0x42, 0x42, 0x42, 0x42, 0x66, 0x38};\n"
    "    max7219_init(MAX7219_FORM_MATRIX, 1);\n"
    "    max7219_write_matrix(rows, 1);\n"
    "    max7219_write_reg(0, 0x0F, 0x00);\n"
    "    max7219_clear();\n"
    "    max7219_set_chip_count(1);\n"
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
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bDL_GPIO\b", "DL_GPIO（mspm0 调用）"),
    (r"\bti_msp_dl_config\.h\b", "ti_msp_dl_config.h"),
]


def test_max7219_stm32_manifest_shape():
    """max7219 stm32 条目：双平台文件齐；三角色 = PC13/14/15（macros 逐脚
    端口宏）；mspm0 条目原样零改动。"""
    manifest = ModuleManifest.load(MODULES / "max7219")
    assert manifest.dependencies == ()

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "max7219_stm32.c",
        "max7219_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "max7219" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("MAX7219_DIN", "gpio_out", "PC13", True, ("MAX7219_DIN_GPIO", "MAX7219_DIN_PIN")),
        ("MAX7219_CLK", "gpio_out", "PC14", True, ("MAX7219_CLK_GPIO", "MAX7219_CLK_PIN")),
        ("MAX7219_CS", "gpio_out", "PC15", True, ("MAX7219_CS_GPIO", "MAX7219_CS_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dmx/module/screen/8-bit-led-tube.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/screen--8-bit-led-tube.md",
        "lckfb-地阔星移植手册/screen--max7219-matrix-display.md",
        "互替",
        "PC13",
        "未上板",
    ):
        assert needle in stm32.notes
    # mspm0 条目零改动（文件齐 + 默认脚不变）
    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["max7219.c", "max7219.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MAX7219_DIN", "gpio_out", "PB9", True, ()),
        ("MAX7219_CLK", "gpio_out", "PA18", True, ()),
        ("MAX7219_CS", "gpio_out", "PB18", True, ()),
    ]


def test_max7219_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：MAX7219 六宏在母版 pin_config.h（默认 PC13/14/15）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+MAX7219_DIN_GPIO\s+GPIO_C", text)
    assert re.search(r"#define\s+MAX7219_DIN_PIN\s+Pin_13", text)
    assert re.search(r"#define\s+MAX7219_CLK_GPIO\s+GPIO_C", text)
    assert re.search(r"#define\s+MAX7219_CLK_PIN\s+Pin_14", text)
    assert re.search(r"#define\s+MAX7219_CS_GPIO\s+GPIO_C", text)
    assert re.search(r"#define\s+MAX7219_CS_PIN\s+Pin_15", text)


def test_max7219_stm32_single_select_generation(tmp_path):
    """max7219 stm32 单选生成：静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["max7219"])
    assert {m.slug for m in resolved.manifests} == {"max7219"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/max7219/code/max7219_stm32.c").is_file()
    assert (out / "modules/max7219/code/max7219_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("max7219_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_max7219_stm32_code_guards():
    """stm32 代码层守卫：软 SPI 位操作（gpio_set）+ 寄存器族
    （0x09/0x0A/0x0B/0x0C/0x0F）+ 级联链序语义 + 零演示字模数组/printf。"""
    c = (MODULES / "max7219" / "code" / "max7219_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "max7219" / "code" / "max7219_stm32.h").read_text(encoding="utf-8")
    code_only = strip_comments(c + "\n" + h, keep_preprocessor=True)

    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"
    # 软 SPI 位操作宏族（gpio_set——零引脚字面量检查由 test_pins 兜底）
    assert re.search(r"#define\s+MAX7219_DIN\(x\)\s+gpio_set\(MAX7219_DIN_GPIO", code_only)
    assert re.search(r"#define\s+MAX7219_CS\(x\)\s+gpio_set\(MAX7219_CS_GPIO", code_only)
    # 寄存器族（页面/数据手册：0x00 NOOP/0x01-0x08 位行/0x09 译码/0x0A 亮度/
    # 0x0B 扫描/0x0C 掉电/0x0F 测试）
    assert "MAX7219_REG_DECODE_MODE  0x09u" in code_only
    assert "MAX7219_REG_DISPLAY_TEST 0x0Fu" in code_only
    # 形态宏（BCD 译码/无译码）
    assert "MAX7219_FORM_DIGIT  0u" in code_only
    assert "MAX7219_FORM_MATRIX 1u" in code_only
    # 级联语义：先发最远片（链序循环——16 位包沿链移位，首包落最远片）+
    # NOOP 空操作
    assert "MAX7219_REG_NOOP" in code_only
    assert "for (c = s_chips; c > 0; c--)" in code_only
    assert "MAX7219_CS(0);" in code_only and "MAX7219_CS(1);" in code_only
    # API 六函数（与 mspm0 同名同型）
    for fn in ("max7219_init", "max7219_write_digit", "max7219_write_matrix",
               "max7219_write_reg", "max7219_clear", "max7219_set_chip_count"):
        assert re.search(r"void " + fn + r"\(", code_only), fn
