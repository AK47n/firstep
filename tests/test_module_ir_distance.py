"""ir_distance 红外测距模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / us016 同款结构测试：manifest 形状（仅 mspm0、无依赖、单角色
IR_DIST_OUT_CH3 = adc PA27——ADC12_0 sequence 四通道 MEM3）、母版 syscfg
共享事实（endAdd=3 / adcMem3chansel=CHAN_0 / adcPin0=PA27，与 adc/joystick/
us016 同实例）、mspm0 单选生成（syscfg 裁剪保留 ADC12_0、模块文件落盘、
main.c 调 init/读距离过静态门禁）。全程无 LLM、无服务。
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
    '#include "ir_distance.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ir_distance_init();\n"
    "    float d = ir_distance_read_distance_cm();\n"
    "    (void)d;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ir_distance_manifest_shape_mspm0():
    """ir_distance：仅 mspm0 平台条目；无依赖；单角色 = adc PA27（MEM3 槽位）。"""
    manifest = ModuleManifest.load(MODULES / "ir_distance")
    assert manifest.slug == "ir_distance"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ir_distance.c", "ir_distance.h"]
    for rel in mspm0.files:
        assert (MODULES / "ir_distance" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("IR_DIST_OUT_CH3", "adc", "PA27", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_ir_distance_mspm0_master_syscfg_shared_facts():
    """母版 ADC12_0 四通道共享事实（JOYSTICK 相关断言同步：endAdd 2→3、
    adcMem3=CHAN_0、adcPin0=PA27 归 ir_distance——手册原脚）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'ADC12_0.samplingOperationMode      = "sequence";' in syscfg
    assert 'ADC12_0.startAdd                   = 0;' in syscfg
    assert 'ADC12_0.endAdd                     = 3;' in syscfg
    assert 'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' in syscfg
    assert 'ADC12_0.adcMem1chansel             = "DL_ADC12_INPUT_CHAN_1";' in syscfg
    assert 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' in syscfg
    assert 'ADC12_0.adcMem3chansel             = "DL_ADC12_INPUT_CHAN_0";' in syscfg
    assert 'ADC12_0.peripheral.adcPin3.$assign = "PA24";' in syscfg
    assert 'ADC12_0.peripheral.adcPin1.$assign  = "PA26";' in syscfg
    assert 'ADC12_0.peripheral.adcPin2.$assign  = "PA25";' in syscfg
    assert 'ADC12_0.peripheral.adcPin0.$assign = "PA27";' in syscfg


def test_ir_distance_mspm0_single_select_generation(tmp_path):
    """ir_distance mspm0 单选生成：syscfg 保留 ADC12_0、模块文件落盘、静态
    门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ir_distance"])
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
    assert 'ADC12_0.endAdd                     = 3;' in syscfg
    assert 'ADC12_0.peripheral.adcPin0.$assign = "PA27";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "BH1750",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ir_distance/code/ir_distance.c").is_file()
    assert (out / "modules/ir_distance/code/ir_distance.h").is_file()
