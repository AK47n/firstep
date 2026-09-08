"""临时探针：常备名额保底方案（配额）对可见性的影响（只读）。

在「得分降序 + 预算截断」之上加一层：先按得分取足配额，再从常备清单
（核心执行/交互件）补进剩余名额——保证小车类赛题的关键模块一定可见。

用法：python .scratch/library-audit/probe_sim_quota.py 2024H stm32
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.budget import MODULE_SUMMARY_BYTES, wire_size  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    _activated_terms,
    _preselect_score,
    _wordlist_hit_slugs,
)

# 常备清单（核心执行件 + 基础交互件：不依赖题面词面，任何题都可能用到）
STAPLE = (
    "motor", "pid", "servo", "step_motor", "xunji", "key", "led", "led_beep",
    "beep", "oled", "lcd", "delay", "config", "adc", "uart", "debug_uart",
)

PROBES = ("motor", "pid", "servo", "led", "key", "beep", "oled", "delay", "config")

topic = sys.argv[1] if len(sys.argv) > 1 else "2024H"
platform = sys.argv[2] if len(sys.argv) > 2 else "stm32"
text = (ROOT / "library" / "topics" / topic / "topic.md").read_text(
    encoding="utf-8", errors="replace"
)
words = wordlist_mod.load_wordlist()
summaries = build_manifest_summaries(
    [m for m in list_modules(ROOT / "library" / "modules") if platform in m.platforms]
)

activated = _activated_terms(text, ())
boost = _wordlist_hit_slugs(text, words)
scored = [(_preselect_score(s, activated, boost), s) for s in summaries]
scored.sort(key=lambda it: (-it[0], it[1].slug))
by_slug = {s.slug: (sc, s) for sc, s in scored}


def fit(rows: list) -> list:
    kept, total = [], 0
    for sc, s in rows:
        w = wire_size(s.to_line())
        if total + w > MODULE_SUMMARY_BYTES and kept:
            break
        kept.append((sc, s))
        total += w + 1
    return kept


def quota_fit(rows: list, staple_slugs: tuple[str, ...], quota: int) -> list:
    """得分序装填 + 常备保底：常备里未进榜者按清单序插入剩余名额。"""
    kept = fit(rows)
    kept_slugs = {s.slug for _, s in kept}
    missing = [sl for sl in staple_slugs if sl in by_slug and sl not in kept_slugs]
    if not missing:
        return kept
    total = sum(wire_size(s.to_line()) + 1 for _, s in kept)
    for slug in missing[:quota]:
        sc, s = by_slug[slug]
        w = wire_size(s.to_line())
        if total + w > MODULE_SUMMARY_BYTES:
            continue
        kept.append((sc, s))
        total += w + 1
    return kept


for label, rows in (
    ("现状（纯得分序 + 截断）", fit(scored)),
    ("常备保底 6 名额", quota_fit(scored, STAPLE, 6)),
    ("常备保底 10 名额", quota_fit(scored, STAPLE, 10)),
):
    kept_slugs = {s.slug for _, s in rows}
    total_wire = sum(wire_size(s.to_line()) + 1 for _, s in rows)
    marks = " ".join(f"{p}{'✓' if p in kept_slugs else '✗'}" for p in PROBES)
    print(f"{label:<24} 可见 {len(rows)}/{len(summaries)}  {total_wire}B  {marks}")
