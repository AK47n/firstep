"""临时探针：参考库条目里「候选新词项」的出现面（第 3 批词表扩展的依据）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    PERIPHERAL_TERMS,
    list_references,
)

refs = list_references(ROOT / "library" / "references")
titles = [r.title for r in refs]

CANDIDATES = (
    "spi", "i2c", "gpio", "dma", "rtc", "nvic", "systick", "timer", "pwm", "can",
    "flash", "comp", "cmp", "opamp",
    "显示", "屏幕", "屏", "数码管", "灯", "按键", "触摸", "摇杆", "遥控", "红外",
    "超声波", "测距", "距离", "气压", "海拔", "称重", "重量", "颜色", "气体",
    "烟雾", "温度", "湿度", "光照", "紫外", "粉尘", "雨滴", "土壤", "雷达",
    "指纹", "语音", "姿态", "陀螺仪", "加速度", "磁力", "编码器", "灰度",
    "定位", "存储", "时钟", "滤波", "延时", "计时", "串口", "无线", "蓝牙",
    "无线通信", "通信", "网络", "摄像头", "视觉", "电机", "舵机", "步进",
    "循迹", "巡线", "继电器", "低功耗", "中断", "蜂鸣器", "显示屏",
)

print(f"参考条目 {len(titles)} 条；现有词项 {len(PERIPHERAL_TERMS)} 个\n")
print("候选词项 | 标题命中数 | 已在词表")
for term in CANDIDATES:
    hits = sum(1 for t in titles if term.lower() in t.lower())
    print(f"{term:<10} {hits:>4}  {'是' if term in PERIPHERAL_TERMS else '否'}")
