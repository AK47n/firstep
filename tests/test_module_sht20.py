"""sht20 温湿度传感器模块（软 I2C 总线件）：真实库 + 真实母版不变量与
双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成。软 I2C 换算
守卫（自实现原语族、零 ml_i2c/标准库调用、页面原式 0x80/0x81 地址与换算
公式、SDA 方向切换 OD/IU）与 **页面缺陷防回潮**（① ≤50×2ms 重试上限；
② & 0xFFFC 状态位掩码；③ 0xF3/0xF5 命令（no-hold 采信代码）；④ 失败码
1/2/3 返回（无 printf 残留））。全程无 LLM、无服务。
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
    '#include "sht20.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    sht20_init();\n"
    "    (void)sht20_read(&t, &h);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "sht20_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    sht20_init();\n"
    "    (void)sht20_read(&t, &h);\n"
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


def test_sht20_manifest_shape_both_platforms():
    """sht20：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PA16/PA17）。"""
    manifest = ModuleManifest.load(MODULES / "sht20")
    assert manifest.slug == "sht20"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "sht20_stm32.c",
        "sht20_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "sht20" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("SHT20_SCL", "i2c_scl", "PA6", True, ("SHT20_SCL_GPIO", "SHT20_SCL_PIN")),
        ("SHT20_SDA", "i2c_sda", "PA7", True, ("SHT20_SDA_GPIO", "SHT20_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/sht20-temp-humi-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--sht20-temp-humi-sensor.md",
        "0xFFFC",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["sht20.c", "sht20.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SHT20_SCL", "gpio_out", "PA16", True, ()),
        ("SHT20_SDA", "gpio_out", "PA17", True, ()),
    ]
    assert mspm0.verified is True


def test_sht20_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：SHT20_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+SHT20_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+SHT20_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+SHT20_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+SHT20_SDA_PIN\s+Pin_7", text)


def test_sht20_mspm0_syscfg_instance():
    """mspm0 母版必须有 SHT20 实例（SCL=PA16 / SDA=PA17）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SHT20 = GPIO.addInstance();" in syscfg
    assert 'SHT20.associatedPins[0].pin.$assign  = "PA16";' in syscfg
    assert 'SHT20.associatedPins[1].pin.$assign  = "PA17";' in syscfg


def test_sht20_stm32_single_select_generation(tmp_path):
    """sht20 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 sht20_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["sht20"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/sht20/code/sht20_stm32.c").is_file()
    assert (out / "modules/sht20/code/sht20_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("sht20_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_sht20_mspm0_single_select_generation(tmp_path):
    """sht20 mspm0 单选生成：syscfg 只留 SHT20、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["sht20"])
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
    assert "const SHT20 = GPIO.addInstance();" in syscfg
    assert 'SHT20.associatedPins[1].pin.$assign  = "PA17";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "GP2Y1014",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/sht20/code/sht20.c").is_file()
    assert (out / "modules/sht20/code/sht20.h").is_file()


def test_sht20_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；页面原式
    地址/命令/换算保留；**页面缺陷防回潮**（重试上限 50×2ms、& 0xFFFC
    掩码、0xF3/0xF5 命令、失败码 1/2/3 返回、无 printf 残留）。"""
    c = (MODULES / "sht20" / "code" / "sht20_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "sht20" / "code" / "sht20_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+SHT20_SDA_OUT\(\)\s+gpio_init\(SHT20_SDA_GPIO", code_only
    )
    assert re.search(
        r"SHT20_SDA_IN\(\)\s+gpio_init\(SHT20_SDA_GPIO, SHT20_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+SHT20_SDA\(x\)\s+gpio_set", code_only)
    assert "sht20_iic_start" in code_only and "sht20_iic_wait_ack" in code_only

    # 页面原式保留：地址 0x80/0x81（SHT20_ADDR<<1 表达式）、命令 0xF3/0xF5、
    # 换算 175.72/46.85/125.0/6.0
    assert "SHT20_ADDR << 1" in code_only and "| 1u" in code_only
    assert "SHT20_CMD_TEMP" in code_only and "SHT20_CMD_HUMI" in code_only
    assert "175.72f" in code_only and "46.85f" in code_only
    assert "125.0f" in code_only and "6.0f" in code_only

    # 页面缺陷防回潮：① 重试上限（≤50×2ms → SHT20_READ_RETRY_MAX）；
    # ② & 0xFFFC 掩码；③ 失败码 1/2/3 返回；④ 无 printf 残留
    assert "SHT20_READ_RETRY_MAX" in code_only
    assert "SHT20_READ_RETRY_MS" in code_only
    assert "& 0xFFFCu" in code_only
    assert "return 1;" in code_only and "return 2;" in code_only and "return 3;" in code_only
