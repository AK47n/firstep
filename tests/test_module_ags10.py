"""ags10 有害气体传感器模块（软 I2C 总线件 + CRC8）：真实库 + 真实母版
不变量与双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、
stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成。软 I2C 换算
守卫（自实现原语族、零 ml_i2c/标准库调用、地址 0x34 写/0x35 读、SDA 方向
切换 OD/IU）与 **页面缺陷防回潮（全批最重页）**（① `timeout <
AGS10_RETRY_MAX` 条件修正（页面 `>= 50` 写反致命缺陷）；② 出参+状态码
（无 uint32_t 主返回与错误码混用）；③ 无 delay_1us/delay_1ms；④ CRC8
0x31/0xFF 覆盖 data[0..3]；⑤ 失败码 1-4；⑥ 无 printf 残留）。全程无 LLM、
无服务。
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
    '#include "ags10.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    uint32_t voc = 0;\n"
    "    ags10_init();\n"
    "    (void)ags10_read(&voc);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ags10_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    uint32_t voc = 0;\n"
    "    ags10_init();\n"
    "    (void)ags10_read(&voc);\n"
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
    (r"\bdelay_1us\b|\bdelay_1ms\b", "库内不存在的延时函数"),
]


def test_ags10_manifest_shape_both_platforms():
    """ags10：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/SDA=PA7，
    macros 逐脚端口宏）；mspm0 条目原样（syscfg gpio_out PB18/PA14）。"""
    manifest = ModuleManifest.load(MODULES / "ags10")
    assert manifest.slug == "ags10"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ags10_stm32.c",
        "ags10_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ags10" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("AGS10_SCL", "i2c_scl", "PA6", True, ("AGS10_SCL_GPIO", "AGS10_SCL_PIN")),
        ("AGS10_SDA", "i2c_sda", "PA7", True, ("AGS10_SDA_GPIO", "AGS10_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/ags10-harmful-gas-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--ags10-harmful-gas-sensor.md",
        "15kHz",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ags10.c", "ags10.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("AGS10_SCL", "gpio_out", "PB18", True, ()),
        ("AGS10_SDA", "gpio_out", "PA14", True, ()),
    ]
    assert mspm0.verified is True


def test_ags10_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：AGS10_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 六件共总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+AGS10_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+AGS10_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+AGS10_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+AGS10_SDA_PIN\s+Pin_7", text)


def test_ags10_mspm0_syscfg_instance():
    """mspm0 母版必须有 AGS10 实例（SCL=PB18 / SDA=PA14）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const AGS10 = GPIO.addInstance();" in syscfg
    assert 'AGS10.associatedPins[0].pin.$assign  = "PB18";' in syscfg
    assert 'AGS10.associatedPins[1].pin.$assign  = "PA14";' in syscfg


def test_ags10_stm32_single_select_generation(tmp_path):
    """ags10 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 ags10_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ags10"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ags10/code/ags10_stm32.c").is_file()
    assert (out / "modules/ags10/code/ags10_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ags10_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ags10_mspm0_single_select_generation(tmp_path):
    """ags10 mspm0 单选生成：syscfg 只留 AGS10、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ags10"])
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
    assert "const AGS10 = GPIO.addInstance();" in syscfg
    assert 'AGS10.associatedPins[1].pin.$assign  = "PA14";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "GP2Y1014",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ags10/code/ags10.c").is_file()
    assert (out / "modules/ags10/code/ags10.h").is_file()


def test_ags10_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用、零 delay_1us/delay_1ms（页面不存在延时函数→delay_us/ms 改写）；
    软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；页面原式地址/CRC
    保留；**页面缺陷防回潮**（① `timeout < AGS10_RETRY_MAX` 重试条件修正
    ——页面 `>= 50` 写反；② 出参+状态码（无 uint32_t 主返回）；③ CRC8
    0x31/0xFF 覆盖 data[0..3]；④ 失败码 1-4；⑤ 无 printf 残留）。"""
    c = (MODULES / "ags10" / "code" / "ags10_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ags10" / "code" / "ags10_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（页面原式 OD 输出 / IPU 输入 → OUT_OD/IU）
    assert re.search(
        r"#define\s+AGS10_SDA_OUT\(\)\s+gpio_init\(AGS10_SDA_GPIO", code_only
    )
    assert re.search(
        r"AGS10_SDA_IN\(\)\s+gpio_init\(AGS10_SDA_GPIO, AGS10_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+AGS10_SDA\(x\)\s+gpio_set", code_only)
    assert "ags10_iic_start" in code_only and "ags10_iic_wait_ack" in code_only

    # 页面原式保留：地址 0x34/0x35（AGS10_ADDR<<1 表达式）、寄存器 0x00、
    # CRC8 0x31/0xFF、TVOC 24bit 拼装
    assert "AGS10_ADDR << 1" in code_only and "AGS10_REG_TVOC" in code_only
    assert "0x31u" in code_only and "0xFFu" in code_only
    assert "data[1] << 16" in code_only

    # 页面缺陷防回潮：① 重试条件修正（timeout < AGS10_RETRY_MAX——页面
    # `timeout >= 50` 写反）；② 出参+状态码；③ 失败码 1-4
    assert "timeout < AGS10_RETRY_MAX" in code_only
    assert "AGS10_RETRY_MAX" in code_only and "AGS10_RETRY_MAX" in h
    assert "uint8_t ags10_read(uint32_t *voc_ppb)" in h
    assert "return 1;" in code_only and "return 4;" in code_only


def test_ags10_stm32_scl_init_guard():
    """SCL 初始化防回潮（批次 3/01）：init 必须含 gpio_init(AGS10_SCL_GPIO,
    AGS10_SCL_PIN, OUT_OD) + 置高——F1 复位后浮空输入、ODR 写入无效，
    不初始化 = 总线死（批次 2 六件 SCL 从未初始化的真 bug 回修）。"""
    c = (MODULES / "ags10" / "code" / "ags10_stm32.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert re.search(
        r"gpio_init\(AGS10_SCL_GPIO, AGS10_SCL_PIN, OUT_OD\)", code_only
    )
    assert "AGS10_SCL(1)" in code_only
