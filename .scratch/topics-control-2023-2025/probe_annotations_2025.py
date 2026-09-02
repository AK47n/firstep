"""扫 2025E p1 全文搜索标注文本（50cm 是否存在）+ 2025H 四页块 dump。"""

from __future__ import annotations

from pathlib import Path

import fitz

for key in ("2025E", "2025H"):
    doc = fitz.open(Path(f".scratch/topics-control-2023-2025/pdf/{key}.pdf"))
    print(f"########## {key} ##########")
    for page_no in range(doc.page_count):
        page = doc[page_no]
        hits = []
        for needle in ("50cm", "100cm", "A4", "感光", "场景图", "图1", "图2", "图3"):
            for r in page.search_for(needle):
                hits.append((needle, tuple(round(v) for v in r)))
        print(f"--- p{page_no+1} 搜索命中:")
        for h in hits:
            print("   ", h)
    doc.close()
