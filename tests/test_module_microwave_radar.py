"""microwave_radar 微波多普勒雷达模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 human_ir/ttp224 同款结构测试：manifest 形状（仅 mspm0、无依赖、单角色
MICROWAVE_OUT = gpio_in PA31——默认与母版 syscfg 一致性由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 MICROWAVE、模块
文件落盘、main.c 调 init/read 过静态门禁）。极性（按页面自一致：检测到=输出
低——页面注释 + main 演示同口径）以 MICROWAVE_TRIGGER_LEVEL 单点反相宏
守卫钉死；页面演示开/关门时序归生成骨架（ADR 0009）以「无演示时序」守卫。
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
    '#include "microwave_radar.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    microwave_radar_init();\n"
    "    uint8_t detected = microwave_radar_read();\n"
    "    (void)detected;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_microwave_radar_manifest_shape_mspm0():
    """microwave_radar：仅 mspm0 平台条目；无依赖；单角色 gpio_in 上拉输入。"""
    manifest = ModuleManifest.load(MODULES / "microwave_radar")
    assert manifest.slug == "microwave_radar"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == [
        "microwave_radar.c",
        "microwave_radar.h",
    ]
    for rel in mspm0.files:
        assert (MODULES / "microwave_radar" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MICROWAVE_OUT", "gpio_in", "PA31", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 页面演示时序归骨架 + 极性按页面说明必须写入 notes
    assert "归生成骨架" in mspm0.notes
    assert "低" in mspm0.notes


def test_microwave_radar_mspm0_syscfg_instances():
    """mspm0 母版：MICROWAVE GPIO 实例（OUT 输入，内部上拉，默认 PA31）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const MICROWAVE = GPIO.addInstance();" in syscfg
    assert 'MICROWAVE.associatedPins[0].$name            = "OUT";' in syscfg
    assert 'MICROWAVE.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'MICROWAVE.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'MICROWAVE.associatedPins[0].pin.$assign      = "PA31";' in syscfg


def test_microwave_radar_mspm0_single_select_generation(tmp_path):
    """microwave_radar mspm0 单选生成：syscfg 只留 MICROWAVE、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["microwave_radar"])
    assert {m.slug for m in resolved.manifests} == {"microwave_radar"}
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
    assert "const MICROWAVE = GPIO.addInstance();" in syscfg
    assert 'MICROWAVE.associatedPins[0].pin.$assign      = "PA31";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "IR_REMOTE", "NRF24L01", "HUMAN_IR",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/microwave_radar/code/microwave_radar.c").is_file()
    assert (out / "modules/microwave_radar/code/microwave_radar.h").is_file()


def test_microwave_radar_polarity_and_no_demo_guards():
    """页面极性（检测到=输出低）与单点反相宏守卫（防回潮）：
    MICROWAVE_TRIGGER_LEVEL 默认 0u（页面注释+演示自一致——低=检测到）、read
    返回 level == 宏（1=检测到移动）、页面演示时序不落码（开/关门 flag/time
    逻辑归生成骨架——ADR 0009）、无页面残留命名（OUTPIN_Scanf/OUT_IN 不落码）。"""
    source = (MODULES / "microwave_radar" / "code" / "microwave_radar.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "microwave_radar" / "code" / "microwave_radar.h").read_text(
        encoding="utf-8"
    )
    assert "MICROWAVE_TRIGGER_LEVEL 0u" in header
    assert "level == MICROWAVE_TRIGGER_LEVEL" in source
    assert "MICROWAVE_OUT_PIN" in source
    assert "OUTPIN_Scanf" not in source  # 页面命名残留守卫
    assert "GPIO_OUT_PIN" not in source
    assert "flag" not in source and "time" not in source  # 演示时序归骨架
    assert "1=检测到移动" in header  # read 语义守卫
