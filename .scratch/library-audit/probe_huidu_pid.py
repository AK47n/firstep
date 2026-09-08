"""临时探针：huidu / pid / xunji 映射候选对参考条目的命中试算（工单 03 收尾）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    _entry_score,
    _synonym_group,
    _text_has_term,
    list_references,
)

CANDIDATES = {
    "huidu": ("灰度",),
    "pid": ("pid", "巡线"),
    "xunji": ("循迹", "巡线"),
}

refs = list_references(ROOT / "library" / "references")
titles = [(r.title, r.platform) for r in refs]

for slug, terms in CANDIDATES.items():
    print(f"=== {slug} 候选词项 {terms}")
    for term in terms:
        hits = [
            (title, platform)
            for title, platform in titles
            if _text_has_term(title.lower(), term)
        ]
        print(f"  词项 {term!r} → {len(hits)} 命中：{hits[:3]}")
    activated = frozenset(term for term in terms)
    scored = sorted(
        ((_entry_score(r, activated), r) for r in refs), key=lambda item: -item[0]
    )
    print(f"  关联得分 >0 的条目：{[(s, r.title) for s, r in scored if s > 0][:5]}")
