"""jy61p 六轴姿态模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 sht30 / sht20 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PA28/PA31——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
JY61P、模块文件落盘、main.c 调 init/read_angles/read_raw 过静态门禁）。
页面初始化序列/寄存器地址/换算公式/回绕源码守卫钉死（页面原式 + I2C_WaitAck
时序修正——与库内 ml_mpu6050/imu_uart 分工写入 notes）。
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
    '#include "jy61p.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    jy61p_init();\n"
    "    float r = 0.0f, p = 0.0f, y = 0.0f;\n"
    "    uint8_t ok = jy61p_read_angles(&r, &p, &y);\n"
    "    (void)ok;\n"
    "    (void)r;\n"
    "    (void)p;\n"
    "    (void)y;\n"
    "    uint8_t raw[6] = {0};\n"
    "    (void)jy61p_read_raw(raw);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_jy61p_manifest_shape_mspm0():
    """jy61p：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "jy61p")
    assert manifest.slug == "jy61p"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["jy61p.c", "jy61p.h"]
    for rel in mspm0.files:
        assert (MODULES / "jy61p" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("JY61P_SCL", "gpio_out", "PA28", True, ()),
        ("JY61P_SDA", "gpio_out", "PA31", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 与库内 ml_mpu6050 / imu_uart 的分工说明必须写入 notes
    assert "ml_mpu6050" in mspm0.notes
    assert "imu_uart" in mspm0.notes
    # 模块化姿态传感器直接出角度（器件内卡尔曼融合）
    assert "卡尔曼" in mspm0.notes
    # I2C_WaitAck 时序修正说明
    assert "SCL" in mspm0.notes


def test_jy61p_mspm0_syscfg_instances():
    """mspm0 母版：JY61P GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const JY61P = GPIO.addInstance();" in syscfg
    assert 'JY61P.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'JY61P.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'JY61P.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'JY61P.associatedPins[1].pin.$assign  = "PA31";' in syscfg


def test_jy61p_mspm0_single_select_generation(tmp_path):
    """jy61p mspm0 单选生成：syscfg 只留 JY61P、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["jy61p"])
    assert {m.slug for m in resolved.manifests} == {"jy61p", "delay"}
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
    assert "const JY61P = GPIO.addInstance();" in syscfg
    assert 'JY61P.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'JY61P.associatedPins[1].pin.$assign  = "PA31";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "BH1750", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "SHT30", "SHT20", "L298N_PWM", "L298N",
        "OPENMV4_UART",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/jy61p/code/jy61p.c").is_file()
    assert (out / "modules/jy61p/code/jy61p.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()


def test_jy61p_init_sequence_and_conversion_guards():
    """页面初始化序列/寄存器/换算/回绕守卫（防回潮）。"""
    source = (MODULES / "jy61p" / "code" / "jy61p.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "jy61p" / "code" / "jy61p.h").read_text(
        encoding="utf-8"
    )
    # 地址与寄存器常量（头文件单源）
    assert re.search(r"JY61P_ADDR\s+0x50u", header)
    assert re.search(r"JY61P_REG_UN\s+0x69u", header)
    assert re.search(r"JY61P_REG_SAVE\s+0x00u", header)
    assert re.search(r"JY61P_REG_ANGLE_REFER\s+0x01u", header)
    assert re.search(r"JY61P_REG_ROLL_LOW\s+0x3Du", header)
    assert re.search(r"JY61P_ANGLE_BYTES\s+6u", header)
    # 初始化序列（页面原样：解锁 0x88B5 / Z 归零 0x0400 / 角度归零 0x0800 / 保存）
    assert "0x88, 0xB5" in source
    assert "0x04, 0x00" in source
    assert "0x08, 0x00" in source
    assert "0x00, 0x00" in source
    assert source.count("delay_ms(JY61P_INIT_DELAY_MS)") == 6
    assert re.search(r"JY61P_INIT_DELAY_MS\s+200u", header)
    # 换算（页面原式）+ ±180 回绕
    assert "32768.0f" in source
    assert "* 180.0f" in source
    assert "-= 360.0f" in source
    assert "+= 360.0f" in source
    # 页面演示/调试件剔除 + 读取统一约定 0=成功
    assert "printf" not in source
    assert "GYRO_DEBUG" not in source
    assert "IRQHandler" not in source
    # I2C_WaitAck 时序修正（SCL 拉高后采样）
    assert "JY61P_SCL(1);" in source
