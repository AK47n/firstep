"""ir_remote_tx 红外编码发射模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / dht11 / max7219 同款结构测试：manifest 形状（仅 mspm0、
依赖 delay、单角色 OUT = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 IR_TX + delay 展开、模块文件落盘、
main.c 调 init/send 过静态门禁）。38kHz 载波 CPU 忙等不占 TIMER；默认
PA0 与 ir_remote 默认 PA26 刻意错开（发/收常配对）。
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
    '#include "ir_remote_tx.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ir_tx_init();\n"
    "    ir_tx_send(0xE0, 0xFD);\n"
    "    ir_tx_send(0x01, 0x45);\n"
    "    ir_tx_send_repeat();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ir_remote_tx_manifest_shape_mspm0():
    """ir_remote_tx：仅 mspm0 平台条目；依赖 delay；单角色 OUT = gpio_out PA0。"""
    manifest = ModuleManifest.load(MODULES / "ir_remote_tx")
    assert manifest.slug == "ir_remote_tx"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ir_remote_tx.c", "ir_remote_tx.h"]
    for rel in mspm0.files:
        assert (MODULES / "ir_remote_tx" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("IR_TX_OUT", "gpio_out", "PA0", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_ir_remote_tx_mspm0_syscfg_instances():
    """mspm0 母版：IR_TX GPIO 实例（OUT 输出，初始 CLEARED = 载波空闲低）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const IR_TX = GPIO.addInstance();" in syscfg
    assert 'IR_TX.associatedPins[0].$name        = "OUT";' in syscfg
    assert 'IR_TX.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'IR_TX.associatedPins[0].initialValue = "CLEARED";' in syscfg
    assert 'IR_TX.associatedPins[0].pin.$assign  = "PA0";' in syscfg


def test_ir_remote_tx_mspm0_single_select_generation(tmp_path):
    """ir_remote_tx mspm0 单选生成：syscfg 只留 IR_TX、依赖 delay 展开、文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ir_remote_tx"])
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
    assert "const IR_TX = GPIO.addInstance();" in syscfg
    assert 'IR_TX.associatedPins[0].pin.$assign  = "PA0";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "DC_MOTOR",
        "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219", "PCA9685", "DHT11",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ir_remote_tx/code/ir_remote_tx.c").is_file()
    assert (out / "modules/ir_remote_tx/code/ir_remote_tx.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


def test_ir_remote_tx_burst_cycle_formula_guard():
    """载波 burst 时长公式守卫（code-review 收尾修正）：每轮循环 = 一完整 38kHz
    周期（26.3us），周期数必须按 us×38000/1000000 换算——早产实现按「us/2 轮」
    循环曾把引导码 9ms 放大到 118ms、位载波 560us 放大到 7.37ms（ir_remote
    解码阈值窗口 0.4-1.2ms 全面超窗，收发无法配对）；编译矩阵只验编译不验
    时序，此处以源码文本守卫钉死。"""
    source = (MODULES / "ir_remote_tx" / "code" / "ir_remote_tx.c").read_text(
        encoding="utf-8"
    )
    assert "us * IR_TX_FREQ_HZ / 1000000u" in source
    assert "us / 2u" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch8/06：stm32 平台条目（38kHz 载波 delay_us(13) 忙等）
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ir_remote_tx_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ir_tx_init();\n"
    "    ir_tx_send(0xE0, 0xFD);\n"
    "    ir_tx_send_repeat();\n"
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
    (r"\bGPIO_WriteBit\b", "GPIO_WriteBit"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bUSART\w*\b", "USART（页面 UART 指令形态归骨架）"),
    (r"\bTIM\d\b", "TIM（不占定时器）"),
    (r"\bPWM\b", "PWM（不占 PWM 外设）"),
    (r"\bIRQHandler\b", "IRQHandler（无中断件）"),
]


def test_ir_remote_tx_manifest_shape_stm32():
    """stm32 条目：单角色 OUT = gpio_out PA9（与接收 PA10 刻意错开）。"""
    manifest = ModuleManifest.load(MODULES / "ir_remote_tx")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ir_remote_tx_stm32.c",
        "ir_remote_tx_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ir_remote_tx" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("IR_TX_OUT", "gpio_out", "PA9", True, ("IR_TX_PORT", "IR_TX_OUT_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/Infrared-decoding-coding-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/rf--Infrared-decoding-coding-module.md",
        "PA9",
        "PA10",
        "delay_us(13)",
        "未上板",
    ):
        assert needle in stm32.notes


def test_ir_remote_tx_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：ir_remote_tx 两宏在母版 pin_config.h（PORT=GPIO_A/Pin_9）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+IR_TX_PORT\s+GPIO_A", text)
    assert re.search(r"#define\s+IR_TX_OUT_PIN\s+Pin_9", text)


def test_ir_remote_tx_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：依赖 delay 展开、uvprojx 注册、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ir_remote_tx"])
    assert {m.slug for m in resolved.manifests} == {"ir_remote_tx", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ir_remote_tx/code/ir_remote_tx_stm32.c").is_file()
    assert (out / "modules/ir_remote_tx/code/ir_remote_tx_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ir_remote_tx_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ir_remote_tx_stm32_code_guards():
    """stm32 代码层守卫：38kHz/周期数公式 + delay_us(13) 半周期 + MSB 先 +
    无 TIM/PWM/USART 残留、零引脚字面量。"""
    c = (MODULES / "ir_remote_tx" / "code" / "ir_remote_tx_stm32.c").read_text(
        encoding="utf-8"
    )
    h = (MODULES / "ir_remote_tx" / "code" / "ir_remote_tx_stm32.h").read_text(
        encoding="utf-8"
    )
    full = c + "\n" + h

    assert "#define IR_TX_FREQ_HZ 38000u" in h
    assert "#define IR_TX_MSB_FIRST 1" in h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 载波：周期数公式（code-review 修正防回潮）+ delay_us(13) 半周期
    assert "us * IR_TX_FREQ_HZ / 1000000u" in code_only
    assert "#define IR_TX_HALF_CYCLES() delay_us(13)" in code_only
    assert "delay_us(IR_TX_LEADER_HIGH_US)" in code_only
    assert "delay_us(IR_TX_REPEAT_HIGH_US)" in code_only
    # 帧格式：引导 9ms/4.5ms + 4 字节反码 + MSB 先 + 结束位 560us
    assert "IR_TX_LEADER_LOW_US" in code_only
    assert "(uint8_t)~address" in code_only
    assert "(uint8_t)~command" in code_only
    assert "7 - bit" in code_only
    # 走 ml_gpio/ml_delay（零引脚字面量）
    assert "gpio_init(IR_TX_PORT, IR_TX_OUT_PIN, OUT_PP)" in code_only
    assert "gpio_set(IR_TX_PORT, IR_TX_OUT_PIN, 1)" in code_only
    assert "PA9" not in code_only
