"""查 2025H mini 每页字体资源 + 内容流实际使用的 Tf 指令。"""

from __future__ import annotations

from pathlib import Path

import fitz

p = Path(".scratch/topics-control-2023-2025/pdf/2025H.pdf")
doc = fitz.open(p)

for page_no in range(doc.page_count):
    page = doc[page_no]
    fonts = page.get_fonts(full=True)
    print(f"--- p{page_no+1} get_fonts:")
    for f in fonts:
        print("   ", f)
    # 内容流里出现 Tf 的字体名
    xref = page.get_contents()
    names = set()
    for cx in xref:
        raw = doc.xref_stream_raw(cx)
        if raw is None:
            continue
        txt = raw.decode("latin-1", "replace")
        names |= set(__import__("re").findall(r"/(F\d+)\s+[\d.]+\s+Tf", txt))
    print(f"   内容流 Tf 字体: {sorted(names)}")

# 每个 font 对象的子集信息
print("--- 字体对象（含 FontFile 流）:")
for cref in range(1, doc.xref_length()):
    obj = doc.xref_object(cref, compressed=True)
    if "/Type /Font" in obj:
        print(f"xref={cref} {obj[:200]}")
doc.close()
