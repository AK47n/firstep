"""临时探针：词项 → 参考条目标题命中面（骨架映射扩展的可落地范围）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    PERIPHERAL_TERMS,
    _text_has_term,
    list_references,
)

refs = list_references(ROOT / "library" / "references")
titles = [(r.title, r.platform) for r in refs]

print(f"参考条目 {len(refs)} 条；词表 {len(PERIPHERAL_TERMS)} 项\n")
print("=== 有命中的词项 ===")
for term in PERIPHERAL_TERMS:
    hits = [t for t, _ in titles if _text_has_term(t.lower(), term)]
    if hits:
        print(f"{term:<10} {len(hits):>3}  " + "；".join(hits[:3])[:100])

print("\n=== 0 命中的词项（骨架关联写进去也无效）===")
dead = [
    term
    for term in PERIPHERAL_TERMS
    if not any(_text_has_term(t.lower(), term) for t, _ in titles)
]
print("、".join(dead))
