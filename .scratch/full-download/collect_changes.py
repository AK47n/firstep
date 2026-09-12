"""一次性脚本：统计 v1.0.0（2026-08-30）以来的累计变更，供 VERSIONS.md 归纳。

输出：提交数、按类型前缀分组的主题（feat / fix / perf 优先，chore/docs/test 跳过）。
"""

from __future__ import annotations

import collections
import re
import subprocess

result = subprocess.run(
    ["git", "log", "--no-merges", "--pretty=format:%s", "v1.0.0..HEAD"],
    capture_output=True, text=True, encoding="utf-8",
)
subjects = [s for s in result.stdout.splitlines() if s.strip()]
print("v1.0.0..HEAD 提交数：", len(subjects))

buckets: dict[str, list[str]] = collections.defaultdict(list)
for subject in subjects:
    match = re.match(r"^([a-z]+)(\([^)]*\))?:\s*(.*)$", subject)
    if not match:
        buckets["其他"].append(subject)
        continue
    kind = match.group(1)
    scope = (match.group(2) or "").strip("()")
    text = match.group(3)
    if kind in ("chore", "docs", "test", "lib"):
        buckets["跳过（开发侧）"].append(subject)
        continue
    buckets[kind].append(f"[{scope}] {text}" if scope else text)

for kind, items in buckets.items():
    print(f"\n## {kind}（{len(items)}）")
    for item in items[:40]:
        print("  -", item)
    if len(items) > 40:
        print(f"  …（还有 {len(items) - 40} 条）")
