"""被截断的「相关模块」统计：得分 > 0 却没进提示词的模块。

预筛是排序 + 预算截断：得分高的先进。得分 ≥1 但排名靠后被 40KB 砍掉 =
模块与题面相关、AI 却看不到它。
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.budget import MODULE_SUMMARY_BYTES  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    _activated_terms,
    _preselect_score,
    _wordlist_hit_slugs,
    preselect_module_summaries,
)

MODULES_DIR = ROOT / "library" / "modules"
TOPICS_DIR = ROOT / "library" / "topics"


def main() -> None:
    manifests = list_modules(MODULES_DIR)
    words = wordlist_mod.load_wordlist()
    topics = sorted(
        p for p in TOPICS_DIR.iterdir() if p.is_dir() and (p / "topic.md").is_file()
    )
    for platform in KNOWN_PLATFORMS:
        scoped = [m for m in manifests if platform in m.platforms]
        summaries = build_manifest_summaries(scoped)
        cut_relevant: Counter[str] = Counter()
        for topic in topics:
            text = (topic / "topic.md").read_text(encoding="utf-8", errors="replace")
            activated = _activated_terms(text, ())
            boost = _wordlist_hit_slugs(text, words)
            scores = {
                s.slug: _preselect_score(s, activated, boost) for s in summaries
            }
            result = preselect_module_summaries(summaries, text, words)
            kept = {s.slug for s in result.summaries}
            for slug, score in scores.items():
                if score > 0 and slug not in kept:
                    cut_relevant[slug] += 1
        print(f"=== {platform}（{len(scoped)} 条，{len(topics)} 份题面）===")
        print("  得分>0 却被截断的次数（越多 = 越常漏）:")
        for slug, count in cut_relevant.most_common():
            print(f"    {count:2d}/{len(topics)}  {slug}")
        print()


if __name__ == "__main__":
    main()
