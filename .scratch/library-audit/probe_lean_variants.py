"""临时探针：摘要行瘦身形态的字节账（只读，为第 2 批 spec 定形态）。

对照形态：
- 现状完整行 to_line()
- 完整行去掉套件段的采购链接尾巴（保留套件名）
- 瘦身行 to_line()（lean_copy() 形态，**生产实现**，不复制行文法）

首句切分与上限由生产实现 `manifest._bounded_first_sentence` /
`LEAN_SUMMARY_SENTENCE_CHARS` 决定（最早「。」「；」切点 + 100 字符上限），
本探针只消费它——行文法不在这里复制（避免与实现漂移）。想量不同上限的代价：
临时改 `manifest.LEAN_SUMMARY_SENTENCE_CHARS` 再跑本脚本。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import MODULE_SUMMARY_BYTES, wire_size  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import (  # noqa: E402
    LEAN_SUMMARY_SENTENCE_CHARS,
    build_manifest_summaries,
)

_LINK_TAIL = re.compile(r"[（(][^（）()]*采购链接[^（）()]*[）)]")


for platform in ("stm32", "mspm0"):
    summaries = build_manifest_summaries(
        [m for m in list_modules(ROOT / "library" / "modules") if platform in m.platforms]
    )
    print(f"=== {platform}（{len(summaries)} 条）预算 {MODULE_SUMMARY_BYTES}B ===")
    rows: list[tuple[str, list[str]]] = [
        ("现状完整行", [s.to_line() for s in summaries]),
        ("完整行去采购链接", [_LINK_TAIL.sub("", s.to_line()) for s in summaries]),
        (
            f"瘦身行（首句{LEAN_SUMMARY_SENTENCE_CHARS}字上限，生产实现）",
            [s.lean_copy().to_line() for s in summaries],
        ),
    ]
    for label, lines in rows:
        total = sum(wire_size(line) + 1 for line in lines)
        longest = max(lines, key=len)
        verdict = (
            "全库可装"
            if total <= MODULE_SUMMARY_BYTES
            else f"超 {total - MODULE_SUMMARY_BYTES}B"
        )
        print(
            f"  {label:<34}{total:>7}B  均值 {total // len(lines):>4}B  "
            f"最长 {len(longest):>4} 字符  {verdict}"
        )
    print()
