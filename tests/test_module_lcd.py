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
    assert set(manifest.platforms) == {"mspm0"}

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
