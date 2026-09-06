"""tp_xpt2046 触摸模块（批次 12/06）：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / max7219 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
五角色 CS/CLK/DIN/DOUT/PEN = gpio_out/gpio_in）、mspm0 单选生成（syscfg
裁剪保留 TP_XPT2046、模块文件落盘、main.c 调 init/read_xy/is_pressed 过
静态门禁）、软 SPI 位操作无平台依赖守卫（GPIO_ResetBits/RCC_/printf/
DL_SPI 不得出现）、无 IRQHandler 守卫（GROUP1 单向量被 motor 编码器独占）。
全程无 LLM、无服务。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
TP_DIR = MODULES / "tp_xpt2046"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402
from contest_generator.clex import strip_comments  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "tp_xpt2046.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    xpt2046_init();\n"
    "    uint16_t x = 0, y = 0;\n"
    "    if (xpt2046_is_pressed()) {\n"
    "        xpt2046_read_xy(&x, &y);\n"
    "    }\n"
    "    xpt2046_read_raw(&x, &y);\n"
    "    xpt2046_set_calibration(0.034f, 0.043f, -5, -7);\n"
    "    (void)x;\n"
    "    (void)y;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_tp_xpt2046_manifest_shape_mspm0():
    """tp_xpt2046：仅 mspm0 平台条目；依赖 delay；五角色 CS/CLK/DIN 输出 +
    DOUT/PEN 输入。"""
    manifest = ModuleManifest.load(TP_DIR)
    assert manifest.slug == "tp_xpt2046"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["tp_xpt2046.c", "tp_xpt2046.h"]
    for rel in mspm0.files:
        assert (TP_DIR / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required) for p in mspm0.pins] == [
        ("TP_XPT2046_CS", "gpio_out", "PA8", True),
        ("TP_XPT2046_CLK", "gpio_out", "PA13", True),
        ("TP_XPT2046_DIN", "gpio_out", "PA9", True),
        ("TP_XPT2046_DOUT", "gpio_in", "PA28", True),
        ("TP_XPT2046_PEN", "gpio_in", "PB24", True),
    ]
    assert mspm0.kit and mspm0.source_url


def test_tp_xpt2046_mspm0_syscfg_instances():
    """mspm0 母版：TP_XPT2046 GPIO 实例（CS/CLK/DIN/DOUT/PEN 五脚）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const TP_XPT2046 = GPIO.addInstance();" in syscfg
    assert "TP_XPT2046.associatedPins.create(5);" in syscfg
    for i, (name, pin, direction) in enumerate([
        ("CS", "PA8", "OUTPUT"), ("CLK", "PA13", "OUTPUT"),
        ("DIN", "PA9", "OUTPUT"), ("DOUT", "PA28", "INPUT"),
        ("PEN", "PB24", "INPUT"),
    ]):
        assert f'TP_XPT2046.associatedPins[{i}].$name        = "{name}";' in syscfg
        assert (f"TP_XPT2046.associatedPins[{i}].direction    = "
                f'"{direction}";') in syscfg
        assert f'TP_XPT2046.associatedPins[{i}].pin.$assign  = "{pin}";' in syscfg
    assert 'TP_XPT2046.associatedPins[0].initialValue = "SET";' in syscfg  # CS


def test_tp_xpt2046_mspm0_single_select_generation(tmp_path):
    """tp_xpt2046 mspm0 单选生成：syscfg 保留 TP_XPT2046、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["tp_xpt2046"])
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
    assert "const TP_XPT2046 = GPIO.addInstance();" in syscfg
    assert 'TP_XPT2046.associatedPins[4].pin.$assign  = "PB24";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "DC_MOTOR",
        "PWMAB", "SERVO_PWM", "IR_REMOTE", "PCA9685", "IR_TX", "MAX7219",
        "LCD",
    ):
        assert f"const {drop}" not in syscfg
    for rel in ("tp_xpt2046.c", "tp_xpt2046.h"):
        assert (out / f"modules/tp_xpt2046/code/{rel}").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_tp_xpt2046_no_platform_deps_no_irq():
    """无平台依赖守卫（STM32/printf/硬件 SPI 不得出现）+ 无 IRQHandler 守卫
    （GROUP1 单向量被 motor 编码器独占——轮询读坐标）。"""
    code_text = ""
    for rel in ("code/tp_xpt2046.c", "code/tp_xpt2046.h"):
        code_text += strip_comments((TP_DIR / rel).read_text(encoding="utf-8"),
                                    keep_preprocessor=True)
    for banned in ("GPIO_ResetBits", "GPIO_SetBits", "RCC_APB2PeriphClockCmd",
                   "printf", "DL_SPI", "USART", "TP_Init", "TP_Scan"):
        assert banned not in code_text, f"平台依赖/状态机残留：{banned}"
    full = ""
    for rel in ("code/tp_xpt2046.c", "code/tp_xpt2046.h"):
        full += (TP_DIR / rel).read_text(encoding="utf-8")
    for banned in ("IRQHandler", "Group1IRQ"):
        assert banned not in full, f"中断残留：{banned}"
    # 校准常量/命令守卫（方向 1 预设 + X/Y 命令）
    assert "0.034810" in full
    assert "0xD0" in full and "0x90" in full
