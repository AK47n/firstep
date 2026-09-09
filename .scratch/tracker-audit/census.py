"""统计 .scratch/*/issues/*.md 的状态分布（按 feature 分组）。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch/tracker-audit/census.py
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    total = Counter()
    by_feature: dict[str, Counter] = defaultdict(Counter)
    for path in sorted(ROOT.glob(".scratch/*/issues/*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"\*\*(?:Status|状态)：\*\*\s*([^\s（(]+)", text)
        state = m.group(1) if m else "(none)"
        total[state] += 1
        by_feature[path.parent.parent.name][state] += 1
    print("总计：", dict(total))
    print()
    for feature in sorted(by_feature):
        counts = by_feature[feature]
        if any(k != "resolved" for k in counts):
            print(f"{feature:34s} {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
