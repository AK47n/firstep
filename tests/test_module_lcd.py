"""lcd 彩屏模块（六屏合一，批次 12 决策 A）：真实库 + 真实母版不变量与
mspm0 单选生成。

与 ws2812 / max7219 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
六角色 SCL/SDA/RES/DC/CS/BLK = gpio_out）、mspm0 单选生成（syscfg 裁剪保留
LCD、模块文件落盘、main.c 调 init/显示函数过静态门禁）、软 SPI 位操作无
平台依赖守卫（GPIO_ResetBits/RCC_/printf/DL_SPI 不得出现）、字库体积断言
（lcdfont.h ≤ 16KB + ascii_1206/ascii_1608/tfont16 存在 + ascii_2412/3216
与 pic.h 裁剪）、型号常量完整性（LCD_MODEL_096..180 六常量 + 0.96 分辨率
表项：80/160×…、默认方向 2）。全程无 LLM、无服务。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
LCD_DIR = MODULES / "lcd"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402
from contest_generator.clex import strip_comments  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "lcd.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    lcd_init(LCD_MODEL_096, LCD_DIR_DEFAULT);\n"
    "    lcd_clear(BLACK);\n"
    "    lcd_fill(0, 0, 40, 20, RED);\n"
    "    lcd_draw_point(10, 10, GREEN);\n"
    "    lcd_draw_line(0, 0, 30, 20, BLUE);\n"
    "    lcd_draw_rectangle(1, 1, 20, 10, YELLOW);\n"
    "    lcd_draw_circle(50, 40, 6, WHITE);\n"
    "    lcd_show_char(0, 0, 'A', WHITE, BLACK, 16, 0);\n"
    "    lcd_show_string(8, 20, (const uint8_t *)\"OK\", WHITE, BLACK, 16, 1);\n"
    "    lcd_show_num(0, 40, 123, 3, WHITE, BLACK, 16);\n"
    "    lcd_show_float(0, 60, 3.14f, 4, WHITE, BLACK, 16);\n"
    "    uint8_t hz[2] = {0xD6, 0xD0};\n"
    "    lcd_show_chinese16x16(0, 80, hz, WHITE, BLACK, 0);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_lcd_manifest_shape_mspm0():
    """lcd：仅 mspm0 平台条目；依赖 delay；六角色 SCL/SDA/RES/DC/CS/BLK = gpio_out。"""
    manifest = ModuleManifest.load(LCD_DIR)
    assert manifest.slug == "lcd"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == [
        "lcd.c", "lcd.h", "lcd_init.c", "lcd_init.h", "lcdfont.h",
    ]
    for rel in mspm0.files:
        assert (LCD_DIR / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required) for p in mspm0.pins] == [
        ("LCD_SCL", "gpio_out", "PA16", True),
        ("LCD_SDA", "gpio_out", "PA17", True),
        ("LCD_RES", "gpio_out", "PA27", True),
        ("LCD_DC", "gpio_out", "PA22", True),
        ("LCD_CS", "gpio_out", "PB19", True),
        ("LCD_BLK", "gpio_out", "PB20", True),
    ]
    assert mspm0.kit and mspm0.source_url


def test_lcd_mspm0_syscfg_instances():
    """mspm0 母版：LCD GPIO 实例（SCL/SDA/RES/DC/CS/BLK 六输出，CS/BLK 初始高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const LCD = GPIO.addInstance();" in syscfg
    assert "LCD.associatedPins.create(6);" in syscfg
    for i, (name, pin) in enumerate([
        ("SCL", "PA16"), ("SDA", "PA17"), ("RES", "PA27"),
        ("DC", "PA22"), ("CS", "PB19"), ("BLK", "PB20"),
    ]):
        assert f'LCD.associatedPins[{i}].$name        = "{name}";' in syscfg
        assert f"LCD.associatedPins[{i}].direction    = \"OUTPUT\";" in syscfg
        assert f'LCD.associatedPins[{i}].pin.$assign  = "{pin}";' in syscfg
    assert 'LCD.associatedPins[4].initialValue = "SET";' in syscfg  # CS
    assert 'LCD.associatedPins[5].initialValue = "SET";' in syscfg  # BLK


def test_lcd_mspm0_single_select_generation(tmp_path):
    """lcd mspm0 单选生成：syscfg 保留 LCD、模块文件落盘、静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["lcd"])
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
    assert "const LCD = GPIO.addInstance();" in syscfg
    assert 'LCD.associatedPins[5].pin.$assign  = "PB20";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "DC_MOTOR",
        "PWMAB", "SERVO_PWM", "IR_REMOTE", "PCA9685", "IR_TX", "MAX7219",
    ):
        assert f"const {drop}" not in syscfg
    for rel in ("lcd.c", "lcd.h", "lcd_init.c", "lcd_init.h", "lcdfont.h"):
        assert (out / f"modules/lcd/code/{rel}").is_file()
    # 依赖 delay 落盘（delay 模块随依赖展开）
    assert (out / "modules/delay/code/delay.c").is_file()


def test_lcd_font_trim_assertions():
    """字库裁剪（spec 决策 A）：lcdfont.h ≤ 16KB；ASCII 两套（1206/1608）+ tfont16
    存在；大字号 ascii_2412/3216 与演示位图 pic.h 裁剪（不入库）。"""
    font = (LCD_DIR / "code" / "lcdfont.h").read_text(encoding="utf-8")
    assert len(font.encode("utf-8")) <= 16 * 1024, \
        f"lcdfont.h {len(font.encode('utf-8'))}B 超 16KB 预算"
    for name in ("ascii_1206", "ascii_1608", "tfont16"):
        assert name in font
    for name in ("ascii_2412", "ascii_3216", "tfont12", "tfont24", "tfont32"):
        # 数组定义形态（注释提及不算——header 注释记录裁剪策略）
        assert name + "[][" not in font, f"{name} 应裁剪"
    assert not (LCD_DIR / "code" / "pic.h").exists(), "pic.h 演示位图不入库"


def test_lcd_no_platform_deps_and_model_contract():
    """无平台依赖守卫（STM32/printf/硬件 SPI 不得出现）+ 型号常量完整性：
    LCD_MODEL_096..180 六常量齐全 + 0.96 型号表项（默认方向 2、横屏 160×80、
    竖屏 80×160）已落表。"""
    code_text = ""
    for rel in ("code/lcd.c", "code/lcd.h", "code/lcd_init.c", "code/lcd_init.h"):
        code_text += strip_comments((LCD_DIR / rel).read_text(encoding="utf-8"),
                                    keep_preprocessor=True)
    for banned in ("GPIO_ResetBits", "GPIO_SetBits", "RCC_APB2PeriphClockCmd",
                   "printf", "DL_SPI", "USE_HORIZONTAL"):
        assert banned not in code_text, f"平台依赖残留：{banned}"
    h = (LCD_DIR / "code" / "lcd.h").read_text(encoding="utf-8")
    for model in (
        "LCD_MODEL_096", "LCD_MODEL_128", "LCD_MODEL_130",
        "LCD_MODEL_147", "LCD_MODEL_169", "LCD_MODEL_180",
    ):
        assert f"#define {model}" in h
    init_c = (LCD_DIR / "code" / "lcd_init.c").read_text(encoding="utf-8")
    # 0.96 型号表项：默认方向 = 2（横屏），w[2]=160 / h[2]=80，竖屏 80×160
    assert "lcd_seq_096" in init_c
    assert "{1, {80, 80, 160, 160}, {160, 160, 80, 80}," in init_c
    # 1.3（ST7789V2 240×240，默认方向 0 竖屏）+ 1.69（ST7789V2 240×280）表项
    assert "lcd_seq_130" in init_c
    assert "{1, {240, 240, 240, 240}, {240, 240, 240, 240}," in init_c
    assert "lcd_seq_169" in init_c
    assert "{1, {240, 240, 280, 280}, {280, 280, 240, 240}," in init_c
    # 1.28（GC9A01 240×240 圆屏）/1.47（ST7789V3 172×320）/1.8（ST7735S 128×160）
    assert "lcd_seq_128" in init_c
    assert "lcd_seq_147" in init_c
    assert "{1, {172, 172, 320, 320}, {320, 320, 172, 172}," in init_c
    assert "lcd_seq_180" in init_c
    assert "{1, {128, 128, 160, 160}, {160, 160, 128, 128}," in init_c
    # 六型号全部实现（无占位空行——valid=0 表项消失）
    assert "[0, 0, 0, 0]}, {0, 0, 0, 0}, 0, NULL, 0" not in init_c


# ---------------------------------------------------------------------------
# 批次 10（wiki-stm32-batch10/02）：stm32 平台条目
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "lcd_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    lcd_init(LCD_MODEL_096, LCD_DIR_DEFAULT);\n"
    "    (void)lcd_get_width();\n"
    "    (void)lcd_get_height();\n"
    "    lcd_clear(BLACK);\n"
    "    lcd_fill(0, 0, 40, 20, RED);\n"
    "    lcd_draw_point(10, 10, GREEN);\n"
    "    lcd_draw_line(0, 0, 30, 20, BLUE);\n"
    "    lcd_draw_rectangle(1, 1, 20, 10, YELLOW);\n"
    "    lcd_draw_circle(50, 40, 6, WHITE);\n"
    "    lcd_show_char(0, 0, 'A', WHITE, BLACK, 16, 0);\n"
    "    lcd_show_string(8, 20, (const uint8_t *)\"OK\", WHITE, BLACK, 16, 1);\n"
    "    lcd_show_num(0, 40, 123, 3, WHITE, BLACK, 16);\n"
    "    lcd_show_float(0, 60, 3.14f, 4, WHITE, BLACK, 16);\n"
    "    uint8_t hz[2] = {0xD6, 0xD0};\n"
    "    lcd_show_chinese16x16(0, 80, hz, WHITE, BLACK, 0);\n"
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
    (r"\bDL_GPIO\b|\bDL_SPI\b", "DL_ 调用（mspm0）"),
    (r"\bti_msp_dl_config\.h\b", "ti_msp_dl_config.h"),
]


def test_lcd_stm32_manifest_shape():
    """lcd stm32 条目：三文件（stm32 两件 + 共享 lcdfont.h）；六角色 =
    PB4/PB5/PA5/PB6/PB7/PA15（macros 逐脚端口宏）；mspm0 条目原样零改动。"""
    manifest = ModuleManifest.load(LCD_DIR)
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "lcd_stm32.c",
        "lcd_stm32.h",
        "lcdfont.h",
    ]
    for rel in stm32.files:
        assert (LCD_DIR / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("LCD_SCL", "gpio_out", "PB4", True, ("LCD_SCL_GPIO", "LCD_SCL_PIN")),
        ("LCD_SDA", "gpio_out", "PB5", True, ("LCD_SDA_GPIO", "LCD_SDA_PIN")),
        ("LCD_RES", "gpio_out", "PA5", True, ("LCD_RES_GPIO", "LCD_RES_PIN")),
        ("LCD_DC", "gpio_out", "PB6", True, ("LCD_DC_GPIO", "LCD_DC_PIN")),
        ("LCD_CS", "gpio_out", "PB7", True, ("LCD_CS_GPIO", "LCD_CS_PIN")),
        ("LCD_BLK", "gpio_out", "PA15", True, ("LCD_BLK_GPIO", "LCD_BLK_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dmx/module/screen/0-96-color-screen.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/screen--0-96-color-screen.md",
        "lckfb-地阔星移植手册/screen--1-47-color-screen.md",
        "F4",
        "互替",
        "lcdfont.h",
        "未上板",
    ):
        assert needle in stm32.notes
    # mspm0 条目零改动
    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == [
        "lcd.c", "lcd.h", "lcd_init.c", "lcd_init.h", "lcdfont.h",
    ]
    assert [(p.id, p.type, p.default, p.required) for p in mspm0.pins] == [
        ("LCD_SCL", "gpio_out", "PA16", True),
        ("LCD_SDA", "gpio_out", "PA17", True),
        ("LCD_RES", "gpio_out", "PA27", True),
        ("LCD_DC", "gpio_out", "PA22", True),
        ("LCD_CS", "gpio_out", "PB19", True),
        ("LCD_BLK", "gpio_out", "PB20", True),
    ]


def test_lcd_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：lcd 六脚 12 宏在母版 pin_config.h（默认 PB4/5/PA5/PB6/7/PA15）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    for macro, value in (
        ("LCD_SCL_GPIO", "GPIO_B"), ("LCD_SCL_PIN", "Pin_4"),
        ("LCD_SDA_GPIO", "GPIO_B"), ("LCD_SDA_PIN", "Pin_5"),
        ("LCD_RES_GPIO", "GPIO_A"), ("LCD_RES_PIN", "Pin_5"),
        ("LCD_DC_GPIO", "GPIO_B"), ("LCD_DC_PIN", "Pin_6"),
        ("LCD_CS_GPIO", "GPIO_B"), ("LCD_CS_PIN", "Pin_7"),
        ("LCD_BLK_GPIO", "GPIO_A"), ("LCD_BLK_PIN", "Pin_15"),
    ):
        assert re.search(r"#define\s+" + macro + r"\s+" + value, text), macro


def test_lcd_stm32_single_select_generation(tmp_path):
    """lcd stm32 单选生成：静态门禁通过、三文件落盘、uvprojx 注册 lcd_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["lcd"])
    assert {m.slug for m in resolved.manifests} == {"lcd", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    for rel in ("lcd_stm32.c", "lcd_stm32.h", "lcdfont.h"):
        assert (out / "modules/lcd/code" / rel).is_file(), rel
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("lcd_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_lcd_stm32_code_guards():
    """stm32 代码层守卫：软 SPI 六脚位操作（gpio_set）+ 六模型常量 +
    LCD_DIR_DEFAULT 0xFF + MADCTL 0x36 序列占位/0x2A/0x2B/0x2C 地址 +
    字库体积 ≤16KB + 零演示位图数组 + 零 DL_/printf/GPIO_Init/RCC_。"""
    c = (LCD_DIR / "code" / "lcd_stm32.c").read_text(encoding="utf-8")
    h = (LCD_DIR / "code" / "lcd_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 总线原语 + 六脚宏族（gpio_set 位操作）
    assert re.search(r"#define\s+LCD_SCL\(x\)\s+gpio_set\(LCD_SCL_GPIO", code_only)
    assert re.search(r"#define\s+LCD_BLK\(x\)\s+gpio_set\(LCD_BLK_GPIO", code_only)
    # 六模型常量 + 出厂默认方向
    for model in (
        "LCD_MODEL_096", "LCD_MODEL_128", "LCD_MODEL_130",
        "LCD_MODEL_147", "LCD_MODEL_169", "LCD_MODEL_180",
    ):
        assert f"#define {model}" in code_only
    assert "LCD_DIR_DEFAULT 0xFFu" in code_only
    # 序列关键字节：MADCTL 0x36 / 16 位色 0x3A / 列 0x2A / 行 0x2B / 写 0x2C
    assert "0x36" in code_only and "0x3A" in code_only
    assert "0x2A" in code_only and "0x2B" in code_only and "0x2C" in code_only
    # 型号表驱动（lcd_models[6]）+ 绘制 API 全族
    assert "lcd_models[6]" in code_only
    for fn in (
        "lcd_init", "lcd_get_width", "lcd_get_height", "lcd_fill", "lcd_clear",
        "lcd_draw_point", "lcd_draw_line", "lcd_draw_rectangle",
        "lcd_draw_circle", "lcd_show_char", "lcd_show_string", "lcd_show_num",
        "lcd_show_float", "lcd_show_chinese16x16", "lcd_show_picture",
    ):
        assert re.search(r"\b" + fn + r"\s*\(", code_only), fn
    # 字库：共享 lcdfont.h 在库内（≤16KB——mspm0 断言同款口径）
    font = (LCD_DIR / "code" / "lcdfont.h").read_text(encoding="utf-8")
    assert len(font.encode("utf-8")) <= 16 * 1024
    for name in ("ascii_1206", "ascii_1608", "tfont16"):
        assert name in font
    # 零演示位图（pic.h 不入库——mspm0 先例）
    assert not (LCD_DIR / "code" / "pic.h").exists()
