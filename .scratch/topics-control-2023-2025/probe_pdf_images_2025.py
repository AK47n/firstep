"""工单 04 探测：2025 小题 PDF 图片构成（超 1MB 原因）。"""

from __future__ import annotations

from pathlib import Path

import fitz

for key in ("2025E", "2025H"):
    p = Path(f".scratch/topics-control-2023-2025/pdf/{key}.pdf")
    doc = fitz.open(p)
    print(key, "页数", doc.page_count)
    for page_no in range(doc.page_count):
        page = doc[page_no]
        imgs = page.get_images(full=True)
        for img in imgs:
            xref = img[0]
            info = doc.extract_image(xref)
            print(
                f"  p{page_no+1} xref={xref} {info['width']}x{info['height']} "
                f"ext={info['ext']} size={len(info['image'])//1024}KB"
            )
    doc.close()
