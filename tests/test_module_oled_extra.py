"""oled 总线/SH1106 变体补缺口（wiki-stm32-batch10/04-05，C 类口径）：stm32
侧 oled 条目 files [] → oled_extra_stm32.c/.h（SPI 总线变体 + 0.91 128×32 +
SH1106）——真实库 + 真实母版不变量与 stm32 单选生成。

照 mspm0 批 12/07 测试对仗：I2C 路径零变化断言（母版 ml_oled 头 + 既有
pins 不动）+ SPI 变体（5 脚宏存在 + oled_spi_init + OLED_RES_128X32 +
MUX 0x1F/COM 0x00）+ SH1106 变体（0xAD/0x8B/0x33 + 列偏移 0x02）+ 单选
生成（既有 oled 用例回归）+ 守卫（无 printf/GPIO_Init/RCC_、软 SPI 无硬件
SPI 调用、无 I2C 路径符号重定义）。全程无 LLM、无服务。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.generator import generate
from contest_generator.manifest import ModuleManifest
from contest_generator.platforms import PLATFORM_STM32
from contest_generator.selection import resolve_selection

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"
OLED = MODULES / "oled"

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "oled_extra_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    oled_set_res(OLED_RES_128X32);\n"
    "    oled_spi_init();\n"
    "    oled_spi_show_text(0, 0, \"OK\");\n"
    "    oled_spi_show_number(1, 0, 123, 3);\n"
    "    oled_spi_refresh();\n"
    "    oled_spi_clear();\n"
    "    oled_init_sh1106();\n"
    "    oled_spi_show_string(0, 0, \"SH1106\");\n"
    "    oled_spi_refresh();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bDL_GPIO\b|\bDL_SPI\b|\bDL_I2C\b", "DL_ 调用（mspm0）"),
    (r"\bti_msp_dl_config\.h\b", "ti_msp_dl_config.h"),
    (r"\bOLED_Init\b|\bOLED_ShowString\b|\bOLED_ShowChar\b|\bOLED_WR_Byte\b",
     "ml_oled 符号重定义（母版占用）"),
    (r"\bSPI_Init\b|\bSPI_\w+Ex\b", "硬件 SPI 调用"),
]


def test_oled_extra_stm32_manifest_shape():
    """oled stm32 条目：files = oled_extra 两件（既有 I2C 零改动——pins 保留
    OLED_SCL/SDA + 增 SPI 五角色 = PB4/5/6/7/PA5）。"""
    manifest = ModuleManifest.load(OLED)
    assert manifest.slug == "oled"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "oled_extra_stm32.c",
        "oled_extra_stm32.h",
    ]
    for rel in stm32.files:
        assert (OLED / rel).is_file(), rel
    pins = [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins]
    # 既有 I2C 双角色（PB8/PB9——共享端口宏 OLED_GPIO）零改动 + 新增 SPI 五角色
    assert pins[0] == ("OLED_SCL", "i2c_scl", "PB8", True,
                       ("OLED_GPIO", "OLED_SCL_Pin"))
    assert pins[1] == ("OLED_SDA", "i2c_sda", "PB9", True,
                       ("OLED_GPIO", "OLED_SDA_Pin"))
    assert pins[2:] == [
        ("OLED_SPI_SCL", "gpio_out", "PB4", True, ("OLED_SPI_SCL_GPIO", "OLED_SPI_SCL_PIN")),
        ("OLED_SPI_SDA", "gpio_out", "PB5", True, ("OLED_SPI_SDA_GPIO", "OLED_SPI_SDA_PIN")),
        ("OLED_SPI_DC", "gpio_out", "PB6", True, ("OLED_SPI_DC_GPIO", "OLED_SPI_DC_PIN")),
        ("OLED_SPI_CS", "gpio_out", "PB7", True, ("OLED_SPI_CS_GPIO", "OLED_SPI_CS_PIN")),
        ("OLED_SPI_RES", "gpio_out", "PA5", True, ("OLED_SPI_RES_GPIO", "OLED_SPI_RES_PIN")),
    ]
    for needle in (
        "批次 10 补缺口",
        "0x8B",
        "0xAD",
        "0x02",
        "互替同脚",
        "未上板",
    ):
        assert needle in stm32.notes


def test_oled_extra_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：OLED_SPI 五脚 10 宏在母版 pin_config.h（PB4/5/6/7/PA5）
    + 既有 OLED_GPIO/OLED_SCL_Pin/OLED_SDA_Pin（PB8/PB9）保留不动。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    for macro, value in (
        ("OLED_SPI_SCL_GPIO", "GPIO_B"), ("OLED_SPI_SCL_PIN", "Pin_4"),
        ("OLED_SPI_SDA_GPIO", "GPIO_B"), ("OLED_SPI_SDA_PIN", "Pin_5"),
        ("OLED_SPI_DC_GPIO", "GPIO_B"), ("OLED_SPI_DC_PIN", "Pin_6"),
        ("OLED_SPI_CS_GPIO", "GPIO_B"), ("OLED_SPI_CS_PIN", "Pin_7"),
        ("OLED_SPI_RES_GPIO", "GPIO_A"), ("OLED_SPI_RES_PIN", "Pin_5"),
    ):
        assert re.search(r"#define\s+" + macro + r"\s+" + value, text), macro
    # 既有 I2C 宏零改动（PB8/PB9）
    assert re.search(r"#define\s+OLED_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+OLED_SCL_Pin\s+Pin_8", text)
    assert re.search(r"#define\s+OLED_SDA_Pin\s+Pin_9", text)


def test_oled_extra_stm32_code_guards():
    """SPI 变体守卫：oled_spi_init + OLED_RES_128X32（MUX 0x1F/COM 0x00）+
    SH1106 序列（0xAD/0x8B/0x33 + 列偏移 0x02）+ 软 SPI 无硬件 SPI + 零
    ml_oled 符号重定义 + 零 printf/GPIO_Init/RCC_。"""
    c = (OLED / "code" / "oled_extra_stm32.c").read_text(encoding="utf-8")
    h = (OLED / "code" / "oled_extra_stm32.h").read_text(encoding="utf-8")
    code_only = strip_comments(c + "\n" + h, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # API 入口 + 分辨率宏
    assert re.search(r"void oled_spi_init\(void\)", code_only)
    assert re.search(r"void oled_init_sh1106\(void\)", code_only)
    assert re.search(r"void oled_set_res\(uint8_t res\)", code_only)
    assert "OLED_RES_128X32 1u" in code_only
    # 软 SPI 总线宏（gpio_set 位操作）
    assert re.search(r"#define\s+OLED_SPI_SCL\(x\)\s+gpio_set\(OLED_SPI_SCL_GPIO", code_only)
    assert re.search(r"#define\s+OLED_SPI_DC\(x\)\s+gpio_set\(OLED_SPI_DC_GPIO", code_only)
    # SSD1306 序列: MUX 0x1F/COM 0x00（128×32 分支）
    assert "0x1F : 0x3F" in code_only
    assert "0x00 : 0x12" in code_only
    # SH1106 专属序列（0xAD/0x8B/0x33 + 列偏移 0x02）
    assert "0xAD" in code_only and "0x8B" in code_only and "0x33" in code_only
    assert "0x02" in code_only
    assert "low_col = s_sh1106 ? 0x02 : 0x00" in code_only
    # 显存绘制 API（小写族 + 刷新/清屏）
    for fn in ("oled_spi_refresh", "oled_spi_clear", "oled_spi_show_char",
               "oled_spi_show_string", "oled_spi_show_num",
               "oled_spi_show_text", "oled_spi_show_number"):
        assert re.search(r"\b" + fn + r"\s*\(", code_only), fn


def test_oled_extra_stm32_i2c_path_zero_change():
    """I2C 路径零变化：母版 ml_oled.h/ml_oled.c 未被本工单触碰（既有
    OLED_Init/OLED_ShowString/oled_show_text 保存）——content checksum 语义：
    关键 API 名逐一存在 + 无 SPI 符号混入。"""
    mlh = (STM32_MASTER / "ml_libs" / "ml_oled.h").read_text(encoding="utf-8")
    for name in ("OLED_Init", "OLED_ShowString", "OLED_ShowChar",
                 "oled_show_text", "oled_show_number", "oled_refresh"):
        assert re.search(r"\b" + name + r"\s*\(", mlh), name
    # 母版头不含 SPI 变体符号（零增量——SPI 变体全在模块 extra）
    assert "oled_spi_init" not in mlh
    assert "oled_init_sh1106" not in mlh


def test_oled_extra_stm32_single_select_generation(tmp_path):
    """oled stm32 单选生成：extra 两件落盘、uvprojx 注册、pin_config.h 在
    工程根——既有 oled 单选用例回归（I2C 路径在母版，生成零变化）。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["oled"])
    assert {m.slug for m in resolved.manifests} == {"oled", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/oled/code/oled_extra_stm32.c").is_file()
    assert (out / "modules/oled/code/oled_extra_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("oled_extra_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()
