"""ir_remote 红外遥控接收模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / hc05 / nrf24l01 同款结构测试：manifest 形状（仅 mspm0、依赖
delay、单 GPIO 输入默认 = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 IR_REMOTE + delay 依赖文件落盘、
main.c 调 init/poll/读码过静态门禁）。解码 = CPU 忙等（20us 步进），不占
TIMER、不注册 GPIO 中断（GROUP1 被 motor 编码器独占）。全程无 LLM、无服务。
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
    '#include "ir_remote.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ir_remote_init();\n"
    "    uint8_t result = ir_remote_poll();\n"
    "    (void)result;\n"
    "    (void)ir_remote_has_data();\n"
    "    (void)ir_remote_get_code();\n"
    "    (void)ir_remote_get_address();\n"
    "    ir_remote_clear();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ir_remote_manifest_shape_mspm0():
    """ir_remote：仅 mspm0 平台条目；依赖 delay；单 gpio_in（OUT 默认 PA26）。"""
    manifest = ModuleManifest.load(MODULES / "ir_remote")
    assert manifest.slug == "ir_remote"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ir_remote.c", "ir_remote.h"]
    for rel in mspm0.files:
        assert (MODULES / "ir_remote" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("IR_REMOTE_OUT", "gpio_in", "PA26", True, ()),
    ]
    # 简介判据：硬件身份（kit/source_url 必填）+ 能力方向 + 无题绑定词
    assert mspm0.kit and mspm0.source_url


def test_ir_remote_mspm0_syscfg_instance():
    """mspm0 母版必须有 IR_REMOTE 输入实例（OUT = PA26，上拉）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const IR_REMOTE = GPIO.addInstance();" in syscfg
    assert 'IR_REMOTE.associatedPins[0].$name            = "OUT";' in syscfg
    assert 'IR_REMOTE.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'IR_REMOTE.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'IR_REMOTE.associatedPins[0].pin.$assign      = "PA26";' in syscfg


def test_ir_remote_mspm0_single_select_generation(tmp_path):
    """ir_remote mspm0 单选生成：syscfg 只留 IR_REMOTE、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ir_remote"])
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
    assert "const IR_REMOTE = GPIO.addInstance();" in syscfg
    assert 'IR_REMOTE.associatedPins[0].pin.$assign      = "PA26";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "JOYSTICK",
        "HC05", "NRF24L01", "DIGIT_UART", "DEBUG_UART", "UWB_UART",
        "ZIGBEE_UART", "IMU601", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ir_remote/code/ir_remote.c").is_file()
    assert (out / "modules/ir_remote/code/ir_remote.h").is_file()
    # 依赖展开：delay 模块文件随选中落盘
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


# ---------------------------------------------------------------------------
# wiki-stm32-batch8/05：stm32 平台条目（EXTI 改轮询忙等解码）
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ir_remote_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ir_remote_init();\n"
    "    (void)ir_remote_poll();\n"
    "    (void)ir_remote_has_data();\n"
    "    (void)ir_remote_get_code();\n"
    "    (void)ir_remote_get_address();\n"
    "    ir_remote_clear();\n"
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
    (r"\bEXTI\w*_IRQHandler\b", "EXTI IRQHandler（改轮询不注册）"),
    (r"\bIRQHandler\b", "IRQHandler（轮询件）"),
    (r"\bTIM\d\b", "TIM（不占定时器）"),
]


def test_ir_remote_manifest_shape_stm32():
    """stm32 条目：单 gpio_in（OUT 默认 PA10——mspm0 PA26 UART 族同型推理）。"""
    manifest = ModuleManifest.load(MODULES / "ir_remote")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ir_remote_stm32.c",
        "ir_remote_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ir_remote" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("IR_REMOTE_OUT", "gpio_in", "PA10", True, ("IR_REMOTE_PORT", "IR_REMOTE_OUT_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/infrared-receiving-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/rf--infrared-receiving-module.md",
        "PA10",
        "轮询",
        "PA9",
        "未上板",
    ):
        assert needle in stm32.notes


def test_ir_remote_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：ir_remote 两宏在母版 pin_config.h（PORT=GPIO_A/Pin_10）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+IR_REMOTE_PORT\s+GPIO_A", text)
    assert re.search(r"#define\s+IR_REMOTE_OUT_PIN\s+Pin_10", text)


def test_ir_remote_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：依赖 delay 展开、uvprojx 注册、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ir_remote"])
    assert {m.slug for m in resolved.manifests} == {"ir_remote", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ir_remote/code/ir_remote_stm32.c").is_file()
    assert (out / "modules/ir_remote/code/ir_remote_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ir_remote_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ir_remote_stm32_code_guards():
    """stm32 代码层守卫：20us 拍忙等 + 反码严格校验 + 轮询（无 EXTI/TIM）+
    零引脚字面量、无寄存器残留。"""
    c = (MODULES / "ir_remote" / "code" / "ir_remote_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ir_remote" / "code" / "ir_remote_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "#define IR_TICK_US     20u" in c
    assert "#define IR_TIMEOUT_TICKS 500u" in c

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 忙等：delay_us(IR_TICK_US) 步进 + 反码严格校验（页面错乱判定修正）
    assert "delay_us(IR_TICK_US)" in code_only
    assert "(uint8_t)~value[1] != value[0]" in code_only
    assert "(uint8_t)~value[3] != value[2]" in code_only
    # 轮询读取 gpio_get（上拉输入）
    assert "gpio_get(IR_REMOTE_PORT, IR_REMOTE_OUT_PIN)" in code_only
    assert "PA10" not in code_only
