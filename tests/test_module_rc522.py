"""rc522 RFID IC 卡识别模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / max7219 / ir_remote_tx 同款结构测试：manifest 形状（仅 mspm0、
依赖 delay、五角色 CS/RST/SCK/MOSI/MISO = 母版 syscfg 由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 RC522 + delay
展开、模块文件落盘、main.c 调 init/read_card/read_block 过静态门禁）。
页面 Pcd* 通信族全套保留在驱动内（软 SPI 位操作 5 脚，无硬件 SPI 依赖）；
上游缺陷（PcdAuthState UID 复制 6→4 字节）以源码守卫钉住。
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
    '#include "rc522.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    rc522_init();\n"
    "    uint8_t uid[4];\n"
    "    uint8_t data[16];\n"
    "    uint8_t key[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};\n"
    "    (void)rc522_read_card(uid);\n"
    "    (void)rc522_auth_block(RC522_AUTH_KEYA, 4, key, uid);\n"
    "    (void)rc522_read_block(6, key, uid, data);\n"
    "    (void)rc522_write_block(6, key, uid, data);\n"
    "    rc522_halt();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_rc522_manifest_shape_mspm0():
    """rc522：仅 mspm0 平台条目；依赖 delay；五角色（4 输出 + 1 输入）。"""
    manifest = ModuleManifest.load(MODULES / "rc522")
    assert manifest.slug == "rc522"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["rc522.c", "rc522.h"]
    for rel in mspm0.files:
        assert (MODULES / "rc522" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("RC522_CS", "gpio_out", "PA7", True, ()),
        ("RC522_RST", "gpio_out", "PA18", True, ()),
        ("RC522_SCK", "gpio_out", "PA14", True, ()),
        ("RC522_MOSI", "gpio_out", "PA16", True, ()),
        ("RC522_MISO", "gpio_in", "PA17", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_rc522_mspm0_syscfg_instances():
    """mspm0 母版：RC522 GPIO 实例（5 associatedPins 全 GPIOA 单口）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const RC522 = GPIO.addInstance();" in syscfg
    assert 'RC522.associatedPins[0].$name        = "CS";' in syscfg
    assert 'RC522.associatedPins[0].pin.$assign  = "PA7";' in syscfg
    assert 'RC522.associatedPins[1].$name        = "RST";' in syscfg
    assert 'RC522.associatedPins[1].pin.$assign  = "PA18";' in syscfg
    assert 'RC522.associatedPins[2].$name        = "SCK";' in syscfg
    assert 'RC522.associatedPins[2].pin.$assign  = "PA14";' in syscfg
    assert 'RC522.associatedPins[3].$name        = "MOSI";' in syscfg
    assert 'RC522.associatedPins[3].pin.$assign  = "PA16";' in syscfg
    assert 'RC522.associatedPins[4].$name        = "MISO";' in syscfg
    assert 'RC522.associatedPins[4].direction    = "INPUT";' in syscfg
    assert 'RC522.associatedPins[4].pin.$assign  = "PA17";' in syscfg


def test_rc522_mspm0_single_select_generation(tmp_path):
    """rc522 mspm0 单选生成：syscfg 只留 RC522、依赖 delay 展开、文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["rc522"])
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
    assert "const RC522 = GPIO.addInstance();" in syscfg
    assert 'RC522.associatedPins[4].pin.$assign  = "PA17";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "DEBUG_UART", "UWB_UART", "ZIGBEE_UART", "OLED", "I2C_0",
        "ADC12_0", "DC_MOTOR", "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219",
        "PCA9685", "IR_TX", "NRF24L01", "HC05_UART", "HC05", "JQ8900",
        "SYN6288",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/rc522/code/rc522.c").is_file()
    assert (out / "modules/rc522/code/rc522.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


def test_rc522_upstream_defect_fix_guards():
    """上游缺陷修正源码守卫：PcdAuthState 序列号复制 4 字节（页面原 6 字节
    越界 bug）——编译矩阵不验协议，此处以源码文本钉死（nrf24l01 先例）。"""
    source = (MODULES / "rc522" / "code" / "rc522.c").read_text(encoding="utf-8")
    assert "0x93u" in source                           # 防冲突命令
    assert "0x52u" in source                           # PICC_REQALL
    assert "RC522_OK" in source                        # MI_OK=0x26
    # 修正后：密钥复制 6 字节、序列号复制 4 字节（页面原两处都是 6）
    assert 'for (uc = 0; uc < 6; uc++) {\n        buf[uc + 2] = p_key[uc];' in source
    assert 'for (uc = 0; uc < 4; uc++) {\n        buf[uc + 8] = p_snr[uc];' in source
    assert "_spi_send_byte" in source and "_spi_read_byte" in source
