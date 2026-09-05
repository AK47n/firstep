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
    assert set(manifest.platforms) == {"mspm0"}

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
