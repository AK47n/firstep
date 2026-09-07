"""hc05 蓝牙串口模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / ws2812 同款结构测试：manifest 形状（仅 mspm0、四角色默认 =
母版 syscfg 由 test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成
（syscfg 裁剪保留 HC05_UART + HC05、模块文件落盘、main.c 调 init/收发/
状态过静态门禁）。HC05_UART 与 DEBUG+UWB 同 UART2 共享先例（9600 波特率，
独立 targetBaudRate 无冲突）。全程无 LLM、无服务。
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
    '#include "hc05.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    hc05_init();\n"
    "    hc05_send_string(\"hello\");\n"
    "    uint8_t buf[16];\n"
    "    uint16_t n = hc05_receive(buf, sizeof(buf));\n"
    "    uint16_t avail = hc05_available();\n"
    "    uint8_t connected = hc05_is_connected();\n"
    "    hc05_at_mode_exit();\n"
    "    (void)n;\n"
    "    (void)avail;\n"
    "    (void)connected;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_hc05_manifest_shape_mspm0():
    """hc05：仅 mspm0 平台条目；无依赖；TX(uart_tx PA23) + RX(uart_rx PA24) +
    STATE(gpio_in PA8) + KEY(gpio_out PB24)。"""
    manifest = ModuleManifest.load(MODULES / "hc05")
    assert manifest.slug == "hc05"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["hc05.c", "hc05.h"]
    for rel in mspm0.files:
        assert (MODULES / "hc05" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("HC05_TX", "uart_tx", "PA23", True, ()),
        ("HC05_RX", "uart_rx", "PA24", True, ()),
        ("HC05_STATE", "gpio_in", "PA8", True, ()),
        ("HC05_KEY", "gpio_out", "PB24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_hc05_mspm0_syscfg_instances():
    """mspm0 母版：HC05_UART（UART2, 9600, RX 中断）+ HC05 GPIO（STATE 输入 +
    KEY 输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const HC05_UART = UART.addInstance();" in syscfg
    assert 'HC05_UART.peripheral.$assign = "UART2";' in syscfg
    assert "HC05_UART.targetBaudRate    = 9600;" in syscfg
    assert 'HC05_UART.peripheral.rxPin.$assign = "PA24";' in syscfg
    assert 'HC05_UART.peripheral.txPin.$assign = "PA23";' in syscfg
    assert "const HC05 = GPIO.addInstance();" in syscfg
    assert 'HC05.associatedPins[0].$name            = "STATE";' in syscfg
    assert 'HC05.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'HC05.associatedPins[0].pin.$assign      = "PA8";' in syscfg
    assert 'HC05.associatedPins[1].$name            = "KEY";' in syscfg
    assert 'HC05.associatedPins[1].direction        = "OUTPUT";' in syscfg
    assert 'HC05.associatedPins[1].pin.$assign      = "PB24";' in syscfg


def test_hc05_mspm0_single_select_generation(tmp_path):
    """hc05 mspm0 单选生成：syscfg 只留 HC05_UART+HC05、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["hc05"])
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
    assert "const HC05_UART = UART.addInstance();" in syscfg
    assert "const HC05 = GPIO.addInstance();" in syscfg
    assert 'HC05_UART.peripheral.rxPin.$assign = "PA24";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "JOYSTICK",
        "NRF24L01", "IR_REMOTE", "DIGIT_UART", "DEBUG_UART", "UWB_UART",
        "ZIGBEE_UART", "IMU601", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/hc05/code/hc05.c").is_file()
    assert (out / "modules/hc05/code/hc05.h").is_file()


# ---------------------------------------------------------------------------
# wiki-stm32-batch8/02：stm32 平台条目（UART_1/UWB 互替 + RX 中断聚合）
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "hc05_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    hc05_init();\n"
    "    hc05_send_char('h');\n"
    "    hc05_send_string(\"hello\");\n"
    "    static const uint8_t data[4] = {1, 2, 3, 4};\n"
    "    hc05_send_buffer(data, 4);\n"
    "    static uint8_t buf[32];\n"
    "    (void)hc05_available();\n"
    "    (void)hc05_receive(buf, sizeof(buf));\n"
    "    (void)hc05_is_connected();\n"
    "    hc05_at_mode_enter();\n"
    "    hc05_at_mode_exit();\n"
    "    hc05_clear_rx();\n"
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
    (r"\bUSART_Init\b", "USART_Init（走 ml_uart）"),
    (r"\bUSART_ITConfig\b", "USART_ITConfig（聚合归 isr.c）"),
    (r"\bvoid\s+USART[123]_IRQHandler\b", "USARTx_IRQHandler 定义（归母版 isr.c）"),
    (r"\bBSP_BLUETOOTH\b", "BSP_BLUETOOTH（页面宏）"),
]


def test_hc05_manifest_shape_stm32():
    """stm32 条目：四角色（TX=PA9/RX=PA10/STATE=PA8/KEY=PB4），TX 带实例宏。"""
    manifest = ModuleManifest.load(MODULES / "hc05")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "hc05_stm32.c",
        "hc05_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "hc05" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (
            "HC05_TX",
            "uart_tx",
            "PA9",
            True,
            ("HC05_UART", "HC05_UART_INST", "HC05_UART_TX_GPIO", "HC05_UART_TX_Pin"),
        ),
        ("HC05_RX", "uart_rx", "PA10", True, ("HC05_UART_RX_GPIO", "HC05_UART_RX_Pin")),
        ("HC05_STATE", "gpio_in", "PA8", True, ("HC05_STATE_GPIO", "HC05_STATE_PIN")),
        ("HC05_KEY", "gpio_out", "PB4", True, ("HC05_KEY_GPIO", "HC05_KEY_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/hc05-bluetooth-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/rf--hc05-bluetooth-module.md",
        "UART_1",
        "9600",
        "互替件",
        "hc05_rx_handler",
        "未上板",
    ):
        assert needle in stm32.notes


def test_hc05_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：hc05 十宏在母版 pin_config.h（UART_1/USART1/PA9/PA10/PA8/PB4）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+HC05_UART\s+UART_1", text)
    assert re.search(r"#define\s+HC05_UART_INST\s+USART1", text)
    assert re.search(r"#define\s+HC05_UART_TX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+HC05_UART_TX_Pin\s+Pin_9", text)
    assert re.search(r"#define\s+HC05_UART_RX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+HC05_UART_RX_Pin\s+Pin_10", text)
    assert re.search(r"#define\s+HC05_STATE_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+HC05_STATE_PIN\s+Pin_8", text)
    assert re.search(r"#define\s+HC05_KEY_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+HC05_KEY_PIN\s+Pin_4", text)
    # 默认聚合：USART1_IRQ_CALLS 含 hc05_rx_handler（isr.c 强/弱符号配对）
    m = re.search(r"#define\s+USART1_IRQ_CALLS\s+(.*)", text)
    assert m is not None
    assert "hc05_rx_handler();" in m.group(1)


def test_hc05_stm32_isr_weak_stub():
    """母版 isr.c：__weak hc05_rx_handler 空兜底（选中模块强定义覆盖）。"""
    text = (STM32_MASTER / "isr.c").read_text(encoding="utf-8")
    assert "__weak void hc05_rx_handler(void) {}" in text


def test_hc05_stm32_pinwriter_roles_registered():
    """pinwriter：_UART_CALLS_ROLES 含 HC05_UART→hc05_rx_handler（聚合重分组）。"""
    text = Path(__file__).resolve().parents[1] / "src" / "contest_generator" / "pinwriter.py"
    src = text.read_text(encoding="utf-8")
    assert '"HC05_UART", "hc05_rx_handler"' in src


def test_hc05_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 hc05_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["hc05"])
    assert {m.slug for m in resolved.manifests} == {"hc05"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/hc05/code/hc05_stm32.c").is_file()
    assert (out / "modules/hc05/code/hc05_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("hc05_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_hc05_stm32_code_guards():
    """stm32 代码层守卫：9600、环形缓冲（% HC05_RX_BUF_SIZE）、hc05_rx_handler、
    走 ml_uart/ml_gpio、零页面宏/标准库残留、无 USARTx_IRQHandler 定义。"""
    c = (MODULES / "hc05" / "code" / "hc05_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "hc05" / "code" / "hc05_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "#define HC05_RX_BUF_SIZE   128u" in h
    assert "#define HC05_CONNECTED_LEVEL 1" in h
    assert "#define HC05_BAUDRATE      9600" in h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 聚合归 isr.c：只定义 hc05_rx_handler，不定义 USARTx_IRQHandler
    assert "void hc05_rx_handler(void)" in code_only
    assert "USART1_IRQHandler" not in code_only
    # 环形缓冲读写 + 溢出丢新字节（背压）
    assert "% HC05_RX_BUF_SIZE" in code_only
    assert "next != _rx_tail" in code_only
    # 换算走母版 ml_uart/ml_gpio + 引脚宏（零引脚字面量）
    assert "uart_pin_init_ex(HC05_UART, HC05_UART_TX_GPIO, HC05_UART_TX_Pin," in code_only
    assert "uart_baud_config(HC05_UART, HC05_BAUDRATE)" in code_only
    assert "uart_sendbyte(HC05_UART" in code_only
    assert "gpio_init(HC05_STATE_GPIO, HC05_STATE_PIN, IU)" in code_only
    assert "gpio_get(HC05_STATE_GPIO, HC05_STATE_PIN)" in code_only
    assert "PA9" not in code_only and "PA10" not in code_only
