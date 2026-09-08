# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent / ".."))
BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"
FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
FUNC_DEF_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)


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
blks = blocks(t)
print("blocks:", len(blks), [len(b.splitlines()) for b in blks])
defs = set()
for bi, b in enumerate(blks):
    d = {m.group(1) for m in FUNC_DEF_RE.finditer(b)}
    defs |= d
    print(f"block {bi} defs({len(d)}):", sorted(d))
print("Calc_CRC8 in defs:", "Calc_CRC8" in defs)
