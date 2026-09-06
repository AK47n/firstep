"""ms5611 高精度气压/温度传感器模块：真实库 + 真实母版不变量与 mspm0
单选生成。

与 sht30 / bmp180 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双角色 = PA28/PA31——母版 syscfg 由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 MS5611 + delay
展开、模块文件落盘、main.c 调 init/read/read_altitude 过静态门禁）。
**压力换算纯函数单测（与 bmp180 共用海拔公式镜像——bmp180 先例）**：Python
镜像 ms5611_altitude(pa)（44330 公式）断言同表（math.pow 基线 ±0.5m）。
源码守卫（防回潮）：复位/PROM/转换命令/器件地址常量、页面原式系数、
温度出参 TEMP/100.0（0.01℃ 分辨率修正）、气压出参 Pa、10ms 转换等待 ×4（段内×2 转换 + 段间×2）、
无 printf/IRQHandler/main、页面原式注释。全程无 LLM、无服务。
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
    '#include "ms5611.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ms5611_init();\n"
    "    float t = 0.0f, p = 0.0f;\n"
    "    uint8_t ret = ms5611_read(&t, &p);\n"
    "    (void)ret;\n"
    "    float alt = ms5611_read_altitude(p);\n"
    "    (void)alt;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ms5611_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    float t = 0.0f, p = 0.0f;\n"
    "    ms5611_init();\n"
    "    (void)ms5611_read(&t, &p);\n"
    "    (void)ms5611_read_altitude(p);\n"
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


def ms5611_altitude(pa: float) -> float:
    """C 侧 ms5611_read_altitude 语义镜像（与 bmp180 共用 44330 公式——
    math.pow 基线）。"""
    return 44330.0 * (1.0 - math.pow(pa / 101325.0, 1.0 / 5.255))


def ms5611_pressure(d1: int, d2: int, cal: list[int]) -> tuple[int, float, int]:
    """C 侧 ms5611_read 换算语义镜像（**int64 口径**——页面公式 + 人工复核
    修正 ⑥：dT 有符号 64 位；TEMP 的 (float)dT×C6 按 float32 单精度（同
    C）、OFF 的 C4×dT/128 按整数除法向零截断（同 C）、P 的 long long→
    double 转精确舍入（同 C——IEEE））。返回 (dT, TEMP0.01C, P_Pa)。"""
    dT = d2 - cal[5] * 256
    temp = 2000.0 + _f32(float(dT) * cal[6]) / 8388608.0
    off = cal[2] * 65536.0 + float(_div_tz(cal[4] * dT, 128))
    sens = cal[1] * 32768.0 + (cal[3] * dT) / 256.0
    p = int((d1 * sens / 2097152.0 - off) / 32768.0)
    return dT, temp, p


def _f32(x: float) -> float:
    """float32 舍入（同 C 单精度算术）。"""
    import struct
    return struct.unpack("f", struct.pack("f", x))[0]


def _div_tz(a: int, b: int) -> int:
    """C 整数除法（向零截断——Python // 为向下取整，负值不等同）。"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def test_ms5611_pressure_conversion_int64_regression():
    """气压换算 int64 回归单测（Standards 轴审查整改——页面 C4×dT/128、
    C3×dT/256.0 在 32 位有符号乘法溢出（积可达 1e11 ≫ 2^31，全温区多数读数
    偏差数十 hPa）→ 本件 dT 有符号 64 位 long long（人工复核修正 ⑥）。
    回归表基线按 Python 精确整数（int64 语义）+ 页面 double/float 表达式
    计算；用例含 32 位回绕对照会在 dT=±3.6e6 时偏差 ~18kPa（修正前形态）。"""
    cal = [0, 40127, 36924, 29016, 33123, 29022, 16437, 0]  # 典型量级系数
    # dT=+3.6e6（高温）：修正前 32 位形态 P≈80093，偏差 18203 Pa
    dT, temp, p = ms5611_pressure(8000000, 29022 * 256 + 3600000, cal)
    assert dT == 3600000
    assert round(temp, 1) == 9054.0  # 0.01℃ 单位（≈90.5℃，页面 float 口径）
    assert p == 98296
    # dT=-3.6e6（低温）：修正前 32 位形态 P≈78355，偏差 -18203 Pa
    dT, temp, p = ms5611_pressure(8000000, 29022 * 256 - 3600000, cal)
    assert dT == -3600000
    assert round(temp, 1) == -5054.0
    assert p == 60152
    # dT=0（20.00℃ 校准点）：两形态一致（无溢出边界——回归锚点）
    dT, temp, p = ms5611_pressure(8000000, 29022 * 256, cal)
    assert dT == 0
    assert round(temp, 1) == 2000.0
    assert p == 79224


def test_ms5611_altitude_formula_matches_baseline():
    """气压→海拔换算纯函数单测（与 bmp180 共用公式镜像，math.pow 基线
    ±0.5m）：页面原式钉死。"""
    assert ms5611_altitude(101325.0) == 0.0
    for pa, expect in (
        (100000.0, 110.9),
        (95000.0, 540.4),
        (90000.0, 988.6),
        (85000.0, 1457.5),
    ):
        got = ms5611_altitude(pa)
        assert abs(got - expect) <= 0.5, (pa, got, expect)


def test_ms5611_manifest_shape_mspm0():
    """ms5611：双平台条目（mspm0 原样 + stm32 批次 4 新增）；依赖 delay；
    SCL/SDA 双角色（gpio_out）。"""
    manifest = ModuleManifest.load(MODULES / "ms5611")
    assert manifest.slug == "ms5611"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ms5611.c", "ms5611.h"]
    for rel in mspm0.files:
        assert (MODULES / "ms5611" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MS5611_SCL", "gpio_out", "PA28", True, ()),
        ("MS5611_SDA", "gpio_out", "PA31", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 关键 notes 子串：出参单位修正 + 人工复核修正 + 与 bmp180 分工 + 未上板
    assert "0.01℃" in mspm0.notes
    assert "Pa" in mspm0.notes
    assert "bmp180" in mspm0.notes
    assert "未上板" in mspm0.notes


def test_ms5611_mspm0_syscfg_instances():
    """mspm0 母版：MS5611 GPIO 实例（SCL/SDA 输出 PA28/PA31）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const MS5611 = GPIO.addInstance();" in syscfg
    assert 'MS5611.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'MS5611.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'MS5611.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'MS5611.associatedPins[1].pin.$assign  = "PA31";' in syscfg


def test_ms5611_mspm0_single_select_generation(tmp_path):
    """ms5611 mspm0 单选生成：syscfg 只留 MS5611、依赖 delay 展开、模块文件
    落盘、main.c 调用过静态门禁。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ms5611"])
    assert {m.slug for m in resolved.manifests} == {"ms5611", "delay"}
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
    assert "const MS5611 = GPIO.addInstance();" in syscfg
    assert 'MS5611.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'MS5611.associatedPins[1].pin.$assign  = "PA31";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "SHT30",
        "SHT20", "JY61P", "SGP30", "AGS10", "BMP180", "TTP224", "HUMAN_IR",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ms5611/code/ms5611.c").is_file()
    assert (out / "modules/ms5611/code/ms5611.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_ms5611_source_guards():
    """源码守卫（防回潮）：复位/PROM/转换命令/器件地址常量、页面原式系数、
    温度出参 0.01℃（TEMP/100.0）、气压出参 Pa、10ms 转换等待 ×4、无
    printf/IRQHandler/main。"""
    source = (MODULES / "ms5611" / "code" / "ms5611.c").read_text(encoding="utf-8")
    header = (MODULES / "ms5611" / "code" / "ms5611.h").read_text(encoding="utf-8")
    # 器件地址（页面 0xEE|0/0xEE|1，CSB 高）与复位/PROM/转换命令
    assert "MS5611_ADDR_W 0xEEu" in header
    assert "MS5611_ADDR_R 0xEFu" in header
    assert "MS5611_CMD_RESET 0x1Eu" in header
    assert "MS5611_PROM_BASE 0xA0u" in header
    assert "MS5611_CMD_D1 0x48u" in header
    assert "MS5611_CMD_D2 0x58u" in header
    # 页面原式换算系数（C5×256、C6/8388608、C2×65536、C1×32768、P=/2097152）
    assert "256.0" in source
    assert "8388608.0" in source
    assert "65536.0" in source
    assert "32768.0" in source
    assert "2097152.0" in source
    # 温度出参 TEMP/100.0（0.01℃ 分辨率——页面整数℃截断修正）
    assert "temp / 100.0f" in source
    # 气压出参 Pa（P 单位 0.01mbar == 1Pa——页面 /100 = hPa 修正）
    assert "pressure_pa" in source and "0.01mbar" in source
    # 10ms 转换等待 ×4（页面原式：每段内部命令/数据请求各 10ms ×2 转换 +
    # 段间 10ms ×2——Get_TEMP L384/386）
    assert "MS5611_CONV_WAIT_MS 10u" in header
    assert source.count("delay_ms(MS5611_CONV_WAIT_MS)") == 4
    # 复位后 300ms（页面「等待初始化完成」）
    assert "MS5611_INIT_WAIT_MS 300u" in header
    # 页面原式注释与出参单位说明
    assert "0.01℃" in header or "0.01℃" in source
    assert "printf(" not in source and "printf(" not in header
    assert "IRQHandler" not in source and "main(" not in source


# ---------------------------------------------------------------------------
# 批次 4（wiki-stm32-batch4/02）：stm32 平台条目（64 位换算核心件）
# ---------------------------------------------------------------------------


def test_ms5611_stm32_manifest_shape():
    """ms5611 stm32 条目：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda
    （SCL=PA6/SDA=PA7，macros 逐脚端口宏）；mspm0 条目原样零改动。"""
    manifest = ModuleManifest.load(MODULES / "ms5611")
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ms5611_stm32.c",
        "ms5611_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ms5611" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("MS5611_SCL", "i2c_scl", "PA6", True, ("MS5611_SCL_GPIO", "MS5611_SCL_PIN")),
        ("MS5611_SDA", "i2c_sda", "PA7", True, ("MS5611_SDA_GPIO", "MS5611_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/ms5611-pressure-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--ms5611-pressure-sensor.md",
        "long long",
        "bmp180",
        "0.01℃",
        "未上板",
    ):
        assert needle in stm32.notes

    # mspm0 条目零改动（文件齐 + 默认脚不变）
    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ms5611.c", "ms5611.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MS5611_SCL", "gpio_out", "PA28", True, ()),
        ("MS5611_SDA", "gpio_out", "PA31", True, ()),
    ]


def test_ms5611_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：MS5611_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+MS5611_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+MS5611_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+MS5611_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+MS5611_SDA_PIN\s+Pin_7", text)


def test_ms5611_stm32_single_select_generation(tmp_path):
    """ms5611 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 ms5611_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ms5611"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ms5611/code/ms5611_stm32.c").is_file()
    assert (out / "modules/ms5611/code/ms5611_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ms5611_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ms5611_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OUT_OD/IU）；页面原式
    地址/命令/换算保留；**64 位换算防回潮**（dT 声明 long long、无 uint32_t
    dT 式、dT 表达式还原）；**页面缺陷防回潮**（TEMP/100.0 出 0.01℃、出 Pa、
    PROM 应答检查返回 3、段间 2×10ms、无 printf）。"""
    c = (MODULES / "ms5611" / "code" / "ms5611_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ms5611" / "code" / "ms5611_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"
    # mspm0 零改动：stm32 源码不含 DL_GPIO 调用
    assert "DL_GPIO" not in code_only

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+MS5611_SDA_OUT\(\)\s+gpio_init\(MS5611_SDA_GPIO", code_only
    )
    assert re.search(
        r"MS5611_SDA_IN\(\)\s+gpio_init\(MS5611_SDA_GPIO, MS5611_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+MS5611_SDA\(x\)\s+gpio_set", code_only)
    assert "ms5611_iic_start" in code_only and "ms5611_iic_wait_ack" in code_only

    # 页面原式保留：复位 0x1E / PROM 0xA0 / 转换命令 0x48 0x58
    assert "MS5611_CMD_RESET" in code_only and "MS5611_CMD_D1" in code_only
    assert "MS5611_CMD_D2" in code_only and "MS5611_PROM_BASE" in code_only

    # **64 位换算防回潮**：dT 声明 long long（无 uint32_t dT 式）+ 换算系数
    assert "long long dT = 0;" in code_only
    assert re.search(r"long long\s+dT|long long dT", code_only)
    assert "uint32_t dT" not in code_only
    assert "256.0" in code_only and "8388608.0" in code_only
    assert "65536.0" in code_only and "32768.0" in code_only
    assert "2097152.0" in code_only
    # 温度出参 TEMP/100.0（0.01℃——页面整数℃截断修正）
    assert "temp / 100.0f" in code_only
    # 气压出参 Pa（注释记录 P 单位 0.01mbar == 1Pa）
    assert "0.01mbar" in c
    assert "(float)p" in code_only
    # PROM 应答检查（逐段 return 3）
    assert "return 3;" in code_only
    # 段间 2×10ms（10ms 转换等待共 4 处：段内×2 + 段间×2）
    assert c.count("delay_ms(MS5611_CONV_WAIT_MS)") == 4
    # 返回码 0/1/2/3 齐
    assert "return 3;" in code_only and "return 2;" in code_only
    assert "return 1;" in code_only


def test_ms5611_stm32_scl_init_guard():
    """SCL 初始化防回潮（批次 3/01）：init 必须含 gpio_init(MS5611_SCL_GPIO,
    MS5611_SCL_PIN, OUT_OD) + 置高——F1 复位后浮空输入、ODR 写入无效。"""
    c = (MODULES / "ms5611" / "code" / "ms5611_stm32.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert re.search(
        r"gpio_init\(MS5611_SCL_GPIO, MS5611_SCL_PIN, OUT_OD\)", code_only
    )
    assert "MS5611_SCL(1)" in code_only


def test_ms5611_stm32_int64_mirror_regression():
    """stm32 版 64 位换算镜像回归（与 mspm0 共用 ms5611_pressure int64 镜像
    ——mspm0 批 13 先例）：负温 dT 向量（int64 基线）钉死——防 uint32_t 回潮
    （32 位形态在 ±3.6e6 偏差 ~18kPa）。"""
    cal = [0, 40127, 36924, 29016, 33123, 29022, 16437, 0]  # 典型量级系数
    # dT=+3.6e6（高温）
    dT, temp, p = ms5611_pressure(8000000, 29022 * 256 + 3600000, cal)
    assert dT == 3600000
    assert round(temp, 1) == 9054.0
    assert p == 98296
    # dT=-3.6e6（低温——32 位 uint32_t 回绕路径）
    dT, temp, p = ms5611_pressure(8000000, 29022 * 256 - 3600000, cal)
    assert dT == -3600000
    assert round(temp, 1) == -5054.0
    assert p == 60152
    assert p > 50000  # 合理气压量级（32 位形态会偏差 ~18kPa 出界）
