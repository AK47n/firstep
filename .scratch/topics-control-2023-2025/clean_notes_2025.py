"""图注段人工校订（对齐 2026C 先例形态=纯图内标注行）。

enrich 的文字标注兜底（pdf_figure_annotations）在 2025E/H 上产出了
混入正文短行的图注（机制收窗：正文引用「如图1 所示」与标题同 y、行首
「图1 中小车…」被当标题行、正文短行在窗口内无长行阻断）。图中实际
标注文字保留（2025E：A4 紫外感光靶纸 / A B / C 100cm D；2025H：
B1-B7 / A1-A9 网格标），混入的正文行删除——与 2026C 图注形态一致。

题面已含 [图1 标注]（幂等标记），后续 enrich 不会重跑，人工校订稳定。
库自动提交打桩为 no-op（人工精确提交）。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import contest_generator.topic_library as _topic_lib  # noqa: E402

_topic_lib.commit_after_write = lambda *args, **kwargs: None

CLEAN_NOTES = {
    "2025E": (
        "[图1 标注]\n"
        "A4 紫外感光靶纸\n"
        "A B\n"
        "C 100cm D\n"
    ),
    "2025H": (
        "[图1 标注]\n"
        "B7\n"
        "B6\n"
        "B5\n"
        "B4\n"
        "B3\n"
        "B2\n"
        "B1\n"
        "A1 A2 A3 A4 A5 A6 A7 A8 A9\n"
    ),
}

for key, notes in CLEAN_NOTES.items():
    path = REPO_ROOT / "library" / "topics" / key / "topic.md"
    text = path.read_text(encoding="utf-8")
    i = text.find("[图")
    assert i >= 0, f"{key}: topic.md 无图注段（enrich 未产出？）"
    head = text[:i].rstrip("\n")
    new = head + "\n\n" + notes
    path.write_text(new, encoding="utf-8")
    print(f"{key}: 图注段校订 {len(text) - len(new)} chars 净变化（{len(text)} → {len(new)}）")
