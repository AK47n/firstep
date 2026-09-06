"""pca9685 16 路舵机驱动模块（软 I2C 器件库件）：真实库 + 真实母版不变量与
双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成（syscfg 裁剪
保留 PCA9685 + 模块文件落盘）。软 I2C 换算守卫（自实现原语族、零 ml_i2c/
标准库调用、**SCL OUT_OD 初始化守卫**（批次 3 回修口径防回潮）、SDA 方向
切换 OD/IU）与 **页面缺陷防回潮**（① 角度映射单式（无 `* 2.2f`/`* 2.4f`
双式、含 0.5-2.5ms 换算 0.0005f/0.0025f）；② 默认 50Hz；③ 无 delay_1ms；
④ set_address/0x40 出现；⑤ prescale 浮点 round；⑥ 无 printf/GPIO_Init/
RCC_ 残留）。全程无 LLM、无服务。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "pca9685.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    pca9685_init(PCA9685_DEFAULT_FREQ_HZ);\n"
    "    pca9685_set_angle(0, 90);\n"
    "    pca9685_set_angle(1, 180);\n"
    "    pca9685_set_pwm(2, 512);\n"
    "    pca9685_set_freq(100);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "pca9685_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    pca9685_init(50);\n"
    "    pca9685_set_pwm(0, 0);\n"
    "    pca9685_set_angle(1, 90);\n"
    "    pca9685_set_freq(100);\n"
    "    pca9685_set_address(0);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/
# 母版 ml_i2c 调用）。
BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bI2C_Init\b|\bI2C_Start\b|\bI2C_Stop\b|\bI2C_SendByte\b", "母版 ml_i2c 调用"),
    (r"\bGPIO_ReadInputDataBit\b", "GPIO_ReadInputDataBit"),
    (r"\bGPIO_WriteBit\b", "GPIO_WriteBit"),
]


def test_pca9685_manifest_shape_both_platforms():
    """pca9685：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PB6/PB7）。"""
    manifest = ModuleManifest.load(MODULES / "pca9685")
    assert manifest.slug == "pca9685"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "pca9685_stm32.c",
        "pca9685_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "pca9685" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("PCA9685_SCL", "i2c_scl", "PA6", True, ("PCA9685_SCL_GPIO", "PCA9685_SCL_PIN")),
        ("PCA9685_SDA", "i2c_sda", "PA7", True, ("PCA9685_SDA_GPIO", "PCA9685_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/control/16-ch-servo-drive-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/control--16-ch-servo-drive-module.md",
        "角度映射",
        "同址",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["pca9685.c", "pca9685.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("PCA9685_SCL", "gpio_out", "PB6", True, ()),
        ("PCA9685_SDA", "gpio_out", "PB7", True, ()),
    ]
    assert mspm0.verified is True


def test_pca9685_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：PCA9685_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 与批次 2 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+PCA9685_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+PCA9685_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+PCA9685_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+PCA9685_SDA_PIN\s+Pin_7", text)


def test_pca9685_mspm0_syscfg_instance():
    """mspm0 母版必须有 PCA9685 实例（SCL=PB6 / SDA=PB7，输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const PCA9685 = GPIO.addInstance();" in syscfg
    assert 'PCA9685.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'PCA9685.associatedPins[0].pin.$assign  = "PB6";' in syscfg
    assert 'PCA9685.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'PCA9685.associatedPins[1].pin.$assign  = "PB7";' in syscfg


def test_pca9685_stm32_single_select_generation(tmp_path):
    """pca9685 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 pca9685_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["pca9685"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/pca9685/code/pca9685_stm32.c").is_file()
    assert (out / "modules/pca9685/code/pca9685_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("pca9685_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_pca9685_mspm0_single_select_generation(tmp_path):
    """pca9685 mspm0 单选生成：syscfg 只留 PCA9685、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["pca9685"])
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
    assert "const PCA9685 = GPIO.addInstance();" in syscfg
    assert 'PCA9685.associatedPins[1].pin.$assign  = "PB7";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "DC_MOTOR",
        "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219", "IR_TX", "DHT11",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/pca9685/code/pca9685.c").is_file()
    assert (out / "modules/pca9685/code/pca9685.h").is_file()


def test_pca9685_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；**SCL OUT_OD
    初始化**（批次 3 回修口径）；**页面缺陷防回潮**（角度映射单式无
    `* 2.2f`/`* 2.4f`、默认 50Hz、无 delay_1ms、set_address/0x40、
    prescale 浮点 round）。"""
    c = (MODULES / "pca9685" / "code" / "pca9685_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "pca9685" / "code" / "pca9685_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+PCA9685_SDA_OUT\(\)\s+gpio_init\(PCA9685_SDA_GPIO", code_only
    )
    assert re.search(
        r"PCA9685_SDA_IN\(\)\s+gpio_init\(PCA9685_SDA_GPIO, PCA9685_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+PCA9685_SDA\(x\)\s+gpio_set", code_only)
    assert "pca9685_iic_start" in code_only and "pca9685_iic_wait_ack" in code_only

    # SCL OUT_OD 初始化守卫（批次 3 回修口径防回潮）
    assert re.search(
        r"gpio_init\(PCA9685_SCL_GPIO, PCA9685_SCL_PIN, OUT_OD\)", code_only
    )
    assert "PCA9685_SCL(1)" in code_only

    # 页面缺陷防回潮：① 角度映射单式（0.5-2.5ms → 0.0005f/0.0025f，无
    # * 2.2f/* 2.4f 双式）；② 默认 50Hz；③ 无 delay_1ms；④ set_address/0x40
    assert "0.0005f" in code_only and "0.0025f" in code_only
    assert "* 2.2f" not in code_only and "* 2.4f" not in code_only
    assert "PCA9685_DEFAULT_FREQ_HZ 50u" in h
    assert "delay_1ms" not in code_only
    assert "pca9685_set_address" in code_only
    assert "(0x40u + a5) << 1" in code_only

    # prescale 浮点 round 守卫（同 mspm0 版）
    assert "- 1.0f + 0.5f" in code_only
