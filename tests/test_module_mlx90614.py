"""mlx90614 非接触红外测温模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 aht10 / bh1750 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PA9/PA8——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
MLX90614、模块文件落盘、main.c 调 init/read_object_temp/read_ambient_temp
过静态门禁）。软 I2C（SMBus 兼容）位操作走 delay 模块；页面 0.02−273.15
换算与 0x06/0x07 寄存器常量源码守卫钉死（页面返回 0.0 失败语义已改出参+
状态——notes 记录）。
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
    '#include "mlx90614.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    mlx90614_init();\n"
    "    float obj = 0.0f;\n"
    "    float amb = 0.0f;\n"
    "    if (mlx90614_read_object_temp(&obj) == 0) {\n"
    "        (void)obj;\n"
    "    }\n"
    "    if (mlx90614_read_ambient_temp(&amb) == 0) {\n"
    "        (void)amb;\n"
    "    }\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_mlx90614_manifest_shape_mspm0():
    """mlx90614：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "mlx90614")
    assert manifest.slug == "mlx90614"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["mlx90614.c", "mlx90614.h"]
    for rel in mspm0.files:
        assert (MODULES / "mlx90614" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MLX90614_SCL", "gpio_out", "PA9", True, ()),
        ("MLX90614_SDA", "gpio_out", "PA8", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # SMBus 时序差异取证必须写入 notes（PEC/命令字节/页面缺陷）
    assert "PEC" in mspm0.notes
    assert "SMBus" in mspm0.notes


def test_mlx90614_mspm0_syscfg_instances():
    """mspm0 母版：MLX90614 GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const MLX90614 = GPIO.addInstance();" in syscfg
    assert 'MLX90614.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'MLX90614.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'MLX90614.associatedPins[0].pin.$assign  = "PA9";' in syscfg
    assert 'MLX90614.associatedPins[1].pin.$assign  = "PA8";' in syscfg


def test_mlx90614_mspm0_single_select_generation(tmp_path):
    """mlx90614 mspm0 单选生成：syscfg 只留 MLX90614、模块文件落盘、门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["mlx90614"])
    assert {m.slug for m in resolved.manifests} == {"mlx90614", "delay"}
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
    assert "const MLX90614 = GPIO.addInstance();" in syscfg
    assert 'MLX90614.associatedPins[0].pin.$assign  = "PA9";' in syscfg
    assert 'MLX90614.associatedPins[1].pin.$assign  = "PA8";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "BH1750", "ADS1115", "TCS34725", "SR04",
        "JOYSTICK", "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART",
        "OLED", "ADC12_0", "PWMAB", "IR_TX",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/mlx90614/code/mlx90614.c").is_file()
    assert (out / "modules/mlx90614/code/mlx90614.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_mlx90614_conversion_and_reg_guards():
    """源码守卫：页面 0.02−273.15 换算与 0x06/0x07 寄存器常量不得走样。"""
    source = (MODULES / "mlx90614" / "code" / "mlx90614.c").read_text(
        encoding="utf-8"
    )
    assert "* 0.02f - 273.15f" in source
    assert "return 0.0" not in source  # 页面失败语义已改出参 + 状态
    header = (MODULES / "mlx90614" / "code" / "mlx90614.h").read_text(
        encoding="utf-8"
    )
    assert "MLX90614_REG_AMBIENT_TEMP 0x06" in header
    assert "MLX90614_REG_OBJECT_TEMP  0x07" in header
    assert "MLX90614_ADDR  0x5A" in header
