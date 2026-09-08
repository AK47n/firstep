"""临时探针：70 个未映射模块的分类底稿（简介 + 平台 + 是否内部件）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.library import list_modules  # noqa: E402
from contest_generator.reference_library import MODULE_PERIPHERAL_TERMS  # noqa: E402

UNMAPPED = (
    "ads1115 ags10 aht10 as32 at24c02 bh1750 bmp180 coord_detect dht11 ds18b20 "
    "ec01g ec11 esp01s fingerprint flame gp2y1014au hc05 human_ir hx711 ili9341 "
    "ili9488 ir_beam ir_distance ir_remote ir_remote_tx joystick jq8900 jy61p "
    "key_matrix l298n lcd max7219 microwave_radar ml_mpu6050 mlx90614 mq135 mq2 "
    "mq3 mq4 mq5 mq6 mq7 mq8 mq9 ms1100 ms5611 neo_6m nrf24l01 open_mv4 pca9685 "
    "photoresistance pid rain rc522 relay s12sd sgp30 sht20 sht30 soil sr04 "
    "st7789_para syn6288 tcs34725 tp_xpt2046 ttp224 us016 vl53l0x ws2812 zigbee_link"
).split()

by = {m.slug: m for m in list_modules(ROOT / "library" / "modules")}
for slug in UNMAPPED:
    manifest = by.get(slug)
    if manifest is None:
        print(f"{slug:<16} 不在库内")
        continue
    platforms = ",".join(sorted(manifest.platforms))
    mapped = slug in MODULE_PERIPHERAL_TERMS
    print(f"{slug:<16} [{platforms:<11}] mapped={mapped} {manifest.description[:70]}")
