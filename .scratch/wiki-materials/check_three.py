# -*- coding: utf-8 -*-
"""抽查：三篇新产物关键指标 + 大围栏去重。"""
import collections
import re
from pathlib import Path

base = Path("sources/materials/lckfb-地猛星移植手册")

s = (base / "sensor--sht30-temp-humi-sensor.md").read_text(encoding="utf-8")
fences = re.findall(r"^```c\n([\s\S]*?)\n^```", s, re.M)
big = fences[0]
lines = big.splitlines()
nonempty = [l for l in lines if l.strip()]
dups = [l for l, c in collections.Counter(nonempty).items() if c > 1]
print("fence0 total:", len(lines), "nonempty:", len(nonempty), "dup:", len(dups), dups[:3])
print("IIC_Start 出现:", big.count("IIC_Start"))
print("头部片段:")
print("\n".join(lines[:8]))
print("尾部片段:")
print("\n".join(lines[-8:]))
