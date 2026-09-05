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
    assert set(manifest.platforms) == {"mspm0"}

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
