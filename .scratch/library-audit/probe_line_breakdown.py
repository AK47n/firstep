"""临时探针：摘要行字节构成分解（只读）——哪一段在吃预算。"""

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

base = kit = dep = multi = artifact = group = 0
kit_rows = 0
worst: list[tuple[int, str]] = []
for s in summaries:
    line = s.to_line()
    b = wire_size(f"- {s.slug}: ")
    d = wire_size(s.description)
    k = wire_size("（套件: " + "、".join(s.kits)) if s.kits else 0
    p = wire_size("; 依赖: " + ", ".join(s.dependencies)) if s.dependencies else 0
    m = wire_size(f"（多实例：上限 {s.multi_instance.max}，变体 = {s.multi_instance.variant}）") if s.multi_instance else 0
    a = wire_size(line) - b - d - k - p - m
    base += b
    kit += k
    dep += p
    multi += m
    artifact += max(a, 0)
    if s.kits:
        kit_rows += 1
    worst.append((wire_size(line), s.slug))

total = base + kit + dep + multi + artifact
print(f"=== {platform}（{len(summaries)} 条）合计 {total}B ===")
for label, value in (
    ("slug 前缀", base),
    ("description", None),
    ("套件段", kit),
    ("依赖段", dep),
    ("多实例段", multi),
    ("其余（副产物/互斥组）", artifact),
):
    if value is None:
        value = sum(wire_size(s.description) for s in summaries)
    print(f"  {label:<22}{value:>7}B  {value * 100 // total:>3}%")
print(f"  有 kit 的行：{kit_rows}/{len(summaries)}")
print("\n最长的 8 行：")
for size, slug in sorted(worst, reverse=True)[:8]:
    print(f"  {size:>5}B  {slug}")
