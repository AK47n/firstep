"""sgp30 空气质量传感器模块（软 I2C + CRC8 器件库件）：真实库 + 真实母版
不变量与双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成（syscfg 裁剪
保留 SGP30 + 模块文件落盘）。软 I2C 换算守卫（自实现原语族、零 ml_i2c/
标准库调用、**SCL OUT_OD 初始化守卫**（批次 3 回修口径防回潮）、SDA 方向
切换 OD/IU）与 **页面缺陷防回潮**（① 读满 6 字节 + 两组 CRC8（0x31/0xFF）
校验（无 `crc = crc` 自赋值）；② 失败码 1-5（NACK 检查补齐）；③ 命令
0x2003/0x2008；④ 双出参 tvoc_ppb/co2_ppm；⑤ 无 printf/GPIO_Init/RCC_
残留）。全程无 LLM、无服务。
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
    '#include "sgp30.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    sgp30_init();\n"
    "    uint16_t tvoc = 0;\n"
    "    uint16_t co2 = 0;\n"
    "    uint8_t ret = sgp30_read(&tvoc, &co2);\n"
    "    (void)ret;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "sgp30_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    uint16_t tvoc = 0;\n"
    "    uint16_t co2 = 0;\n"
    "    sgp30_init();\n"
    "    (void)sgp30_read(&tvoc, &co2);\n"
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


def test_sgp30_manifest_shape_both_platforms():
    """sgp30：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PA18/PB9）。"""
    manifest = ModuleManifest.load(MODULES / "sgp30")
    assert manifest.slug == "sgp30"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "sgp30_stm32.c",
        "sgp30_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "sgp30" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("SGP30_SCL", "i2c_scl", "PA6", True, ("SGP30_SCL_GPIO", "SGP30_SCL_PIN")),
        ("SGP30_SDA", "i2c_sda", "PA7", True, ("SGP30_SDA_GPIO", "SGP30_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/sgp30-gas-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--sgp30-gas-sensor.md",
        "CRC 缺失",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["sgp30.c", "sgp30.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SGP30_SCL", "gpio_out", "PA18", True, ()),
        ("SGP30_SDA", "gpio_out", "PB9", True, ()),
    ]
    assert mspm0.verified is True


def test_sgp30_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：SGP30_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 与批次 2 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+SGP30_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+SGP30_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+SGP30_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+SGP30_SDA_PIN\s+Pin_7", text)


def test_sgp30_mspm0_master_syscfg_instance():
    """mspm0 母版必须有 SGP30 实例（SCL=PA18 / SDA=PB9，输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SGP30 = GPIO.addInstance();" in syscfg
    assert 'SGP30.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'SGP30.associatedPins[0].pin.$assign  = "PA18";' in syscfg
    assert 'SGP30.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'SGP30.associatedPins[1].pin.$assign  = "PB9";' in syscfg


def test_sgp30_stm32_single_select_generation(tmp_path):
    """sgp30 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 sgp30_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["sgp30"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/sgp30/code/sgp30_stm32.c").is_file()
    assert (out / "modules/sgp30/code/sgp30_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("sgp30_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_sgp30_mspm0_single_select_generation(tmp_path):
    """sgp30 mspm0 单选生成：syscfg 只留 SGP30、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["sgp30"])
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
    assert "const SGP30 = GPIO.addInstance();" in syscfg
    assert 'SGP30.associatedPins[1].pin.$assign  = "PB9";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "TTP224", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/sgp30/code/sgp30.c").is_file()
    assert (out / "modules/sgp30/code/sgp30.h").is_file()


def test_sgp30_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；**SCL OUT_OD
    初始化**（批次 3 回修口径）；**页面缺陷防回潮**（读满 6 字节 + 两组 CRC8
    （0x31/0xFF）、无 `crc = crc` 自赋值、失败码 1-5、双出参、无 printf/
    GPIO_Init/RCC_）。"""
    c = (MODULES / "sgp30" / "code" / "sgp30_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "sgp30" / "code" / "sgp30_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+SGP30_SDA_OUT\(\)\s+gpio_init\(SGP30_SDA_GPIO", code_only
    )
    assert re.search(
        r"SGP30_SDA_IN\(\)\s+gpio_init\(SGP30_SDA_GPIO, SGP30_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+SGP30_SDA\(x\)\s+gpio_set", code_only)
    assert "sgp30_iic_start" in code_only and "sgp30_iic_wait_ack" in code_only

    # SCL OUT_OD 初始化守卫（批次 3 回修口径防回潮）
    assert re.search(
        r"gpio_init\(SGP30_SCL_GPIO, SGP30_SCL_PIN, OUT_OD\)", code_only
    )
    assert "SGP30_SCL(1)" in code_only

    # 页面缺陷防回潮：① CRC 修正（6 字节 + 两组 0x31/0xFF 校验、无 crc=crc）；
    # ② 失败码 1-5（NACK 检查补齐）
    assert "sgp30_crc8(buff, 2) != buff[2]" in code_only
    assert "sgp30_crc8(buff + 3, 2) != buff[5]" in code_only
    assert "buff[5] = sgp30_iic_read_byte();" in code_only  # 读满 6 字节
    assert "0x31u" in code_only and "0xFFu" in code_only
    assert "crc = crc" not in code_only
    assert "return 4;" in code_only and "return 5;" in code_only

    # 页面原式保留：地址 0x58、命令 0x2003/0x2008、写命令内嵌 delay_ms(100)
    assert "SGP30_ADDR              0x58u" in h
    assert "SGP30_CMD_INIT_AIR      0x2003u" in h
    assert "SGP30_CMD_MEASURE_AIR   0x2008u" in h
    assert "delay_ms(100)" in code_only
