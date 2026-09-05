"""ttp224 4 路电容触摸模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / dht11 同款结构测试：manifest 形状（仅 mspm0、无依赖、
四角色 gpio_in = PA22/PA25/PA26/PA27——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
TTP224、模块文件落盘、main.c 调 init/read/read_all 过静态门禁）。页面极性
= 引脚高=触摸（TTP224_TOUCH_LEVEL 单点反相宏）与 4 位掩码以源码守卫钉死。
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
    '#include "ttp224.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ttp224_init();\n"
    "    uint8_t k1 = ttp224_read(1);\n"
    "    uint8_t k4 = ttp224_read(4);\n"
    "    uint8_t all = ttp224_read_all();\n"
    "    (void)k1;\n"
    "    (void)k4;\n"
    "    (void)all;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ttp224_manifest_shape_mspm0():
    """ttp224：仅 mspm0 平台条目；无依赖；四角色 gpio_in 上拉输入。"""
    manifest = ModuleManifest.load(MODULES / "ttp224")
    assert manifest.slug == "ttp224"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ttp224.c", "ttp224.h"]
    for rel in mspm0.files:
        assert (MODULES / "ttp224" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("TTP224_OUT1", "gpio_in", "PA22", True, ()),
        ("TTP224_OUT2", "gpio_in", "PA25", True, ()),
        ("TTP224_OUT3", "gpio_in", "PA26", True, ()),
        ("TTP224_OUT4", "gpio_in", "PA27", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_ttp224_mspm0_syscfg_instances():
    """mspm0 母版：TTP224 GPIO 实例（OUT1-4 输入，内部上拉）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const TTP224 = GPIO.addInstance();" in syscfg
    for i, name in enumerate(("OUT1", "OUT2", "OUT3", "OUT4"), start=0):
        assert f'TTP224.associatedPins[{i}].$name            = "{name}";' in syscfg
        assert f'TTP224.associatedPins[{i}].direction        = "INPUT";' in syscfg
        assert f'TTP224.associatedPins[{i}].internalResistor = "PULL_UP";' in syscfg
    assert 'TTP224.associatedPins[0].pin.$assign      = "PA22";' in syscfg
    assert 'TTP224.associatedPins[1].pin.$assign      = "PA25";' in syscfg
    assert 'TTP224.associatedPins[2].pin.$assign      = "PA26";' in syscfg
    assert 'TTP224.associatedPins[3].pin.$assign      = "PA27";' in syscfg


def test_ttp224_mspm0_single_select_generation(tmp_path):
    """ttp224 mspm0 单选生成：syscfg 只留 TTP224、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ttp224"])
    assert {m.slug for m in resolved.manifests} == {"ttp224"}
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
    assert "const TTP224 = GPIO.addInstance();" in syscfg
    assert 'TTP224.associatedPins[0].pin.$assign      = "PA22";' in syscfg
    assert 'TTP224.associatedPins[3].pin.$assign      = "PA27";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "IR_REMOTE", "NRF24L01",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ttp224/code/ttp224.c").is_file()
    assert (out / "modules/ttp224/code/ttp224.h").is_file()


def test_ttp224_polarity_and_mask_guards():
    """页面极性（引脚高=触摸）与 4 位掩码守卫：单点反相宏
    TTP224_TOUCH_LEVEL（默认 1 = 高有效，低有效改 0）、read 返回
    level == 宏、read_all 按 ch-1 位移位生成 bit0-3。"""
    source = (MODULES / "ttp224" / "code" / "ttp224.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "ttp224" / "code" / "ttp224.h").read_text(
        encoding="utf-8"
    )
    assert "TTP224_TOUCH_LEVEL 1u" in header
    assert "level == TTP224_TOUCH_LEVEL" in source
    assert "1u << (ch - 1)" in source
    assert "ch <= TTP224_CHANNELS" in source
    # 页面 4 键序（Key_IN1-4 → 通道 1-4；无 5+ 通道）
    assert "channel" in source
    assert "TTP224_OUT4_PIN" in source
