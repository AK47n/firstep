"""模块可达性分析：哪些模块在推荐链路上「几乎不可能被 AI 看见」。

判据（预筛打分面 _preselect_score 的两条得分路径）：
  A. 题面激活的 PERIPHERAL_TERMS 命中「slug + description + kits」；
  B. 题面命中词表行/方案 → lib_modules 挂接加分。
A 与 B 都不成立的模块 = 只有在题面恰好命中其词时才有分；否则得分 0，
排在所有有分模块之后，被 40KB 预算截断掉。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    PERIPHERAL_TERMS,
    _synonym_group,
    _text_has_term,
    _term_matches_token,
)
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402

MODULES_DIR = ROOT / "library" / "modules"


def main() -> None:
    manifests = list_modules(MODULES_DIR)
    words = wordlist_mod.load_wordlist()
    linked: set[str] = set()
    for group in words:
        for solution in group.solutions:
            linked.update(solution.lib_modules)
    print(f"词表挂接模块 {len(linked)} 个；PERIPHERAL_TERMS {len(PERIPHERAL_TERMS)} 词\n")

    for platform in KNOWN_PLATFORMS:
        print(f"=== {platform} ===")
        scoped = [m for m in manifests if platform in m.platforms]
        for summary in build_manifest_summaries(scoped):
            match_text = " ".join((summary.description, *summary.kits)).lower()
            term_hits = [
                term
                for term in PERIPHERAL_TERMS
                if any(_text_has_term(match_text, syn) for syn in _synonym_group(term))
                or any(
                    _term_matches_token(syn, summary.slug)
                    for syn in _synonym_group(term)
                )
            ]
            has_a = bool(term_hits)
            has_b = summary.slug in linked
            if not has_a and not has_b:
                print(f"  [双失] {summary.slug}：题面词表零命中 + 词表无挂接")
            elif not has_a:
                print(f"  [仅挂接] {summary.slug}：靠词表挂接得分，题面词表零命中")
        print()


if __name__ == "__main__":
    main()
