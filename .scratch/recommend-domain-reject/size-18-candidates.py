# -*- coding: utf-8 -*-
"""工单 real-acceptance/08：候选裸名的**词表段增量**逐条现算（只读）。

口径：models 加一条名会让词表段涨两处（该行 models 列表 + format_wordlist_prompt
的「选购方案」段重复），所以只能逐条试加、按词表段实发增量记账——按 JSON 或
wire_size 估都会偏差数倍。

用法：仓库根 `python .scratch/recommend-domain-reject/size-18-candidates.py`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import wire_size  # noqa: E402
from contest_generator.llm import _wordlist_prompt_segment  # noqa: E402
from contest_generator.wordlist import (  # noqa: E402
    HardwareWordGroup,
    SolutionOption,
    load_wordlist,
)

CANDIDATES = (
    "MPU6050 六轴姿态模块", "DHT11 温湿度传感器", "SHT30 温湿度传感器",
    "AHT10 温湿度传感器", "SHT20 温湿度传感器", "DS18B20 单总线温度传感器",
    "JY61P 六轴姿态传感器", "独立轻触按键模块", "WS2812 幻彩灯带",
    "红外对射传感器", "MQ-2 烟雾/可燃气体传感器", "MQ-135 空气质量传感器",
    "1 路 5V 继电器模块", "L298N 大电流驱动板", "PCA9685 16 路舵机板",
    "脉冲式步进电机 + 驱动板", "RC522 射频 IC 卡读卡器", "NRF24L01 2.4G 点对点",
    "HC05 蓝牙串口", "ESP8266 WiFi 模块", "Zigbee 模块", "LoRa 数传",
    "EC-01G NB-IoT+GPS 模块", "蓝牙遥控", "NRF24L01 2.4G 遥控", "双轴摇杆按键",
    "红外遥控接收头 VS1838B", "0.96 寸 OLED 单色屏", "MAX7219 数码管/点阵",
    "IPS 彩屏", "AT24C02 EEPROM", "GPS/北斗", "UWB 定位", "蓝牙信标定位",
    "OpenMV Cam H7", "有源蜂鸣器模块", "JQ8900 语音播报模块",
    "SYN6288 语音合成模块", "TTP224 4 路电容触摸按键", "BH1750 光照度传感器",
    "GP2Y1014AU 粉尘传感器", "S12SD 紫外线传感器", "TCS34725 颜色识别传感器",
    "MLX90614 非接触红外测温", "BMP180 气压/海拔传感器", "MS5611 高精度气压传感器",
    "磁力计指南针",
)


def groups_of(data):
    return tuple(
        HardwareWordGroup(
            category=item["category"],
            models=tuple(item.get("models", [])),
            solutions=tuple(
                SolutionOption(name=o["name"]) for o in item.get("solutions", []) or []
            ),
        )
        for item in data
    )


def seg_wire(data) -> int:
    return wire_size(_wordlist_prompt_segment(groups_of(data)))


def main() -> int:
    path = ROOT / "src" / "contest_generator" / "wordlist.json"
    live = json.loads(path.read_bytes().decode("utf-8"))
    base = seg_wire(live)
    old = load_wordlist(
        ROOT / ".scratch" / "recommend-domain-reject" / "wordlist-before-18.json",
        lib_slugs=None,
    )
    print(f"HEAD 词表段实发 = {wire_size(_wordlist_prompt_segment(old))}B")
    print(f"现状词表段实发 = {base}B\n")
    print("候选（试加一条后的段增量）：")
    for name in CANDIDATES:
        trial = json.loads(json.dumps(live, ensure_ascii=False))
        placed = False
        for item in trial:
            for option in item.get("solutions", []) or []:
                bare = option["name"].split("（")[0].strip()
                if bare == name or option["name"] == name:
                    item.setdefault("models", []).append(name)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            print(f"  {'?':>5}  {name}（无归属行——不在方案裸名集内）")
            continue
        print(f"  {seg_wire(trial) - base:>4}B  {name}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
