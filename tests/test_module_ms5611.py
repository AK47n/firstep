"""ms5611 高精度气压/温度传感器模块：真实库 + 真实母版不变量与 mspm0
单选生成。

与 sht30 / bmp180 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双角色 = PA28/PA31——母版 syscfg 由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 MS5611 + delay
展开、模块文件落盘、main.c 调 init/read/read_altitude 过静态门禁）。
**压力换算纯函数单测（与 bmp180 共用海拔公式镜像——bmp180 先例）**：Python
镜像 ms5611_altitude(pa)（44330 公式）断言同表（math.pow 基线 ±0.5m）。
源码守卫（防回潮）：复位/PROM/转换命令/器件地址常量、页面原式系数、
温度出参 TEMP/100.0（0.01℃ 分辨率修正）、气压出参 Pa、10ms 转换等待 ×2、
无 printf/IRQHandler/main、页面原式注释。全程无 LLM、无服务。
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


def ms5611_altitude(pa: float) -> float:
    """C 侧 ms5611_read_altitude 语义镜像（与 bmp180 共用 44330 公式——
    math.pow 基线）。"""
    return 44330.0 * (1.0 - math.pow(pa / 101325.0, 1.0 / 5.255))


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
    """ms5611：仅 mspm0 平台条目；依赖 delay；SCL/SDA 双角色（gpio_out）。"""
    manifest = ModuleManifest.load(MODULES / "ms5611")
    assert manifest.slug == "ms5611"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

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
    温度出参 0.01℃（TEMP/100.0）、气压出参 Pa、10ms 转换等待 ×2、无
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
    # 10ms 转换等待 ×2（命令段 + 数据请求段——页面原式）
    assert "MS5611_CONV_WAIT_MS 10u" in header
    assert source.count("delay_ms(MS5611_CONV_WAIT_MS)") == 2
    # 复位后 300ms（页面「等待初始化完成」）
    assert "MS5611_INIT_WAIT_MS 300u" in header
    # 页面原式注释与出参单位说明
    assert "0.01℃" in header or "0.01℃" in source
    assert "printf(" not in source and "printf(" not in header
    assert "IRQHandler" not in source and "main(" not in source
