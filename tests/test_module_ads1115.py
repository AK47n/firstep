"""ads1115 四通道 16bit 外扩 ADC 模块（软 I2C 器件库件）：真实库 + 真实母版
不变量与双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成（syscfg 裁剪
保留 ADS1115 + 模块文件落盘）。软 I2C 换算守卫（自实现原语族、零 ml_i2c/
标准库调用、**SCL OUT_OD 初始化守卫**（批次 3 回修口径防回潮）、SDA 方向
切换 OD/IU）与 **页面缺陷防回潮**（① 负值换算正确式 `raw/32768*FSR`（无
`65535-num` 近似、无 `* 0.000125` 页面错误系数）——与 mspm0 版守卫同款；
② 失败返回 0（int16_t）；③ 无 printf/delay_1ms/GPIO_Init/RCC_ 残留）。
全程无 LLM、无服务。
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
    '#include "ads1115.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ads1115_init();\n"
    "    ads1115_set_gain(ADS1115_PGA_4_096V);\n"
    "    ads1115_set_data_rate(ADS1115_DR_128SPS);\n"
    "    (void)ads1115_set_address(0x48);\n"
    "    for (uint8_t ch = 0; ch < 4; ch++) {\n"
    "        int16_t raw = ads1115_read(ch);\n"
    "        float volt = ads1115_read_voltage(ch);\n"
    "        (void)raw;\n"
    "        (void)volt;\n"
    "    }\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ads1115_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ads1115_init();\n"
    "    (void)ads1115_read(0);\n"
    "    (void)ads1115_read_voltage(1);\n"
    "    (void)ads1115_set_gain(1);\n"
    "    (void)ads1115_set_data_rate(4);\n"
    "    (void)ads1115_set_address(0x48);\n"
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


def test_ads1115_manifest_shape_both_platforms():
    """ads1115：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PA16/PA17）。"""
    manifest = ModuleManifest.load(MODULES / "ads1115")
    assert manifest.slug == "ads1115"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ads1115_stm32.c",
        "ads1115_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ads1115" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("ADS1115_SCL", "i2c_scl", "PA6", True, ("ADS1115_SCL_GPIO", "ADS1115_SCL_PIN")),
        ("ADS1115_SDA", "i2c_sda", "PA7", True, ("ADS1115_SDA_GPIO", "ADS1115_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/ads1115-multichannel-a-to-d-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--ads1115-multichannel-a-to-d-sensor.md",
        "负值换算错误",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ads1115.c", "ads1115.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("ADS1115_SCL", "gpio_out", "PA16", True, ()),
        ("ADS1115_SDA", "gpio_out", "PA17", True, ()),
    ]
    assert mspm0.verified is True


def test_ads1115_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：ADS1115_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 与批次 2 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+ADS1115_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+ADS1115_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+ADS1115_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+ADS1115_SDA_PIN\s+Pin_7", text)


def test_ads1115_mspm0_syscfg_instance():
    """mspm0 母版必须有 ADS1115 实例（SCL=PA16 / SDA=PA17，输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const ADS1115 = GPIO.addInstance();" in syscfg
    assert 'ADS1115.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'ADS1115.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'ADS1115.associatedPins[0].pin.$assign  = "PA16";' in syscfg
    assert 'ADS1115.associatedPins[1].pin.$assign  = "PA17";' in syscfg


def test_ads1115_stm32_single_select_generation(tmp_path):
    """ads1115 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 ads1115_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ads1115"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ads1115/code/ads1115_stm32.c").is_file()
    assert (out / "modules/ads1115/code/ads1115_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ads1115_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ads1115_mspm0_single_select_generation(tmp_path):
    """ads1115 mspm0 单选生成：syscfg 只留 ADS1115、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ads1115"])
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
    assert "const ADS1115 = GPIO.addInstance();" in syscfg
    assert 'ADS1115.associatedPins[1].pin.$assign  = "PA17";' in syscfg
    for drop in (
        "TCS34725", "MLX90614", "SGP30", "PCA9685", "HX711", "AHT10",
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART",
        "ZIGBEE_UART", "OLED", "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ads1115/code/ads1115.c").is_file()
    assert (out / "modules/ads1115/code/ads1115.h").is_file()


def test_ads1115_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；**SCL OUT_OD
    初始化**（批次 3 回修口径——F1 复位浮空输入不初始化 = 总线死）；
    **页面缺陷防回潮**（负值换算 = raw/32768×FSR 且无 65535 近似、失败返 0、
    无 printf/delay_1ms/GPIO_Init/RCC_）。"""
    c = (MODULES / "ads1115" / "code" / "ads1115_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ads1115" / "code" / "ads1115_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（页面原式 Out_PP/IN_FLOATING → OD/IU）
    assert re.search(
        r"#define\s+ADS1115_SDA_OUT\(\)\s+gpio_init\(ADS1115_SDA_GPIO", code_only
    )
    assert re.search(
        r"ADS1115_SDA_IN\(\)\s+gpio_init\(ADS1115_SDA_GPIO, ADS1115_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+ADS1115_SDA\(x\)\s+gpio_set", code_only)
    assert "ads1115_iic_start" in code_only and "ads1115_iic_wait_ack" in code_only

    # SCL OUT_OD 初始化守卫（批次 3 回修口径防回潮）
    assert re.search(
        r"gpio_init\(ADS1115_SCL_GPIO, ADS1115_SCL_PIN, OUT_OD\)", code_only
    )
    assert "ADS1115_SCL(1)" in code_only

    # 页面原式保留：地址 0x90（ADS1115_ADDR_DEFAULT）、配置 0xC283、
    # 寄存器 0x00/0x01、重试 ≤20×1ms、int16_t 补码换算 raw/32768×FSR
    # （0.000125 = 4.096/2^15 语义——无 65535-num 近似、无 * 0.000125
    # 页面错误系数，与 mspm0 版守卫同款）
    assert "ADS1115_ADDR_DEFAULT 0x90" in h
    assert "0xC283u" in code_only
    assert "ADS1115_REG_CONVERSION" in code_only and "ADS1115_REG_CONFIG" in code_only
    assert "timeout > 20" in code_only
    assert "/ 32768.0f * fsr" in code_only
    assert "65535" not in code_only
    assert "* 0.000125" not in code_only

    # 失败语义：read 失败返回 0（int16_t）；失败码 1/2 保留（write_register）
    assert "return 0;" in code_only
    assert "return 1;" in code_only and "return 2;" in code_only
