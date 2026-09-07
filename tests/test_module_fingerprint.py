"""fingerprint 指纹识别模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 hc05（UART 模块）/ max7219 同款结构测试：manifest 形状（仅 mspm0、依赖
delay、三角色 TX/RX/TOUCH = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 FINGERPRINT_UART + FINGERPRINT + delay
展开、模块文件落盘、main.c 调 init/check/search/enroll 过静态门禁）。
真实 UART 独立实例（UART0 默认）+ **轮询接收**（无 IRQHandler 强符号——
源码守卫钉死）；帧封装按页面原样（包头+指令+校验和镜像测试）。
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
    '#include "fingerprint.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    fingerprint_init();\n"
    "    (void)fingerprint_check_device();\n"
    "    (void)fingerprint_is_touched();\n"
    "    (void)fingerprint_get_image();\n"
    "    (void)fingerprint_img_to_buffer(1);\n"
    "    (void)fingerprint_reg_model();\n"
    "    (void)fingerprint_search();\n"
    "    (void)fingerprint_save_finger(1);\n"
    "    (void)fingerprint_delete_all();\n"
    "    (void)fingerprint_enroll(2);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def fpm10a_body(body: list[int]) -> list[int]:
    """FPM10A 指令段镜像：指令段 + 校验和（前面字节求和 &0xFF，页面原样）。"""
    return body + [(sum(body) & 0xFF)]


def test_fingerprint_page_command_checksums_mirror():
    """页面命令数组校验和镜像（逐字节原样，页面数组值守卫）。

    页面数组：Get_Img={01,00,03,01,00,05}、Search={01,00,08,04,01,00,00,03,
    E7,00,F8}、Delete_All={01,00,03,0D,00,11}——校验和 = 前面字节求和 &0xFF。
    """
    assert fpm10a_body([0x01, 0x00, 0x03, 0x01, 0x00]) == [0x01, 0x00, 0x03, 0x01, 0x00, 0x05]
    assert fpm10a_body([0x01, 0x00, 0x08, 0x04, 0x01, 0x00, 0x00, 0x03, 0xE7, 0x00]) == [
        0x01, 0x00, 0x08, 0x04, 0x01, 0x00, 0x00, 0x03, 0xE7, 0x00, 0xF8,
    ]
    assert fpm10a_body([0x01, 0x00, 0x03, 0x0D, 0x00]) == [0x01, 0x00, 0x03, 0x0D, 0x00, 0x11]


def test_fingerprint_polling_and_frame_source_guards():
    """源码守卫：真实 UART + 轮询（无 IRQHandler）+ 帧封装按页面原样。"""
    source = (MODULES / "fingerprint" / "code" / "fingerprint.c").read_text(
        encoding="utf-8"
    )
    assert "FINGERPRINT_UART_INST_IRQHandler" not in source  # 轮询，无 ISR 强符号
    assert "DL_UART_isRXFIFOEmpty" in source               # 轮询接收
    assert "FINGERPRINT_UART_INST" in source               # 真实 UART 实例
    assert "0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF" in source  # 包头（页面原样）
    assert "0x01, 0x00, 0x03, 0x01, 0x00, 0x05" in source  # Get_Img（页面原样）
    assert "_resp[9]" in source                            # 确认码判定（页面原样）
    assert "FINGERPRINT_NOT_FOUND" in source               # 255 = 未找到


# ---------------------------------------------------------------------------
# 结构 + 生成（既有接缝）
# ---------------------------------------------------------------------------


def test_fingerprint_manifest_shape_mspm0():
    """fingerprint mspm0 条目（stm32 条目见下方 stm32 段）：依赖 delay；
    TX(uart_tx PA28) + RX(uart_rx PA31) + TOUCH(gpio_in PA12)。"""
    manifest = ModuleManifest.load(MODULES / "fingerprint")
    assert manifest.slug == "fingerprint"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["fingerprint.c", "fingerprint.h"]
    for rel in mspm0.files:
        assert (MODULES / "fingerprint" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("FINGERPRINT_TX", "uart_tx", "PA28", True, ()),
        ("FINGERPRINT_RX", "uart_rx", "PA31", True, ()),
        ("FINGERPRINT_TOUCH", "gpio_in", "PA12", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_fingerprint_mspm0_syscfg_instances():
    """mspm0 母版：FINGERPRINT_UART（UART0, 57600, 无中断=轮询）+
    FINGERPRINT GPIO（TOUCH 输入 PA12）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const FINGERPRINT_UART = UART.addInstance();" in syscfg
    assert 'FINGERPRINT_UART.peripheral.$assign = "UART0";' in syscfg
    assert "FINGERPRINT_UART.targetBaudRate    = 57600;" in syscfg
    assert "FINGERPRINT_UART.enabledInterrupts = [];" in syscfg
    assert 'FINGERPRINT_UART.peripheral.rxPin.$assign = "PA31";' in syscfg
    assert 'FINGERPRINT_UART.peripheral.txPin.$assign = "PA28";' in syscfg
    assert "const FINGERPRINT = GPIO.addInstance();" in syscfg
    assert 'FINGERPRINT.associatedPins[0].$name        = "TOUCH";' in syscfg
    assert 'FINGERPRINT.associatedPins[0].direction    = "INPUT";' in syscfg
    assert 'FINGERPRINT.associatedPins[0].pin.$assign  = "PA12";' in syscfg


def test_fingerprint_mspm0_single_select_generation(tmp_path):
    """fingerprint mspm0 单选生成：syscfg 只留 FINGERPRINT_UART+FINGERPRINT、
    依赖 delay 展开、文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["fingerprint"])
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
    assert "const FINGERPRINT_UART = UART.addInstance();" in syscfg
    assert "const FINGERPRINT = GPIO.addInstance();" in syscfg
    assert 'FINGERPRINT_UART.peripheral.$assign = "UART0";' in syscfg
    assert 'FINGERPRINT.associatedPins[0].pin.$assign  = "PA12";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "DEBUG_UART", "UWB_UART", "ZIGBEE_UART", "OLED", "I2C_0",
        "ADC12_0", "DC_MOTOR", "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219",
        "PCA9685", "IR_TX", "NRF24L01", "HC05_UART", "HC05", "JQ8900",
        "SYN6288", "RC522",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/fingerprint/code/fingerprint.c").is_file()
    assert (out / "modules/fingerprint/code/fingerprint.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


# ---------------------------------------------------------------------------
# wiki-stm32-batch9/03：stm32 平台条目（真实 UART 帧协议——UART_1/K230 身份
# 识别互替同脚 + 57600 + RX 中断状态机精确收 12/16 字节——isr.c 聚合扩展）
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "fingerprint_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    fingerprint_init();\n"
    "    (void)fingerprint_check_device();\n"
    "    (void)fingerprint_is_touched();\n"
    "    (void)fingerprint_get_image();\n"
    "    (void)fingerprint_img_to_buffer(0);\n"
    "    (void)fingerprint_reg_model();\n"
    "    (void)fingerprint_search();\n"
    "    (void)fingerprint_save_finger(1);\n"
    "    (void)fingerprint_delete_all();\n"
    "    (void)fingerprint_enroll(1);\n"
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
    (r"\bUART_Init\b", "UART_Init（走 ml_uart）"),
    (r"\bUSART_Init\b", "USART_Init（走 ml_uart）"),
    (r"\bvoid\s+USART[123]_IRQHandler\b", "USARTx_IRQHandler 定义（归母版 isr.c）"),
    (r"\bu2_recv_length\b", "u2_recv_length（页面无上限变量）"),
]


def test_fingerprint_manifest_shape_stm32():
    """stm32 条目：TX(uart_tx PA9)/RX(uart_rx PA10)/TOUCH(gpio_in PB5)，
    TX 带实例宏 + TOUCH 两宏。"""
    manifest = ModuleManifest.load(MODULES / "fingerprint")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "fingerprint_stm32.c",
        "fingerprint_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "fingerprint" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (
            "FINGERPRINT_TX",
            "uart_tx",
            "PA9",
            True,
            (
                "FINGERPRINT_UART",
                "FINGERPRINT_UART_INST",
                "FINGERPRINT_UART_TX_GPIO",
                "FINGERPRINT_UART_TX_Pin",
            ),
        ),
        (
            "FINGERPRINT_RX",
            "uart_rx",
            "PA10",
            True,
            ("FINGERPRINT_UART_RX_GPIO", "FINGERPRINT_UART_RX_Pin"),
        ),
        (
            "FINGERPRINT_TOUCH",
            "gpio_in",
            "PB5",
            True,
            ("FINGERPRINT_TOUCH_GPIO", "FINGERPRINT_TOUCH_PIN"),
        ),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/fingerprint-recognition-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--fingerprint-recognition-sensor.md",
        "57600",
        "UART_1",
        "互替",
        "fingerprint_rx_handler",
        "精确收 12/16",
        "无上限越界修正",
        "未上板",
    ):
        assert needle in stm32.notes


def test_fingerprint_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：fingerprint 八宏在母版 pin_config.h（UART_1/USART1/
    PA9/PA10/PB5）+ 默认聚合 USART1_IRQ_CALLS 含 fingerprint_rx_handler。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+FINGERPRINT_UART\s+UART_1", text)
    assert re.search(r"#define\s+FINGERPRINT_UART_INST\s+USART1", text)
    assert re.search(r"#define\s+FINGERPRINT_UART_TX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+FINGERPRINT_UART_TX_Pin\s+Pin_9", text)
    assert re.search(r"#define\s+FINGERPRINT_UART_RX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+FINGERPRINT_UART_RX_Pin\s+Pin_10", text)
    assert re.search(r"#define\s+FINGERPRINT_TOUCH_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+FINGERPRINT_TOUCH_PIN\s+Pin_5", text)
    m = re.search(r"#define\s+USART1_IRQ_CALLS\s+(.*)", text)
    assert m is not None
    assert "fingerprint_rx_handler();" in m.group(1)


def test_fingerprint_stm32_isr_weak_stub():
    """母版 isr.c：__weak fingerprint_rx_handler 空兜底（选中模块强定义覆盖）。"""
    text = (STM32_MASTER / "isr.c").read_text(encoding="utf-8")
    assert "__weak void fingerprint_rx_handler(void) {}" in text


def test_fingerprint_stm32_pinwriter_roles_registered():
    """pinwriter：_UART_CALLS_ROLES 含 FINGERPRINT_UART→fingerprint_rx_handler。"""
    text = (
        Path(__file__).resolve().parents[1] / "src" / "contest_generator"
        / "pinwriter.py"
    )
    src = text.read_text(encoding="utf-8")
    assert '"FINGERPRINT_UART", "fingerprint_rx_handler"' in src


def test_fingerprint_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 fingerprint_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["fingerprint"])
    assert {m.slug for m in resolved.manifests} == {"fingerprint", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/fingerprint/code/fingerprint_stm32.c").is_file()
    assert (out / "modules/fingerprint/code/fingerprint_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("fingerprint_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_fingerprint_stm32_code_guards():
    """stm32 代码层守卫：57600、帧头、状态机精确收 12/16（Len 字段）、
    无页面无上限变量/IRQHandler 定义/printf；API 全族断言。"""
    c = (MODULES / "fingerprint" / "code" / "fingerprint_stm32.c").read_text(
        encoding="utf-8"
    )
    h = (MODULES / "fingerprint" / "code" / "fingerprint_stm32.h").read_text(
        encoding="utf-8"
    )
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 常量与帧协议
    assert "#define FINGERPRINT_RX_BUF_SIZE  32u" in h
    assert "#define FINGERPRINT_BAUDRATE     57600" in h
    assert "0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF" in code_only  # 包头（页面原样）
    assert "0x01, 0x00, 0x03, 0x01, 0x00, 0x05" in code_only  # Get_Img（页面原样）
    # RX 状态机：帧头同步 + Len 大端解析精确收齐（页面 u2_recv_length++ 无上限修正）
    assert "FINGERPRINT_UART_INST->SR & 0x20u" in code_only
    assert "_pack_head[_rx_head]" in code_only
    assert "((uint16_t)_rx[7] << 8) | _rx[8]" in code_only  # Len 大端
    assert "_rx_flag = 1;" in code_only                     # 整帧收齐
    assert "_wait_response(12u)" in code_only               # 12 字节响应
    assert "_wait_response(16u)" in code_only               # search 16 字节
    assert "_resp[9]" in code_only                          # 确认码判定
    # 服务函数全族（10 函数名——与 mspm0 fingerprint.h 同名同型）
    assert "void fingerprint_init(" in code_only
    for fn in (
        "fingerprint_check_device",
        "fingerprint_is_touched",
        "fingerprint_get_image",
        "fingerprint_img_to_buffer",
        "fingerprint_reg_model",
        "fingerprint_save_finger",
        "fingerprint_delete_all",
        "fingerprint_enroll",
    ):
        assert f"uint8_t {fn}(" in code_only, fn
    assert "uint16_t fingerprint_search(" in code_only
    # 换算走母版 ml_uart/ml_gpio + 引脚宏（零引脚字面量）
    assert "uart_pin_init_ex(FINGERPRINT_UART, FINGERPRINT_UART_TX_GPIO," in code_only
    assert "uart_baud_config(FINGERPRINT_UART, FINGERPRINT_BAUDRATE)" in code_only
    assert "uart_sendbyte(FINGERPRINT_UART" in code_only
    assert "gpio_init(FINGERPRINT_TOUCH_GPIO, FINGERPRINT_TOUCH_PIN, IU)" in code_only
    assert "gpio_get(FINGERPRINT_TOUCH_GPIO, FINGERPRINT_TOUCH_PIN)" in code_only
    assert "PA9" not in code_only and "PA10" not in code_only
