"""dump 2025H 补全后的题面文本全文。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_2025 import RANGES, build_problem_text, extract_pages

texts = extract_pages()
built = build_problem_text("2025H", texts["2025H"])
print(f"===== 2025H ({len(built)} chars) =====")
print(built)
