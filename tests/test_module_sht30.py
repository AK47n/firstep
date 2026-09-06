"""sht30 温湿度传感器模块（软 I2C 总线件 + CRC8）：真实库 + 真实母版不变量
与双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成。软 I2C 换算
守卫（自实现原语族、零 ml_i2c/标准库调用、页面原式 0x88/0x89 地址与换算
公式、SDA 方向切换 PP/IF——本件为全批唯一推挽+浮空配置）与 **页面缺陷
防回潮**（① 无 ADS1115 串台；② 无 extern 全局泄漏（出参）；③ 0x2130
采信代码；④ sht30_crc8 静态化 0x31/0xFF；⑤ 无 printf（校验失败返回 5）；
⑥ 失败码 1-5）。全程无 LLM、无服务。
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
    '#include "sht30.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    sht30_init();\n"
    "    (void)sht30_read(&t, &h);\n"
    "    (void)sht30_read_temperature(&t);\n"
    "    (void)sht30_read_humidity(&h);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "sht30_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    sht30_init();\n"
    "    (void)sht30_read(&t, &h);\n"
    "    (void)sht30_read_temperature(&t);\n"
    "    (void)sht30_read_humidity(&h);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/母版
# ml_i2c 调用）。
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


def test_sht30_manifest_shape_both_platforms():
    """sht30：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PA28/PA31）。"""
    manifest = ModuleManifest.load(MODULES / "sht30")
    assert manifest.slug == "sht30"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "sht30_stm32.c",
        "sht30_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "sht30" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("SHT30_SCL", "i2c_scl", "PA6", True, ("SHT30_SCL_GPIO", "SHT30_SCL_PIN")),
        ("SHT30_SDA", "i2c_sda", "PA7", True, ("SHT30_SDA_GPIO", "SHT30_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/sht30-temp-humi-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--sht30-temp-humi-sensor.md",
        "ADS1115",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["sht30.c", "sht30.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SHT30_SCL", "gpio_out", "PA28", True, ()),
        ("SHT30_SDA", "gpio_out", "PA31", True, ()),
    ]
    assert mspm0.verified is True


def test_sht30_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：SHT30_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+SHT30_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+SHT30_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+SHT30_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+SHT30_SDA_PIN\s+Pin_7", text)


def test_sht30_mspm0_syscfg_instance():
    """mspm0 母版必须有 SHT30 实例（SCL=PA28 / SDA=PA31）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SHT30 = GPIO.addInstance();" in syscfg
    assert 'SHT30.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'SHT30.associatedPins[1].pin.$assign  = "PA31";' in syscfg


def test_sht30_stm32_single_select_generation(tmp_path):
    """sht30 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 sht30_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["sht30"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/sht30/code/sht30_stm32.c").is_file()
    assert (out / "modules/sht30/code/sht30_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("sht30_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_sht30_mspm0_single_select_generation(tmp_path):
    """sht30 mspm0 单选生成：syscfg 只留 SHT30、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["sht30"])
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
    assert "const SHT30 = GPIO.addInstance();" in syscfg
    assert 'SHT30.associatedPins[1].pin.$assign  = "PA31";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "GP2Y1014",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/sht30/code/sht30.c").is_file()
    assert (out / "modules/sht30/code/sht30.h").is_file()


def test_sht30_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（本件 SDA 方向切换 = gpio_init PP/IF——页面
    原式推挽+浮空，全批唯一一派）；页面原式地址/命令/换算保留；**页面
    缺陷防回潮**（CRC8 0x31/0xFF 双组、0x2130、失败码 1-5、无 printf、
    无 extern 泄漏、无 u8 宏、sht30_crc8/write_mode 静态化）。"""
    c = (MODULES / "sht30" / "code" / "sht30_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "sht30" / "code" / "sht30_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（本件页面原式 PP 输出 / 浮空输入）
    assert re.search(
        r"#define\s+SHT30_SDA_OUT\(\)\s+gpio_init\(SHT30_SDA_GPIO", code_only
    )
    assert re.search(
        r"SHT30_SDA_IN\(\)\s+gpio_init\(SHT30_SDA_GPIO, SHT30_SDA_PIN, IF\)",
        code_only,
    )
    assert re.search(r"#define\s+SHT30_SDA\(x\)\s+gpio_set", code_only)
    assert "sht30_iic_start" in code_only and "sht30_iic_wait_ack" in code_only

    # 页面原式保留：地址 0x44（SHT30_ADDR<<1 表达式）、命令 0x2130/0xE000、
    # CRC8 0x31/0xFF、换算 175.0/45.0/100.0
    assert "SHT30_ADDR << 1" in code_only and "| 1u" in code_only
    assert "SHT30_CMD_PERIODIC" in code_only and "SHT30_CMD_READ" in code_only
    assert "0x31u" in code_only and "0xFFu" in code_only
    assert "175.0f" in code_only and "45.0f" in code_only and "100.0f" in code_only

    # 页面缺陷防回潮：①② 无 extern 泄漏（static）/无 ADS1115（注释剥离后
    # 代码零）；③ 0x2130 采信；④ crc8 静态（static 前缀）；⑤ 失败码 1-5
    # 返回 + 无 printf；⑥ 无 u8 宏
    assert "extern" not in code_only
    assert "ADS1115" not in code_only
    assert "static uint8_t sht30_crc8" in code_only
    assert "return 4;" in code_only and "return 5;" in code_only
    assert code_only.count("return ") >= 4
