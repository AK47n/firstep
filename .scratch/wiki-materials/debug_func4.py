# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

f = BATCH / "sensor--aht10-temp-humi-sensor.md"
t = f.read_text(encoding="utf-8")
lines = t.splitlines()

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
out = []
i = 0
while i < len(lines):
    if FENCE_RE.match(lines[i]):
        j, buf = i + 1, []
        while j < len(lines) and not FENCE_RE.match(lines[j]):
            buf.append(lines[j])
            j += 1
        out.append("\n".join(buf))
        i = j + 1
    else:
        i += 1

b = out[1]
bl = b.splitlines()
print("block1 lines:", len(bl))
for k in range(0, min(12, len(bl))):
    print(repr(bl[k][:90]))

FUNC_HDR_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
# 找 'void' 开头的行
for k, ln in enumerate(bl):
    if "void" in ln and "(" in ln:
        print("LINE", k, repr(ln[:80]))
        m = FUNC_HDR_RE.match(ln)
        print("  match:", m.group(1) if m else None)
        break
