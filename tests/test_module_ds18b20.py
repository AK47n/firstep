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


def test_ds18b20_manifest_shape_mspm0():
    """ds18b20：仅 mspm0 平台条目；依赖 delay；单角色 DATA = gpio_out PA7。"""
    manifest = ModuleManifest.load(MODULES / "ds18b20")
    assert manifest.slug == "ds18b20"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

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
