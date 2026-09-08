"""临时探针：摘要行字节分解（逐条打印，定位算术矛盾）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import wire_size  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402

platform = sys.argv[1] if len(sys.argv) > 1 else "stm32"
summaries = build_manifest_summaries(
    [m for m in list_modules(ROOT / "library" / "modules") if platform in m.platforms]
)

totals = {"slug": 0, "desc": 0, "kit": 0, "dep": 0, "multi": 0, "rest": 0, "line": 0}
for index, s in enumerate(summaries):
    line = s.to_line()
    parts = {
        "slug": wire_size(f"- {s.slug}: "),
        "desc": wire_size(s.description),
        "kit": wire_size("（套件: " + "、".join(s.kits)) if s.kits else 0,
        "dep": wire_size("; 依赖: " + ", ".join(s.dependencies)) if s.dependencies else 0,
        "multi": (
            wire_size(
                f"（多实例：上限 {s.multi_instance.max}，变体 = {s.multi_instance.variant}）"
            )
            if s.multi_instance
            else 0
        ),
    }
    parts["rest"] = wire_size(line) - sum(parts.values())
    for key, value in parts.items():
        totals[key] += value
    totals["line"] += wire_size(line)
    if index < 2:
        print(f"第 {index + 1} 条 {s.slug}: {parts}  行 {wire_size(line)}B")

print()
for key, value in totals.items():
    print(f"  {key:<7}{value:>8}B")
print(f"  段和 {sum(v for k, v in totals.items() if k != 'line')}B vs 行和 {totals['line']}B")
