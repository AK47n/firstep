"""验证 subset 后文本层完整：对比原 mini 与 subset 的提取文本。"""

from __future__ import annotations

from pathlib import Path

import fitz

a = Path(".scratch/topics-control-2023-2025/pdf/2025H.pdf")
b = Path(".scratch/topics-control-2023-2025/pdf/2025H_subset.pdf")
da, db = fitz.open(a), fitz.open(b)
ta = "\n".join(da[i].get_text("text") for i in range(da.page_count))
tb = "\n".join(db[i].get_text("text") for i in range(db.page_count))
print("原文本 chars", len(ta), " subset 文本 chars", len(tb))
print("完全一致:", ta == tb)
if ta != tb:
    import difflib

    for line in difflib.unified_diff(
        ta.splitlines(), tb.splitlines(), lineterm="", n=0
    ):
        print(line[:100])
da.close()
db.close()
