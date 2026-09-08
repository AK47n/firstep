"""st7789_para 1.14 寸 8 位并口彩屏模块（B 类新 slug——仅 stm32 条目、无
mspm0 对照）：真实库 + 真实母版不变量与 stm32 单选生成。

与 ili9341/ili9488（B 类同款）同构测试：manifest 形状（仅 stm32、deps ()——
delay_ms 走母版内嵌 ml_delay（headfile.h，B 类口径）、14 角 = DB0-7/
RD/WR/CS/DC/RES/BLK（工单重拍默认脚——包默认 14 脚全弃用）、stm32 单选
生成（模块文件落盘含 st7789_para_font.h 副本、uvprojx 注册）、守卫（8080
并口序列关键字节、无 lcdwiki 旧壳 POINT_COLOR/LCD_ShowString、**无 FSMC**、
无 sys.h 位带、无打印/标准外设残留、无 pic.h 位图数组、135/240 分辨率、
字库 ≤17KB）。全程无 LLM、无服务。
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
ST7789_PARA = MODULES / "st7789_para"

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "st7789_para_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    st7789_para_init(ST7789_PARA_DIR_DEFAULT);\n"
    "    (void)st7789_para_get_width();\n"
    "    (void)st7789_para_get_height();\n"
    "    st7789_para_clear(BLACK);\n"
    "    st7789_para_fill(0, 0, 40, 20, RED);\n"
    "    st7789_para_draw_point(10, 10, GREEN);\n"
    "    st7789_para_draw_line(0, 0, 30, 20, BLUE);\n"
    "    st7789_para_draw_rectangle(1, 1, 20, 10, YELLOW);\n"
    "    st7789_para_draw_circle(50, 40, 6, WHITE);\n"
    "    st7789_para_show_char(0, 0, 'A', WHITE, BLACK, 16, 0);\n"
    "    st7789_para_show_string(8, 20, (const uint8_t *)\"OK\", WHITE, BLACK, 16, 1);\n"
    "    st7789_para_show_num(0, 40, 123, 3, WHITE, BLACK, 16);\n"
    "    st7789_para_show_float(0, 60, 3.14f, 4, WHITE, BLACK, 16);\n"
    "    uint8_t hz[2] = {0xD6, 0xD0};\n"
    "    st7789_para_show_chinese16x16(0, 80, hz, WHITE, BLACK, 0);\n"
    "    uint8_t pic[8] = {0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0xFF, 0xFF};\n"
    "    st7789_para_show_picture(0, 100, 2, 2, pic);\n"
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
    (r"\bFSMC\b", "FSMC（不用——GPIO 位操作）"),
    (r"\bDL_GPIO\b|\bDL_SPI\b", "DL_ 调用（mspm0）"),
    (r"\bti_msp_dl_config\.h\b", "ti_msp_dl_config.h"),
]


def test_st7789_para_manifest_shape():
    """B 类口径：仅 stm32 平台条目（无 mspm0）；依赖 delay；14 角 =
    DB0-7/RD/WR/CS/DC/RES/BLK 工单重拍默认脚（macros 逐脚端口宏 28 个）。"""
    manifest = ModuleManifest.load(ST7789_PARA)
    assert manifest.slug == "st7789_para"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "st7789_para_stm32.c",
        "st7789_para_stm32.h",
        "st7789_para_font.h",
    ]
    for rel in stm32.files:
        assert (ST7789_PARA / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("ST7789_PARA_DB0", "gpio_out", "PB4", True, ("ST7789_PARA_DB0_GPIO", "ST7789_PARA_DB0_PIN")),
        ("ST7789_PARA_DB1", "gpio_out", "PB5", True, ("ST7789_PARA_DB1_GPIO", "ST7789_PARA_DB1_PIN")),
        ("ST7789_PARA_DB2", "gpio_out", "PB6", True, ("ST7789_PARA_DB2_GPIO", "ST7789_PARA_DB2_PIN")),
        ("ST7789_PARA_DB3", "gpio_out", "PB7", True, ("ST7789_PARA_DB3_GPIO", "ST7789_PARA_DB3_PIN")),
        ("ST7789_PARA_DB4", "gpio_out", "PB0", True, ("ST7789_PARA_DB4_GPIO", "ST7789_PARA_DB4_PIN")),
        ("ST7789_PARA_DB5", "gpio_out", "PB1", True, ("ST7789_PARA_DB5_GPIO", "ST7789_PARA_DB5_PIN")),
        ("ST7789_PARA_DB6", "gpio_out", "PB3", True, ("ST7789_PARA_DB6_GPIO", "ST7789_PARA_DB6_PIN")),
        ("ST7789_PARA_DB7", "gpio_out", "PA8", True, ("ST7789_PARA_DB7_GPIO", "ST7789_PARA_DB7_PIN")),
        ("ST7789_PARA_RD", "gpio_out", "PA5", True, ("ST7789_PARA_RD_GPIO", "ST7789_PARA_RD_PIN")),
        ("ST7789_PARA_WR", "gpio_out", "PA4", True, ("ST7789_PARA_WR_GPIO", "ST7789_PARA_WR_PIN")),
        ("ST7789_PARA_CS", "gpio_out", "PC13", True, ("ST7789_PARA_CS_GPIO", "ST7789_PARA_CS_PIN")),
        ("ST7789_PARA_DC", "gpio_out", "PC14", True, ("ST7789_PARA_DC_GPIO", "ST7789_PARA_DC_PIN")),
        ("ST7789_PARA_RES", "gpio_out", "PC15", True, ("ST7789_PARA_RES_GPIO", "ST7789_PARA_RES_PIN")),
        ("ST7789_PARA_BLK", "gpio_out", "PA15", True, ("ST7789_PARA_BLK_GPIO", "ST7789_PARA_BLK_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/screen/"
        "1-14-color-screen.html"
    )
    for needle in (
        "B 类：无 mspm0 条目",
        "网盘下载/st7789_para/",
        "库内首个 8 位并口",
        "互替",
        "st7789_para_font.h",
        "未上板",
    ):
        assert needle in stm32.notes
    # 能力方向（简介判据③）
    assert "并口" in manifest.description
    assert "ST7789V" in manifest.description
    assert "1.14" in manifest.description
    for banned in ("21F", "2024H", "2026H", "题目", "专用"):
        assert banned not in manifest.description


def test_st7789_para_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：st7789_para 14 脚 28 宏在母版 pin_config.h（工单重拍）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    for macro, value in (
        ("ST7789_PARA_DB0_GPIO", "GPIO_B"), ("ST7789_PARA_DB0_PIN", "Pin_4"),
        ("ST7789_PARA_DB1_GPIO", "GPIO_B"), ("ST7789_PARA_DB1_PIN", "Pin_5"),
        ("ST7789_PARA_DB2_GPIO", "GPIO_B"), ("ST7789_PARA_DB2_PIN", "Pin_6"),
        ("ST7789_PARA_DB3_GPIO", "GPIO_B"), ("ST7789_PARA_DB3_PIN", "Pin_7"),
        ("ST7789_PARA_DB4_GPIO", "GPIO_B"), ("ST7789_PARA_DB4_PIN", "Pin_0"),
        ("ST7789_PARA_DB5_GPIO", "GPIO_B"), ("ST7789_PARA_DB5_PIN", "Pin_1"),
        ("ST7789_PARA_DB6_GPIO", "GPIO_B"), ("ST7789_PARA_DB6_PIN", "Pin_3"),
        ("ST7789_PARA_DB7_GPIO", "GPIO_A"), ("ST7789_PARA_DB7_PIN", "Pin_8"),
        ("ST7789_PARA_RD_GPIO", "GPIO_A"), ("ST7789_PARA_RD_PIN", "Pin_5"),
        ("ST7789_PARA_WR_GPIO", "GPIO_A"), ("ST7789_PARA_WR_PIN", "Pin_4"),
        ("ST7789_PARA_CS_GPIO", "GPIO_C"), ("ST7789_PARA_CS_PIN", "Pin_13"),
        ("ST7789_PARA_DC_GPIO", "GPIO_C"), ("ST7789_PARA_DC_PIN", "Pin_14"),
        ("ST7789_PARA_RES_GPIO", "GPIO_C"), ("ST7789_PARA_RES_PIN", "Pin_15"),
        ("ST7789_PARA_BLK_GPIO", "GPIO_A"), ("ST7789_PARA_BLK_PIN", "Pin_15"),
    ):
        assert re.search(r"#define\s+" + macro + r"\s+" + value, text), macro


def test_st7789_para_stm32_single_select_generation(tmp_path):
    """st7789_para stm32 单选生成：静态门禁通过、三文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["st7789_para"])
    assert {m.slug for m in resolved.manifests} == {"st7789_para"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    for rel in ("st7789_para_stm32.c", "st7789_para_stm32.h", "st7789_para_font.h"):
        assert (out / "modules/st7789_para/code" / rel).is_file(), rel
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("st7789_para_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_st7789_para_stm32_code_guards():
    """代码层守卫：8080 并口序列关键字节（0x11/0x36/0x3A 0x05/0xB2/0xE0/
    0xE1/0x21/0x29 + 120ms）+ MADCTL 方向表（0x00/0xC0/0x70/0xA0）+ 地址偏移
    表（52/53/40/40）+ 无 lcdwiki 旧壳 + 无 FSMC + 无位带宏 + 字库 ≤17KB +
    API 全族 + 135/240 分辨率。"""
    c = (ST7789_PARA / "code" / "st7789_para_stm32.c").read_text(encoding="utf-8")
    h = (ST7789_PARA / "code" / "st7789_para_stm32.h").read_text(encoding="utf-8")
    code_only = strip_comments(c + "\n" + h, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 8080 并口总线宏（gpio_set 位操作——14 脚全族）
    for macro in ("DB0", "DB1", "DB2", "DB3", "DB4", "DB5", "DB6", "DB7",
                  "RD", "WR", "CS", "DC", "RES", "BLK"):
        assert re.search(
            rf"#define\s+ST7789_PARA_{macro}\(x\)\s+gpio_set\(ST7789_PARA_{macro}_GPIO",
            code_only,
        ), f"总线宏 ST7789_PARA_{macro} 缺失"
    # 初始化序列关键字节（包内 LCD_Init 原式）
    for needle in ("0x11", "0x36", "0x3A", "0x05", "0xB2", "0xB7", "0xBB",
                   "0xC0", "0xC2", "0xC3", "0xC4", "0xC6", "0xD0", "0xE0",
                   "0xE1", "0x21", "0x29"):
        assert needle in code_only
    assert "120" in code_only  # Exit Sleep 120ms
    # MADCTL 方向表（包内 USE_HORIZONTAL 原式）
    assert "0x00u, 0xC0u, 0x70u, 0xA0u" in code_only
    # 地址窗口偏移表（包内 LCD_Address_Set 原式）
    assert "52u, 53u, 40u, 40u" in code_only
    assert "40u, 40u, 53u, 52u" in code_only
    # 地址窗口（0x2A/0x2B/0x2C）
    assert "0x2A" in code_only and "0x2B" in code_only and "0x2C" in code_only
    # 分辨率（135/240）
    assert "135" in code_only and "240" in code_only
    # API 全族（照 mspm0 lcd.h 风格——st7789_para_ 前缀）
    for fn in (
        "st7789_para_init", "st7789_para_get_width", "st7789_para_get_height",
        "st7789_para_fill", "st7789_para_clear", "st7789_para_draw_point",
        "st7789_para_draw_line", "st7789_para_draw_rectangle",
        "st7789_para_draw_circle", "st7789_para_show_char",
        "st7789_para_show_string", "st7789_para_show_num",
        "st7789_para_show_float", "st7789_para_show_chinese16x16",
        "st7789_para_show_picture",
    ):
        assert re.search(r"\b" + fn + r"\s*\(", code_only), fn
    # 字库：库内 lcdfont.h 同源副本在库内（≤17KB——与 ili 同款预算）
    font = (ST7789_PARA / "code" / "st7789_para_font.h").read_text(encoding="utf-8")
    assert len(font.encode("utf-8")) <= 17 * 1024
    for name in ("ascii_1206", "ascii_1608", "tfont16"):
        assert name in font
    assert "static const" in font  # 副本 static 化（双选安全）
    assert "__ST7789_PARA_FONT_H" in font  # 头基名/守卫唯一
