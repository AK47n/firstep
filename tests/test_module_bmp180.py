"""bmp180 气压/温度/海拔传感器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 sht30 / sgp30 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双角色 = PA23/PA24——母版 syscfg 由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 BMP180 + delay
展开、模块文件落盘、main.c 调 init/read/read_altitude 过静态门禁）。
**压力换算纯函数单测（最高既有接缝——open_mv4 帧解析镜像先例）**：Python
镜像 bmp180_altitude(pa)（页面 44330 公式）断言气压→海拔表（基线以
math.pow 计算为准，±0.5m）。源码守卫（防回潮）：寄存器/器件地址常量、
页面原式系数、海拔公式、B7 uint32_t 页面原式分支、无 & 0xFFFC 掩码、
无 printf。全程无 LLM、无服务。
"""
from __future__ import annotations

import math
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
from contest_generator.platforms import (  # noqa: E402
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "bmp180.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    bmp180_init();\n"
    "    float t = 0.0f, p = 0.0f;\n"
    "    uint8_t ret = bmp180_read(&t, &p);\n"
    "    (void)ret;\n"
    "    float alt = bmp180_read_altitude(p);\n"
    "    (void)alt;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "bmp180_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    float t = 0.0f, p = 0.0f;\n"
    "    bmp180_init();\n"
    "    (void)bmp180_read(&t, &p);\n"
    "    (void)bmp180_read_altitude(p);\n"
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


def bmp180_altitude(pa: float) -> float:
    """C 侧 bmp180_read_altitude 语义镜像（页面原式：44330×(1-(p/101325)^
    (1/5.255))，math.pow 基线）。"""
    return 44330.0 * (1.0 - math.pow(pa / 101325.0, 1.0 / 5.255))


def test_bmp180_altitude_formula_matches_baseline():
    """气压→海拔换算纯函数单测（基线 math.pow，±0.5m）：页面原式钉死。"""
    assert bmp180_altitude(101325.0) == 0.0
    # 基线表（math.pow）：100000→110.9、95000→540.4、90000→988.6、85000→1457.5
    for pa, expect in (
        (100000.0, 110.9),
        (95000.0, 540.4),
        (90000.0, 988.6),
        (85000.0, 1457.5),
    ):
        got = bmp180_altitude(pa)
        assert abs(got - expect) <= 0.5, (pa, got, expect)


def test_bmp180_manifest_shape_mspm0():
    """bmp180：双平台条目（mspm0 原样 + stm32 批次 4 新增）；依赖 delay；
    SCL/SDA 双角色（gpio_out）。"""
    manifest = ModuleManifest.load(MODULES / "bmp180")
    assert manifest.slug == "bmp180"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["bmp180.c", "bmp180.h"]
    for rel in mspm0.files:
        assert (MODULES / "bmp180" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("BMP180_SCL", "gpio_out", "PA23", True, ()),
        ("BMP180_SDA", "gpio_out", "PA24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 关键 notes 子串：人工复核修正 + 与 ms5611 分工 + 未上板
    assert "B7" in mspm0.notes
    assert "ms5611" in mspm0.notes
    assert "oss" in mspm0.notes
    assert "未上板" in mspm0.notes


def test_bmp180_mspm0_syscfg_instances():
    """mspm0 母版：BMP180 GPIO 实例（SCL/SDA 输出 PA23/PA24）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const BMP180 = GPIO.addInstance();" in syscfg
    assert 'BMP180.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'BMP180.associatedPins[0].pin.$assign  = "PA23";' in syscfg
    assert 'BMP180.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'BMP180.associatedPins[1].pin.$assign  = "PA24";' in syscfg


def test_bmp180_mspm0_single_select_generation(tmp_path):
    """bmp180 mspm0 单选生成：syscfg 只留 BMP180、依赖 delay 展开、模块文件
    落盘、main.c 调用过静态门禁。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["bmp180"])
    assert {m.slug for m in resolved.manifests} == {"bmp180", "delay"}
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
    assert "const BMP180 = GPIO.addInstance();" in syscfg
    assert 'BMP180.associatedPins[0].pin.$assign  = "PA23";' in syscfg
    assert 'BMP180.associatedPins[1].pin.$assign  = "PA24";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "SHT30",
        "SHT20", "JY61P", "SGP30", "AGS10", "TTP224", "HUMAN_IR",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/bmp180/code/bmp180.c").is_file()
    assert (out / "modules/bmp180/code/bmp180.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_bmp180_source_guards():
    """源码守卫（防回潮）：器件/寄存器/命令常量、页面原式系数、海拔公式、
    B7 页面原式分支、无掩码、无 printf/IRQHandler/main。"""
    source = (MODULES / "bmp180" / "code" / "bmp180.c").read_text(encoding="utf-8")
    header = (MODULES / "bmp180" / "code" / "bmp180.h").read_text(encoding="utf-8")
    # 器件地址（页面 0xEE 写/0xEF 读）与命令寄存器/命令
    assert "BMP180_ADDR_W 0xEEu" in header
    assert "BMP180_ADDR_R 0xEFu" in header
    assert "BMP180_REG_CTRL_MEAS 0xF4u" in header
    assert "BMP180_CMD_TEMP 0x2Eu" in header
    assert "BMP180_CMD_PRES 0x34u" in header
    # 校准寄存器地址（页面 0xAA..0xBE）
    assert "0xaa" in source and "0xbe" in source
    # 温度/气压读取地址（页面 0xF6）与换算系数（页面原式）
    assert "0xf6" in source
    assert "32768.0" in source and "2048.0" in source and "0.1f" in source
    # 气压 B6..B7/p 页面原式（B7 uint32_t 页面声明 + 标准双分支保留记录）
    assert "b6" in source and "b7" in source
    assert "B7" in source  # 人工复核修正注释（B7 可达 ≥2^31——else 分支不可删）
    # 海拔公式（页面 44330/101325/5.255 + math.h/pow）
    assert "44330" in source and "101325.0" in source and "5.255" in source
    assert "pow(" in source and "math.h" in source
    # 无掩码（BMP180 无 & 0xFFFC 类掩码——页面无此表达式）
    assert "0xFFFC" not in source
    assert "printf(" not in source and "printf(" not in header
    assert "IRQHandler" not in source and "main(" not in source


# ---------------------------------------------------------------------------
# 批次 4（wiki-stm32-batch4/01）：stm32 平台条目
# ---------------------------------------------------------------------------


def test_bmp180_stm32_manifest_shape():
    """bmp180 stm32 条目：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda
    （SCL=PA6/SDA=PA7，macros 逐脚端口宏）；mspm0 条目原样零改动。"""
    manifest = ModuleManifest.load(MODULES / "bmp180")
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "bmp180_stm32.c",
        "bmp180_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "bmp180" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("BMP180_SCL", "i2c_scl", "PA6", True, ("BMP180_SCL_GPIO", "BMP180_SCL_PIN")),
        ("BMP180_SDA", "i2c_sda", "PA7", True, ("BMP180_SDA_GPIO", "BMP180_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/bmp180-pressure-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--bmp180-pressure-sensor.md",
        "B7",
        "ms5611",
        "0xFFFC",
        "未上板",
    ):
        assert needle in stm32.notes

    # mspm0 条目零改动（mspm0 文件齐 + 默认脚不变）
    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["bmp180.c", "bmp180.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("BMP180_SCL", "gpio_out", "PA23", True, ()),
        ("BMP180_SDA", "gpio_out", "PA24", True, ()),
    ]


def test_bmp180_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：BMP180_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+BMP180_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+BMP180_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+BMP180_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+BMP180_SDA_PIN\s+Pin_7", text)


def test_bmp180_stm32_single_select_generation(tmp_path):
    """bmp180 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 bmp180_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["bmp180"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/bmp180/code/bmp180_stm32.c").is_file()
    assert (out / "modules/bmp180/code/bmp180_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("bmp180_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_bmp180_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OUT_OD/IU——页面
    原式开漏+上拉输入主流一派）；页面原式地址/命令/换算保留；**页面缺陷
    防回潮**（B5 复用单次转换、NACK 状态码 1/2/3、无 char ack 死变量、
    B7 双分支保留、无 & 0xFFFC）。"""
    c = (MODULES / "bmp180" / "code" / "bmp180_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "bmp180" / "code" / "bmp180_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"
    # mspm0 零改动：stm32 源码不含 DL_GPIO 调用
    assert "DL_GPIO" not in code_only

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+BMP180_SDA_OUT\(\)\s+gpio_init\(BMP180_SDA_GPIO", code_only
    )
    assert re.search(
        r"BMP180_SDA_IN\(\)\s+gpio_init\(BMP180_SDA_GPIO, BMP180_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+BMP180_SDA\(x\)\s+gpio_set", code_only)
    assert "bmp180_iic_start" in code_only and "bmp180_iic_wait_ack" in code_only

    # 页面原式保留：地址 0xEE/0xEF、校准 0xAA/0xBE、系数 32768.0/2048.0/0.1f
    assert "BMP180_ADDR_W" in code_only and "BMP180_ADDR_R" in code_only
    assert "0xaa" in code_only and "0xbe" in code_only
    assert "32768.0" in code_only and "2048.0" in code_only and "0.1f" in code_only

    # 页面缺陷防回潮：① B5 复用（read_temp static + bmp180_b5 模块静态）
    assert "static uint8_t bmp180_read_temp" in code_only
    assert "bmp180_b5" in code_only
    # ② NACK → 状态码（write_cmd/read16 返回 1/2/3 + read 段级 1/2）
    assert "return 1;" in code_only and "return 2;" in code_only and "return 3;" in code_only
    # ③ 无 char ack 死变量
    assert "char ack" not in code_only
    # ④ B7 双分支保留（页面/标准——非恒真，else 分支不可删）
    assert "0x80000000u" in code_only
    assert "b7 < 0x80000000u" in code_only
    # ⑤ 无 & 0xFFFC 掩码（反向守卫）
    assert "0xFFFC" not in code_only
    # 海拔公式（44330/101325/5.255 + pow）
    assert "44330.0f" in code_only and "101325.0" in code_only and "5.255" in code_only


def test_bmp180_stm32_scl_init_guard():
    """SCL 初始化防回潮（批次 3/01）：init 必须含 gpio_init(BMP180_SCL_GPIO,
    BMP180_SCL_PIN, OUT_OD) + 置高——F1 复位后浮空输入、ODR 写入无效。"""
    c = (MODULES / "bmp180" / "code" / "bmp180_stm32.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert re.search(
        r"gpio_init\(BMP180_SCL_GPIO, BMP180_SCL_PIN, OUT_OD\)", code_only
    )
    assert "BMP180_SCL(1)" in code_only
