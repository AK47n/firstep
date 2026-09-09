"""统计 .scratch/*/issues/*.md 的状态分布（按 feature 分组）。

只出计数、不出工单内容；要逐张看未完成工单的标题 / 要做什么 / 被谁阻塞，
用 `.scratch/library-audit/list_open_tickets.py`（分工见其 docstring）。

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
