"""工单 topics-control-2023-2025/03 探测：E/G/I 三题文本结构与 PDF 提取试跑。"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF = (
    REPO_ROOT
    / "library/topics/2018C/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)

RANGES = {"2023E": (183, 185), "2023G": (189, 193), "2023I": (197, 199)}

doc = fitz.open(PDF)
for key, (first, last) in RANGES.items():
    parts = []
    for page_no in range(first, last + 1):
        parts.append(doc[page_no - 1].get_text("text"))
    text = "\n".join(parts)
    print(f"========== {key} 文本（{len(text)} chars）==========")
    for i, ln in enumerate(text.splitlines()[:34], 1):
        print(f"{i:3}: {ln}")
    print()
    # 页眉是否重复（每页第一行）——去页眉后核心
    heads = [doc[p - 1].get_text("text").splitlines()[0] for p in range(first, last + 1)]
    print(f"页眉：{heads}")
    print()
