"""探查 2025H mini PDF 的对象构成，找体积大头。"""

from __future__ import annotations

from pathlib import Path

import fitz

p = Path(".scratch/topics-control-2023-2025/pdf/2025H.pdf")
doc = fitz.open(p)
total = {}
for xref in range(1, doc.xref_length()):
    try:
        obj = doc.xref_object(xref, compressed=True)
    except Exception:
        continue
    total[xref] = len(obj)
# 按大小排序取前 30
for xref, size in sorted(total.items(), key=lambda kv: -kv[1])[:30]:
    obj = doc.xref_object(xref, compressed=True)
    kind = obj[:80].replace("\n", " ")
    print(f"xref={xref} {size//1024}KB {kind}")
print("总对象数", doc.xref_length(), " 非空总字节",
      sum(total.values()) // 1024, "KB")
doc.close()
