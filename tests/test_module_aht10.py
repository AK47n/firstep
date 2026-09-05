"""aht10 温湿度模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / hx711 同款结构测试：manifest 形状（mspm0 文件齐、两角色默认 =
母版 syscfg $assign 由 test_pins.py 守）、mspm0 单选生成（syscfg 裁剪保留
AHT10 实例 + 模块文件落盘 + main.c 调 init/read 过静态门禁）。全程无 LLM、
无服务：main.c 手写，直驱 generate()。
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
    '#include "aht10.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    aht10_init();\n"
    "    float t = aht10_read_temperature();\n"
    "    float h = aht10_read_humidity();\n"
    "    (void)t;\n"
    "    (void)h;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_aht10_manifest_shape_mspm0():
    """aht10：仅 mspm0 平台条目；依赖 delay；SCL/SDA 均 gpio_out（软 I2C）。"""
    manifest = ModuleManifest.load(MODULES / "aht10")
    assert manifest.slug == "aht10"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["aht10.c", "aht10.h"]
    for rel in mspm0.files:
        assert (MODULES / "aht10" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("AHT10_SCL", "gpio_out", "PB6", True, ()),
        ("AHT10_SDA", "gpio_out", "PB7", True, ()),
    ]
    # 简介判据：硬件身份（kit/source_url 必填）+ 能力方向 + 无题绑定
    assert mspm0.kit and mspm0.source_url


def test_aht10_mspm0_syscfg_instance():
    """mspm0 母版必须有 AHT10 实例（SCL=PB6 / SDA=PB7，输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const AHT10 = GPIO.addInstance();" in syscfg
    assert 'AHT10.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'AHT10.associatedPins[0].pin.$assign  = "PB6";' in syscfg
    assert 'AHT10.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'AHT10.associatedPins[1].pin.$assign  = "PB7";' in syscfg


def test_aht10_mspm0_single_select_generation(tmp_path):
    """aht10 mspm0 单选生成：syscfg 只留 AHT10、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["aht10"])
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
    assert "const AHT10 = GPIO.addInstance();" in syscfg
    assert 'AHT10.associatedPins[1].pin.$assign  = "PB7";' in syscfg
    for drop in ("STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812", "HX711"):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/aht10/code/aht10.c").is_file()
    assert (out / "modules/aht10/code/aht10.h").is_file()
