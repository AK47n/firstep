"""relay 1 路 5V 继电器模块（GPIO 迷你驱动）：真实库 + 真实母版不变量与
双平台单选生成。

照 test_module_ir_beam.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、
mspm0 单选生成（syscfg 裁剪保留 RELAY + 模块文件落盘）。极性归一化守卫
（RELAY_ON_LEVEL 0u = 低电平吸合、relay_set(1)=吸合、init 初始断开）与
页面 Set_Relay_Switch 对照注释钉死（页面 0=吸合/1=断开 →
Set_Relay_Switch(s) ≡ relay_set(1-s)）；**页面 F4 口径甄别**（stm32f4xx.h/
RCC_AHB1PeriphClockCmd/GPIO_OType 与 F103 标题矛盾 → F1 换算记录 + 代码层
零标准库调用守卫）。全程无 LLM、无服务。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
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
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "relay_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    relay_init();\n"
    "    relay_set(1);\n"
    "    relay_set(0);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 页面（F4 口径）换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/
# 演示残留）。RCC_ 引用与 #include stm32*.h 均在注释甄别记录里（豁免注释）。
BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
]


def test_relay_manifest_shape_both_platforms():
    """relay：双平台文件齐；stm32 单角色 RELAY_OUT = gpio_out PB4（macros =
    RELAY_GPIO/RELAY_PIN，初始未验证）；mspm0 条目原样（syscfg gpio_out PA1）。"""
    manifest = ModuleManifest.load(MODULES / "relay")
    assert manifest.slug == "relay"
    assert manifest.dependencies == ()

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == ["relay_stm32.c", "relay_stm32.h"]
    for rel in stm32.files:
        assert (MODULES / "relay" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("RELAY_OUT", "gpio_out", "PB4", True, ("RELAY_GPIO", "RELAY_PIN"))
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/control/relay-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/control--relay-module.md",
        "F4",
        "RCC_APB2PeriphClockCmd",
        "Set_Relay_Switch(s) ≡ relay_set(1-s)",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["relay.c", "relay.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("RELAY_OUT", "gpio_out", "PA1", True, ())
    ]
    assert mspm0.verified is True
    assert mspm0.kit and mspm0.source_url
    assert "Set_Relay_Switch" in mspm0.notes


def test_relay_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：RELAY_GPIO / RELAY_PIN 必须在母版 pin_config.h。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+RELAY_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+RELAY_PIN\s+Pin_4", text)


def test_relay_mspm0_syscfg_instance():
    """mspm0 母版必须有 RELAY 输出实例（OUT = PA1），方向 OUTPUT + 初始 SET
    （模块低电平吸合 → SET = 引脚高 = 初始断开）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const RELAY = GPIO.addInstance();" in syscfg
    assert 'RELAY.associatedPins[0].$name        = "OUT";' in syscfg
    assert 'RELAY.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'RELAY.associatedPins[0].initialValue = "SET";' in syscfg
    assert 'RELAY.associatedPins[0].pin.$assign  = "PA1";' in syscfg


def test_relay_stm32_single_select_generation(tmp_path):
    """relay stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 relay_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["relay"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/relay/code/relay_stm32.c").is_file()
    assert (out / "modules/relay/code/relay_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("relay_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


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
    低电平吸合）、relay_set 内 state×RELAY_ON_LEVEL 分发（1=吸合→0u→低、
    0=断开→1u→高）、relay_init 初始断开（relay_set(0)）、页面
    Set_Relay_Switch 对照注释、无 printf/IRQHandler/main。"""
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


def test_relay_stm32_code_guards():
    """stm32 代码层守卫：注释里有 F4 甄别记录（与原页对照），剥离注释后
    零标准库/寄存器/演示残留；只吃母版 ml_* API。"""
    c = (MODULES / "relay" / "code" / "relay_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "relay" / "code" / "relay_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "F4" in c and "stm32f4xx.h" in c  # 页面甄别记录（注释）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 极性宏与归一化对照（页面 0=吸合/1=断开 → API 1=吸合/0=断开）
    assert re.search(r"#define\s+RELAY_ON_LEVEL\s+0u", h)
    assert "Set_Relay_Switch(s) ≡ relay_set(1-s)" in h
    # 只吃母版 ml_* API
    assert "gpio_init(RELAY_GPIO, RELAY_PIN, OUT_PP)" in code_only
    assert "gpio_set(RELAY_GPIO, RELAY_PIN" in code_only
