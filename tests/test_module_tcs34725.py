"""tcs34725 颜色识别传感器模块（软 I2C 器件库件）：真实库 + 真实母版不变量
与双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成（syscfg 裁剪
保留 TCS34725 + 模块文件落盘）。软 I2C 换算守卫（自实现原语族、零 ml_i2c/
标准库调用、**SCL OUT_OD 初始化守卫**（批次 3 回修口径防回潮）、SDA 方向
切换 OD/IU）与 **页面缺陷防回潮**（① 读写路径 NACK 检查+失败传播；②
`rgb->c == 0` 除零防护；③ ID 判定 `||`（无按位或）；④ RGBC 低字节在前；
⑤ 无 printf/GPIO_Init/RCC_ 残留）。全程无 LLM、无服务。
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
    '#include "tcs34725.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    if (tcs34725_init() == 0) {\n"
    "        while (1) {\n"
    "        }\n"
    "    }\n"
    "    TCS34725_RGBC rgb;\n"
    "    TCS34725_HSL hsl;\n"
    "    tcs34725_set_gain(TCS34725_GAIN_4X);\n"
    "    tcs34725_set_integration_time(TCS34725_INTEGRATIONTIME_50MS);\n"
    "    if (tcs34725_read_rgb(&rgb)) {\n"
    "        tcs34725_rgb_to_hsl(&rgb, &hsl);\n"
    "        (void)hsl.h;\n"
    "        (void)hsl.s;\n"
    "        (void)hsl.l;\n"
    "    }\n"
    "    tcs34725_disable();\n"
    "    tcs34725_enable();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "tcs34725_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    TCS34725_RGBC rgb;\n"
    "    TCS34725_HSL hsl;\n"
    "    (void)tcs34725_init();\n"
    "    (void)tcs34725_read_rgb(&rgb);\n"
    "    tcs34725_rgb_to_hsl(&rgb, &hsl);\n"
    "    tcs34725_set_integration_time(TCS34725_INTEGRATIONTIME_24MS);\n"
    "    tcs34725_set_gain(TCS34725_GAIN_1X);\n"
    "    tcs34725_enable();\n"
    "    tcs34725_disable();\n"
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


def test_tcs34725_manifest_shape_both_platforms():
    """tcs34725：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PA23/PA24）。"""
    manifest = ModuleManifest.load(MODULES / "tcs34725")
    assert manifest.slug == "tcs34725"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "tcs34725_stm32.c",
        "tcs34725_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "tcs34725" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("TCS34725_SCL", "i2c_scl", "PA6", True, ("TCS34725_SCL_GPIO", "TCS34725_SCL_PIN")),
        ("TCS34725_SDA", "i2c_sda", "PA7", True, ("TCS34725_SDA_GPIO", "TCS34725_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/tcs34725-color-recognition-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--tcs34725-color-recognition-sensor.md",
        "除零",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["tcs34725.c", "tcs34725.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("TCS34725_SCL", "gpio_out", "PA23", True, ()),
        ("TCS34725_SDA", "gpio_out", "PA24", True, ()),
    ]
    assert mspm0.verified is True


def test_tcs34725_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：TCS34725_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 与批次 2 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+TCS34725_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+TCS34725_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+TCS34725_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+TCS34725_SDA_PIN\s+Pin_7", text)


def test_tcs34725_mspm0_syscfg_instance():
    """mspm0 母版必须有 TCS34725 实例（SCL=PA23 / SDA=PA24，输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const TCS34725 = GPIO.addInstance();" in syscfg
    assert 'TCS34725.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'TCS34725.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'TCS34725.associatedPins[0].pin.$assign  = "PA23";' in syscfg
    assert 'TCS34725.associatedPins[1].pin.$assign  = "PA24";' in syscfg


def test_tcs34725_stm32_single_select_generation(tmp_path):
    """tcs34725 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 tcs34725_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["tcs34725"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/tcs34725/code/tcs34725_stm32.c").is_file()
    assert (out / "modules/tcs34725/code/tcs34725_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("tcs34725_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_tcs34725_mspm0_single_select_generation(tmp_path):
    """tcs34725 mspm0 单选生成：syscfg 只留 TCS34725、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["tcs34725"])
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
    assert "const TCS34725 = GPIO.addInstance();" in syscfg
    assert 'TCS34725.associatedPins[1].pin.$assign  = "PA24";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "BH1750", "ADS1115", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "PWMAB", "MAX7219",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/tcs34725/code/tcs34725.c").is_file()
    assert (out / "modules/tcs34725/code/tcs34725.h").is_file()


def test_tcs34725_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；**SCL OUT_OD
    初始化**（批次 3 回修口径）；**页面缺陷防回潮**（rgb->c==0 防护、ID 判定
    `||` 无按位或、RGBC 低字节在前、读写路径 NACK 检查、无 printf/GPIO_Init/
    RCC_）。"""
    c = (MODULES / "tcs34725" / "code" / "tcs34725_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "tcs34725" / "code" / "tcs34725_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+TCS34725_SDA_OUT\(\)\s+gpio_init\(TCS34725_SDA_GPIO", code_only
    )
    assert re.search(
        r"TCS34725_SDA_IN\(\)\s+gpio_init\(TCS34725_SDA_GPIO, TCS34725_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+TCS34725_SDA\(x\)\s+gpio_set", code_only)
    assert "tcs34725_iic_start" in code_only and "tcs34725_iic_wait_ack" in code_only

    # SCL OUT_OD 初始化守卫（批次 3 回修口径防回潮）
    assert re.search(
        r"gpio_init\(TCS34725_SCL_GPIO, TCS34725_SCL_PIN, OUT_OD\)", code_only
    )
    assert "TCS34725_SCL(1)" in code_only

    # 页面缺陷防回潮：① ID 判定 ||（无按位或）；② c==0 除零防护；
    # ③ RGBC 低字节在前；④ 读写路径 NACK 检查（helper 返回状态）
    assert "id == 0x4D || id == 0x44" in code_only
    assert "id == 0x4D | id == 0x44" not in code_only
    assert "rgb->c == 0" in code_only
    assert "tmp[1] << 8) | tmp[0]" in code_only
    assert "低字节在前" in c  # 注释记录
    assert "tcs34725_i2c_write(&cmd, 1, 0) != 0" in code_only
    assert "tcs34725_i2c_read(data, n)" in code_only
    assert "tcs34725_read_reg_checked" in code_only

    # 页面原式保留：地址 0x29、命令位 0x80、积分时间/增益宏、HSL 换算
    assert "TCS34725_ADDR" in h and "(0x29u)" in h
    assert "TCS34725_COMMAND_BIT" in h and "(0x80u)" in h
    assert "TCS34725_INTEGRATIONTIME_24MS" in h and "(0xF6u)" in h
    assert "TCS34725_GAIN_1X" in h and "(0x00u)" in h
    assert "* 100 / rgb->c" in code_only
