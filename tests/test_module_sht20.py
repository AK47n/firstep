"""sht20 温湿度模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 sht30 / aht10 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PA16/PA17——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
SHT20、模块文件落盘、main.c 调 init/read 过静态门禁）。软 I2C 位操作走
delay 模块（依赖声明），页面原式公式/命令字/14bit 状态位掩码修正/测量
重试窗口源码守卫钉死（页面原式 + 人工复核修正——与库内 aht10/dht11/sht30
分工与 0x40×pca9685 地址冲突提醒写入 notes）。
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
    '#include "sht20.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    sht20_init();\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    uint8_t ok = sht20_read(&t, &h);\n"
    "    (void)ok;\n"
    "    (void)t;\n"
    "    (void)h;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_sht20_manifest_shape_mspm0():
    """sht20：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "sht20")
    assert manifest.slug == "sht20"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["sht20.c", "sht20.h"]
    for rel in mspm0.files:
        assert (MODULES / "sht20" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SHT20_SCL", "gpio_out", "PA16", True, ()),
        ("SHT20_SDA", "gpio_out", "PA17", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 与库内 aht10 / dht11 / sht30 的分工说明必须写入 notes
    assert "aht10" in mspm0.notes
    assert "dht11" in mspm0.notes
    assert "sht30" in mspm0.notes
    # SHT2x 旧系列 / 地址 0x40 / 低功耗单次测量 / 地址冲突提醒
    assert "SHT2x" in mspm0.notes
    assert "0x40" in mspm0.notes
    assert "pca9685" in mspm0.notes
    # CRC 取舍说明（页面无 CRC）
    assert "CRC" in mspm0.notes


def test_sht20_mspm0_syscfg_instances():
    """mspm0 母版：SHT20 GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SHT20 = GPIO.addInstance();" in syscfg
    assert 'SHT20.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'SHT20.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'SHT20.associatedPins[0].pin.$assign  = "PA16";' in syscfg
    assert 'SHT20.associatedPins[1].pin.$assign  = "PA17";' in syscfg


def test_sht20_mspm0_single_select_generation(tmp_path):
    """sht20 mspm0 单选生成：syscfg 只留 SHT20、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["sht20"])
    assert {m.slug for m in resolved.manifests} == {"sht20", "delay"}
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
    assert 'SHT20.associatedPins[0].pin.$assign  = "PA16";' in syscfg
    assert 'SHT20.associatedPins[1].pin.$assign  = "PA17";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "BH1750", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "SHT30", "JY61P", "L298N_PWM", "L298N",
        "OPENMV4_UART",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/sht20/code/sht20.c").is_file()
    assert (out / "modules/sht20/code/sht20.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()


def test_sht20_formula_and_command_guards():
    """页面原式公式/命令字/掩码修正/重试窗口守卫（防回潮）。"""
    source = (MODULES / "sht20" / "code" / "sht20.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "sht20" / "code" / "sht20.h").read_text(
        encoding="utf-8"
    )
    # 页面公式原式（0.01 系数口径）
    assert "65536.0f" in source
    assert "* 175.72f - 46.85f" in source
    assert "* 125.0f - 6.0f" in source
    # 命令/地址常量（头文件单源 + 源码引用；写 0x80/读 0x81 = 0x40<<1 形态）
    assert re.search(r"SHT20_CMD_TEMP\s+0xF3u", header)
    assert re.search(r"SHT20_CMD_HUMI\s+0xF5u", header)
    assert re.search(r"SHT20_ADDR\s+0x40u", header)
    assert "SHT20_CMD_TEMP" in source
    assert "SHT20_CMD_HUMI" in source
    assert "(SHT20_ADDR << 1) | 0u" in source  # 写地址（页面 0x80 形态）
    assert "(SHT20_ADDR << 1) | 1u" in source  # 读地址（页面 0x81 形态）
    # 无 CRC（页面取舍：数据 2 字节 + NACK）——无 CRC 计算函数
    assert "crc8" not in source.lower()
    # 14bit 状态位掩码修正（页面正文要求、页面代码未实现）
    assert "0xFFFCu" in source
    # 测量等待重试窗口（≤50×2ms = 100ms 覆盖页面 85ms 最长测量）
    assert re.search(r"SHT20_READ_RETRY_MAX\s+50u", header)
    assert re.search(r"SHT20_READ_RETRY_MS\s+2u", header)
    assert "SHT20_READ_RETRY_MAX" in source
    # 页面演示/调试件剔除
    assert "printf" not in source
    assert "IRQHandler" not in source
    assert "main" not in source
