r"""统计 .scratch/*/issues/*.md 的状态分布（按 feature 分组）。

只出计数、不出工单内容；要逐张看未完成工单的标题 / 要做什么 / 被谁阻塞，
用 `.scratch/tracker-audit/list_open_tickets.py`（分工见其 docstring）。

**状态行形态单源 = `.scratch/tracker-audit/ticket_status.py`**（2026-09-09 在途盘点修复）：
旧版正则只认「粗体 + 全角冒号」，把 301 个半角冒号 / 标题式写法的文件误算成
`(none)`，还漏报过开放工单。现在三种形态都认，且非标准值（`已实施` /
`resolved：2026-08-23` 这类历史遗留）单独成桶，不与标准五值混为一谈。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch\tracker-audit\census.py
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ticket_status import STANDARD_STATES, extract_status  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NO_STATUS = "(无状态行)"
NONSTANDARD = "(非标准值)"


def _bucket(state: str | None) -> tuple[str, str | None]:
    """→ (计数桶, 形态变体)。resolved 的变体形态（`resolved：日期` / `resolved。5`）归 resolved。"""
    if state is None:
        return NO_STATUS, None
    if state in STANDARD_STATES:
        return state, None
    if state.startswith("resolved"):
        return "resolved", state
    return NONSTANDARD, None


def main() -> int:
    total = Counter()
    by_feature: dict[str, Counter] = defaultdict(Counter)
    variants: list[tuple[str, str]] = []
    nonstandard: list[tuple[str, str]] = []
    missing: list[str] = []
    for path in sorted(ROOT.glob(".scratch/*/issues/*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        state = extract_status(text)
        bucket, variant = _bucket(state)
        rel = f"{path.parent.parent.name}/{path.name}"
        total[bucket] += 1
        by_feature[path.parent.parent.name][bucket] += 1
        if variant:
            variants.append((variant, rel))
        elif state is None:
            missing.append(rel)
        elif bucket == NONSTANDARD:
            nonstandard.append((state, rel))
    print("总计：", dict(total))
    print()
    print(f"resolved 变体形态 {len(variants)} 张（按 resolved 计数，形态待归一）：")
    for state, rel in variants:
        print(f"    {state:24s} {rel}")
    print()
    print(f"非标准值 {len(nonstandard)} 张（历史遗留，不与标准五值混算）：")
    for state, rel in nonstandard:
        print(f"    {state:24s} {rel}")
    print()
    print(f"无状态行 {len(missing)} 张：")
    for rel in missing:
        print(f"    {rel}")
    print()
    for feature in sorted(by_feature):
        counts = by_feature[feature]
        if any(k != "resolved" for k in counts):
            print(f"{feature:34s} {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
