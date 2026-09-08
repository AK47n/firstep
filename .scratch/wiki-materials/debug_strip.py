# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"
FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)


def blocks(md: str) -> list[str]:
    out, i, lines = [], 0, md.splitlines()
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
    return out


t = (BATCH / "sensor--ags10-harmful-gas-sensor.md").read_text(encoding="utf-8")
b0 = blocks(t)[0]

raw = b0.splitlines()
# 找 Calc_CRC8 在原始 block 中的行号
for k, ln in enumerate(raw):
    if "Calc_CRC8" in ln and "uint8_t" in ln:
        print("raw index", k, repr(ln))
        print("raw neighbors:")
        for j in range(max(0, k - 3), min(len(raw), k + 8)):
            print("   ", j, repr(raw[j][:70]))
        break

print()
stripped = re.sub(r"/\*[\s\S]*?\*/", "", b0)
stripped = re.sub(r"//[^\n]*", "", stripped)
stripped = re.sub(r"^\s*#\s*(?!include|define|ifndef|ifdef|endif|elif|\w)", "", stripped)
sl = stripped.splitlines()
for k, ln in enumerate(sl):
    if "Calc" in ln:
        print("stripped index", k, repr(ln))
