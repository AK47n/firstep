"""逐页 dump 2025E 文本块（含坐标），核实图 1 标题行/标注是否文本层。"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

src = Path(".scratch/topics-control-2023-2025/pdf/2025E.pdf")
doc = fitz.open(src)
for page_no in range(doc.page_count):
    page = doc[page_no]
    print(f"===== p{page_no+1} =====")
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text, *_ = block
        t = text.strip().replace("\n", "⏎")
        if t:
            print(f"  ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f}) {t[:80]}")
doc.close()
