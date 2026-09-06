"""as32 AS32-TTL-100 LoRa 无线数传模块：真实库 + 真实母版不变量与 mspm0
单选生成。

与 open_mv4 / fingerprint 同款结构测试：manifest 形状（仅 mspm0、无依赖、
UART TX/RX 双角色 = PA26/PA25——默认与母版 syscfg 一致性由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 AS32_UART（UART3
9600 轮询——与 ZIGBEE_UART 同外设、单选裁剪后独占）、模块文件落盘、main.c
调 init/send_string/send_hex/receive 过静态门禁）。源码守卫（防回潮）：轮询
接收无 IRQHandler/NVIC、AS32_UART_INST、9600、AS32_RX_BUF_MAX 300、发送
DL_UART_isBusy + DL_UART_Main_transmitData、receive 清缓冲 + 截断保护
（页面模运算回绕修正）、页面无 AT。全程无 LLM、无服务。
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


def test_as32_manifest_shape_mspm0():
    """as32：仅 mspm0 平台条目；无依赖；UART TX/RX 双角色（PA26/PA25）。"""
    manifest = ModuleManifest.load(MODULES / "as32")
    assert manifest.slug == "as32"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

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
    """源码守卫（防回潮）：9600/AS32_UART_INST/轮询 isRXFIFOEmpty/发送
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
