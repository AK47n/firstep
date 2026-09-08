"""临时探针：某份题面下预筛的排序真相（谁进、谁不进、得分几许、卡在哪）。

只读。用法：python .scratch/library-audit/probe_rank.py 2024H stm32
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.budget import MIN_PRESELECT, MODULE_SUMMARY_BYTES, wire_size  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.reference_library import PERIPHERAL_TERMS  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    _activated_terms,
    _fit_summaries_by_wire,
    _preselect_score,
    _wordlist_hit_slugs,
    preselect_module_summaries,
)

topic = sys.argv[1] if len(sys.argv) > 1 else "2024H"
platform = sys.argv[2] if len(sys.argv) > 2 else "stm32"

text = (ROOT / "library" / "topics" / topic / "topic.md").read_text(
    encoding="utf-8", errors="replace"
)
words = wordlist_mod.load_wordlist()
manifests = [m for m in list_modules(ROOT / "library" / "modules") if platform in m.platforms]
summaries = build_manifest_summaries(manifests)

activated = _activated_terms(text, ())
boost = _wordlist_hit_slugs(text, words)
print(f"题面 {topic} / {platform}：{len(summaries)} 条候选")
print(f"激活词（{len(activated)}）：{'、'.join(sorted(activated))}")
print(f"词表挂接加分 slug（{len(boost)}）：{'、'.join(sorted(boost))}")
print()

scored = [(_preselect_score(s, activated, boost), s) for s in summaries]
scored.sort(key=lambda it: (-it[0], it[1].slug))
kept = {s.slug for s in _fit_summaries_by_wire([s for _, s in scored], MODULE_SUMMARY_BYTES)}
res = preselect_module_summaries(summaries, text, words)

from collections import Counter  # noqa: E402

dist = Counter(score for score, _ in scored)
print(f"得分分布：{dict(sorted(dist.items(), reverse=True))}")
print(f"保留 {len(res.summaries)}/{res.total}（truncated={res.truncated}）")
print()

print("=== 排序前 55 条（★ = 进入提示词）===")
for score, s in scored[:55]:
    mark = "★" if s.slug in kept else " "
    print(f"  {mark} {score:2d}  {s.slug:<16} {wire_size(s.to_line()):>5}B  {s.description[:34]}")

print()
print("=== 被截断但题面强相关者 ===")
for probe in ("motor", "pid", "servo", "xunji", "step_motor", "key", "led", "beep", "oled"):
    hit = [(sc, s) for sc, s in scored if s.slug == probe]
    if not hit:
        print(f"  {probe:<12} 不在本平台候选内")
        continue
    sc, s = hit[0]
    rank = [i for i, (_, x) in enumerate(scored) if x.slug == probe][0] + 1
    mark = "★可见" if probe in kept else "不可见"
    print(f"  {probe:<12} 得分 {sc:2d} 排名 {rank:>3}/{len(scored)}  {mark}")

print()
print("=== 截断边界（预算 %d）===" % MODULE_SUMMARY_BYTES)
total = 0
for i, (sc, s) in enumerate(scored):
    w = wire_size(s.to_line())
    if total + w > MODULE_SUMMARY_BYTES:
        print(f"  第 {i + 1} 条 {s.slug} 装不下（已用 {total}B，本行 {w}B）→ 此后全裁")
        break
    total += w + 1
print(f"  MIN_PRESELECT={MIN_PRESELECT}")
