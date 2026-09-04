"""ir_beam 红外对射传感器模块：真实库 + 真实母版不变量与双平台单选生成。

与 zigbee_link / key 等模块同款结构测试：manifest 形状（双平台文件齐、
stm32 宏在母版 pin_config.h、mspm0 默认 = 母版 syscfg $assign 由
test_pins.py 守）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0
单选生成（syscfg 裁剪保留 IR_BEAM 输入实例 + 模块文件落盘）。全程无 LLM、
无服务：main.c 手写，直驱 generate()（与 /api/generate 同一接缝）。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ir_beam.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ir_beam_init();\n"
    "    (void)ir_beam_read();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "ir_beam_mspm0.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ir_beam_init();\n"
    "    (void)ir_beam_read();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ir_beam_manifest_shape_both_platforms():
    """ir_beam：双平台文件齐；stm32 只声明一个 gpio_in（OUT 默认 PA8，
    macros = IR_BEAM_GPIO/IR_BEAM_PIN）；mspm0 同角色默认 PA8（无 macros）。"""
    manifest = ModuleManifest.load(MODULES / "ir_beam")
    assert manifest.slug == "ir_beam"
    assert manifest.dependencies == ()

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == ["ir_beam.c", "ir_beam.h"]
    for rel in stm32.files:
        assert (MODULES / "ir_beam" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("IR_BEAM_OUT", "gpio_in", "PA8", True, ("IR_BEAM_GPIO", "IR_BEAM_PIN"))
    ]

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == [
        "ir_beam_mspm0.c",
        "ir_beam_mspm0.h",
    ]
    for rel in mspm0.files:
        assert (MODULES / "ir_beam" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("IR_BEAM_OUT", "gpio_in", "PA8", True, ())
    ]


def test_ir_beam_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：IR_BEAM_GPIO / IR_BEAM_PIN 必须在母版 pin_config.h。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+IR_BEAM_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+IR_BEAM_PIN\s+Pin_8", text)


def test_ir_beam_mspm0_syscfg_instance():
    """mspm0 母版必须有 IR_BEAM 输入实例（OUT = PA8），方向 INPUT 且内部
    上拉（PULL_UP，与 stm32 侧 IU 对等——遮挡高电平依赖上拉钳位）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const IR_BEAM = GPIO.addInstance();" in syscfg
    assert 'IR_BEAM.associatedPins[0].$name            = "OUT";' in syscfg
    assert 'IR_BEAM.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'IR_BEAM.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'IR_BEAM.associatedPins[0].pin.$assign      = "PA8";' in syscfg


def test_ir_beam_stm32_single_select_generation(tmp_path):
    """ir_beam stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 ir_beam.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ir_beam"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ir_beam/code/ir_beam.c").is_file()
    assert (out / "modules/ir_beam/code/ir_beam.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ir_beam.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ir_beam_mspm0_single_select_generation(tmp_path):
    """ir_beam mspm0 单选生成：syscfg 只留 IR_BEAM（含 GPIO 模块变量）、
    模块文件落盘、main.c 调用过静态门禁。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ir_beam"])
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
    assert "const IR_BEAM = GPIO.addInstance();" in syscfg
    assert 'IR_BEAM.associatedPins[0].pin.$assign      = "PA8";' in syscfg
    assert 'IR_BEAM.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    for drop in ("KEY", "HUIDU", "DIGIT_UART", "LED_BEEP", "STEP_MOTOR"):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ir_beam/code/ir_beam_mspm0.c").is_file()
    assert (out / "modules/ir_beam/code/ir_beam_mspm0.h").is_file()
