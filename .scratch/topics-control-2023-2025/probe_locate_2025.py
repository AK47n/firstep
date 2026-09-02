"""工单 topics-control-2023-2025/04 探测：定位 2025 章节内 E/H 题边界。"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF = (
    REPO_ROOT
    / "library/topics/2018C/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)
MARK = re.compile(r"[（(]\s*([A-H])\s*题\s*[)）]")

doc = fitz.open(PDF)
print(f"总页数：{doc.page_count}")
for page_no in range(235, 261):
    page = doc[page_no - 1]
    text = page.get_text("text")
    first_lines = [ln.rstrip() for ln in text.splitlines()[:2] if ln.strip()]
    marks = list(MARK.finditer(text))
    header = first_lines[0][:36] if first_lines else ""
    print(f"p{page_no}: {header}")
    for m in marks:
        line_no = text[: m.start()].count("\n") + 1
        print(f"    MARK {m.group(0)!r} @ line {line_no}")
