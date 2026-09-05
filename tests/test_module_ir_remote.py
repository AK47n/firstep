"""ir_remote 红外遥控接收模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / hc05 / nrf24l01 同款结构测试：manifest 形状（仅 mspm0、依赖
delay、单 GPIO 输入默认 = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 IR_REMOTE + delay 依赖文件落盘、
main.c 调 init/poll/读码过静态门禁）。解码 = CPU 忙等（20us 步进），不占
TIMER、不注册 GPIO 中断（GROUP1 被 motor 编码器独占）。全程无 LLM、无服务。
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
    '#include "ir_remote.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ir_remote_init();\n"
    "    uint8_t result = ir_remote_poll();\n"
    "    (void)result;\n"
    "    (void)ir_remote_has_data();\n"
    "    (void)ir_remote_get_code();\n"
    "    (void)ir_remote_get_address();\n"
    "    ir_remote_clear();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ir_remote_manifest_shape_mspm0():
    """ir_remote：仅 mspm0 平台条目；依赖 delay；单 gpio_in（OUT 默认 PA26）。"""
    manifest = ModuleManifest.load(MODULES / "ir_remote")
    assert manifest.slug == "ir_remote"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ir_remote.c", "ir_remote.h"]
    for rel in mspm0.files:
        assert (MODULES / "ir_remote" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("IR_REMOTE_OUT", "gpio_in", "PA26", True, ()),
    ]
    # 简介判据：硬件身份（kit/source_url 必填）+ 能力方向 + 无题绑定词
    assert mspm0.kit and mspm0.source_url


def test_ir_remote_mspm0_syscfg_instance():
    """mspm0 母版必须有 IR_REMOTE 输入实例（OUT = PA26，上拉）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const IR_REMOTE = GPIO.addInstance();" in syscfg
    assert 'IR_REMOTE.associatedPins[0].$name            = "OUT";' in syscfg
    assert 'IR_REMOTE.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'IR_REMOTE.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'IR_REMOTE.associatedPins[0].pin.$assign      = "PA26";' in syscfg


def test_ir_remote_mspm0_single_select_generation(tmp_path):
    """ir_remote mspm0 单选生成：syscfg 只留 IR_REMOTE、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ir_remote"])
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
    assert "const IR_REMOTE = GPIO.addInstance();" in syscfg
    assert 'IR_REMOTE.associatedPins[0].pin.$assign      = "PA26";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "JOYSTICK",
        "HC05", "NRF24L01", "DIGIT_UART", "DEBUG_UART", "UWB_UART",
        "ZIGBEE_UART", "IMU601", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ir_remote/code/ir_remote.c").is_file()
    assert (out / "modules/ir_remote/code/ir_remote.h").is_file()
    # 依赖展开：delay 模块文件随选中落盘
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()
