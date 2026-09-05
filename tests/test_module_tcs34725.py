"""tcs34725 颜色识别传感器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 aht10 / bh1750 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PA23/PA24——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
TCS34725、模块文件落盘、main.c 调 init/read_rgb/rgb_to_hsl 等过静态门禁）。
软 I2C 位操作走 delay 模块（依赖声明）；ID 判定 `||` 与 RGBtoHSL 公式源码头
守卫钉死（页面按位或写法已修正——notes 记录）。
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
    '#include "tcs34725.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    if (tcs34725_init() == 0) {\n"
    "        while (1) {\n"
    "        }\n"
    "    }\n"
    "    TCS34725_RGBC rgb;\n"
    "    TCS34725_HSL hsl;\n"
    "    tcs34725_set_gain(TCS34725_GAIN_4X);\n"
    "    tcs34725_set_integration_time(TCS34725_INTEGRATIONTIME_50MS);\n"
    "    if (tcs34725_read_rgb(&rgb)) {\n"
    "        tcs34725_rgb_to_hsl(&rgb, &hsl);\n"
    "        (void)hsl.h;\n"
    "        (void)hsl.s;\n"
    "        (void)hsl.l;\n"
    "    }\n"
    "    tcs34725_disable();\n"
    "    tcs34725_enable();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_tcs34725_manifest_shape_mspm0():
    """tcs34725：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "tcs34725")
    assert manifest.slug == "tcs34725"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["tcs34725.c", "tcs34725.h"]
    for rel in mspm0.files:
        assert (MODULES / "tcs34725" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("TCS34725_SCL", "gpio_out", "PA23", True, ()),
        ("TCS34725_SDA", "gpio_out", "PA24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_tcs34725_mspm0_syscfg_instances():
    """mspm0 母版：TCS34725 GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const TCS34725 = GPIO.addInstance();" in syscfg
    assert 'TCS34725.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'TCS34725.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'TCS34725.associatedPins[0].pin.$assign  = "PA23";' in syscfg
    assert 'TCS34725.associatedPins[1].pin.$assign  = "PA24";' in syscfg


def test_tcs34725_mspm0_single_select_generation(tmp_path):
    """tcs34725 mspm0 单选生成：syscfg 只留 TCS34725、模块文件落盘、门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["tcs34725"])
    assert {m.slug for m in resolved.manifests} == {"tcs34725", "delay"}
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
    assert "const TCS34725 = GPIO.addInstance();" in syscfg
    assert 'TCS34725.associatedPins[0].pin.$assign  = "PA23";' in syscfg
    assert 'TCS34725.associatedPins[1].pin.$assign  = "PA24";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "BH1750", "ADS1115", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "PWMAB", "MAX7219",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/tcs34725/code/tcs34725.c").is_file()
    assert (out / "modules/tcs34725/code/tcs34725.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_tcs34725_id_check_and_hsl_formula_guards():
    """源码守卫：ID 判定必须 ||（页面按位或写法不得回潮）；RGBtoHSL 页面原式
    保留（Clear 通道标定 [0,100] + max3v/min3v 括号法 + 分段补偿）。"""
    source = (MODULES / "tcs34725" / "code" / "tcs34725.c").read_text(
        encoding="utf-8"
    )
    assert "id == 0x4D || id == 0x44" in source
    assert "id == 0x4D | id == 0x44" not in source
    assert "MAX3V" in source and "MIN3V" in source
    assert "* 100 / rgb->c" in source  # Clear 通道标定
    assert "60 * (g - b) / dif_val" in source
    assert "60 * (b - r) / dif_val + 120" in source
    assert "60 * (r - g) / dif_val + 240" in source
    assert "dif_val * 100 / (200 - (max_val + min_val))" in source
    header = (MODULES / "tcs34725" / "code" / "tcs34725.h").read_text(
        encoding="utf-8"
    )
    assert "0x29u" in header  # 7 位地址（页面原式）
    assert "TCS34725_COMMAND_BIT (0x80u)" in header
