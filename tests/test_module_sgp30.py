"""sgp30 空气质量传感器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 sht30 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、双角色
SGP30_SCL/SGP30_SDA = gpio_out PA18/PB9——软 I2C 2 脚不占硬件 I2C 外设）、
mspm0 单选生成（syscfg 裁剪保留 SGP30 实例 + 模块文件落盘 + main.c 调
init/read 过静态门禁）。命令常量 / CRC8 原式 / 读满 6 字节两组校验（器件
正确性修正——页面缺 CRC 且只读 5 字节漏 TVOC CRC）源码守卫钉死。
全程无 LLM、无服务。
"""

from __future__ import annotations

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


def test_sgp30_manifest_shape_mspm0():
    """sgp30：仅 mspm0 平台条目；依赖 delay；双角色 = gpio_out PA18/PB9
    （软 I2C 2 脚）。"""
    manifest = ModuleManifest.load(MODULES / "sgp30")
    assert manifest.slug == "sgp30"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["sgp30.c", "sgp30.h"]
    for rel in mspm0.files:
        assert (MODULES / "sgp30" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SGP30_SCL", "gpio_out", "PA18", True, ()),
        ("SGP30_SDA", "gpio_out", "PB9", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 器件正确性修正记录（CRC 补齐）必须写入 notes
    assert "CRC" in mspm0.notes
    assert "器件正确性" in mspm0.notes


def test_sgp30_mspm0_master_syscfg_instances():
    """mspm0 母版：SGP30 GPIO 实例（SCL=PA18 输出 / SDA=PB9 输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SGP30 = GPIO.addInstance();" in syscfg
    assert 'SGP30.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'SGP30.associatedPins[0].pin.$assign  = "PA18";' in syscfg
    assert 'SGP30.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'SGP30.associatedPins[1].pin.$assign  = "PB9";' in syscfg


def test_sgp30_mspm0_single_select_generation(tmp_path):
    """sgp30 mspm0 单选生成：syscfg 保留 SGP30 + 依赖 delay 模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["sgp30"])
    assert {m.slug for m in resolved.manifests} == {"sgp30", "delay"}
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
    assert 'SGP30.associatedPins[0].pin.$assign  = "PA18";' in syscfg
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
    assert (out / "modules/delay/code/delay.c").is_file()


def test_sgp30_protocol_and_crc_guards():
    """命令常量 / CRC8 原式 / 读满 6 字节两组校验守卫（防回潮）：
    - 0x2003（init_air_quality）/ 0x2008（measure_air_quality）命令常量；
    - CRC8 多项式 0x31、初值 0xFF；
    - 页面实现缺 CRC 校验且只读 5 字节漏 TVOC CRC 字节——修正后必须读 6 字节
      且两组校验（buff[2] = CO2 CRC、buff[5] = TVOC CRC）；
    - 双出参 tvoc_ppb/co2_ppm（页面打包 uint32_t 收敛）。"""
    source = (MODULES / "sgp30" / "code" / "sgp30.c").read_text(encoding="utf-8")
    header = (MODULES / "sgp30" / "code" / "sgp30.h").read_text(encoding="utf-8")
    assert "0x2003u" in header
    assert "0x2008u" in header
    assert "0x31u" in source
    assert "0xFFu" in source
    assert "sgp30_crc8(buff, 2) != buff[2]" in source  # CO2 两组 CRC 校验
    assert "sgp30_crc8(buff + 3, 2) != buff[5]" in source  # TVOC 组（页面漏读）
    assert "buff[5] = sgp30_iic_read_byte();" in source  # 读满 6 字节（器件修正）
    assert "tvoc_ppb" in header and "co2_ppm" in header  # 双出参
    assert "IIC_Stop" not in source  # 页面未用该命名（原语静态化）
