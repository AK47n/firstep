"""工单 topics-control-2023-2025/04 探测：E/H 两题文本结构。"""

from __future__ import annotations

from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF = (
    REPO_ROOT
    / "library/topics/2018C/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)
RANGES = {"2025E": (249, 252), "2025H": (258, 261)}

doc = fitz.open(PDF)
for key, (first, last) in RANGES.items():
    parts = []
    for page_no in range(first, last + 1):
        parts.append(doc[page_no - 1].get_text("text"))
    text = "\n".join(parts)
    print(f"========== {key} 文本（{len(text)} chars）==========")
    for i, ln in enumerate(text.splitlines()[:30], 1):
        print(f"{i:3}: {ln}")
    heads = [doc[p - 1].get_text("text").splitlines()[0] for p in range(first, last + 1)]
    print(f"页眉：{heads}")
    print()
