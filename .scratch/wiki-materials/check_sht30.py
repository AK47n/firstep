# -*- coding: utf-8 -*-
"""检查 sht30 泄漏区域修复情况。"""
import re
from pathlib import Path

s = Path("sources/materials/lckfb-地猛星移植手册/sensor--sht30-temp-humi-sensor.md").read_text(encoding="utf-8")

for pat in ("在文件 bsp_sht30.h", "上电效果", "然后点击编译"):
    for line in s.splitlines():
        if pat in line:
            print(repr(line[:110]))

print("--- 数字序列泄漏 ---")
print(re.findall(r"^\d{1,3}(?: \d{1,3}){2,}", s, re.M)[:3])

fences = re.findall(r"^```c\n([\s\S]*?)\n^```", s, re.M)
print("--- 围栏行数 ---", [len(f.splitlines()) for f in fences])
print("--- 末段 ---")
print(s[-260:])
