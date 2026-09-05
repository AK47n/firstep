"""fingerprint 指纹识别模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 hc05（UART 模块）/ max7219 同款结构测试：manifest 形状（仅 mspm0、依赖
delay、三角色 TX/RX/TOUCH = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 FINGERPRINT_UART + FINGERPRINT + delay
展开、模块文件落盘、main.c 调 init/check/search/enroll 过静态门禁）。
真实 UART 独立实例（UART0 默认）+ **轮询接收**（无 IRQHandler 强符号——
源码守卫钉死）；帧封装按页面原样（包头+指令+校验和镜像测试）。
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
    '#include "fingerprint.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    fingerprint_init();\n"
    "    (void)fingerprint_check_device();\n"
    "    (void)fingerprint_is_touched();\n"
    "    (void)fingerprint_get_image();\n"
    "    (void)fingerprint_img_to_buffer(1);\n"
    "    (void)fingerprint_reg_model();\n"
    "    (void)fingerprint_search();\n"
    "    (void)fingerprint_save_finger(1);\n"
    "    (void)fingerprint_delete_all();\n"
    "    (void)fingerprint_enroll(2);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def fpm10a_body(body: list[int]) -> list[int]:
    """FPM10A 指令段镜像：指令段 + 校验和（前面字节求和 &0xFF，页面原样）。"""
    return body + [(sum(body) & 0xFF)]


def test_fingerprint_page_command_checksums_mirror():
    """页面命令数组校验和镜像（逐字节原样，页面数组值守卫）。

    页面数组：Get_Img={01,00,03,01,00,05}、Search={01,00,08,04,01,00,00,03,
    E7,00,F8}、Delete_All={01,00,03,0D,00,11}——校验和 = 前面字节求和 &0xFF。
    """
    assert fpm10a_body([0x01, 0x00, 0x03, 0x01, 0x00]) == [0x01, 0x00, 0x03, 0x01, 0x00, 0x05]
    assert fpm10a_body([0x01, 0x00, 0x08, 0x04, 0x01, 0x00, 0x00, 0x03, 0xE7, 0x00]) == [
        0x01, 0x00, 0x08, 0x04, 0x01, 0x00, 0x00, 0x03, 0xE7, 0x00, 0xF8,
    ]
    assert fpm10a_body([0x01, 0x00, 0x03, 0x0D, 0x00]) == [0x01, 0x00, 0x03, 0x0D, 0x00, 0x11]


def test_fingerprint_polling_and_frame_source_guards():
    """源码守卫：真实 UART + 轮询（无 IRQHandler）+ 帧封装按页面原样。"""
    source = (MODULES / "fingerprint" / "code" / "fingerprint.c").read_text(
        encoding="utf-8"
    )
    assert "FINGERPRINT_UART_INST_IRQHandler" not in source  # 轮询，无 ISR 强符号
    assert "DL_UART_isRXFIFOEmpty" in source               # 轮询接收
    assert "FINGERPRINT_UART_INST" in source               # 真实 UART 实例
    assert "0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF" in source  # 包头（页面原样）
    assert "0x01, 0x00, 0x03, 0x01, 0x00, 0x05" in source  # Get_Img（页面原样）
    assert "_resp[9]" in source                            # 确认码判定（页面原样）
    assert "FINGERPRINT_NOT_FOUND" in source               # 255 = 未找到


# ---------------------------------------------------------------------------
# 结构 + 生成（既有接缝）
# ---------------------------------------------------------------------------


def test_fingerprint_manifest_shape_mspm0():
    """fingerprint：仅 mspm0 平台条目；依赖 delay；TX(uart_tx PA28) +
    RX(uart_rx PA31) + TOUCH(gpio_in PA12)。"""
    manifest = ModuleManifest.load(MODULES / "fingerprint")
    assert manifest.slug == "fingerprint"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["fingerprint.c", "fingerprint.h"]
    for rel in mspm0.files:
        assert (MODULES / "fingerprint" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("FINGERPRINT_TX", "uart_tx", "PA28", True, ()),
        ("FINGERPRINT_RX", "uart_rx", "PA31", True, ()),
        ("FINGERPRINT_TOUCH", "gpio_in", "PA12", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_fingerprint_mspm0_syscfg_instances():
    """mspm0 母版：FINGERPRINT_UART（UART0, 57600, 无中断=轮询）+
    FINGERPRINT GPIO（TOUCH 输入 PA12）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const FINGERPRINT_UART = UART.addInstance();" in syscfg
    assert 'FINGERPRINT_UART.peripheral.$assign = "UART0";' in syscfg
    assert "FINGERPRINT_UART.targetBaudRate    = 57600;" in syscfg
    assert "FINGERPRINT_UART.enabledInterrupts = [];" in syscfg
    assert 'FINGERPRINT_UART.peripheral.rxPin.$assign = "PA31";' in syscfg
    assert 'FINGERPRINT_UART.peripheral.txPin.$assign = "PA28";' in syscfg
    assert "const FINGERPRINT = GPIO.addInstance();" in syscfg
    assert 'FINGERPRINT.associatedPins[0].$name        = "TOUCH";' in syscfg
    assert 'FINGERPRINT.associatedPins[0].direction    = "INPUT";' in syscfg
    assert 'FINGERPRINT.associatedPins[0].pin.$assign  = "PA12";' in syscfg


def test_fingerprint_mspm0_single_select_generation(tmp_path):
    """fingerprint mspm0 单选生成：syscfg 只留 FINGERPRINT_UART+FINGERPRINT、
    依赖 delay 展开、文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["fingerprint"])
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
    assert "const FINGERPRINT_UART = UART.addInstance();" in syscfg
    assert "const FINGERPRINT = GPIO.addInstance();" in syscfg
    assert 'FINGERPRINT_UART.peripheral.$assign = "UART0";' in syscfg
    assert 'FINGERPRINT.associatedPins[0].pin.$assign  = "PA12";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "DEBUG_UART", "UWB_UART", "ZIGBEE_UART", "OLED", "I2C_0",
        "ADC12_0", "DC_MOTOR", "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219",
        "PCA9685", "IR_TX", "NRF24L01", "HC05_UART", "HC05", "JQ8900",
        "SYN6288", "RC522",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/fingerprint/code/fingerprint.c").is_file()
    assert (out / "modules/fingerprint/code/fingerprint.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()
