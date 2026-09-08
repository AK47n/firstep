# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"
f = BATCH / "screen--0-96-color-screen.md"
t = f.read_text(encoding="utf-8")

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
print("fence count:", len(FENCE_RE.findall(t)))

FUNC_RE = re.compile(r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{", re.M)

# 逐行找函数定义（不依赖 fence）
for i, line in enumerate(t.splitlines(), 1):
    m = FUNC_RE.match(line)
    if m:
        print(f"line {i}: FUNC={m.group(1)!r} :: {line[:80]!r}")
