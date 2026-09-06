"""bh1750 光照强度传感器模块（软 I2C 总线件）：真实库 + 真实母版不变量与
双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成（syscfg 裁剪
保留 BH1750 + 模块文件落盘）。软 I2C 换算守卫（自实现原语族、零 ml_i2c/
标准库调用、页面原式 0x46 地址与 /1.2f 换算、SDA 方向切换 OD/IU）与
**页面缺陷防回潮**（① 读路径 wait_ack 检查返回 1；② 无 MLX90614 串台文案；
③ 无 BUF[8] 全局；④ BH1750_MEASURE_DELAY_MS 140）。全程无 LLM、无服务。
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
    '#include "bh1750.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    bh1750_init();\n"
    "    uint8_t ok = bh1750_start_measure();\n"
    "    delay_ms(BH1750_MEASURE_DELAY_MS);\n"
    "    float lux = 0.0f;\n"
    "    ok = bh1750_read_lux(&lux);\n"
    "    (void)ok;\n"
    "    (void)lux;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "bh1750_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    float lux = 0.0f;\n"
    "    bh1750_init();\n"
    "    (void)bh1750_start_measure();\n"
    "    (void)bh1750_read_lux(&lux);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/母版
# ml_i2c 调用）。
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


def test_bh1750_manifest_shape_both_platforms():
    """bh1750：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PA12/PA13）。"""
    manifest = ModuleManifest.load(MODULES / "bh1750")
    assert manifest.slug == "bh1750"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "bh1750_stm32.c",
        "bh1750_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "bh1750" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("BH1750_SCL", "i2c_scl", "PA6", True, ("BH1750_SCL_GPIO", "BH1750_SCL_PIN")),
        ("BH1750_SDA", "i2c_sda", "PA7", True, ("BH1750_SDA_GPIO", "BH1750_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/bh1750-light-intensity-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--bh1750-light-intensity-sensor.md",
        "MLX90614",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["bh1750.c", "bh1750.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("BH1750_SCL", "gpio_out", "PA12", True, ()),
        ("BH1750_SDA", "gpio_out", "PA13", True, ()),
    ]
    assert mspm0.verified is True


def test_bh1750_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：BH1750_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+BH1750_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+BH1750_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+BH1750_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+BH1750_SDA_PIN\s+Pin_7", text)


def test_bh1750_mspm0_syscfg_instance():
    """mspm0 母版必须有 BH1750 实例（SCL=PA12 / SDA=PA13）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const BH1750 = GPIO.addInstance();" in syscfg
    assert 'BH1750.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'BH1750.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'BH1750.associatedPins[0].pin.$assign  = "PA12";' in syscfg
    assert 'BH1750.associatedPins[1].pin.$assign  = "PA13";' in syscfg


def test_bh1750_stm32_single_select_generation(tmp_path):
    """bh1750 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 bh1750_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["bh1750"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/bh1750/code/bh1750_stm32.c").is_file()
    assert (out / "modules/bh1750/code/bh1750_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("bh1750_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_bh1750_mspm0_single_select_generation(tmp_path):
    """bh1750 mspm0 单选生成：syscfg 只留 BH1750、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["bh1750"])
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
    assert "const BH1750 = GPIO.addInstance();" in syscfg
    assert 'BH1750.associatedPins[1].pin.$assign  = "PA13";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0",
        "PWMAB",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/bh1750/code/bh1750.c").is_file()
    assert (out / "modules/bh1750/code/bh1750.h").is_file()


def test_bh1750_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；页面原式
    0x46 地址与 /1.2f 换算保留；**页面缺陷防回潮**（读路径 wait_ack 检查
    返回 1、无 MLX90614 串台、无 BUF[8] 全局、MEASURE_DELAY_MS 140）。"""
    c = (MODULES / "bh1750" / "code" / "bh1750_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "bh1750" / "code" / "bh1750_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+BH1750_SDA_OUT\(\)\s+gpio_init\(BH1750_SDA_GPIO", code_only
    )
    assert re.search(
        r"BH1750_SDA_IN\(\)\s+gpio_init\(BH1750_SDA_GPIO, BH1750_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+BH1750_SDA\(x\)\s+gpio_set", code_only)
    assert "bh1750_iic_start" in code_only and "bh1750_iic_wait_ack" in code_only

    # 页面原式保留：地址 0x46/读地址 0x47（BH1750_ADDR_WRITE+1 表达式）、
    # 命令 0x01/0x10、换算 /1.2f
    assert "0x46" in code_only
    assert "BH1750_ADDR_WRITE + 1" in code_only
    assert "0x01" in code_only and "0x10" in code_only
    assert "/ 1.2f" in code_only
    assert "BH1750_MEASURE_DELAY_MS 140" in h

    # 页面缺陷防回潮：① 读路径 wait_ack 检查返回 1；
    # ② 无 MLX90614 串台（注释剥离后代码无）；③ 无 BUF[8] 死全局
    assert "if (bh1750_iic_wait_ack() != 0)" in code_only
    assert "MLX90614" not in code_only
    assert "BUF" not in code_only


def test_bh1750_stm32_scl_init_guard():
    """SCL 初始化防回潮（批次 3/01）：init 必须含 gpio_init(BH1750_SCL_GPIO,
    BH1750_SCL_PIN, OUT_OD) + 置高——F1 复位后浮空输入、ODR 写入无效，
    不初始化 = 总线死（批次 2 六件 SCL 从未初始化的真 bug 回修）。"""
    c = (MODULES / "bh1750" / "code" / "bh1750_stm32.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert re.search(
        r"gpio_init\(BH1750_SCL_GPIO, BH1750_SCL_PIN, OUT_OD\)", code_only
    )
    assert "BH1750_SCL(1)" in code_only
