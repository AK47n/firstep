# -*- coding: utf-8 -*-
"""wiki-stm32-batch10 收官一致性快检（提交前只读扫描，stm32 线版）。"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from contest_generator.clex import strip_comments  # noqa: E402

MOD = Path("library/modules")
PIN_CFG = Path("library/masters/stm32/pin_config.h").read_text(
    encoding="utf-8", errors="replace"
)
wl = json.load(open("src/contest_generator/wordlist.json", encoding="utf-8"))
libmods = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

CHECK = {
    "vl53l0x": {
        "files": ["vl53l0x_core.c", "vl53l0x_core.h", "vl53l0x_stm32.c", "vl53l0x_stm32.h"],
        "pins": [("VL53L0X_SCL", "i2c_scl", "PA6"), ("VL53L0X_SDA", "i2c_sda", "PA7"),
                 ("VL53L0X_XSHUT", "gpio_out", "PB0")],
        "macros": [("VL53L0X_SCL_GPIO", "GPIO_A"), ("VL53L0X_SCL_PIN", "Pin_6"),
                   ("VL53L0X_SDA_GPIO", "GPIO_A"), ("VL53L0X_SDA_PIN", "Pin_7"),
                   ("VL53L0X_XSHUT_GPIO", "GPIO_B"), ("VL53L0X_XSHUT_PIN", "Pin_0")],
        "deps": [],
        "needles": ["B 类：无 mspm0 条目", "0x29", "未上板", "最小切片"],
        "c_guard": [(r"\bPBout\b|\bPAin\b", None), (r"\bGPIO_Init\b", None),
                    (r"\bprintf\b", None),
                    (r"static void vl53l0x_iic_start", "存在"),
                    (r"VL53L0X_ADDR 0x52u", "存在")],
        "wordlist": True,
    },
    "max7219": {
        "files": ["max7219_stm32.c", "max7219_stm32.h"],
        "pins": [("MAX7219_DIN", "gpio_out", "PC13"), ("MAX7219_CLK", "gpio_out", "PC14"),
                 ("MAX7219_CS", "gpio_out", "PC15")],
        "macros": [("MAX7219_DIN_GPIO", "GPIO_C"), ("MAX7219_DIN_PIN", "Pin_13"),
                   ("MAX7219_CLK_GPIO", "GPIO_C"), ("MAX7219_CLK_PIN", "Pin_14"),
                   ("MAX7219_CS_GPIO", "GPIO_C"), ("MAX7219_CS_PIN", "Pin_15")],
        "deps": [],
        "needles": ["互替", "未上板"],
        "c_guard": [(r"\bprintf\b", None), (r"\bGPIO_Init\b", None),
                    (r"MAX7219_REG_DECODE_MODE  0x09u", "存在")],
    },
    "lcd": {
        "files": ["lcd_stm32.c", "lcd_stm32.h", "lcdfont.h"],
        "pins": [("LCD_SCL", "gpio_out", "PB4"), ("LCD_SDA", "gpio_out", "PB5"),
                 ("LCD_RES", "gpio_out", "PA5"), ("LCD_DC", "gpio_out", "PB6"),
                 ("LCD_CS", "gpio_out", "PB7"), ("LCD_BLK", "gpio_out", "PA15")],
        "macros": [("LCD_SCL_GPIO", "GPIO_B"), ("LCD_SCL_PIN", "Pin_4"),
                   ("LCD_SDA_GPIO", "GPIO_B"), ("LCD_SDA_PIN", "Pin_5"),
                   ("LCD_RES_GPIO", "GPIO_A"), ("LCD_RES_PIN", "Pin_5"),
                   ("LCD_DC_GPIO", "GPIO_B"), ("LCD_DC_PIN", "Pin_6"),
                   ("LCD_CS_GPIO", "GPIO_B"), ("LCD_CS_PIN", "Pin_7"),
                   ("LCD_BLK_GPIO", "GPIO_A"), ("LCD_BLK_PIN", "Pin_15")],
        "deps": ["delay"],
        "needles": ["F4", "互替", "lcdfont.h", "未上板"],
        "c_guard": [(r"\bprintf\b", None), (r"\bDL_GPIO\b", None),
                    (r"lcd_models\[6\]", "存在")],
    },
    "tp_xpt2046": {
        "files": ["tp_xpt2046_stm32.c", "tp_xpt2046_stm32.h"],
        "pins": [("TP_XPT2046_CS", "gpio_out", "PB12"), ("TP_XPT2046_CLK", "gpio_out", "PB13"),
                 ("TP_XPT2046_DIN", "gpio_out", "PB14"), ("TP_XPT2046_DOUT", "gpio_in", "PB15"),
                 ("TP_XPT2046_PEN", "gpio_in", "PB0")],
        "macros": [("TP_XPT2046_CS_GPIO", "GPIO_B"), ("TP_XPT2046_CS_PIN", "Pin_12"),
                   ("TP_XPT2046_CLK_GPIO", "GPIO_B"), ("TP_XPT2046_CLK_PIN", "Pin_13"),
                   ("TP_XPT2046_DIN_GPIO", "GPIO_B"), ("TP_XPT2046_DIN_PIN", "Pin_14"),
                   ("TP_XPT2046_DOUT_GPIO", "GPIO_B"), ("TP_XPT2046_DOUT_PIN", "Pin_15"),
                   ("TP_XPT2046_PEN_GPIO", "GPIO_B"), ("TP_XPT2046_PEN_PIN", "Pin_0")],
        "deps": ["delay"],
        "needles": ["互替", "未上板"],
        "c_guard": [(r"\bprintf\b", None), (r"\bIRQHandler\b", None),
                    (r"XPT2046_CMD_X  0xD0u", "存在")],
    },
    "oled": {
        "files": ["oled_extra_stm32.c", "oled_extra_stm32.h"],
        "pins_extra": [("OLED_SPI_SCL", "gpio_out", "PB4"), ("OLED_SPI_SDA", "gpio_out", "PB5"),
                       ("OLED_SPI_DC", "gpio_out", "PB6"), ("OLED_SPI_CS", "gpio_out", "PB7"),
                       ("OLED_SPI_RES", "gpio_out", "PA5")],
        "macros": [("OLED_SPI_SCL_GPIO", "GPIO_B"), ("OLED_SPI_SCL_PIN", "Pin_4"),
                   ("OLED_SPI_SDA_GPIO", "GPIO_B"), ("OLED_SPI_SDA_PIN", "Pin_5"),
                   ("OLED_SPI_DC_GPIO", "GPIO_B"), ("OLED_SPI_DC_PIN", "Pin_6"),
                   ("OLED_SPI_CS_GPIO", "GPIO_B"), ("OLED_SPI_CS_PIN", "Pin_7"),
                   ("OLED_SPI_RES_GPIO", "GPIO_A"), ("OLED_SPI_RES_PIN", "Pin_5")],
        "deps": ["delay"],
        "needles": ["0xAD", "0x8B", "0x02", "互替同脚", "未上板"],
        "c_guard": [(r"\bprintf\b", None), (r"\bOLED_Init\b", None),
                    (r"0xAD", "存在"), (r"0x1F : 0x3F", "存在")],
        "kit_optional": True,  # 既有 I2C 内嵌条目 kit/source_url 空（mspm0 同款既有状）
    },
    "ili9341": {
        "files": ["ili9341_stm32.c", "ili9341_stm32.h", "ili9341_font.h"],
        "pins": [("ILI9341_SCL", "gpio_out", "PB4"), ("ILI9341_SDA", "gpio_out", "PB5"),
                 ("ILI9341_RES", "gpio_out", "PA5"), ("ILI9341_DC", "gpio_out", "PB6"),
                 ("ILI9341_CS", "gpio_out", "PB7"), ("ILI9341_BLK", "gpio_out", "PA15")],
        "macros": [("ILI9341_SCL_GPIO", "GPIO_B"), ("ILI9341_SCL_PIN", "Pin_4"),
                   ("ILI9341_SDA_GPIO", "GPIO_B"), ("ILI9341_SDA_PIN", "Pin_5"),
                   ("ILI9341_RES_GPIO", "GPIO_A"), ("ILI9341_RES_PIN", "Pin_5"),
                   ("ILI9341_DC_GPIO", "GPIO_B"), ("ILI9341_DC_PIN", "Pin_6"),
                   ("ILI9341_CS_GPIO", "GPIO_B"), ("ILI9341_CS_PIN", "Pin_7"),
                   ("ILI9341_BLK_GPIO", "GPIO_A"), ("ILI9341_BLK_PIN", "Pin_15")],
        "deps": [],
        "needles": ["B 类：无 mspm0 条目", "MSP2807", "互替", "未上板"],
        "c_guard": [(r"\bPBout\b|\bPAin\b", None), (r"\bGPIO_Init\b", None),
                    (r"\bPOINT_COLOR\b|\bLCD_ShowString\b", None),
                    (r"0x08u, 0x68u, 0xC8u, 0xA8u", "存在")],
        "wordlist": True,
        "font": True,
    },
    "ili9488": {
        "files": ["ili9488_stm32.c", "ili9488_stm32.h", "ili9488_font.h"],
        "pins": [("ILI9488_SCL", "gpio_out", "PB4"), ("ILI9488_SDA", "gpio_out", "PB5"),
                 ("ILI9488_RES", "gpio_out", "PA5"), ("ILI9488_DC", "gpio_out", "PB6"),
                 ("ILI9488_CS", "gpio_out", "PB7"), ("ILI9488_BLK", "gpio_out", "PA15")],
        "macros": [("ILI9488_SCL_GPIO", "GPIO_B"), ("ILI9488_SCL_PIN", "Pin_4"),
                   ("ILI9488_SDA_GPIO", "GPIO_B"), ("ILI9488_SDA_PIN", "Pin_5"),
                   ("ILI9488_RES_GPIO", "GPIO_A"), ("ILI9488_RES_PIN", "Pin_5"),
                   ("ILI9488_DC_GPIO", "GPIO_B"), ("ILI9488_DC_PIN", "Pin_6"),
                   ("ILI9488_CS_GPIO", "GPIO_B"), ("ILI9488_CS_PIN", "Pin_7"),
                   ("ILI9488_BLK_GPIO", "GPIO_A"), ("ILI9488_BLK_PIN", "Pin_15")],
        "deps": [],
        "needles": ["B 类：无 mspm0 条目", "MSP3520", "18bit", "互替", "未上板"],
        "c_guard": [(r"\bPBout\b|\bPAin\b", None), (r"\bGPIO_Init\b", None),
                    (r"\bPOINT_COLOR\b|\bLCD_ShowString\b", None),
                    (r"0x66", "存在"), (r"dat << 3", "存在")],
        "wordlist": True,
        "font": True,
    },
}

problems: list[str] = []

def check_manifest(slug, exp):
    manifest = json.load(open(MOD / slug / "manifest.json", encoding="utf-8"))
    st = manifest["platforms"].get("stm32")
    if st is None:
        problems.append(f"{slug}: 无 stm32 条目")
        return
    if "files" in exp:
        got_files = [Path(f).name for f in st["files"]]
        if sorted(got_files) != sorted(exp["files"]):
            problems.append(f"{slug}: files {got_files} ≠ {exp['files']}")
    for rel in st["files"]:
        if not (MOD / slug / rel).is_file():
            problems.append(f"{slug}: 文件缺失 {rel}")
    if st.get("verified") is not True:
        problems.append(f"{slug}: verified {st.get('verified')} ≠ True")
    if st.get("hardware_bound") is not False:
        problems.append(f"{slug}: hardware_bound 应 False")
    if not exp.get("kit_optional") and (not st.get("kit") or not st.get("source_url")):
        problems.append(f"{slug}: kit/source_url 缺失")
    pins_exp = exp.get("pins")
    if pins_exp is None:
        # oled：既有 I2C 两行保留 + 新增 SPI 五行——只查 SPI 五行存在
        pins_exp = exp.get("pins_extra")
        got = [(p["id"], p["type"], p["default"]) for p in st["pins"]]
        for row in pins_exp:
            if row not in got:
                problems.append(f"{slug}: pins 缺 {row}")
    else:
        got_pins = [(p["id"], p["type"], p["default"]) for p in st["pins"]]
        if got_pins != pins_exp:
            problems.append(f"{slug}: pins {got_pins} ≠ {pins_exp}")
    if sorted(manifest.get("dependencies", [])) != sorted(exp["deps"]):
        problems.append(f"{slug}: deps {manifest.get('dependencies')} ≠ {exp['deps']}")
    for needle in exp["needles"]:
        if needle not in (st.get("notes") or ""):
            problems.append(f"{slug}: notes 缺子串 {needle!r}")
    if exp.get("wordlist") and slug not in libmods:
        problems.append(f"{slug}: wordlist lib_modules 未挂接")
    for name, value in exp["macros"]:
        if not re.search(r"#define\s+%s\s+%s" % (name, value), PIN_CFG):
            problems.append(f"{slug}: pin_config.h 缺 {name}={value}")
    # 代码守卫只查实现 .c（存在性守卫）
    impl = sorted(p for p in (MOD / slug).glob("code/*_stm32.c"))
    for path in impl:
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"),
                              keep_preprocessor=True)
        for pat, label in exp["c_guard"]:
            if label == "存在":
                if not re.search(pat, text):
                    problems.append(f"{slug}/{path.name}: 守卫 {pat!r} 未命中")
            else:
                if re.search(pat, text):
                    problems.append(f"{slug}/{path.name}: 守卫 {pat!r} 残留")
    if exp.get("font"):
        font = MOD / slug / ("code/%s_font.h" % slug)
        if not font.is_file():
            problems.append(f"{slug}: 字体副本缺失")
        else:
            ft = font.read_text(encoding="utf-8", errors="replace")
            for arr in ("ascii_1206", "ascii_1608", "tfont16"):
                if not re.search(r"static const\s+(?:unsigned\s+char|typFNT_GB16)\s+%s" % arr, ft):
                    problems.append(f"{slug}: 字体 {arr} 未 static 化")
            if not re.search(r"#ifndef\s+__ILI\d+_FONT_H", ft):
                problems.append(f"{slug}: 字体头守卫未改名")

def check_header_basename_uniqueness():
    owners: dict[str, set[str]] = {}
    for manifest_dir in MOD.iterdir():
        if not manifest_dir.is_dir():
            continue
        for path in manifest_dir.rglob("*.h"):
            if path.is_file():
                owners.setdefault(path.name.lower(), set()).add(manifest_dir.name)
    for name, slugs in owners.items():
        if len(slugs) > 1:
            problems.append(f"头基名跨模块重复: {name} -> {sorted(slugs)}")

for slug, exp in CHECK.items():
    check_manifest(slug, exp)
check_header_basename_uniqueness()

if problems:
    print("FAIL (%d)" % len(problems))
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("SWEEP OK（%d 模块）" % len(CHECK))
