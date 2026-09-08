"""临时探针：题面命中的词表行是「方案级」还是「行级兜底」进来的（只读）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.selection import _term_matches_topic  # noqa: E402

topic = sys.argv[1] if len(sys.argv) > 1 else "2024H"
text = (ROOT / "library" / "topics" / topic / "topic.md").read_text(
    encoding="utf-8", errors="replace"
).lower()
groups = wordlist_mod.load_wordlist()

for group in groups:
    row_hit = any(
        _term_matches_topic(text, term) for term in (group.category, *group.models)
    )
    named = [s for s in group.solutions if _term_matches_topic(text, s.name)]
    if not row_hit and not named:
        continue
    kind = "方案级" if named else "行级兜底"
    print(f"[{kind}] {group.category}")
    print(f"    models: {'、'.join(group.models)}")
    if named:
        for s in named:
            print(f"    命中方案: {s.name}  → {s.lib_modules}")
    else:
        allslugs = sorted({sl for s in group.solutions for sl in s.lib_modules})
        print(f"    整行并集（{len(allslugs)}）: {'、'.join(allslugs)}")
