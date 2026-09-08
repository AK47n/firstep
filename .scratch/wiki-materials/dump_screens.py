# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

p = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"
for f in sorted(p.glob("screen--*.md")):
    t = f.read_text(encoding="utf-8")
    chip = re.search(r"驱动芯片[：:]\s*([^\n]+)", t)
    proto = re.search(r"通信协议[：:]\s*([^\n]+)", t)
    name = re.search(r"^# (.+)$", t, re.M)
    n = name.group(1) if name else "?"
    c = chip.group(1).strip() if chip else "?"
    pr = proto.group(1).strip() if proto else "?"
    print(f"{f.name:<42} | {n:<16} | chip={c:<10} | proto={pr}")
