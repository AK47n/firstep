# -*- coding: utf-8 -*-
"""收官盘点：wiki 70 页 → 库内 80 模块覆盖对照，列未覆盖页。"""
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path("sources/materials/lckfb-地猛星移植手册")
LIB = Path("library/modules")

lib_slugs = sorted(d.name for d in LIB.iterdir() if d.is_dir())
files = sorted(f for f in BATCH.glob("*.md") if f.name not in ("模块索引.md", "网盘索引.md"))

# 关键词 → 库内 slug（人工映射，覆盖既有模块的语义等价件）
COVER = {
    "16-ch-servo": "pca9685", "at24c02": "at24c02", "jq8900": "jq8900",
    "l298n": "l298n", "relay": "relay", "sg90": "servo", "syn6288": "syn6288",
    "tb6612": "motor", "two-axis": "joystick", "ws2812": "ws2812",
    "Infrared-decoding": "ir_remote_tx", "as32": "as32", "hc05": "hc05",
    "infrared-receiving": "ir_remote", "nrf24l01": "nrf24l01",
    "open-mv4": "open_mv4", "rc522": "rc522",
    "0-91": "oled", "0-96-color": "lcd", "0-96-iic": "oled",
    "0-96-single-spi": "oled",  # oled SPI 变体
    "1-28-round": "lcd", "1-3-color": "lcd", "1-3-single-oled": "oled",
    "1-47": "lcd", "1-69": "lcd", "1-8-touch": "lcd", "8-bit-led-tube": "max7219",
    "max7219": "max7219", "Infrared-distance": "ir_distance",
    "Infrared-tracking": "xunji", "ads1115": "ads1115", "ags10": "ags10",
    "aht10": "aht10", "bh1750": "bh1750", "bmp180": "bmp180", "dht11": "dht11",
    "ds18b20": "ds18b20", "fingerprint": "fingerprint", "flame": "flame",
    "gp2y1014": "gp2y1014au", "grayscale": "huidu", "human-body": "human_ir",
    "hx711": "hx711", "jy61p": "jy61p", "microwave": "microwave_radar",
    "mlx90614": "mlx90614", "mpu6050": "ml_mpu6050", "mq-135": "mq135",
    "mq-2": "mq2", "mq-3": "mq3", "mq-4": "mq4", "mq-5": "mq5", "mq-6": "mq6",
    "mq-7": "mq7", "mq-8": "mq8", "mq-9": "mq9", "ms1100": "ms1100",
    "ms5611": "ms5611", "photoresistance": "photoresistance", "rain": "rain",
    "s12sd": "s12sd", "sgp30": "sgp30", "sht20": "sht20", "sht30": "sht30",
    "soil": "soil", "sr04": "sr04", "tcs34725": "tcs34725", "ttp224": "ttp224",
    "us-016": "us016",
}

uncovered = []
for f in files:
    slug = f.stem.split("--", 1)[-1]
    hit = None
    for key, target in COVER.items():
        if key.lower() in slug.lower():
            if target is None:
                hit = "无库内条目（低价值/砍件候选）"
            elif target in lib_slugs:
                hit = f"已覆盖({target})"
            else:
                hit = f"目标 {target} 缺失!"
            break
    if hit is None or "缺失" in hit or "无库内条目" in hit:
        uncovered.append((slug, hit))

print("== 未覆盖页面 ==")
for slug, note in uncovered:
    print(f"  - {slug}  →  {note}")
print()
print(f"覆盖检查完成：70 页中未覆盖 {len(uncovered)} 页；库内模块 {len(lib_slugs)} 个")
