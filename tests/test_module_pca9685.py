"""pca9685 16 路舵机驱动模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / dht11 / max7219 同款结构测试：manifest 形状（仅 mspm0、
依赖 delay、双角色 SCL/SDA = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 PCA9685 + delay 展开、模块文件落盘、
main.c 调 init/set_angle/set_pwm 过静态门禁）。软 I2C 位操作不占硬件 I2C
外设（AHT10 先例），PWM 由芯片内部振荡器生成不占 TIMER。
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
    '#include "pca9685.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    pca9685_init(PCA9685_DEFAULT_FREQ_HZ);\n"
    "    pca9685_set_angle(0, 90);\n"
    "    pca9685_set_angle(1, 180);\n"
    "    pca9685_set_pwm(2, 512);\n"
    "    pca9685_set_freq(100);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_pca9685_manifest_shape_mspm0():
    """pca9685：仅 mspm0 平台条目；依赖 delay；双角色 SCL/SDA = gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "pca9685")
    assert manifest.slug == "pca9685"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["pca9685.c", "pca9685.h"]
    for rel in mspm0.files:
        assert (MODULES / "pca9685" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("PCA9685_SCL", "gpio_out", "PB6", True, ()),
        ("PCA9685_SDA", "gpio_out", "PB7", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_pca9685_mspm0_syscfg_instances():
    """mspm0 母版：PCA9685 GPIO 实例（SCL/SDA 输出，SDA 运行时切换）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const PCA9685 = GPIO.addInstance();" in syscfg
    assert 'PCA9685.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'PCA9685.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'PCA9685.associatedPins[0].pin.$assign  = "PB6";' in syscfg
    assert 'PCA9685.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'PCA9685.associatedPins[1].initialValue = "CLEARED";' in syscfg
    assert 'PCA9685.associatedPins[1].pin.$assign  = "PB7";' in syscfg


def test_pca9685_mspm0_single_select_generation(tmp_path):
    """pca9685 mspm0 单选生成：syscfg 只留 PCA9685、依赖 delay 展开、文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["pca9685"])
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
    assert "const PCA9685 = GPIO.addInstance();" in syscfg
    assert 'PCA9685.associatedPins[1].pin.$assign  = "PB7";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "DC_MOTOR",
        "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219", "IR_TX", "DHT11",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/pca9685/code/pca9685.c").is_file()
    assert (out / "modules/pca9685/code/pca9685.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()
