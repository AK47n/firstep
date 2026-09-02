"""精确查看 2025E/H topic.md 图注段（repr 含空白）。"""

from __future__ import annotations

from pathlib import Path

for key in ("2025E", "2025H"):
    t = Path(f"library/topics/{key}/topic.md").read_text(encoding="utf-8")
    i = t.find("[图")
    print(f"===== {key} 图注段@ {i}（全文 {len(t)} chars）=====")
    for ln in t[i:].splitlines(keepends=True):
        print(repr(ln))
    print()
