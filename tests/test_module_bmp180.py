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
from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
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
    """bmp180：仅 mspm0 平台条目；依赖 delay；SCL/SDA 双角色（gpio_out）。"""
    manifest = ModuleManifest.load(MODULES / "bmp180")
    assert manifest.slug == "bmp180"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

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
