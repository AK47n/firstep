"""临时探针：为什么感知传感器的 40 条方案全被题面命中（滑窗命中溯源）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402

topic = sys.argv[1] if len(sys.argv) > 1 else "2024H"
text = (ROOT / "library" / "topics" / topic / "topic.md").read_text(
    encoding="utf-8", errors="replace"
).lower()
groups = wordlist_mod.load_wordlist()
row = next(g for g in groups if g.category == "感知传感器")

# 复刻 _term_matches_topic 的中文滑窗：找出每个方案是被哪个 2-4 字片段命中的
hits: dict[str, set[str]] = {}
for sol in row.solutions:
    name = sol.name.strip().lower()
    if name in text:
        hits.setdefault("整名子串", set()).add(sol.name)
        continue
    for seg in re.findall(r"[\u4e00-\u9fff]{2,}", name):
        for width in (2, 3, 4):
            for index in range(max(0, len(seg) - width + 1)):
                frag = seg[index:index + width]
                if frag in text:
                    hits.setdefault(frag, set()).add(sol.name)

print(f"题面 {topic}：感知传感器行 {len(row.solutions)} 条方案")
print(f"命中片段数 {len(hits)}；命中方案数 "
      f"{len({n for names in hits.values() for n in names})}\n")
for frag, names in sorted(hits.items(), key=lambda kv: -len(kv[1]))[:12]:
    print(f"  片段「{frag}」（{len(frag)} 字）→ 命中 {len(names)} 条方案")
    for n in sorted(names)[:4]:
        print(f"      {n}")
    if len(names) > 4:
        print(f"      … 另 {len(names) - 4} 条")
print()
for probe in ("传感器", "检测", "测量", "控制", "模块", "系统", "精度", "数据"):
    print(f"题面含「{probe}」：{probe in text}（出现 {text.count(probe)} 次）")
