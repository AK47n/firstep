"""核对 2025E 补录段 + 2025H 网格散行迁移段。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_2025 import RANGES, build_problem_text, extract_pages

texts = extract_pages()
for key in RANGES:
    built = build_problem_text(key, texts[key])
    print(f"===== {key} ({len(built)} chars) =====")
    lines = built.splitlines()
    if key == "2025E":
        start = next(i for i, l in enumerate(lines) if l.startswith("图1 中小车"))
        for l in lines[max(0, start - 6) : start + 6]:
            print(repr(l))
    else:
        start = next(i for i, l in enumerate(lines) if "巡查区域示意图" in l)
        for l in lines[max(0, start - 3) : start + 22]:
            print(repr(l))
    print()
