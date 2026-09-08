# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
FUNC_HDR_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)

f = BATCH / "sensor--aht10-temp-humi-sensor.md"
t = f.read_text(encoding="utf-8")
lines = t.splitlines()

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

print("num blocks:", len(out))
for bi, b in enumerate(out):
    hits = []
    for ln in b.splitlines():
        m = FUNC_HDR_RE.match(ln)
        if m:
            hits.append((m.group(1), ln[:60]))
    print(f"block {bi}: {len(b.splitlines())} lines, funcs: {[h[0] for h in hits]}")
