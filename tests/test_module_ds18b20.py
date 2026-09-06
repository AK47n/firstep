"""ds18b20 单总线温度模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 dht11 / joystick 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
单角色 DATA = gpio_out PA7——默认与母版 syscfg 一致性由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 DS18B20、模块
文件落盘、main.c 调 init/read_temp 过静态门禁）。单总线位时序走 delay 模块
（依赖声明），位槽时间轴（12us 采样点 / 60us 槽体 / 750us 复位）以源码常量
守卫钉死（页面上游缺陷 DS18B20_Reset 声明无定义已剔除）。
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
from contest_generator.platforms import (  # noqa: E402
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "ds18b20.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    uint8_t ok = ds18b20_init();\n"
    "    (void)ok;\n"
    "    float t = ds18b20_read_temp();\n"
    "    (void)t;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ds18b20_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    uint8_t ok = ds18b20_init();\n"
    "    (void)ok;\n"
    "    float t = ds18b20_read_temp();\n"
    "    (void)t;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/
# 母版 ml_i2c 调用/页面串台）。
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
    (r"MLX90614", "MLX90614 串台（页面 L107——仅 notes 记录，源码零）"),
]


def test_ds18b20_manifest_shape_mspm0():
    """ds18b20：双平台条目（mspm0 原样 + stm32 批次 4 新增）；依赖 delay；
    单角色 DATA = gpio_out PA7。"""
    manifest = ModuleManifest.load(MODULES / "ds18b20")
    assert manifest.slug == "ds18b20"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ds18b20.c", "ds18b20.h"]
    for rel in mspm0.files:
        assert (MODULES / "ds18b20" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("DS18B20_DATA", "gpio_out", "PA7", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_ds18b20_mspm0_syscfg_instances():
    """mspm0 母版：DS18B20 GPIO 实例（DATA 输出，initialValue SET = 空闲高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const DS18B20 = GPIO.addInstance();" in syscfg
    assert 'DS18B20.associatedPins[0].$name        = "DATA";' in syscfg
    assert 'DS18B20.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'DS18B20.associatedPins[0].initialValue = "SET";' in syscfg
    assert 'DS18B20.associatedPins[0].pin.$assign  = "PA7";' in syscfg


def test_ds18b20_mspm0_single_select_generation(tmp_path):
    """ds18b20 mspm0 单选生成：syscfg 只留 DS18B20、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ds18b20"])
    assert {m.slug for m in resolved.manifests} == {"ds18b20", "delay"}
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
    assert "const DS18B20 = GPIO.addInstance();" in syscfg
    assert 'DS18B20.associatedPins[0].pin.$assign  = "PA7";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ds18b20/code/ds18b20.c").is_file()
    assert (out / "modules/ds18b20/code/ds18b20.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


def _header_constants() -> dict[str, int]:
    header = (MODULES / "ds18b20" / "code" / "ds18b20.h").read_text(
        encoding="utf-8"
    )
    constants: dict[str, int] = {}
    for line in header.splitlines():
        m = re.match(r"#define\s+(DS18B20_T_[A-Z_]+)\s+(\d+)u", line)
        if m:
            constants[m.group(1)] = int(m.group(2))
    return constants


def test_ds18b20_bit_slot_timeline_guard():
    """位槽时间轴守卫（ir_remote_tx burst_cycle_formula_guard 先例）：
    读位槽 = 起始 2us + 采样点 12us + 尾部 50us = 64us；写位槽 = 2+60/60+2 =
    62us——全落页面 60-70us 位槽区间；源码只引用头文件常量，不散写字面量。"""
    constants = _header_constants()
    assert constants.get("DS18B20_T_READ_SAMPLE_US") == 12  # 页面 12us 采样点
    assert constants.get("DS18B20_T_WRITE_HIGH_US") == 60  # 页面 60us 槽体
    assert constants.get("DS18B20_T_READ_HOLD_US") == 50
    assert constants.get("DS18B20_T_RESET_LOW_US") == 750

    read_slot = (
        constants["DS18B20_T_READ_START_US"]
        + constants["DS18B20_T_READ_SAMPLE_US"]
        + constants["DS18B20_T_READ_HOLD_US"]
    )
    write_slot_1 = (
        constants["DS18B20_T_WRITE_START_US"] + constants["DS18B20_T_WRITE_HIGH_US"]
    )
    write_slot_0 = (
        constants["DS18B20_T_WRITE_LOW_US"] + constants["DS18B20_T_WRITE_END_US"]
    )
    assert read_slot == 64 and write_slot_1 == 62 and write_slot_0 == 62
    for slot in (read_slot, write_slot_1, write_slot_0):
        assert 60 <= slot <= 70, f"位槽 {slot}us 落页面 60-70us 区间"

    source = (MODULES / "ds18b20" / "code" / "ds18b20.c").read_text(
        encoding="utf-8"
    )
    assert "delay_us(DS18B20_T_READ_SAMPLE_US)" in source
    assert "delay_us(DS18B20_T_READ_HOLD_US)" in source
    assert "delay_us(DS18B20_T_WRITE_HIGH_US)" in source
    assert "delay_us(DS18B20_T_RESET_LOW_US)" in source
    # 负温补码换算常量守卫（页面 -0.0625 系数；常量单源头文件）
    header = (MODULES / "ds18b20" / "code" / "ds18b20.h").read_text(
        encoding="utf-8"
    )
    assert "0.0625f" in header
    assert "(-DS18B20_TEMP_SCALE)" in source
    assert "DS18B20_TEMP_SCALE" in source
    # 上游缺陷：页面头声明 DS18B20_Reset(void) 但 .c 无定义 → 已剔除
    assert "DS18B20_Reset" not in header


# ---------------------------------------------------------------------------
# 批次 4（wiki-stm32-batch4/04）：stm32 平台条目（单总线件 · 750ms 主缺陷修正）
# ---------------------------------------------------------------------------


def test_ds18b20_stm32_manifest_shape():
    """ds18b20 stm32 条目：双平台文件齐；stm32 单角色 = gpio_out（DATA=PB1，
    macros 端口宏）；mspm0 条目原样零改动。"""
    manifest = ModuleManifest.load(MODULES / "ds18b20")
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ds18b20_stm32.c",
        "ds18b20_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ds18b20" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("DS18B20_DATA", "gpio_out", "PB1", True, ("DS18B20_GPIO", "DS18B20_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/ds18b20-temp-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--ds18b20-temp-sensor.md",
        "750ms",
        "MLX90614",
        "未上板",
    ):
        assert needle in stm32.notes

    # mspm0 条目零改动（文件齐 + 默认脚不变）
    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ds18b20.c", "ds18b20.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("DS18B20_DATA", "gpio_out", "PA7", True, ()),
    ]


def test_ds18b20_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：DS18B20_GPIO/DS18B20_PIN 必须在母版 pin_config.h
    （默认 PB1——叠 motor MOTOR_B_DIR2）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+DS18B20_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+DS18B20_PIN\s+Pin_1", text)


def test_ds18b20_stm32_single_select_generation(tmp_path):
    """ds18b20 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 ds18b20_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ds18b20"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ds18b20/code/ds18b20_stm32.c").is_file()
    assert (out / "modules/ds18b20/code/ds18b20_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ds18b20_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def _ds18b20_stm32_header_constants() -> dict[str, int]:
    header = (MODULES / "ds18b20" / "code" / "ds18b20_stm32.h").read_text(
        encoding="utf-8"
    )
    constants: dict[str, int] = {}
    for line in header.splitlines():
        m = re.match(r"#define\s+(DS18B20_T_[A-Z_]+|DS18B20_CONVERT_MS)\s+(\d+)u", line)
        if m:
            constants[m.group(1)] = int(m.group(2))
    return constants


def test_ds18b20_stm32_bit_slot_timeline_guard():
    """stm32 位槽时间轴守卫（mspm0 test_ds18b20_bit_slot_timeline_guard
    镜像）：读位槽 = 2+12+50 = 64us；写位槽 = 2+60/60+2 = 62us——全落页面
    60-70us 区间；**0x44 后 750ms 转换等待钉死**（主缺陷修正防回潮）；源码
    只引用头文件常量，不散写字面量。"""
    constants = _ds18b20_stm32_header_constants()
    assert constants.get("DS18B20_T_READ_SAMPLE_US") == 12
    assert constants.get("DS18B20_T_WRITE_HIGH_US") == 60
    assert constants.get("DS18B20_T_READ_HOLD_US") == 50
    assert constants.get("DS18B20_T_RESET_LOW_US") == 750
    assert constants.get("DS18B20_CONVERT_MS") == 750  # 主缺陷修正（页面未等）

    read_slot = (
        constants["DS18B20_T_READ_START_US"]
        + constants["DS18B20_T_READ_SAMPLE_US"]
        + constants["DS18B20_T_READ_HOLD_US"]
    )
    write_slot_1 = (
        constants["DS18B20_T_WRITE_START_US"] + constants["DS18B20_T_WRITE_HIGH_US"]
    )
    write_slot_0 = (
        constants["DS18B20_T_WRITE_LOW_US"] + constants["DS18B20_T_WRITE_END_US"]
    )
    assert read_slot == 64 and write_slot_1 == 62 and write_slot_0 == 62
    for slot in (read_slot, write_slot_1, write_slot_0):
        assert 60 <= slot <= 70, f"位槽 {slot}us 落页面 60-70us 区间"

    c = (MODULES / "ds18b20" / "code" / "ds18b20_stm32.c").read_text(
        encoding="utf-8"
    )
    assert "delay_us(DS18B20_T_READ_SAMPLE_US)" in c
    assert "delay_us(DS18B20_T_READ_HOLD_US)" in c
    assert "delay_us(DS18B20_T_WRITE_HIGH_US)" in c
    assert "delay_us(DS18B20_T_RESET_LOW_US)" in c
    assert "delay_ms(DS18B20_CONVERT_MS)" in c  # 750ms 转换等待


def test_ds18b20_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用、**零 MLX90614 串台**（页面 L107 仅 notes 记录）；单总线方向切换
    （gpio_init OUT_PP/IU）；命令 0xCC/0x44/0xBE；0.0625f 负温补码注释；
    **主缺陷防回潮**（DS18B20_CONVERT_MS 750 等待 + 读毕释放总线）；
    **页外声明剔除**（无 DS18B20_Reset）。"""
    c = (MODULES / "ds18b20" / "code" / "ds18b20_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ds18b20" / "code" / "ds18b20_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"
    # mspm0 零改动：stm32 源码不含 DL_GPIO 调用
    assert "DL_GPIO" not in code_only

    # 单总线方向切换（页面原式 PP 输出 / IPU 输入 → OUT_PP/IU）
    assert re.search(
        r"#define\s+DS18B20_DATA_OUT\(\)\s+gpio_init\(DS18B20_GPIO, DS18B20_PIN, OUT_PP\)",
        code_only,
    )
    assert re.search(
        r"DS18B20_DATA_IN\(\)\s+gpio_init\(DS18B20_GPIO, DS18B20_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+DS18B20_DATA_SET\(x\)\s+gpio_set", code_only)

    # 命令：0xCC Skip ROM / 0x44 转换 / 0xBE 读暂存器
    assert "0xCCu" in code_only and "0x44u" in code_only and "0xBEu" in code_only
    # 换算：0.0625 系数 + 负温补码（(~temp)+1 × -0.0625——页面原式）
    assert "DS18B20_TEMP_SCALE" in code_only
    assert "0.0625f" in h
    assert "(~temp) + 1u" in code_only
    assert "(-DS18B20_TEMP_SCALE)" in code_only
    # 主缺陷防回潮：750ms 转换等待
    assert "delay_ms(DS18B20_CONVERT_MS)" in code_only
    # 读毕释放总线（read 尾部 DATA_OUT + SET(1)——防总线占用）
    assert code_only.count("DS18B20_DATA_SET(1)") >= 3  # init + start_convert + read 尾
    # 页外声明剔除：无 DS18B20_Reset（页面 .h 声明无定义）
    assert "DS18B20_Reset" not in code_only
    assert "DS18B20_Reset" not in h
