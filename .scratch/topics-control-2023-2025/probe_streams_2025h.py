"""量 2025H mini PDF 各流的实际字节（内容流/图像流）。"""

from __future__ import annotations

from pathlib import Path

import fitz

p = Path(".scratch/topics-control-2023-2025/pdf/2025H.pdf")
doc = fitz.open(p)
print("xref_length", doc.xref_length(), "file", p.stat().st_size // 1024, "KB")
rows = []
for xref in range(1, doc.xref_length()):
    try:
        raw = doc.xref_stream_raw(xref)
    except Exception:
        raw = None
    if raw is None:
        continue
    try:
        obj = doc.xref_object(xref, compressed=False)
    except Exception:
        obj = ""
    kind = "img" if "/Subtype/Image" in obj else (
        "contents" if "/Length" in obj and obj.count("stream") else "other"
    )
    rows.append((len(raw), xref, kind, obj[:60].replace("\n", " ")))
rows.sort(reverse=True)
for size, xref, kind, desc in rows[:20]:
    print(f"xref={xref} {size//1024}KB kind={kind} {desc}")
print("流总字节", sum(r[0] for r in rows) // 1024, "KB, 流数", len(rows))
doc.close()
