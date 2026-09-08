"""临时探针：每个模块映射词项在参考库标题里的实际命中（骨架关联的真实有效性）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    MODULE_PERIPHERAL_TERMS,
    PERIPHERAL_TERMS,
    _text_has_term,
    list_references,
)

refs = list_references(ROOT / "library" / "references")
print(f"参考条目 {len(refs)} 条\n")

dead_terms = []
for term in PERIPHERAL_TERMS:
    hits = [r.title for r in refs if _text_has_term(r.title.lower(), term)]
    if not hits:
        dead_terms.append(term)

print(f"词表项 {len(PERIPHERAL_TERMS)} 个，其中在参考库标题里 0 命中的 {len(dead_terms)} 个：")
print("  " + "、".join(dead_terms))
print()
print("现有 18 个模块映射的命中情况：")
for slug, terms in sorted(MODULE_PERIPHERAL_TERMS.items()):
    counts = []
    for term in terms:
        hits = [r.title for r in refs if _text_has_term(r.title.lower(), term)]
        counts.append(f"{term}→{len(hits)}")
    print(f"  {slug:<16} {'  '.join(counts)}")
