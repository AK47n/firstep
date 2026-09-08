# -*- coding: utf-8 -*-
"""打印指定页面的全部代码围栏（用于人工判定完整性）。"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"
FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)

names = sys.argv[1:]
for name in names:
    p = BATCH / name
    print("=" * 30, name, "=" * 30)
    if not p.exists():
        print("  MISSING")
        continue
    t = p.read_text(encoding="utf-8")
    lines = t.splitlines()
    i = 0
    bi = 0
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            j, buf = i + 1, []
            while j < len(lines) and not FENCE_RE.match(lines[j]):
                buf.append(lines[j])
                j += 1
            print(f"----- 代码块 {bi}（{len(buf)} 行）-----")
            print("\n".join(buf))
            i = j + 1
            bi += 1
        else:
            i += 1
    print()
