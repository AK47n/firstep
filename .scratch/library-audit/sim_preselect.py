"""真实赛题 × 模块库预筛模拟：AI 到底能看到多少模块、看不到哪些。

只读，不改任何文件。用 library/topics/*/topic.md 的真实题面跑
preselect_module_summaries，统计各平台存活条数与被截断的模块。
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
from contest_generator.selection import preselect_module_summaries  # noqa: E402

MODULES_DIR = ROOT / "library" / "modules"
TOPICS_DIR = ROOT / "library" / "topics"


def main() -> None:
    manifests = list_modules(MODULES_DIR)
    words = wordlist_mod.load_wordlist()
    topics = sorted(
        p for p in TOPICS_DIR.iterdir() if p.is_dir() and (p / "topic.md").is_file()
    )
    never_seen: dict[str, Counter] = {p: Counter() for p in KNOWN_PLATFORMS}
    print(f"题面 {len(topics)} 份；摘要段预算 {MODULE_SUMMARY_BYTES}B\n")
    for platform in KNOWN_PLATFORMS:
        scoped = [m for m in manifests if platform in m.platforms]
        summaries = build_manifest_summaries(scoped)
        print(f"=== {platform}（{len(scoped)} 条）===")
        for topic in topics:
            text = (topic / "topic.md").read_text(encoding="utf-8", errors="replace")
            result = preselect_module_summaries(summaries, text, words)
            kept_slugs = {s.slug for s in result.summaries}
            for s in summaries:
                if s.slug not in kept_slugs:
                    never_seen[platform][s.slug] += 1
            flag = "截断" if result.truncated else "全量"
            print(
                f"  {topic.name}: {len(result.summaries)}/{result.total} 条"
                f"（{flag}）"
            )
        hidden = [
            slug
            for slug, count in never_seen[platform].items()
            if count == len(topics)
        ]
        print(
            f"  → {len(topics)} 份题面全都没进过提示词的模块：{len(hidden)} 个"
        )
        print(f"    {'、'.join(sorted(hidden))}\n")


if __name__ == "__main__":
    main()
