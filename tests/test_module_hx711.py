"""hx711 称重模块（GPIO 双线时序件——非 I2C）：真实库 + 真实母版不变量与
双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = gpio_out（SCK）/gpio_in（DT）默认
PB5/PB0）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成
（syscfg 裁剪保留 HX711 + 模块文件落盘）。**页面缺陷防回潮守卫**（① 20ms
超时（2000×10us、超时返回 0）且无 `while (DT_GET` 无界式；② 无 GapValue
硬编码 207 演示常数（HX711_GAP_VALUE 宏）；③ 补码 `^ 0x800000u`；
④ 模块内 static 收敛无全局泄漏；⑤ 无 printf/GPIO_Init/RCC_ 残留；
⑥ SCK OUT_PP + DT IU 初始化）。全程无 LLM、无服务。
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
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "hx711_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    uint32_t raw = 0;\n"
    "    float gram = 0.0f;\n"
    "    hx711_init();\n"
    "    hx711_tare();\n"
    "    raw = hx711_read_raw();\n"
    "    (void)raw;\n"
    "    gram = hx711_get_gram();\n"
    "    (void)gram;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/
# 母版 ml_i2c 调用）。
BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bI2C_Init\b|\bI2C_Start\b|\bI2C_Stop\b|\bI2C_SendByte\b", "母版 ml_i2c 调用"),
    (r"\bGPIO_ReadInputDataBit\b", "GPIO_ReadInputDataBit"),
    (r"\bGPIO_WriteBit\b", "GPIO_WriteBit"),
]


def test_hx711_manifest_shape_both_platforms():
    """hx711：双平台文件齐；stm32 双角色 = gpio_out（SCK=PB5）/gpio_in
    （DT=PB0）逐脚端口宏；mspm0 条目原样（syscfg gpio_out PA28/gpio_in PA31）。"""
    manifest = ModuleManifest.load(MODULES / "hx711")
    assert manifest.slug == "hx711"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "hx711_stm32.c",
        "hx711_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "hx711" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("HX711_SCK", "gpio_out", "PB5", True, ("HX711_SCK_GPIO", "HX711_SCK_PIN")),
        ("HX711_DT", "gpio_in", "PB0", True, ("HX711_DT_GPIO", "HX711_DT_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/hx711-weighing-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--hx711-weighing-sensor.md",
        "无界轮询",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["hx711.c", "hx711.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("HX711_SCK", "gpio_out", "PA28", True, ()),
        ("HX711_DT", "gpio_in", "PA31", True, ()),
    ]
    assert mspm0.verified is True


def test_hx711_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：HX711_SCK_GPIO/_SCK_PIN/_DT_GPIO/_DT_PIN 必须在
    母版 pin_config.h（默认 SCK=PB5 / DT=PB0——独立 GPIO 双线，非 I2C 总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+HX711_SCK_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+HX711_SCK_PIN\s+Pin_5", text)
    assert re.search(r"#define\s+HX711_DT_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+HX711_DT_PIN\s+Pin_0", text)


def test_hx711_mspm0_syscfg_instance():
    """mspm0 母版必须有 HX711 实例（SCK=PA28 输出 / DT=PA31 输入带上拉）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const HX711 = GPIO.addInstance();" in syscfg
    assert 'HX711.associatedPins[0].$name        = "SCK";' in syscfg
    assert 'HX711.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'HX711.associatedPins[1].$name        = "DT";' in syscfg
    assert 'HX711.associatedPins[1].pin.$assign  = "PA31";' in syscfg


def test_hx711_stm32_single_select_generation(tmp_path):
    """hx711 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 hx711_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["hx711"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/hx711/code/hx711_stm32.c").is_file()
    assert (out / "modules/hx711/code/hx711_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("hx711_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_hx711_mspm0_single_select_generation(tmp_path):
    """hx711 mspm0 单选生成：syscfg 只留 HX711、模块文件落盘。"""
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


def test_hx711_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；引脚初始化（SCK OUT_PP + DT IU）；**页面缺陷防回潮**（① 20ms
    超时（2000×10us、超时返回 0）且无 `while (DT_GET` 无界式；② 补码
    `^ 0x800000u`；③ HX711_GAP_VALUE 宏（无演示常数 207 硬编码于换算）；
    ④ 模块内 static 收敛（无全局泄漏）；⑤ 无 printf/GPIO_Init/RCC_）。"""
    c = (MODULES / "hx711" / "code" / "hx711_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "hx711" / "code" / "hx711_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 引脚初始化：SCK 输出 PP、DT 上拉输入 IU（页面先 PP 输出再重配 IPU
    # 的动作按 mspm0 先例收敛为 init 直配 IU）
    assert re.search(
        r"gpio_init\(HX711_SCK_GPIO, HX711_SCK_PIN, OUT_PP\)", code_only
    )
    assert re.search(
        r"gpio_init\(HX711_DT_GPIO, HX711_DT_PIN, IU\)", code_only
    )

    # 页面缺陷防回潮：① 20ms 超时（2000×10us、超时返回 0）——无 while 无界式
    assert "if (++timeout > 2000)" in code_only
    assert "return 0;" in code_only
    assert "while (DT_GET" not in code_only
    assert "while (gpio_get(HX711_DT_GPIO" in code_only
    # ② 补码 ^0x800000；③ HX711_GAP_VALUE 宏（无 207.00 硬编码进换算——
    # 宏已参数化）
    assert "^ 0x800000u" in code_only
    assert "HX711_GAP_VALUE" in code_only
    assert "207.00f" in h  # 宏默认值保留在头（参数化）
    assert "GapValue 207" not in code_only
    # ④ 模块内 static 收敛（无全局泄漏）
    assert "static uint32_t s_tare" in code_only
    assert "HX711_Buffer" not in code_only
    assert "Weight_Maopi" not in code_only
    assert "Flag_Error" not in code_only

    # 时序/换算原式：24 位读 + 第 25 个脉冲、克 = (raw - tare)/GAP 差 ≤0 钳 0
    assert "for (i = 0; i < 24; i++)" in code_only
    assert "(int32_t)hx711_read_raw() - (int32_t)s_tare" in code_only
    assert "raw <= 0" in code_only
