"""一次性探针：真仓库上跑 excluded_paths，按原因分类看 TOP 条目（不进版本库的临时脚本）。"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.full_pack import excluded_paths  # noqa: E402

repo = Path(__file__).resolve().parents[2]
excluded = excluded_paths(repo)
counter = collections.Counter(excluded.values())
print("total excluded:", len(excluded))
for reason, count in counter.most_common():
    print(f"  {reason}: {count}")
print("--- samples ---")
for reason in counter:
    samples = [p for p, r in excluded.items() if r == reason][:8]
    print(f"[{reason}]")
    for s in samples:
        print("   ", s)
