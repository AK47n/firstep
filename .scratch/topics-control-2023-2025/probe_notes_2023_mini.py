"""探：2023E/G/I 小题 PDF 上文字标注提取是否可行（03 时曾失败）。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from contest_generator.extraction import pdf_figure_annotations

for key in ("2023E", "2023G", "2023I"):
    p = REPO_ROOT / "library" / "topics" / key / f"{key}.pdf"
    notes = pdf_figure_annotations(p)
    print(f"===== {key} （{p.stat().st_size//1024}KB）=====")
    print(repr(notes[:400]) if notes else "(空)")
    print()
