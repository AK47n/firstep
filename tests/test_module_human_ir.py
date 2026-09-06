"""human_ir 人体红外感应模块：真实库 + 真实母版不变量与双平台单选生成。

与 ttp224 / ir_beam 同款结构测试：manifest 形状（双平台文件齐、stm32 引脚
宏在母版 pin_config.h）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、
mspm0 单选生成（syscfg 裁剪保留 HUMAN_IR + 模块文件落盘）。极性定稿
（感应到=输出高——按模块介绍/规格；页面注释 0=感应到 与介绍矛盾已按
HC-SR501 器件标准修正）以 HUMAN_IR_TRIGGER_LEVEL 单点反相宏守卫钉死。
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
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "human_ir.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    human_ir_init();\n"
    "    uint8_t detected = human_ir_read();\n"
    "    (void)detected;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "human_ir_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    human_ir_init();\n"
    "    (void)human_ir_read();\n"
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


def test_human_ir_manifest_shape_both_platforms():
    """human_ir：双平台文件齐；stm32 单角色 gpio_in PB7（macros =
    HUMAN_IR_GPIO/HUMAN_IR_PIN）；mspm0 条目原样（syscfg gpio_in PB8）。"""
    manifest = ModuleManifest.load(MODULES / "human_ir")
    assert manifest.slug == "human_ir"
    assert manifest.dependencies == ()

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "human_ir_stm32.c",
        "human_ir_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "human_ir" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("HUMAN_IR_OUT", "gpio_in", "PB7", True, ("HUMAN_IR_GPIO", "HUMAN_IR_PIN"))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/human-body-infrared-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--human-body-infrared-sensor.md",
        "0=感应到人体红外",
        "修正",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["human_ir.c", "human_ir.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("HUMAN_IR_OUT", "gpio_in", "PB8", True, ())
    ]
    assert mspm0.kit and mspm0.source_url


def test_human_ir_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：HUMAN_IR_GPIO / HUMAN_IR_PIN 必须在母版 pin_config.h。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+HUMAN_IR_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+HUMAN_IR_PIN\s+Pin_7", text)


def test_human_ir_mspm0_syscfg_instances():
    """mspm0 母版：HUMAN_IR GPIO 实例（OUT 输入，内部上拉，默认 PB8）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const HUMAN_IR = GPIO.addInstance();" in syscfg
    assert 'HUMAN_IR.associatedPins[0].$name            = "OUT";' in syscfg
    assert 'HUMAN_IR.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'HUMAN_IR.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'HUMAN_IR.associatedPins[0].pin.$assign      = "PB8";' in syscfg


def test_human_ir_stm32_single_select_generation(tmp_path):
    """human_ir stm32 单选生成：静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["human_ir"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/human_ir/code/human_ir_stm32.c").is_file()
    assert (out / "modules/human_ir/code/human_ir_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("human_ir_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_human_ir_mspm0_single_select_generation(tmp_path):
    """human_ir mspm0 单选生成：syscfg 只留 HUMAN_IR、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["human_ir"])
    assert {m.slug for m in resolved.manifests} == {"human_ir"}
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
    assert "const HUMAN_IR = GPIO.addInstance();" in syscfg
    assert 'HUMAN_IR.associatedPins[0].pin.$assign      = "PB8";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "IR_REMOTE", "NRF24L01", "MICROWAVE",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/human_ir/code/human_ir.c").is_file()
    assert (out / "modules/human_ir/code/human_ir.h").is_file()


def test_human_ir_polarity_guard():
    """页面极性修正与单点反相宏守卫（防回潮）：感应到=输出高（模块介绍/
    规格；页面函数注释「0=感应到」与介绍矛盾已修正——HUMAN_IR_TRIGGER_LEVEL
    默认 1u，实物低有效改 0 即可反相）、read 返回 level == 宏、无页面残留
    命名（Get_HumanIR/GET 宏不落码）。"""
    source = (MODULES / "human_ir" / "code" / "human_ir.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "human_ir" / "code" / "human_ir.h").read_text(
        encoding="utf-8"
    )
    assert "HUMAN_IR_TRIGGER_LEVEL 1u" in header
    assert "level == HUMAN_IR_TRIGGER_LEVEL" in source
    assert "HUMAN_IR_OUT_PIN" in source
    assert "Get_HumanIR" not in source  # 页面命名残留守卫
    assert "GPIO_OUT_PIN" not in source


def test_human_ir_stm32_code_guards():
    """stm32 代码层守卫：注释里有极性修正记录（与原页对照），剥离注释后
    零标准库/寄存器/演示残留；只吃母版 ml_* API（gpio_init IU / gpio_get）。"""
    c = (MODULES / "human_ir" / "code" / "human_ir_stm32.c").read_text(
        encoding="utf-8"
    )
    h = (MODULES / "human_ir" / "code" / "human_ir_stm32.h").read_text(
        encoding="utf-8"
    )
    full = c + "\n" + h

    assert "0=感应到人体红外" in c  # 页面注释矛盾记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+HUMAN_IR_TRIGGER_LEVEL\s+1u", h)
    assert "gpio_init(HUMAN_IR_GPIO, HUMAN_IR_PIN, IU)" in code_only
    assert "gpio_get(HUMAN_IR_GPIO, HUMAN_IR_PIN)" in code_only
    assert "level == HUMAN_IR_TRIGGER_LEVEL" in code_only
