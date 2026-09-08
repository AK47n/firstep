# -*- coding: utf-8 -*-
"""工单 02 预算实测：真实库 15 条相关候选清单段 wire 大小。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

from contest_generator.reference_library import related_references

root = Path("library/references")
cases = [
    ("典型控制", "设计一个巡线小车：用 ADC 采集灰度传感器电压，UART 串口将数据上传，定时器定时采样，按键切模式，OLED 显示"),
    ("时钟中断", "设计一个时钟系统，实现中断管理"),
]
for label, text in cases:
    hits = related_references(root, topic_text=text, limit=15, platform="mspm0")
    lines = [f"- {e.id}: {e.title} —— {e.description}" for e in hits]
    total = sum(len(l.encode("utf-8")) for l in lines)
    print(f"== {label}: {len(hits)} 条, 清单段 {total} B")
    for e in hits[:4]:
        print(
            f"   id={len(e.id.encode('utf-8'))}B, title={len(e.title)}字, desc={len(e.description)}字"
        )
