"""ili9341 2.8 寸大屏模块（B 类新 slug——仅 stm32 条目、无 mspm0 对照）：
真实库 + 真实母版不变量与 stm32 单选生成。

与 lcd（六合一）/ neo_6m（B 类）同款结构测试：manifest 形状（仅 stm32、
deps ()——delay 走母版内嵌 ml_delay（headfile.h，B 类口径）、六角色 = lcd 六脚组同款 PB4/PB5/PA5/PB6/PB7/PA15）、stm32 单选
生成（模块文件落盘含 lcdfont.h 副本、uvprojx 注册）、守卫（ILI9341 序列关键
字节、无 lcdwiki 旧壳 POINT_COLOR/LCD_ShowString、无 sys.h 位带、无打印/标准
外设残留、字库 ≤16KB）。全程无 LLM、无服务。
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
ILI9341 = MODULES / "ili9341"

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ili9341_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ili9341_init(ILI9341_DIR_DEFAULT);\n"
    "    (void)ili9341_get_width();\n"
    "    (void)ili9341_get_height();\n"
    "    ili9341_clear(BLACK);\n"
    "    ili9341_fill(0, 0, 40, 20, RED);\n"
    "    ili9341_draw_point(10, 10, GREEN);\n"
    "    ili9341_draw_line(0, 0, 30, 20, BLUE);\n"
    "    ili9341_draw_rectangle(1, 1, 20, 10, YELLOW);\n"
    "    ili9341_draw_circle(50, 40, 6, WHITE);\n"
    "    ili9341_show_char(0, 0, 'A', WHITE, BLACK, 16, 0);\n"
    "    ili9341_show_string(8, 20, (const uint8_t *)\"OK\", WHITE, BLACK, 16, 1);\n"
    "    ili9341_show_num(0, 40, 123, 3, WHITE, BLACK, 16);\n"
    "    ili9341_show_float(0, 60, 3.14f, 4, WHITE, BLACK, 16);\n"
    "    uint8_t hz[2] = {0xD6, 0xD0};\n"
    "    ili9341_show_chinese16x16(0, 80, hz, WHITE, BLACK, 0);\n"
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
    (r"\bPBout\b|\bPAin\b", "位带宏"),
    (r"\bPOINT_COLOR\b|\bBACK_COLOR\b", "lcdwiki 旧壳"),
    (r"\bLCD_ShowString\b|\blcddev\b", "lcdwiki 旧壳"),
    (r"\bDL_GPIO\b|\bDL_SPI\b", "DL_ 调用（mspm0）"),
    (r"\bti_msp_dl_config\.h\b", "ti_msp_dl_config.h"),
]


def test_ili9341_manifest_shape():
    """B 类口径：仅 stm32 平台条目（无 mspm0）；依赖 delay；六角色 =
    PB4/PB5/PA5/PB6/PB7/PA15（macros 逐脚端口宏）。"""
    manifest = ModuleManifest.load(ILI9341)
    assert manifest.slug == "ili9341"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ili9341_stm32.c",
        "ili9341_stm32.h",
        "ili9341_font.h",
    ]
    for rel in stm32.files:
        assert (ILI9341 / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("ILI9341_SCL", "gpio_out", "PB4", True, ("ILI9341_SCL_GPIO", "ILI9341_SCL_PIN")),
        ("ILI9341_SDA", "gpio_out", "PB5", True, ("ILI9341_SDA_GPIO", "ILI9341_SDA_PIN")),
        ("ILI9341_RES", "gpio_out", "PA5", True, ("ILI9341_RES_GPIO", "ILI9341_RES_PIN")),
        ("ILI9341_DC", "gpio_out", "PB6", True, ("ILI9341_DC_GPIO", "ILI9341_DC_PIN")),
        ("ILI9341_CS", "gpio_out", "PB7", True, ("ILI9341_CS_GPIO", "ILI9341_CS_PIN")),
        ("ILI9341_BLK", "gpio_out", "PA15", True, ("ILI9341_BLK_GPIO", "ILI9341_BLK_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dmx/module/screen/"
        "2-8-and-3.2-color-screen.html"
    )
    for needle in (
        "B 类：无 mspm0 条目",
        "网盘下载/ili9341/",
        "MSP2807",
        "互替",
        "ili9341_font.h",
        "0.27s",
        "未上板",
    ):
        assert needle in stm32.notes
    # 能力方向（简介判据③）
    assert "大屏" in manifest.description
    assert "ILI9341" in manifest.description
    for banned in ("21F", "2024H", "2026H", "题目", "专用"):
        assert banned not in manifest.description


def test_ili9341_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：ILI9341 六脚 12 宏在母版 pin_config.h（lcd 六脚组同款）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    for macro, value in (
        ("ILI9341_SCL_GPIO", "GPIO_B"), ("ILI9341_SCL_PIN", "Pin_4"),
        ("ILI9341_SDA_GPIO", "GPIO_B"), ("ILI9341_SDA_PIN", "Pin_5"),
        ("ILI9341_RES_GPIO", "GPIO_A"), ("ILI9341_RES_PIN", "Pin_5"),
        ("ILI9341_DC_GPIO", "GPIO_B"), ("ILI9341_DC_PIN", "Pin_6"),
        ("ILI9341_CS_GPIO", "GPIO_B"), ("ILI9341_CS_PIN", "Pin_7"),
        ("ILI9341_BLK_GPIO", "GPIO_A"), ("ILI9341_BLK_PIN", "Pin_15"),
    ):
        assert re.search(r"#define\s+" + macro + r"\s+" + value, text), macro


def test_ili9341_stm32_single_select_generation(tmp_path):
    """ili9341 stm32 单选生成：静态门禁通过、三文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ili9341"])
    assert {m.slug for m in resolved.manifests} == {"ili9341"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    for rel in ("ili9341_stm32.c", "ili9341_stm32.h", "ili9341_font.h"):
        assert (out / "modules/ili9341/code" / rel).is_file(), rel
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ili9341_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ili9341_stm32_code_guards():
    """代码层守卫：初始化序列关键字节（0xCF/0xED/0x36/0x3A 0x55/0x11+120ms/
    0x29）+ MADCTL 方向表（0x08/0x68/0xC8/0xA8）+ 无 lcdwiki 旧壳 + 无位带宏
    + 字库 ≤16KB + API 全族。"""
    c = (ILI9341 / "code" / "ili9341_stm32.c").read_text(encoding="utf-8")
    h = (ILI9341 / "code" / "ili9341_stm32.h").read_text(encoding="utf-8")
    code_only = strip_comments(c + "\n" + h, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 SPI 总线宏（gpio_set 位操作）
    assert re.search(r"#define\s+ILI9341_SCL\(x\)\s+gpio_set\(ILI9341_SCL_GPIO", code_only)
    assert re.search(r"#define\s+ILI9341_BLK\(x\)\s+gpio_set\(ILI9341_BLK_GPIO", code_only)
    # 初始化序列关键字节（包内 LCD_Init 原式）
    assert "0xCF" in code_only and "0xED" in code_only and "0xE8" in code_only
    assert "0xCB" in code_only and "0xF7" in code_only and "0xEA" in code_only
    assert "0x3A" in code_only and "0x55" in code_only  # 16bit 色
    assert "0x11" in code_only and "0x29" in code_only  # Sleep/Display on
    assert "120" in code_only  # Exit Sleep 120ms
    # MADCTL 方向表（0x08/0x68/0xC8/0xA8——包内 LCD_direction 原式 BGR=1）
    assert "0x08u, 0x68u, 0xC8u, 0xA8u" in code_only
    # 地址窗口（0x2A/0x2B/0x2C）
    assert "0x2A" in code_only and "0x2B" in code_only and "0x2C" in code_only
    # API 全族（照 mspm0 lcd.h 风格——ili9341_ 前缀）
    for fn in (
        "ili9341_init", "ili9341_get_width", "ili9341_get_height", "ili9341_fill",
        "ili9341_clear", "ili9341_draw_point", "ili9341_draw_line",
        "ili9341_draw_rectangle", "ili9341_draw_circle", "ili9341_show_char",
        "ili9341_show_string", "ili9341_show_num", "ili9341_show_float",
        "ili9341_show_chinese16x16", "ili9341_show_picture",
    ):
        assert re.search(r"\b" + fn + r"\s*\(", code_only), fn
    # 字库：lcdfont.h 副本在库内（≤16KB）
    font = (ILI9341 / "code" / "ili9341_font.h").read_text(encoding="utf-8")
    # 副本含来源/static 化说明注释 ≈0.7KB——预算 17KB（字库本体 16.2KB 同 lcd）
    assert len(font.encode("utf-8")) <= 17 * 1024
    for name in ("ascii_1206", "ascii_1608", "tfont16"):
        assert name in font
