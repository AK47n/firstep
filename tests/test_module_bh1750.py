"""bh1750 光照度模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 aht10 / dht11 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PA12/PA13——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
BH1750、模块文件落盘、main.c 调 init/start_measure/read_lux 过静态门禁）。
软 I2C 时序走 delay 模块（依赖声明）。
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
    '#include "delay.h"\n'
    '#include "bh1750.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    bh1750_init();\n"
    "    uint8_t ok = bh1750_start_measure();\n"
    "    delay_ms(BH1750_MEASURE_DELAY_MS);\n"
    "    float lux = 0.0f;\n"
    "    ok = bh1750_read_lux(&lux);\n"
    "    (void)ok;\n"
    "    (void)lux;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_bh1750_manifest_shape_mspm0():
    """bh1750：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "bh1750")
    assert manifest.slug == "bh1750"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["bh1750.c", "bh1750.h"]
    for rel in mspm0.files:
        assert (MODULES / "bh1750" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("BH1750_SCL", "gpio_out", "PA12", True, ()),
        ("BH1750_SDA", "gpio_out", "PA13", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_bh1750_mspm0_syscfg_instances():
    """mspm0 母版：BH1750 GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const BH1750 = GPIO.addInstance();" in syscfg
    assert 'BH1750.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'BH1750.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'BH1750.associatedPins[0].pin.$assign  = "PA12";' in syscfg
    assert 'BH1750.associatedPins[1].pin.$assign  = "PA13";' in syscfg


def test_bh1750_mspm0_single_select_generation(tmp_path):
    """bh1750 mspm0 单选生成：syscfg 只留 BH1750、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["bh1750"])
    assert {m.slug for m in resolved.manifests} == {"bh1750", "delay"}
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
    assert "const BH1750 = GPIO.addInstance();" in syscfg
    assert 'BH1750.associatedPins[0].pin.$assign  = "PA12";' in syscfg
    assert 'BH1750.associatedPins[1].pin.$assign  = "PA13";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0",
        "PWMAB",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/bh1750/code/bh1750.c").is_file()
    assert (out / "modules/bh1750/code/bh1750.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()


def test_bh1750_main_c_references_delay():
    """bh1750 头文件对外只给 BH1750_MEASURE_DELAY_MS 宏，等待用 delay_ms。"""
    header = (MODULES / "bh1750" / "code" / "bh1750.h").read_text(
        encoding="utf-8"
    )
    assert "BH1750_MEASURE_DELAY_MS" in header
