# -*- coding: utf-8 -*-
"""聚焦：ags10 页 Calc_CRC8 为什么没进 defs；nrf24l01 L01_WriteSingleReg 页内是否有定义。"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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


for fname, want in (("sensor--ags10-harmful-gas-sensor.md", "Calc_CRC8"),
                    ("rf--nrf24l01-2-4-g-control-module.md", "L01_WriteSingleReg"),
                    ("control--syn6288-speech-synthesis-broadcast-module.md", "Get_SYN6288RX_BUFF")):
    t = (BATCH / fname).read_text(encoding="utf-8")
    blks = blocks(t)
    print("=====", fname, "=====")
    for bi, b in enumerate(blks):
        hits = FUNC_DEF_RE.findall(b)
        if want in b:
            print(f"  block {bi}: 含 {want} 的行数 {b.count(want)}，该块函数定义: {hits}")
            for line in b.splitlines():
                if want in line:
                    print(f"      >> {line}")
