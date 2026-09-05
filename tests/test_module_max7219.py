"""max7219 数码管/点阵模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / hx711 / aht10 / sr04 / joystick / dht11 同款结构测试：manifest
形状（仅 mspm0、无依赖、三角色 DIN/CLK/CS = 母版 syscfg 由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 MAX7219、模块
文件落盘、main.c 调 init/write_digit/write_matrix 过静态门禁）。单模块
双形态（数码管 BCD / 点阵行直通），软 SPI 位操作不占硬件 SPI 外设。
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
    '#include "max7219.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    max7219_init(MAX7219_FORM_DIGIT, 3);\n"
    "    max7219_write_digit(1, 3);\n"
    "    uint8_t rows[8] = {0x3C, 0x42, 0x42, 0x42, 0x42, 0x42, 0x66, 0x38};\n"
    "    max7219_init(MAX7219_FORM_MATRIX, 1);\n"
    "    max7219_write_matrix(rows, 1);\n"
    "    max7219_clear();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_max7219_manifest_shape_mspm0():
    """max7219：仅 mspm0 平台条目；无依赖；三角色 DIN/CLK/CS = gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "max7219")
    assert manifest.slug == "max7219"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["max7219.c", "max7219.h"]
    for rel in mspm0.files:
        assert (MODULES / "max7219" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MAX7219_DIN", "gpio_out", "PB9", True, ()),
        ("MAX7219_CLK", "gpio_out", "PA18", True, ()),
        ("MAX7219_CS", "gpio_out", "PB18", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_max7219_mspm0_syscfg_instances():
    """mspm0 母版：MAX7219 GPIO 实例（DIN/CLK/CS 三输出，CS 初始高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const MAX7219 = GPIO.addInstance();" in syscfg
    assert 'MAX7219.associatedPins[0].$name        = "DIN";' in syscfg
    assert 'MAX7219.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'MAX7219.associatedPins[0].pin.$assign  = "PB9";' in syscfg
    assert 'MAX7219.associatedPins[1].pin.$assign  = "PA18";' in syscfg
    assert 'MAX7219.associatedPins[2].$name        = "CS";' in syscfg
    assert 'MAX7219.associatedPins[2].initialValue = "SET";' in syscfg
    assert 'MAX7219.associatedPins[2].pin.$assign  = "PB18";' in syscfg


def test_max7219_mspm0_single_select_generation(tmp_path):
    """max7219 mspm0 单选生成：syscfg 只留 MAX7219、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["max7219"])
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
    assert "const MAX7219 = GPIO.addInstance();" in syscfg
    assert 'MAX7219.associatedPins[2].pin.$assign  = "PB18";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "DC_MOTOR",
        "PWMAB", "SERVO_PWM", "IR_REMOTE", "PCA9685", "IR_TX",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/max7219/code/max7219.c").is_file()
    assert (out / "modules/max7219/code/max7219.h").is_file()
