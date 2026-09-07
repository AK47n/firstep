"""jq8900 语音播报模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / max7219 / ir_remote_tx 同款结构测试：manifest 形状（仅 mspm0、
依赖 delay、单角色 TX = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 JQ8900 + delay 展开、模块文件落盘、
main.c 调 init/play_next/send_cmd 过静态门禁）。**软 UART 单发 TX 为本批新
先例**：9600 8N1 位序列时序用 Python 纯函数镜像（电平时间轴）钉死 + 源码
文本守卫（防公式走样，ir_remote_tx burst_cycle_formula_guard 先例）。
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
    '#include "jq8900.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    jq8900_init();\n"
    "    jq8900_play(3);\n"
    "    jq8900_play_next();\n"
    "    jq8900_play_prev();\n"
    "    jq8900_stop();\n"
    "    jq8900_pause();\n"
    "    jq8900_resume();\n"
    "    jq8900_set_volume(15);\n"
    "    jq8900_volume_up();\n"
    "    jq8900_volume_down();\n"
    "    jq8900_send_cmd(0x06, 0x00);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# ---------------------------------------------------------------------------
# 软 UART 时序纯函数镜像（最高既有接缝 = 与 C 实现同构的 Python 纯函数 +
# 源码文本守卫；编译矩阵只验编译不验时序）
# ---------------------------------------------------------------------------

JQ8900_BIT_US = 104  # 9600 8N1 单位时间 ≈104.17us（取整 104，模块头宏同值）


def soft_uart_timeline(byte: int, bit_us: int = JQ8900_BIT_US) -> list[tuple[int, int]]:
    """9600 8N1 位序列 → [(电平, 时长us), ...]，共 10 段（起始+8 数据+停止）。

    电平：1 = 高（空闲），0 = 低；数据位 LSB 先（JQ8900 帧协议字节序）。
    与 jq8900.c 的 _tx_byte 实现同构（起始位低 → for i in 0..7 取 (byte>>i)&1
    → 停止位高，每段 delay_us(JQ8900_UART_BIT_US)）。
    """
    levels = [0] + [(byte >> i) & 1 for i in range(8)] + [1]
    return [(level, bit_us) for level in levels]


def jq8900_frame(cmd: int, data: int) -> list[int]:
    """JQ8900 两线串口指令帧镜像：0xAA + cmd + data + (前三字节求和 &0xFF)。

    页面 demo {0xAA,0x06,0x00,0xB0}（下一曲）实证——0xAA+0x06+0x00=0xB0。
    """
    body = [0xAA, cmd, data]
    return body + [(sum(body) & 0xFF)]


def test_jq8900_soft_uart_timeline_shape_and_order():
    """9600 8N1：10 段、起始位低、停止位高、数据位 LSB 先、每段 104us。"""
    byte = 0xAA  # 10101010，LSB 先 = 0,1,0,1,0,1,0,1
    timeline = soft_uart_timeline(byte)
    assert len(timeline) == 10
    levels = [level for level, _ in timeline]
    assert levels[0] == 0          # 起始位
    assert levels[-1] == 1         # 停止位
    assert levels[1:9] == [(byte >> i) & 1 for i in range(8)]
    assert all(dur == JQ8900_BIT_US for _, dur in timeline)
    assert sum(dur for _, dur in timeline) == 10 * JQ8900_BIT_US  # ~1040us/字节
    # 空闲电平 = 停止位电平（1），字节间保持高
    assert levels[-1] == 1


def test_jq8900_frame_matches_page_proven_demo():
    """页面 demo 帧 {0xAA,0x06,0x00,0xB0}（下一曲）逐字节镜像。"""
    assert jq8900_frame(0x06, 0x00) == [0xAA, 0x06, 0x00, 0xB0]
    assert jq8900_frame(0x01, 0x03) == [0xAA, 0x01, 0x03, 0xAE]


def test_jq8900_soft_uart_source_guards():
    """源码文本守卫：位时序公式/帧结构走样即红（编译矩阵不验时序）。"""
    source = (MODULES / "jq8900" / "code" / "jq8900.c").read_text(encoding="utf-8")
    assert "0xAAu" in source
    assert "JQ8900_UART_BIT_US" in source
    assert "_tx_bit(0u);" in source           # 起始位
    assert "(ch >> i) & 0x01u" in source      # LSB 先（非 MSB）
    assert "_tx_bit(1u);" in source           # 停止位
    assert "(uint8_t)(sum + frame[i])" in source  # 校验和 = 逐字节求和


# ---------------------------------------------------------------------------
# 结构 + 生成（既有接缝）
# ---------------------------------------------------------------------------


def test_jq8900_manifest_shape_mspm0():
    """jq8900：仅 mspm0 平台条目；依赖 delay；单角色 TX = gpio_out PB19。"""
    manifest = ModuleManifest.load(MODULES / "jq8900")
    assert manifest.slug == "jq8900"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["jq8900.c", "jq8900.h"]
    for rel in mspm0.files:
        assert (MODULES / "jq8900" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("JQ8900_TX", "gpio_out", "PB19", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_jq8900_mspm0_syscfg_instances():
    """mspm0 母版：JQ8900 GPIO 实例（TX 输出，初始 SET = 空闲高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const JQ8900 = GPIO.addInstance();" in syscfg
    assert 'JQ8900.associatedPins[0].$name        = "TX";' in syscfg
    assert 'JQ8900.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'JQ8900.associatedPins[0].initialValue = "SET";' in syscfg
    assert 'JQ8900.associatedPins[0].pin.$assign  = "PB19";' in syscfg


def test_jq8900_mspm0_single_select_generation(tmp_path):
    """jq8900 mspm0 单选生成：syscfg 只留 JQ8900、依赖 delay 展开、文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["jq8900"])
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
    assert "const JQ8900 = GPIO.addInstance();" in syscfg
    assert 'JQ8900.associatedPins[0].pin.$assign  = "PB19";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "DEBUG_UART", "UWB_UART", "ZIGBEE_UART", "OLED", "I2C_0",
        "ADC12_0", "DC_MOTOR", "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219",
        "PCA9685", "IR_TX", "NRF24L01", "HC05_UART", "HC05",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/jq8900/code/jq8900.c").is_file()
    assert (out / "modules/jq8900/code/jq8900.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


# ---------------------------------------------------------------------------
# wiki-stm32-batch9/01：stm32 平台条目（软 UART TX——不占串口实例；
# 默认 PA15 叠 BUZZER 提示输出互替）
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "jq8900_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    jq8900_init();\n"
    "    jq8900_play(1);\n"
    "    jq8900_play_next();\n"
    "    jq8900_play_prev();\n"
    "    jq8900_stop();\n"
    "    jq8900_pause();\n"
    "    jq8900_resume();\n"
    "    jq8900_set_volume(6);\n"
    "    jq8900_volume_up();\n"
    "    jq8900_volume_down();\n"
    "    jq8900_send_cmd(0x06, 0x00);\n"
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
    (r"\bUSART[123]?\b", "USART 寄存器引用（软 UART 无串口外设）"),
    (r"\bUART_[123]\b", "UART 实例枚举引用（软 UART 不占实例）"),
    (r"rx_handler", "rx_handler（RX 未实现）"),
]


def test_jq8900_manifest_shape_stm32():
    """stm32 条目：单角色 TX = gpio_out PA15，宏 JQ8900_GPIO/JQ8900_PIN。"""
    manifest = ModuleManifest.load(MODULES / "jq8900")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "jq8900_stm32.c",
        "jq8900_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "jq8900" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("JQ8900_TX", "gpio_out", "PA15", True, ("JQ8900_GPIO", "JQ8900_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/control/jq8900-voice-broadcast-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/control--jq8900-voice-broadcast-module.md",
        "104us",
        "互替",
        "不占串口实例",
        "未上板",
    ):
        assert needle in stm32.notes


def test_jq8900_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：jq8900 两宏在母版 pin_config.h（默认 PA15 = BUZZER 组）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+JQ8900_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+JQ8900_PIN\s+Pin_15", text)
    # 非 UART 件：不进 USART_IRQ_CALLS 聚合（软 UART 无 rx_handler）
    assert "jq8900_rx_handler" not in text


def test_jq8900_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 jq8900_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["jq8900"])
    assert {m.slug for m in resolved.manifests} == {"jq8900", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/jq8900/code/jq8900_stm32.c").is_file()
    assert (out / "modules/jq8900/code/jq8900_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("jq8900_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_jq8900_stm32_code_guards():
    """stm32 代码层守卫：104us/bit、0xAA 帧头 + 求和校验、API 11 函数、
    走 ml_gpio/ml_delay（零引脚字面量）、无 UART 外设/RX/printf。"""
    c = (MODULES / "jq8900" / "code" / "jq8900_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "jq8900" / "code" / "jq8900_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 UART 位时序常量与帧（与 mspm0 逐字节一致）
    assert "JQ8900_UART_BIT_US   104u" in h
    assert "JQ8900_VOLUME_MAX      30u" in h
    assert "0xAAu" in code_only
    assert "sum = (uint8_t)(sum + frame[i]);" in code_only
    # 位时序原语：gpio_set + delay_us（无 UART 外设写 DR）
    assert "gpio_set(JQ8900_GPIO, JQ8900_PIN, level);" in code_only
    assert "delay_us(JQ8900_UART_BIT_US);" in code_only
    assert "gpio_init(JQ8900_GPIO, JQ8900_PIN, OUT_PP);" in code_only
    # API 全族（11 函数名——与 mspm0 jq8900.h 同名同型）
    for fn in (
        "jq8900_init",
        "jq8900_send_cmd",
        "jq8900_play",
        "jq8900_play_next",
        "jq8900_play_prev",
        "jq8900_stop",
        "jq8900_pause",
        "jq8900_resume",
        "jq8900_set_volume",
        "jq8900_volume_up",
        "jq8900_volume_down",
    ):
        assert f"void {fn}(" in code_only, fn
    assert "PA15" not in code_only and "PA2" not in code_only
