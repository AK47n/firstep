"""joystick 双轴摇杆模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / hx711 / aht10 / sr04 同款结构测试：manifest 形状（仅 mspm0、
三角色默认 = 母版 syscfg 由 test_pins.py / test_pin_bindings.py 守）、
mspm0 单选生成（syscfg 裁剪保留 JOYSTICK + ADC12_0、模块文件落盘、
main.c 调 init/读轴/读键过静态门禁）。摇杆 X/Y 与 adc 模块共享 ADC12_0
实例（sequence 三通道——MEM1=PA26/A0_1、MEM2=PA25/A0_2），SW 独立
GPIO 输入（PA9）。全程无 LLM、无服务。
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
    '#include "joystick.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    joystick_init();\n"
    "    uint16_t x = joystick_read_x_percent();\n"
    "    uint16_t y = joystick_read_y_percent();\n"
    "    uint8_t sw = joystick_read_sw();\n"
    "    (void)x;\n"
    "    (void)y;\n"
    "    (void)sw;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_joystick_manifest_shape_mspm0():
    """joystick：仅 mspm0 平台条目；无依赖；X(adc PA26) + Y(adc PA25) + SW(gpio_in PA9)。"""
    manifest = ModuleManifest.load(MODULES / "joystick")
    assert manifest.slug == "joystick"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["joystick.c", "joystick.h"]
    for rel in mspm0.files:
        assert (MODULES / "joystick" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("JOYSTICK_X_CH1", "adc", "PA26", True, ()),
        ("JOYSTICK_Y_CH2", "adc", "PA25", True, ()),
        ("JOYSTICK_SW", "gpio_in", "PA9", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_joystick_mspm0_syscfg_instances():
    """mspm0 母版：JOYSTICK GPIO 实例（SW=PA9 上拉输入）+ ADC12_0 三通道
    sequence（adcPin1=PA26/A0_1、adcPin2=PA25/A0_2、adcPin3=PA24/A0_3）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const JOYSTICK = GPIO.addInstance();" in syscfg
    assert 'JOYSTICK.associatedPins[0].$name            = "SW";' in syscfg
    assert 'JOYSTICK.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'JOYSTICK.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'JOYSTICK.associatedPins[0].pin.$assign  = "PA9";' in syscfg
    assert 'ADC12_0.samplingOperationMode      = "sequence";' in syscfg
    assert 'ADC12_0.adcMem1chansel             = "DL_ADC12_INPUT_CHAN_1";' in syscfg
    assert 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' in syscfg
    assert 'ADC12_0.peripheral.adcPin1.$assign  = "PA26";' in syscfg
    assert 'ADC12_0.peripheral.adcPin2.$assign  = "PA25";' in syscfg


def test_joystick_mspm0_single_select_generation(tmp_path):
    """joystick mspm0 单选生成：syscfg 只留 JOYSTICK+ADC12_0、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["joystick"])
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
    assert "const JOYSTICK = GPIO.addInstance();" in syscfg
    assert "const ADC12_0 = ADC12.addInstance();" in syscfg
    assert 'JOYSTICK.associatedPins[0].pin.$assign  = "PA9";' in syscfg
    assert 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART",
        "ZIGBEE_UART", "OLED", "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/joystick/code/joystick.c").is_file()
    assert (out / "modules/joystick/code/joystick.h").is_file()
