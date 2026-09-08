"""临时探针：工单 05 的新词项是否已在 PERIPHERAL_TERMS 内 + 候选条目标题试算。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    PERIPHERAL_TERMS,
    _entry_score,
    _synonym_group,
    _term_matches_token,
    ReferenceEntry,
)

NEW_TERMS = (
    "气压", "光照", "颜色", "气体", "测距", "称重", "姿态", "指纹", "语音",
    "触摸", "摇杆", "彩屏", "数码管", "灯带", "无线数传", "蓝牙", "lora",
    "温度", "湿度",
)

print("=== 新词项与既有词表的冲突 ===")
for term in NEW_TERMS:
    print(f"  {term:<8} 已在词表={'是' if term in PERIPHERAL_TERMS else '否'}")

# 候选条目标题：标题 = 器件中文类名 + 英文 slug 词（骨架关联只认标题）
CANDIDATE_TITLES = (
    "气体传感器器件手册合集（气体 / mq2 mq135 ags10 sgp30）",
    "温湿度传感器器件手册合集（温湿度 / dht11 sht20 sht30 aht10 ds18b20）",
    "气压传感器器件手册合集（气压 / bmp180 ms5611）",
    "光照与颜色传感器器件手册合集（光照 颜色 / bh1750 photoresistance s12sd tcs34725）",
    "测距传感器器件手册合集（测距 / sr04 us016 ir_distance vl53l0x）",
    "称重传感器器件手册合集（称重 / hx711）",
    "姿态传感器器件手册合集（姿态 / mpu6050 jy61p）",
    "指纹与语音器件手册合集（指纹 语音 / fingerprint jq8900 syn6288）",
    "触摸与摇杆器件手册合集（触摸 摇杆 / ttp224 joystick）",
    "彩屏与数码管器件手册合集（彩屏 数码管 / lcd ili9341 ili9488 st7789 max7219）",
    "灯带与继电器执行器件手册合集（灯带 / ws2812 relay l298n pca9685）",
    "无线通信器件手册合集（无线数传 蓝牙 lora / as32 hc05 nrf24l01 rc522 ec11）",
)


def tokens(title: str) -> list[str]:
    return [t for t in re.split(r"[-_\s()（）]+", title.lower()) if t]


print("\n=== 候选标题对每个新词项的命中 ===")
for title in CANDIDATE_TITLES:
    entry = ReferenceEntry(
        id="candidate",
        title=title,
        type="器件手册",
        description="候选",
        anchor_kind="none",
        anchor_value="",
        files=("x.md",),
    )
    hits = [
        term
        for term in NEW_TERMS
        if any(
            _term_matches_token(synonym, token)
            for synonym in _synonym_group(term)
            for token in tokens(title)
        )
    ]
    print(f"  {title[:34]:<36} 命中 {hits}")
