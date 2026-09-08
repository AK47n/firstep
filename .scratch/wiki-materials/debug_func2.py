# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

FUNC_RE = re.compile(r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{", re.M)
MAIN_RE = re.compile(r"\bmain\s*\(")

for name in ("screen--1-3-color-screen.md", "sensor--aht10-temp-humi-sensor.md", "sensor--bmp180-pressure-sensor.md"):
    f = BATCH / name
    t = f.read_text(encoding="utf-8")
    print(f"===== {name}  ({len(t.splitlines())} lines) =====")
    for i, line in enumerate(t.splitlines(), 1):
        if "LCD_GPIO_Init" in line or "aht10" in line.lower() and "(" in line or "main(" in line.replace(" ", ""):
            print(f"  line {i}: {line[:100]!r}")
    m = FUNC_RE.findall(t)
    print("  FUNC_RE hits:", m[:40])
