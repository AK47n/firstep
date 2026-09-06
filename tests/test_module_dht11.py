"""dht11 温湿度模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 ws2812 / hx711 / aht10 / sr04 / joystick 同款结构测试：manifest 形状
（仅 mspm0、单角色 DATA = PB7——默认与母版 syscfg 一致性由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 DHT11、模块文件
落盘、main.c 调 init/read 过静态门禁）。单总线延时走 delay 模块（依赖声明）。
全程无 LLM、无服务。
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
from contest_generator.platforms import (  # noqa: E402
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "dht11.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    dht11_init();\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    uint8_t ok = dht11_read(&t, &h);\n"
    "    (void)ok;\n"
    "    (void)t;\n"
    "    (void)h;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "dht11_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    float t = 0.0f, h = 0.0f;\n"
    "    dht11_init();\n"
    "    (void)dht11_read(&t, &h);\n"
    "    (void)dht11_read_temperature();\n"
    "    (void)dht11_read_humidity();\n"
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
    (r"\bdelay_uus\b", "delay_uus 页外工具函数"),
]


def test_dht11_manifest_shape_mspm0():
    """dht11：双平台条目（mspm0 原样 + stm32 批次 4 新增）；依赖 delay；
    单角色 DATA = gpio_out PB7。"""
    manifest = ModuleManifest.load(MODULES / "dht11")
    assert manifest.slug == "dht11"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["dht11.c", "dht11.h"]
    for rel in mspm0.files:
        assert (MODULES / "dht11" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("DHT11_DATA", "gpio_out", "PB7", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_dht11_mspm0_syscfg_instances():
    """mspm0 母版：DHT11 GPIO 实例（DATA 输出，initialValue SET = 空闲高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const DHT11 = GPIO.addInstance();" in syscfg
    assert 'DHT11.associatedPins[0].$name        = "DATA";' in syscfg
    assert 'DHT11.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'DHT11.associatedPins[0].initialValue = "SET";' in syscfg
    assert 'DHT11.associatedPins[0].pin.$assign  = "PB7";' in syscfg


def test_dht11_mspm0_single_select_generation(tmp_path):
    """dht11 mspm0 单选生成：syscfg 只留 DHT11、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["dht11"])
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
    assert "const DHT11 = GPIO.addInstance();" in syscfg
    assert 'DHT11.associatedPins[0].pin.$assign  = "PB7";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/dht11/code/dht11.c").is_file()
    assert (out / "modules/dht11/code/dht11.h").is_file()
    # 依赖 delay 随选展开落盘
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


# ---------------------------------------------------------------------------
# 批次 4（wiki-stm32-batch4/03）：stm32 平台条目（单总线件）
# ---------------------------------------------------------------------------


def test_dht11_stm32_manifest_shape():
    """dht11 stm32 条目：双平台文件齐；stm32 单角色 = gpio_out（DATA=PB3，
    macros 端口宏）；mspm0 条目原样零改动。"""
    manifest = ModuleManifest.load(MODULES / "dht11")
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "dht11_stm32.c",
        "dht11_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "dht11" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("DHT11_DATA", "gpio_out", "PB3", True, ("DHT11_GPIO", "DHT11_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/dht11.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--dht11.md",
        "超时",
        "delay_uus",
        "未上板",
    ):
        assert needle in stm32.notes

    # mspm0 条目零改动（文件齐 + 默认脚不变）
    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["dht11.c", "dht11.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("DHT11_DATA", "gpio_out", "PB7", True, ()),
    ]


def test_dht11_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：DHT11_GPIO/DHT11_PIN 必须在母版 pin_config.h
    （默认 PB3——叠 key KEY_START + pid GRAY_D6）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+DHT11_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+DHT11_PIN\s+Pin_3", text)


def test_dht11_stm32_single_select_generation(tmp_path):
    """dht11 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 dht11_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["dht11"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/dht11/code/dht11_stm32.c").is_file()
    assert (out / "modules/dht11/code/dht11_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("dht11_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def _dht11_header_constants() -> dict[str, int]:
    header = (MODULES / "dht11" / "code" / "dht11_stm32.h").read_text(
        encoding="utf-8"
    )
    constants: dict[str, int] = {}
    for line in header.splitlines():
        m = re.match(r"#define\s+(DHT11_[A-Z0-9_]+)\s+(\d+)u", line)
        if m:
            constants[m.group(1)] = int(m.group(2))
    return constants


def test_dht11_stm32_timeline_constants_guard():
    """单总线时间轴常量守卫：19ms 起始 / 28us 分界 / 54+27/74us 位形 /
    80 步进超时——页面原值单源头文件，源码不散写字面量（ir_remote_tx
    burst_cycle_formula_guard 先例）。"""
    constants = _dht11_header_constants()
    assert constants.get("DHT11_START_MS") == 19      # 页面 18-20ms，代码 19ms
    assert constants.get("DHT11_CHECK_TIME_US") == 28  # 0/1 码位分界（0 码 27 < 28）
    assert constants.get("DHT11_WAIT_US") == 80        # 响应/位超时步进（1us/步）
    assert constants.get("DHT11_RELEASE_US") == 20
    assert constants.get("DHT11_BIT0_LOW_US") == 54    # 位 0/1 共同低电平
    assert constants.get("DHT11_BIT0_HIGH_US") == 27   # 位 0 高（< 28us）
    assert constants.get("DHT11_BIT1_HIGH_US") == 74   # 位 1 高（> 28us）

    c = (MODULES / "dht11" / "code" / "dht11_stm32.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert "delay_ms(DHT11_START_MS)" in code_only
    assert "delay_us(DHT11_CHECK_TIME_US)" in code_only
    assert c.count("DHT11_WAIT_US") >= 4  # 两响应 + 两位等待计数


def test_dht11_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用、零 delay_uus；单总线方向切换（gpio_init OUT_PP/IU）；**页面缺陷
    防回潮**（超时返回 1、返回语义 0=成功、无 extern 全局泄漏、无 RCU_DHT11、
    校验和、0.1 系数、静态缓存）。"""
    c = (MODULES / "dht11" / "code" / "dht11_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "dht11" / "code" / "dht11_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"
    # mspm0 零改动：stm32 源码不含 DL_GPIO 调用
    assert "DL_GPIO" not in code_only

    # 单总线方向切换（页面原式 PP 输出 / IPU 输入 → OUT_PP/IU）
    assert re.search(
        r"#define\s+DHT11_DATA_OUT\(\)\s+gpio_init\(DHT11_GPIO, DHT11_PIN, OUT_PP\)",
        code_only,
    )
    assert re.search(
        r"DHT11_DATA_IN\(\)\s+gpio_init\(DHT11_GPIO, DHT11_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+DHT11_DATA_SET\(x\)\s+gpio_set", code_only)
    assert re.search(r"#define\s+DHT11_DATA_GET\(\)\s+gpio_get", code_only)

    # 页面缺陷防回潮：① 超时计数 + return 1（无应答/回应超时）
    assert code_only.count("return 1;") >= 2
    assert "timeout = DHT11_WAIT_US" in code_only
    assert "if (timeout == 0)" in code_only
    # ② 返回语义 0=成功（read 尾 return 0 + 校验失败 return 1）
    assert re.search(r"return 0;", code_only)
    # ③ 无 delay_uus / 无 extern 全局泄漏 / 无 RCU_DHT11（BANNED 已守）
    assert "extern" not in code_only
    assert "RCU_DHT11" not in code_only
    # ④ 校验和（前 4 字节和末 8 位）+ 0.1 系数
    assert "verify_num" in code_only
    assert "0.1f" in code_only
    # ⑤ 静态缓存（read_temperature/read_humidity 读 s_temperature/s_humidity）
    assert "static float s_temperature" in code_only
    assert "return s_temperature" in code_only and "return s_humidity" in code_only
