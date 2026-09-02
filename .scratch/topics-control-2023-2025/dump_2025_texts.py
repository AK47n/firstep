"""dump 2025E/H 补全后的题面文本（视觉核对用）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_2025 import RANGES, build_problem_text, extract_pages

texts = extract_pages()
for key in RANGES:
    built = build_problem_text(key, texts[key])
    print(f"===== {key} ({len(built)} chars) =====")
    print(built)
    print()
    # 找图引用行
    for m in re.finditer(r"图\s*\d+", built):
        ln = built[: m.start()].count("\n")
        print(f"  图引用@{ln}: {built.splitlines()[ln][:60]!r}")
