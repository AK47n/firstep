"""us016 模拟量超声波模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / aht10 / dht11 同款结构测试：manifest 形状（仅 mspm0、依赖
adc、单角色 US016_OUT_CH0 = adc PA24——与 adc 模块共享 ADC12_0 MEM0 槽位
薄封装）、mspm0 单选生成（syscfg 裁剪保留 ADC12_0、us016 + 依赖 adc 模块
文件落盘、main.c 调 init/读距离过静态门禁）。全程无 LLM、无服务。
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
    '#include "us016.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    us016_init();\n"
    "    float d = us016_read_distance_cm();\n"
    "    (void)d;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_us016_manifest_shape_mspm0():
    """us016：仅 mspm0 平台条目；依赖 adc；单角色 = adc PA24（MEM0 槽位）。"""
    manifest = ModuleManifest.load(MODULES / "us016")
    assert manifest.slug == "us016"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["us016.c", "us016.h"]
    for rel in mspm0.files:
        assert (MODULES / "us016" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("US016_OUT_CH0", "adc", "PA24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_us016_mspm0_single_select_generation(tmp_path):
    """us016 mspm0 单选生成：syscfg 保留 ADC12_0（adc 消费实例）、us016 + 依赖
    adc 模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["us016"])
    assert {m.slug for m in resolved.manifests} == {"us016", "adc"}
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
    assert "const ADC12_0 = ADC12.addInstance();" in syscfg
    assert 'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/us016/code/us016.c").is_file()
    assert (out / "modules/us016/code/us016.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()
