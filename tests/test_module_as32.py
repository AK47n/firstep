"""as32 AS32-TTL-100 LoRa 无线数传模块：真实库 + 真实母版不变量与双平台单选生成。

与 open_mv4 / fingerprint 同款结构测试：manifest 形状（双平台、无依赖、
UART TX/RX 双角色——mspm0 = PA26/PA25（UART3 9600 轮询）、stm32 = PB10/PB11
（**UART_3/ZIGBEE 互替件同脚**，默认共享合法先例——门禁只查用户绑定））、
mspm0 单选生成（syscfg 裁剪保留 AS32_UART）与 stm32 单选生成（uvprojx 注册、
静态门禁）。源码守卫（防回潮）：mspm0 轮询无 IRQHandler/NVIC + stm32 关
RXNEIE（CR1 bit5）+ SR/DR 轮询排空 + cap 截断（无 %MAX 回绕）+ 9600。
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
    '#include "as32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    as32_init();\n"
    "    as32_send_string(\"hello\");\n"
    "    uint8_t tx_hex[2] = {0x01, 0x02};\n"
    "    as32_send_hex(tx_hex, 2);\n"
    "    uint8_t buf[64];\n"
    "    uint16_t n = as32_receive(buf, sizeof(buf));\n"
    "    (void)n;\n"
    "    as32_flush();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "as32_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    as32_init();\n"
    "    as32_send_string(\"hello\");\n"
    "    const uint8_t data[4] = {1, 2, 3, 4};\n"
    "    as32_send_hex(data, 4);\n"
    "    uint8_t buf[32];\n"
    "    (void)as32_receive(buf, sizeof(buf));\n"
    "    as32_flush();\n"
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
    (r"\bUSART_Init\b", "USART_Init（走 ml_uart）"),
    (r"\bUSART_ITConfig\b", "USART_ITConfig（页面中断改轮询）"),
    (r"\bIRQHandler\b", "IRQHandler（轮询件，不进 isr.c 聚合）"),
]


def test_as32_manifest_shape_mspm0():
    """as32：双平台条目（wiki-stm32-batch8/01 补 stm32）；无依赖；UART TX/RX
    双角色（mspm0 = PA26/PA25）。"""
    manifest = ModuleManifest.load(MODULES / "as32")
    assert manifest.slug == "as32"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["as32.c", "as32.h"]
    for rel in mspm0.files:
        assert (MODULES / "as32" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("AS32_UART_TX", "uart_tx", "PA26", True, ()),
        ("AS32_UART_RX", "uart_rx", "PA25", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # UART 放置决策（UART3/实例上限/与 zigbee 互替/页面无 AT）必须写入 notes
    assert "UART3" in mspm0.notes
    assert "实例上限" in mspm0.notes
    assert "zigbee" in mspm0.notes
    assert "页面无 AT" in mspm0.notes
    assert "未上板" in mspm0.notes


def test_as32_mspm0_syscfg_instances():
    """mspm0 母版：AS32_UART（UART3 9600 轮询 PA26(TX)/PA25(RX)）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const AS32_UART = UART.addInstance();" in syscfg
    assert 'AS32_UART.peripheral.$assign = "UART3";' in syscfg
    assert 'AS32_UART.targetBaudRate    = 9600;' in syscfg
    assert 'AS32_UART.enabledInterrupts = [];' in syscfg
    assert 'AS32_UART.peripheral.rxPin.$assign = "PA25";' in syscfg
    assert 'AS32_UART.peripheral.txPin.$assign = "PA26";' in syscfg


def test_as32_mspm0_single_select_generation(tmp_path):
    """as32 mspm0 单选生成：syscfg 只留 AS32_UART（UART3 剥离 ZIGBEE_UART）、
    模块文件落盘、main.c 调用过静态门禁。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["as32"])
    assert {m.slug for m in resolved.manifests} == {"as32"}
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
    assert "const AS32_UART = UART.addInstance();" in syscfg
    assert 'AS32_UART.peripheral.$assign = "UART3";' in syscfg
    assert 'AS32_UART.peripheral.rxPin.$assign = "PA25";' in syscfg
    assert 'AS32_UART.peripheral.txPin.$assign = "PA26";' in syscfg
    for drop in (
        "ZIGBEE_UART", "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM",
        "WS2812", "HX711", "AHT10", "DHT11", "DS18B20", "BH1750", "SR04",
        "JOYSTICK", "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "OLED",
        "I2C_0", "ADC12_0", "SHT30", "SHT20", "JY61P", "L298N_PWM", "L298N",
        "DEBUG_UART", "UWB_UART", "HC05_UART", "FINGERPRINT_UART",
        "OPENMV4_UART", "RELAY",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/as32/code/as32.c").is_file()
    assert (out / "modules/as32/code/as32.h").is_file()


def test_as32_source_guards():
    """mspm0 源码守卫（防回潮）：9600/AS32_UART_INST/轮询 isRXFIFOEmpty/发送
    isBusy+transmitData/截断保护/读后清缓冲/无 IRQHandler/NVIC/printf/页面
    无 AT 注释。"""
    source = (MODULES / "as32" / "code" / "as32.c").read_text(encoding="utf-8")
    header = (MODULES / "as32" / "code" / "as32.h").read_text(encoding="utf-8")
    assert "DL_UART_isRXFIFOEmpty(AS32_UART_INST)" in source  # 轮询排空
    assert "DL_UART_receiveData(AS32_UART_INST)" in source
    assert "DL_UART_isBusy(AS32_UART_INST)" in source  # 发送忙等（页面原样）
    assert "DL_UART_Main_transmitData(AS32_UART_INST" in source
    assert "IRQHandler(" not in source  # 页面 UART_1_INST_IRQHandler 随轮询裁剪
    assert "NVIC_" not in source  # 页面 LOAR_Init NVIC 使能段随轮询裁剪
    assert "AS32_RX_BUF_MAX 300u" in header  # 页面 LOAR_RX_LEN_MAX 300 保留
    assert "截断保护" in source  # 页面模运算回绕修正记录在案
    assert "as32_rx_pending" in source
    assert "as32_flush()" in source  # 读后清缓冲（页面「读到即清」语义）
    assert "printf(" not in source
    assert "AT" in header and "范围外" in header  # 页面无 AT 指令——范围外记录
    assert "无帧结构" in header  # 行分帧/校验归调用方骨架（ADR 0009）


# ---------------------------------------------------------------------------
# wiki-stm32-batch8/01：stm32 平台条目（UART 实例仲裁 + 轮询接收）
# ---------------------------------------------------------------------------


def test_as32_manifest_shape_stm32():
    """stm32 条目：双角色 uart PB10/PB11（UART_3/ZIGBEE 互替同脚），
    TX 角色带实例宏（_UART/_INST），verified 初始 false。"""
    manifest = ModuleManifest.load(MODULES / "as32")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "as32_stm32.c",
        "as32_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "as32" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (
            "AS32_UART_TX",
            "uart_tx",
            "PB10",
            True,
            ("AS32_UART", "AS32_UART_INST", "AS32_UART_TX_GPIO", "AS32_UART_TX_Pin"),
        ),
        (
            "AS32_UART_RX",
            "uart_rx",
            "PB11",
            True,
            ("AS32_UART_RX_GPIO", "AS32_UART_RX_Pin"),
        ),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/as32-lora-wireless-communication-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/rf--as32-lora-wireless-communication-module.md",
        "UART_3",
        "9600",
        "互替件",
        "未上板",
    ):
        assert needle in stm32.notes


def test_as32_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：as32 六宏必须在母版 pin_config.h（UART_3/USART3/PB10/PB11）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+AS32_UART\s+UART_3", text)
    assert re.search(r"#define\s+AS32_UART_INST\s+USART3", text)
    assert re.search(r"#define\s+AS32_UART_TX_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+AS32_UART_TX_Pin\s+Pin_10", text)
    assert re.search(r"#define\s+AS32_UART_RX_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+AS32_UART_RX_Pin\s+Pin_11", text)


def test_as32_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 as32_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["as32"])
    assert {m.slug for m in resolved.manifests} == {"as32"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/as32/code/as32_stm32.c").is_file()
    assert (out / "modules/as32/code/as32_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("as32_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_as32_stm32_code_guards():
    """stm32 代码层守卫：轮询接收（无 IRQHandler/无 %MAX 回绕）、9600 重配、
    关 RXNEIE、SR RXNE 轮询排空、零标准库/寄存器残留（INST + SR/DR 先例）。"""
    c = (MODULES / "as32" / "code" / "as32_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "as32" / "code" / "as32_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "#define AS32_RX_BUF_MAX 300u" in h
    assert "#define AS32_BAUDRATE 9600" in h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 轮询语义：关 RXNEIE + SR/DR 直读；无 isr.c 聚合登记（无 rx_handler）
    assert "CR1 &= (uint16_t)~0x20u" in code_only
    assert "AS32_UART_INST->SR & 0x20u" in code_only
    assert "AS32_UART_INST->DR" in code_only
    assert "rx_handler" not in code_only
    # 截断保护：无 % AS32_RX_BUF_MAX 回绕（页面 (len+1)%MAX 修正）
    assert "% AS32_RX_BUF_MAX" not in code_only
    assert "(AS32_RX_BUF_MAX - 1u)" in code_only
    # 换算走母版 ml_uart + 引脚宏（零引脚字面量）
    assert "uart_pin_init_ex(AS32_UART, AS32_UART_TX_GPIO, AS32_UART_TX_Pin," in code_only
    assert "uart_baud_config(AS32_UART, AS32_BAUDRATE)" in code_only
    assert "uart_sendbyte(AS32_UART" in code_only
    assert "PB10" not in code_only and "PB11" not in code_only
