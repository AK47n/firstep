"""方案：对 2025H mini 做 subset_fonts 子集化后重存，看体积。"""

from __future__ import annotations

from pathlib import Path

import fitz

src = Path(".scratch/topics-control-2023-2025/pdf/2025H.pdf")
out = Path(".scratch/topics-control-2023-2025/pdf/2025H_subset.pdf")
doc = fitz.open(src)
print("before", doc.page_count, "pages")
doc.subset_fonts(verbose=False)
doc.save(out, garbage=4, deflate=True, clean=True)
doc.close()
print(f"subset 后 {out.stat().st_size / 1024:.0f} KB")
