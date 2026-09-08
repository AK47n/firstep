# -*- coding: utf-8 -*-
import re

FUNC_HDR_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
tests = [
    "void IIC_Start(void)",
    "void IIC_Start(void)\n{",
    "void IIC_Start(void) {",
    "void IIC_Start(void)\r",
    "\tvoid IIC_Start(void)\n{",
]
for t in tests:
    m = FUNC_HDR_RE.match(t)
    print(repr(t), "->", m.group(1) if m else None)

# 从真实文件读取一行试试
from pathlib import Path
batch = Path(r"C:\Users\luoji\Desktop\firstep\sources\materials\lckfb-地猛星移植手册")
t = (batch / "sensor--aht10-temp-humi-sensor.md").read_text(encoding="utf-8")
for i, line in enumerate(t.splitlines(), 1):
    if "void IIC_Start" in line:
        print("FILE LINE", i, [hex(ord(c)) for c in line[:30]])
        m = FUNC_HDR_RE.match(line)
        print("  fulltext-findall:", FUNC_HDR_RE.findall(t)[:10])
        print("  match:", m.group(1) if m else None)
        break
