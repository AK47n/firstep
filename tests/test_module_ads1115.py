"""ads1115 四通道 16bit 外扩 ADC 模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 aht10 / bh1750 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PA16/PA17——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
ADS1115、模块文件落盘、main.c 调 init/read/set_gain 等过静态门禁）。
软 I2C 位操作走 delay 模块（依赖声明），电压换算公式源码守卫钉死
（页面负数换算缺陷已修正——上游缺陷记录见 manifest notes）。
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
    "        int16_t again = ads1115_read(0);\n"
    "        (void)raw;\n"
    "        (void)volt;\n"
    "        (void)again;\n"
    "    }\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ads1115_manifest_shape_mspm0():
    """ads1115：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "ads1115")
    assert manifest.slug == "ads1115"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ads1115.c", "ads1115.h"]
    for rel in mspm0.files:
        assert (MODULES / "ads1115" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("ADS1115_SCL", "gpio_out", "PA16", True, ()),
        ("ADS1115_SDA", "gpio_out", "PA17", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 与库内 adc 模块的分工说明必须写入 notes（判据：外扩 vs 板载）
    assert "ADC12_0" in mspm0.notes
    assert "16bit" in mspm0.notes


def test_ads1115_mspm0_syscfg_instances():
    """mspm0 母版：ADS1115 GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const ADS1115 = GPIO.addInstance();" in syscfg
    assert 'ADS1115.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'ADS1115.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'ADS1115.associatedPins[0].pin.$assign  = "PA16";' in syscfg
    assert 'ADS1115.associatedPins[1].pin.$assign  = "PA17";' in syscfg


def test_ads1115_mspm0_single_select_generation(tmp_path):
    """ads1115 mspm0 单选生成：syscfg 只留 ADS1115、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ads1115"])
    assert {m.slug for m in resolved.manifests} == {"ads1115", "delay"}
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
    assert 'ADS1115.associatedPins[0].pin.$assign  = "PA16";' in syscfg
    assert 'ADS1115.associatedPins[1].pin.$assign  = "PA17";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "BH1750", "SR04", "JOYSTICK", "MOTOR_PID",
        "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0",
        "ADC12_0", "PWMAB", "DC_MOTOR", "RC522",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ads1115/code/ads1115.c").is_file()
    assert (out / "modules/ads1115/code/ads1115.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()


def test_ads1115_voltage_formula_guards():
    """电压换算源码守卫：补码 / 32768 × FSR（页面负数分支缺陷已修正——
    `(65535-num)*0.000125` 与 `num>32768`（未含 32768）不得回潮）。"""
    source = (MODULES / "ads1115" / "code" / "ads1115.c").read_text(
        encoding="utf-8"
    )
    assert "32768.0f" in source
    assert "* 0.000125" not in source  # 页面负数换算系数（注释引用除外，防代码回潮）
    assert "65535-num" not in source
    header = (MODULES / "ads1115" / "code" / "ads1115.h").read_text(
        encoding="utf-8"
    )
    # MUX 通道编码：AIN0-3 单端 = 0x04+ch，位 14-12
    assert "0x04u | (ch" in source
    assert "0x7000u" in header  # MUX 位掩码
    assert "ADS1115_DEFAULT_CONFIG 0xC283u" in header  # 页面最终配置
