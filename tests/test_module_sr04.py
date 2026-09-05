"""sr04 超声波模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / hx711 / aht10 同款结构测试：manifest 形状（mspm0 文件齐、
两角色默认 = 母版 syscfg $assign 由 test_pins.py 守）、mspm0 单选生成
（syscfg 裁剪保留 SR04 实例 + 模块文件落盘 + main.c 调 init/get_distance_cm
过静态门禁）。sr04 不占 TIMER 实例（TIMG0/6/7/8/12 全被既有模块占用，
本模块 CPU 忙等测宽）。全程无 LLM、无服务。
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
    '#include "sr04.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    sr04_init();\n"
    "    float d = sr04_get_distance_cm();\n"
    "    (void)d;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_sr04_manifest_shape_mspm0():
    """sr04：仅 mspm0 平台条目；依赖 delay；TRIG(out PB24) + ECHO(in PB8)。"""
    manifest = ModuleManifest.load(MODULES / "sr04")
    assert manifest.slug == "sr04"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["sr04.c", "sr04.h"]
    for rel in mspm0.files:
        assert (MODULES / "sr04" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SR04_TRIG", "gpio_out", "PB24", True, ()),
        ("SR04_ECHO", "gpio_in", "PB8", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_sr04_mspm0_syscfg_instances():
    """mspm0 母版必须有 SR04 GPIO 实例（TRIG=PB24 输出 / ECHO=PB8 输入）；
    不占 TIMER 实例（TIMG0/6/7/8/12 全被既有模块占用）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SR04 = GPIO.addInstance();" in syscfg
    assert 'SR04.associatedPins[0].$name        = "TRIG";' in syscfg
    assert 'SR04.associatedPins[0].pin.$assign  = "PB24";' in syscfg
    assert 'SR04.associatedPins[1].$name        = "ECHO";' in syscfg
    assert 'SR04.associatedPins[1].pin.$assign  = "PB8";' in syscfg
    assert "SR04_TIMER" not in syscfg


def test_sr04_mspm0_single_select_generation(tmp_path):
    """sr04 mspm0 单选生成：syscfg 只留 SR04、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["sr04"])
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
    assert "const SR04 = GPIO.addInstance();" in syscfg
    assert 'SR04.associatedPins[1].pin.$assign  = "PB8";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "MOTOR_PID", "NTB",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/sr04/code/sr04.c").is_file()
    assert (out / "modules/sr04/code/sr04.h").is_file()
