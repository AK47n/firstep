"""l298n 大电流电机驱动模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 motor / joystick 同款结构测试：manifest 形状（仅 mspm0、无依赖、
PWM C0/C1 + EN 三角色 = PA14/PB24/PA27——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
L298N_PWM + L298N、模块文件落盘、main.c 调 init/set_duty/set_direction 过
静态门禁）。页面 AO_Control 方向/调速形态与库风格 API 拆分源码守卫钉死
（dir=1 → C0=0/C1=duty；与 motor 分工写入 notes）。
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
    '#include "l298n.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    l298n_init();\n"
    "    l298n_set_duty(1000);\n"
    "    l298n_set_direction(1);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_l298n_manifest_shape_mspm0():
    """l298n：仅 mspm0 平台条目；无依赖；PWM C0/C1 + EN 三角色。"""
    manifest = ModuleManifest.load(MODULES / "l298n")
    assert manifest.slug == "l298n"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["l298n.c", "l298n.h"]
    for rel in mspm0.files:
        assert (MODULES / "l298n" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("L298N_PWM_C0", "pwm", "PA14", True, ()),
        ("L298N_PWM_C1", "pwm", "PB24", True, ()),
        ("L298N_EN", "gpio_out", "PA27", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 与库内 motor(TB6612) 的分工说明必须写入 notes
    assert "motor" in mspm0.notes
    assert "TB6612" in mspm0.notes


def test_l298n_mspm0_syscfg_instances():
    """mspm0 母版：L298N_PWM（TIMG12 C0/C1）+ L298N GPIO（EN）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const L298N_PWM = PWM.addInstance();" in syscfg
    assert 'L298N_PWM.peripheral.$assign = "TIMG12";' in syscfg
    assert 'L298N_PWM.peripheral.ccp0Pin.$assign = "PA14";' in syscfg
    assert 'L298N_PWM.peripheral.ccp1Pin.$assign = "PB24";' in syscfg
    assert "const L298N = GPIO.addInstance();" in syscfg
    assert 'L298N.associatedPins[0].$name            = "EN";' in syscfg
    assert 'L298N.associatedPins[0].direction        = "OUTPUT";' in syscfg
    assert 'L298N.associatedPins[0].pin.$assign      = "PA27";' in syscfg


def test_l298n_mspm0_single_select_generation(tmp_path):
    """l298n mspm0 单选生成：syscfg 只留 L298N_PWM + L298N、文件落盘、门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["l298n"])
    assert {m.slug for m in resolved.manifests} == {"l298n"}
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
    assert "const L298N_PWM = PWM.addInstance();" in syscfg
    assert "const L298N = GPIO.addInstance();" in syscfg
    assert 'L298N_PWM.peripheral.ccp0Pin.$assign = "PA14";' in syscfg
    assert 'L298N_PWM.peripheral.ccp1Pin.$assign = "PB24";' in syscfg
    assert 'L298N.associatedPins[0].pin.$assign      = "PA27";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "BH1750", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "SHT30", "SHT20", "JY61P", "PWMAB",
        "SERVO_PWM", "OPENMV4_UART",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/l298n/code/l298n.c").is_file()
    assert (out / "modules/l298n/code/l298n.h").is_file()


def test_l298n_ao_control_shapes_and_calls_guards():
    """页面 AO_Control 方向/调速形态守卫（防回潮）：dir=1 → C0=0/C1=duty、
    dir=0 → C0=duty/C1=0；DL_Timer_setCaptureCompareValue + C0/C1 IDX 宏；
    限幅 L298N_PWM_PERIOD-1；EN 置高；无编码器/无 GPIO 中断。"""
    source = (MODULES / "l298n" / "code" / "l298n.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "l298n" / "code" / "l298n.h").read_text(
        encoding="utf-8"
    )
    # 页面形态：dir=1 分支 C0=0/C1=duty；dir=0 分支 C0=duty/C1=0
    assert "l298n_dir == 1" in source
    assert source.count("L298N_PWM_C0_IDX") >= 2
    assert source.count("L298N_PWM_C1_IDX") >= 2
    assert "DL_Timer_setCaptureCompareValue" in source
    # 库 API 三函数 + 页面 A 端口范围说明
    for fn in ("l298n_init", "l298n_set_duty", "l298n_set_direction"):
        assert fn in header
    # 限幅
    assert "L298N_PWM_PERIOD - 1u" in source
    assert "L298N_PWM_PERIOD" in header
    # EN 使能置高（页面 5V 使能高有效）
    assert "L298N_EN_PIN" in source
    # 无编码器脚 / 无 GPIO 中断（GROUP1 保留给 motor 编码器先例）
    assert "encoder" not in source
    assert "IRQHandler" not in source
    assert "printf" not in source
