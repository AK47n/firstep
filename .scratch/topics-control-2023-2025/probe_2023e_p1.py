"""fitz 块 dump：2023E mini p1（图 1 页）文本层。"""

from __future__ import annotations

from pathlib import Path

import fitz

p = Path("library/topics/2023E/2023E.pdf")
doc = fitz.open(p)
page = doc[0]
print("fitz 提取 p1 GET_TEXT（前 2000 chars）:\n")
print(page.get_text("text")[:2000])
print("\n===== blocks =====")
for block in page.get_text("blocks")[:30]:
    x0, y0, x1, y1, text, *_ = block
    t = text.strip().replace("\n", "⏎")
    if t:
        print(f"  ({x0:.0f},{y0:.0f}) {t[:70]}")
doc.close()
