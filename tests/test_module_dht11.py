"""dht11 温湿度模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / hx711 / aht10 / sr04 / joystick 同款结构测试：manifest 形状
（仅 mspm0、单角色 DATA = PB7——默认与母版 syscfg 一致性由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 DHT11、模块文件
落盘、main.c 调 init/read 过静态门禁）。单总线延时走 delay 模块（依赖声明）。
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
    '#include "dht11.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    dht11_init();\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    uint8_t ok = dht11_read(&t, &h);\n"
    "    (void)ok;\n"
    "    (void)t;\n"
    "    (void)h;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_dht11_manifest_shape_mspm0():
    """dht11：仅 mspm0 平台条目；依赖 delay；单角色 DATA = gpio_out PB7。"""
    manifest = ModuleManifest.load(MODULES / "dht11")
    assert manifest.slug == "dht11"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["dht11.c", "dht11.h"]
    for rel in mspm0.files:
        assert (MODULES / "dht11" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("DHT11_DATA", "gpio_out", "PB7", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_dht11_mspm0_syscfg_instances():
    """mspm0 母版：DHT11 GPIO 实例（DATA 输出，initialValue SET = 空闲高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const DHT11 = GPIO.addInstance();" in syscfg
    assert 'DHT11.associatedPins[0].$name        = "DATA";' in syscfg
    assert 'DHT11.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'DHT11.associatedPins[0].initialValue = "SET";' in syscfg
    assert 'DHT11.associatedPins[0].pin.$assign  = "PB7";' in syscfg


def test_dht11_mspm0_single_select_generation(tmp_path):
    """dht11 mspm0 单选生成：syscfg 只留 DHT11、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["dht11"])
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
    assert "const DHT11 = GPIO.addInstance();" in syscfg
    assert 'DHT11.associatedPins[0].pin.$assign  = "PB7";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/dht11/code/dht11.c").is_file()
    assert (out / "modules/dht11/code/dht11.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()
