"""nrf24l01 2.4G 无线模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / hc05 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
六角色默认 = 母版 syscfg 由 test_pins.py / test_pin_bindings.py 守）、
mspm0 单选生成（syscfg 裁剪保留 NRF24L01 + delay 依赖文件落盘、main.c 调
init/收发过静态门禁）。软 SPI 位操作不占 SPI 外设；IRQ 轮询不注册 GROUP1
中断（motor 编码器独占）。全程无 LLM、无服务。
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
    '#include "nrf24l01.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    nrf24l01_init();\n"
    "    nrf24l01_set_mode(NRF24L01_MODE_TX);\n"
    "    uint8_t tx[8] = {1, 2, 3, 4, 5, 6, 7, 8};\n"
    "    uint8_t result = nrf24l01_tx_packet(tx, 8);\n"
    "    (void)result;\n"
    "    nrf24l01_set_mode(NRF24L01_MODE_RX);\n"
    "    uint8_t rx[32];\n"
    "    uint8_t got = nrf24l01_rx_packet(rx, sizeof(rx));\n"
    "    (void)got;\n"
    "    nrf24l01_flush_rx();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_nrf24l01_manifest_shape_mspm0():
    """nrf24l01：仅 mspm0 平台条目；依赖 delay；六角色默认。"""
    manifest = ModuleManifest.load(MODULES / "nrf24l01")
    assert manifest.slug == "nrf24l01"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["nrf24l01.c", "nrf24l01.h"]
    for rel in mspm0.files:
        assert (MODULES / "nrf24l01" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("NRF24L01_CLK", "gpio_out", "PA26", True, ()),
        ("NRF24L01_MOSI", "gpio_out", "PA25", True, ()),
        ("NRF24L01_MISO", "gpio_in", "PA9", True, ()),
        ("NRF24L01_CSN", "gpio_out", "PA24", True, ()),
        ("NRF24L01_CE", "gpio_out", "PA23", True, ()),
        ("NRF24L01_IRQ", "gpio_in", "PA22", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_nrf24l01_mspm0_syscfg_instance():
    """mspm0 母版必须有 NRF24L01 GPIO 实例：6 引脚（CLK/MOSI/MISO/CSN/CE/IRQ）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const NRF24L01 = GPIO.addInstance();" in syscfg
    assert "NRF24L01.associatedPins.create(6);" in syscfg
    assert 'NRF24L01.associatedPins[0].$name        = "CLK";' in syscfg
    assert 'NRF24L01.associatedPins[0].pin.$assign  = "PA26";' in syscfg
    assert 'NRF24L01.associatedPins[1].$name        = "MOSI";' in syscfg
    assert 'NRF24L01.associatedPins[1].pin.$assign  = "PA25";' in syscfg
    assert 'NRF24L01.associatedPins[2].$name        = "MISO";' in syscfg
    assert 'NRF24L01.associatedPins[2].direction    = "INPUT";' in syscfg
    assert 'NRF24L01.associatedPins[2].pin.$assign  = "PA9";' in syscfg
    assert 'NRF24L01.associatedPins[3].$name        = "CSN";' in syscfg
    assert 'NRF24L01.associatedPins[3].pin.$assign  = "PA24";' in syscfg
    assert 'NRF24L01.associatedPins[4].$name        = "CE";' in syscfg
    assert 'NRF24L01.associatedPins[4].pin.$assign  = "PA23";' in syscfg
    assert 'NRF24L01.associatedPins[5].$name        = "IRQ";' in syscfg
    assert 'NRF24L01.associatedPins[5].direction    = "INPUT";' in syscfg
    assert 'NRF24L01.associatedPins[5].pin.$assign  = "PA22";' in syscfg


def test_nrf24l01_mspm0_single_select_generation(tmp_path):
    """nrf24l01 mspm0 单选生成：syscfg 只留 NRF24L01、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["nrf24l01"])
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
    assert "const NRF24L01 = GPIO.addInstance();" in syscfg
    assert 'NRF24L01.associatedPins[0].pin.$assign  = "PA26";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "JOYSTICK",
        "HC05", "IR_REMOTE", "DIGIT_UART", "DEBUG_UART", "UWB_UART",
        "ZIGBEE_UART", "IMU601", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/nrf24l01/code/nrf24l01.c").is_file()
    assert (out / "modules/nrf24l01/code/nrf24l01.h").is_file()
    # 依赖展开：delay 模块文件随选中落盘
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()
