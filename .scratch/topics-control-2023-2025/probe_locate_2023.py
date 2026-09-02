"""工单 topics-control-2023-2025/03 探测：定位 2023 章节内 E/G/I 题边界。

只读探测：打印每页首 2 行 + 页内（X 题）标记命中，供人工核实边界。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF = (
    REPO_ROOT
    / "library/topics/2018C/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)
MARK = re.compile(r"[（(]\s*([A-I])\s*题\s*[)）]|\b([A-I])\s*题\s*[：:]")

doc = fitz.open(PDF)
print(f"总页数：{doc.page_count}")
for page_no in range(171, 206):  # 1-based 页码（工单锚点 2023 章节 = p171-205）
    page = doc[page_no - 1]
    text = page.get_text("text")
    first_lines = [ln.rstrip() for ln in text.splitlines()[:3] if ln.strip()]
    marks = list(MARK.finditer(text))
    mark_hits = [
        (page_no, m.group(0))
        for m in marks
    ]
    print(f"p{page_no}: {' | '.join(first_lines[:2])[:90]}")
    for m in marks:
        line_no = text[: m.start()].count("\n") + 1
        print(f"    MARK {m.group(0)!r} @ line {line_no}")
