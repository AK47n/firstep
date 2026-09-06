"""ttp224 4 路电容触摸模块：真实库 + 真实母版不变量与双平台单选生成。

与 joystick / ir_beam 同款结构测试：manifest 形状（双平台文件齐、stm32 引脚
宏在母版 pin_config.h）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、
mspm0 单选生成（syscfg 裁剪保留 TTP224 + 模块文件落盘）。页面极性 = 引脚
高=触摸（TTP224_TOUCH_LEVEL 单点反相宏）与 4 位掩码以源码守卫钉死；stm32
侧「页面原式 IPD 下拉输入」守卫（与 mspm0 上拉差异记录）。全程无 LLM、无服务。
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
    '#include "ttp224.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ttp224_init();\n"
    "    uint8_t k1 = ttp224_read(1);\n"
    "    uint8_t k4 = ttp224_read(4);\n"
    "    uint8_t all = ttp224_read_all();\n"
    "    (void)k1;\n"
    "    (void)k4;\n"
    "    (void)all;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ttp224_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ttp224_init();\n"
    "    (void)ttp224_read(1);\n"
    "    (void)ttp224_read(4);\n"
    "    (void)ttp224_read_all();\n"
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
]


def test_ttp224_manifest_shape_both_platforms():
    """ttp224：双平台文件齐；stm32 四角色 gpio_in PB12-15（共享 TTP224_GPIO +
    每脚 TTP224_OUTn_PIN）；mspm0 条目原样（syscfg PA22/25/26/27）。"""
    manifest = ModuleManifest.load(MODULES / "ttp224")
    assert manifest.slug == "ttp224"
    assert manifest.dependencies == ()

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ttp224_stm32.c",
        "ttp224_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ttp224" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("TTP224_OUT1", "gpio_in", "PB12", True, ("TTP224_GPIO", "TTP224_OUT1_PIN")),
        ("TTP224_OUT2", "gpio_in", "PB13", True, ("TTP224_GPIO", "TTP224_OUT2_PIN")),
        ("TTP224_OUT3", "gpio_in", "PB14", True, ("TTP224_GPIO", "TTP224_OUT3_PIN")),
        ("TTP224_OUT4", "gpio_in", "PB15", True, ("TTP224_GPIO", "TTP224_OUT4_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/ttp224-touch-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--ttp224-touch-sensor.md",
        "IPD",
        "同口绑定约束",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ttp224.c", "ttp224.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("TTP224_OUT1", "gpio_in", "PA22", True, ()),
        ("TTP224_OUT2", "gpio_in", "PA25", True, ()),
        ("TTP224_OUT3", "gpio_in", "PA26", True, ()),
        ("TTP224_OUT4", "gpio_in", "PA27", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_ttp224_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：TTP224_GPIO + TTP224_OUT1..4_PIN 必须在母版 pin_config.h。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+TTP224_GPIO\s+GPIO_B", text)
    for pin, num in (("Pin_12", 1), ("Pin_13", 2), ("Pin_14", 3), ("Pin_15", 4)):
        assert re.search(rf"#define\s+TTP224_OUT{num}_PIN\s+{pin}", text)


def test_ttp224_mspm0_syscfg_instances():
    """mspm0 母版：TTP224 GPIO 实例（OUT1-4 输入，内部上拉）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const TTP224 = GPIO.addInstance();" in syscfg
    for i, name in enumerate(("OUT1", "OUT2", "OUT3", "OUT4"), start=0):
        assert f'TTP224.associatedPins[{i}].$name            = "{name}";' in syscfg
        assert f'TTP224.associatedPins[{i}].direction        = "INPUT";' in syscfg
        assert f'TTP224.associatedPins[{i}].internalResistor = "PULL_UP";' in syscfg
    assert 'TTP224.associatedPins[0].pin.$assign      = "PA22";' in syscfg
    assert 'TTP224.associatedPins[1].pin.$assign      = "PA25";' in syscfg
    assert 'TTP224.associatedPins[2].pin.$assign      = "PA26";' in syscfg
    assert 'TTP224.associatedPins[3].pin.$assign      = "PA27";' in syscfg


def test_ttp224_stm32_single_select_generation(tmp_path):
    """ttp224 stm32 单选生成：静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ttp224"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ttp224/code/ttp224_stm32.c").is_file()
    assert (out / "modules/ttp224/code/ttp224_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ttp224_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ttp224_mspm0_single_select_generation(tmp_path):
    """ttp224 mspm0 单选生成：syscfg 只留 TTP224、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ttp224"])
    assert {m.slug for m in resolved.manifests} == {"ttp224"}
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
    assert "const TTP224 = GPIO.addInstance();" in syscfg
    assert 'TTP224.associatedPins[0].pin.$assign      = "PA22";' in syscfg
    assert 'TTP224.associatedPins[3].pin.$assign      = "PA27";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "IR_REMOTE", "NRF24L01",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ttp224/code/ttp224.c").is_file()
    assert (out / "modules/ttp224/code/ttp224.h").is_file()


def test_ttp224_polarity_and_mask_guards():
    """页面极性（引脚高=触摸）与 4 位掩码守卫：单点反相宏
    TTP224_TOUCH_LEVEL（默认 1 = 高有效，低有效改 0）、read 返回
    level == 宏、read_all 按 ch-1 位移位生成 bit0-3。"""
    source = (MODULES / "ttp224" / "code" / "ttp224.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "ttp224" / "code" / "ttp224.h").read_text(
        encoding="utf-8"
    )
    assert "TTP224_TOUCH_LEVEL 1u" in header
    assert "level == TTP224_TOUCH_LEVEL" in source
    assert "1u << (ch - 1)" in source
    assert "ch <= TTP224_CHANNELS" in source
    # 页面 4 键序（Key_IN1-4 → 通道 1-4；无 5+ 通道）
    assert "channel" in source
    assert "TTP224_OUT4_PIN" in source


def test_ttp224_stm32_code_guards():
    """stm32 代码层守卫：注释里有 IPD 原式/平台差异记录，剥离注释后零标准库/
    寄存器/演示残留；只吃母版 ml_* API（gpio_init ID 下拉 ×4 / gpio_get）。"""
    c = (MODULES / "ttp224" / "code" / "ttp224_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ttp224" / "code" / "ttp224_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "IPD" in c and "ID" in c  # 页面原式下拉记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+TTP224_TOUCH_LEVEL\s+1u", h)
    assert re.search(r"#define\s+TTP224_CHANNELS\s+4u", h)
    # 页面原式 ID 下拉输入（与 mspm0 上拉差异记录在注释）
    assert code_only.count("gpio_init(TTP224_GPIO, TTP224_OUT") == 4
    assert "gpio_init(TTP224_GPIO, TTP224_OUT1_PIN, ID)" in code_only
    assert "gpio_get(TTP224_GPIO, TTP224_OUT1_PIN)" in code_only
    # read_all 掩码语义
    assert "1u << (ch - 1)" in code_only
    assert "level == TTP224_TOUCH_LEVEL" in code_only
