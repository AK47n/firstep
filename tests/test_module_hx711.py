"""hx711 称重模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / ir_beam 同款结构测试：manifest 形状（mspm0 文件齐、两角色
默认 = 母版 syscfg $assign 由 test_pins.py 守）、mspm0 单选生成（syscfg
裁剪保留 HX711 实例 + 模块文件落盘 + main.c 调 init/tare/get_gram 过静态
门禁）。全程无 LLM、无服务：main.c 手写，直驱 generate()。
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
    '#include "hx711.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    hx711_init();\n"
    "    hx711_tare();\n"
    "    float w = hx711_get_gram();\n"
    "    (void)w;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_hx711_manifest_shape_mspm0():
    """hx711：仅 mspm0 平台条目；依赖 delay；SCK(out PA28) + DT(in PA31)。"""
    manifest = ModuleManifest.load(MODULES / "hx711")
    assert manifest.slug == "hx711"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["hx711.c", "hx711.h"]
    for rel in mspm0.files:
        assert (MODULES / "hx711" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("HX711_SCK", "gpio_out", "PA28", True, ()),
        ("HX711_DT", "gpio_in", "PA31", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_hx711_mspm0_syscfg_instance():
    """mspm0 母版必须有 HX711 实例（SCK=PA28 输出 / DT=PA31 输入带上拉）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const HX711 = GPIO.addInstance();" in syscfg
    assert 'HX711.associatedPins[0].$name        = "SCK";' in syscfg
    assert 'HX711.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'HX711.associatedPins[1].$name        = "DT";' in syscfg
    assert 'HX711.associatedPins[1].pin.$assign  = "PA31";' in syscfg


def test_hx711_mspm0_single_select_generation(tmp_path):
    """hx711 mspm0 单选生成：syscfg 只留 HX711、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["hx711"])
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
    assert "const HX711 = GPIO.addInstance();" in syscfg
    assert 'HX711.associatedPins[1].pin.$assign  = "PA31";' in syscfg
    for drop in ("KEY", "HUIDU", "DIGIT_UART", "LED_BEEP", "IR_BEAM", "WS2812", "IMU601"):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/hx711/code/hx711.c").is_file()
    assert (out / "modules/hx711/code/hx711.h").is_file()
