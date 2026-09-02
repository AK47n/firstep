"""探：2023E/G/I mini PDF 经 garbage+deflate+subset_fonts 重存后，
pdf_figure_annotations 是否可提取（2025 mini 成功、2023 mini 空的原因假设
= 内容流未规范化）。只写临时文件，不动库。"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from contest_generator.extraction import pdf_figure_annotations

tmp = REPO_ROOT / ".scratch/topics-control-2023-2025/pdf/recompress_tmp"
tmp.mkdir(parents=True, exist_ok=True)

for key in ("2023E", "2023G", "2023I"):
    src = REPO_ROOT / "library" / "topics" / key / f"{key}.pdf"
    out = tmp / f"{key}.pdf"
    doc = fitz.open(src)
    doc.subset_fonts(verbose=False)
    doc.save(out, garbage=4, deflate=True, clean=True)
    doc.close()
    notes = pdf_figure_annotations(out)
    print(f"===== {key} 重存后 {out.stat().st_size//1024}KB =====")
    print(repr(notes[:500]) if notes else "(空)")
    print()
