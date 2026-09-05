"""human_ir 人体红外感应模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ttp224 同款结构测试：manifest 形状（仅 mspm0、无依赖、单角色
HUMAN_IR_OUT = gpio_in PB8——默认与母版 syscfg 一致性由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 HUMAN_IR、模块
文件落盘、main.c 调 init/read 过静态门禁）。极性定稿（感应到=输出高——按
模块介绍/规格；页面函数注释 0=感应到 与介绍矛盾已按 HC-SR501 器件标准修正）
以 HUMAN_IR_TRIGGER_LEVEL 单点反相宏守卫钉死。全程无 LLM、无服务。
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
    '#include "human_ir.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    human_ir_init();\n"
    "    uint8_t detected = human_ir_read();\n"
    "    (void)detected;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_human_ir_manifest_shape_mspm0():
    """human_ir：仅 mspm0 平台条目；无依赖；单角色 gpio_in 上拉输入。"""
    manifest = ModuleManifest.load(MODULES / "human_ir")
    assert manifest.slug == "human_ir"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["human_ir.c", "human_ir.h"]
    for rel in mspm0.files:
        assert (MODULES / "human_ir" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("HUMAN_IR_OUT", "gpio_in", "PB8", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 极性修正说明（页面注释与模块介绍矛盾 → 按介绍/规格修正）必须写入 notes
    assert "高" in mspm0.notes
    assert "修正" in mspm0.notes


def test_human_ir_mspm0_syscfg_instances():
    """mspm0 母版：HUMAN_IR GPIO 实例（OUT 输入，内部上拉，默认 PB8）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const HUMAN_IR = GPIO.addInstance();" in syscfg
    assert 'HUMAN_IR.associatedPins[0].$name            = "OUT";' in syscfg
    assert 'HUMAN_IR.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'HUMAN_IR.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'HUMAN_IR.associatedPins[0].pin.$assign      = "PB8";' in syscfg


def test_human_ir_mspm0_single_select_generation(tmp_path):
    """human_ir mspm0 单选生成：syscfg 只留 HUMAN_IR、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["human_ir"])
    assert {m.slug for m in resolved.manifests} == {"human_ir"}
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
    assert "const HUMAN_IR = GPIO.addInstance();" in syscfg
    assert 'HUMAN_IR.associatedPins[0].pin.$assign      = "PB8";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "IR_REMOTE", "NRF24L01", "MICROWAVE",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/human_ir/code/human_ir.c").is_file()
    assert (out / "modules/human_ir/code/human_ir.h").is_file()


def test_human_ir_polarity_guard():
    """页面极性修正与单点反相宏守卫（防回潮）：感应到=输出高（模块介绍/
    规格；页面函数注释「0=感应到」与介绍矛盾已修正——HUMAN_IR_TRIGGER_LEVEL
    默认 1u，实物低有效改 0 即可反相）、read 返回 level == 宏、无页面残留
    命名（Get_HumanIR/GET 宏不落码）。"""
    source = (MODULES / "human_ir" / "code" / "human_ir.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "human_ir" / "code" / "human_ir.h").read_text(
        encoding="utf-8"
    )
    assert "HUMAN_IR_TRIGGER_LEVEL 1u" in header
    assert "level == HUMAN_IR_TRIGGER_LEVEL" in source
    assert "HUMAN_IR_OUT_PIN" in source
    assert "Get_HumanIR" not in source  # 页面命名残留守卫
    assert "GPIO_OUT_PIN" not in source
