"""relay 1 路 5V 继电器模块（GPIO 迷你驱动）：真实库 + 真实母版不变量与
mspm0 单选生成。

与 human_ir / microwave_radar 同款结构测试：manifest 形状（仅 mspm0、无依赖、
单角色 RELAY_OUT = gpio_out PA1——母版 syscfg 由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 RELAY、模块文件
落盘、main.c 调 relay_init/relay_set(0/1) 过静态门禁）。极性归一化守卫
（RELAY_ON_LEVEL 0u = 低电平吸合、relay_set(1)=吸合→clearPins、
relay_set(0)=断开→setPins、init 初始断开）与页面 Set_Relay_Switch 对照
注释钉死（页面 0=吸合/1=断开 → Set_Relay_Switch(s) ≡ relay_set(1-s)）。
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
    '#include "relay.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    relay_init();\n"
    "    relay_set(1);\n"
    "    relay_set(0);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_relay_manifest_shape_mspm0():
    """relay：仅 mspm0 平台条目；无依赖；单角色 = gpio_out PA1（初始断开）。"""
    manifest = ModuleManifest.load(MODULES / "relay")
    assert manifest.slug == "relay"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["relay.c", "relay.h"]
    for rel in mspm0.files:
        assert (MODULES / "relay" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("RELAY_OUT", "gpio_out", "PA1", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 关键 notes 子串：极性归一化对照 + 低电平吸合 + 初始断开
    assert "Set_Relay_Switch" in mspm0.notes
    assert "低电平吸合" in mspm0.notes
    assert "RELAY_ON_LEVEL" in mspm0.notes
    assert "未上板" in mspm0.notes


def test_relay_mspm0_syscfg_instance():
    """mspm0 母版必须有 RELAY 输出实例（OUT = PA1），方向 OUTPUT + 初始 SET
    （模块低电平吸合 → SET = 引脚高 = 初始断开）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const RELAY = GPIO.addInstance();" in syscfg
    assert 'RELAY.associatedPins[0].$name        = "OUT";' in syscfg
    assert 'RELAY.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'RELAY.associatedPins[0].initialValue = "SET";' in syscfg
    assert 'RELAY.associatedPins[0].pin.$assign  = "PA1";' in syscfg


def test_relay_mspm0_single_select_generation(tmp_path):
    """relay mspm0 单选生成：syscfg 只留 RELAY、模块文件落盘、main.c 调用
    过静态门禁（relay_init/relay_set 与头文件声明一致）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["relay"])
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
    assert "const RELAY = GPIO.addInstance();" in syscfg
    assert 'RELAY.associatedPins[0].pin.$assign  = "PA1";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "GP2Y1014",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/relay/code/relay.c").is_file()
    assert (out / "modules/relay/code/relay.h").is_file()


def test_relay_polarity_and_level_guards():
    """极性归一化与电平守卫（防回潮）：RELAY_ON_LEVEL 0u（单点极性宏——
    低电平吸合）、relay_set 内 state×RELAY_ON_LEVEL 分发 setPins/clearPins
    （1=吸合→0u→clearPins、0=断开→1u→setPins）、relay_init 初始断开
    （relay_set(0)）、页面 Set_Relay_Switch 对照注释、无 printf/IRQHandler/main。"""
    source = (MODULES / "relay" / "code" / "relay.c").read_text(encoding="utf-8")
    header = (MODULES / "relay" / "code" / "relay.h").read_text(encoding="utf-8")
    assert "RELAY_ON_LEVEL 0u" in header  # 默认低电平吸合（页面模块）
    assert "Set_Relay_Switch(s) ≡ relay_set(1-s)" in header  # 页面编码对照
    assert "RELAY_OUT" in source  # 页面 RELAY_OUT 宏原式保留为底层
    assert "RELAY_ON_LEVEL" in source
    assert "clearPins" in source  # 0u 分支（吸合=引脚低）
    assert "setPins" in source  # 1u 分支（断开=引脚高）
    assert "relay_set(0)" in source  # init 初始断开
    assert "printf" not in source  # 无 printf（头注释引用页面「去 printf」说明）
    assert "IRQHandler" not in source and "main(" not in source
