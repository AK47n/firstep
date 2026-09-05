"""sht30 温湿度模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 aht10 / ads1115 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PA28/PA31——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
SHT30、模块文件落盘、main.c 调 init/read/read_temperature/read_humidity 过
静态门禁）。软 I2C 位操作走 delay 模块（依赖声明），CRC8 与 0.01 换算公式
源码守卫钉死（页面原式；与库内 aht10/dht11 分工写入 notes）。
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
    '#include "sht30.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    sht30_init();\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    uint8_t ok = sht30_read(&t, &h);\n"
    "    (void)ok;\n"
    "    (void)t;\n"
    "    (void)h;\n"
    "    float t2 = 0.0f;\n"
    "    (void)sht30_read_temperature(&t2);\n"
    "    float h2 = 0.0f;\n"
    "    (void)sht30_read_humidity(&h2);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_sht30_manifest_shape_mspm0():
    """sht30：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "sht30")
    assert manifest.slug == "sht30"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["sht30.c", "sht30.h"]
    for rel in mspm0.files:
        assert (MODULES / "sht30" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SHT30_SCL", "gpio_out", "PA28", True, ()),
        ("SHT30_SDA", "gpio_out", "PA31", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 与库内 aht10 / dht11 / mlx90614 的分工说明必须写入 notes
    assert "aht10" in mspm0.notes
    assert "dht11" in mspm0.notes
    assert "mlx90614" in mspm0.notes


def test_sht30_mspm0_syscfg_instances():
    """mspm0 母版：SHT30 GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SHT30 = GPIO.addInstance();" in syscfg
    assert 'SHT30.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'SHT30.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'SHT30.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'SHT30.associatedPins[1].pin.$assign  = "PA31";' in syscfg


def test_sht30_mspm0_single_select_generation(tmp_path):
    """sht30 mspm0 单选生成：syscfg 只留 SHT30、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["sht30"])
    assert {m.slug for m in resolved.manifests} == {"sht30", "delay"}
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
    assert 'SHT30.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'SHT30.associatedPins[1].pin.$assign  = "PA31";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "BH1750", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/sht30/code/sht30.c").is_file()
    assert (out / "modules/sht30/code/sht30.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()


def test_sht30_crc8_and_formula_guards():
    """CRC8 原式与 0.01 换算公式守卫（防回潮）：多项式 0x31 / 初值 0xFF、
    温度 ×175−45 / 湿度 ×100（/65535.0f）；命令常量在头文件单源。"""
    source = (MODULES / "sht30" / "code" / "sht30.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "sht30" / "code" / "sht30.h").read_text(
        encoding="utf-8"
    )
    # CRC8（页面原式）
    assert "0x31u" in source
    assert "0xFFu" in source
    assert "sht30_crc8" in source
    # 换算公式（页面 0.01 系数）
    assert "65535.0f" in source
    assert "* 175.0f - 45.0f" in source
    assert "* 100.0f" in source
    # 命令/地址常量（头文件单源 + 源码引用）
    assert re.search(r"SHT30_CMD_PERIODIC\s+0x2130u", header)
    assert re.search(r"SHT30_CMD_READ\s+0xE000u", header)
    assert re.search(r"SHT30_ADDR\s+0x44u", header)
    assert "SHT30_CMD_PERIODIC" in source
    assert "SHT30_CMD_READ" in source
