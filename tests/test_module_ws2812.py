"""ws2812 幻彩灯模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ir_beam / zigbee_link 同款结构测试：manifest 形状（mspm0 文件齐、
角色默认 = 母版 syscfg $assign 由 test_pins.py 守）、mspm0 单选生成
（syscfg 裁剪保留 WS2812 实例 + 模块文件落盘 + main.c 调 init/refresh
过静态门禁）。全程无 LLM、无服务：main.c 手写，直驱 generate()。
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
    '#include "ws2812.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ws2812_init();\n"
    "    ws2812_set_color(0, WS2812_RED);\n"
    "    ws2812_refresh();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ws2812_manifest_shape_mspm0():
    """ws2812：仅 mspm0 平台条目；依赖 delay；单 gpio_out（IN 默认 PA14）。"""
    manifest = ModuleManifest.load(MODULES / "ws2812")
    assert manifest.slug == "ws2812"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ws2812.c", "ws2812.h"]
    for rel in mspm0.files:
        assert (MODULES / "ws2812" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("WS2812_IN", "gpio_out", "PA14", True, ())
    ]
    # 简介判据：硬件身份（kit/source_url 必填）+ 能力方向 + 无题绑定词
    assert mspm0.kit and mspm0.source_url


def test_ws2812_mspm0_syscfg_instance():
    """mspm0 母版必须有 WS2812 输出实例（IN = PA14），方向 OUTPUT。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const WS2812 = GPIO.addInstance();" in syscfg
    assert 'WS2812.associatedPins[0].$name        = "IN";' in syscfg
    assert 'WS2812.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'WS2812.associatedPins[0].pin.$assign  = "PA14";' in syscfg


def test_ws2812_mspm0_single_select_generation(tmp_path):
    """ws2812 mspm0 单选生成：syscfg 只留 WS2812、模块文件落盘、main.c 调用
    过静态门禁（ws2812_init/set_color/refresh 与头文件声明一致）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ws2812"])
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
    assert "const WS2812 = GPIO.addInstance();" in syscfg
    assert 'WS2812.associatedPins[0].pin.$assign  = "PA14";' in syscfg
    for drop in ("KEY", "HUIDU", "DIGIT_UART", "LED_BEEP", "STEP_MOTOR", "IR_BEAM"):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ws2812/code/ws2812.c").is_file()
    assert (out / "modules/ws2812/code/ws2812.h").is_file()
