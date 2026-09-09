"""列出 tracker 里状态仍为未完成的工单（标题 + 要做什么 + 阻塞），供人工盘点。

与 `.scratch/tracker-audit/census.py` 的分工（两者不重叠，故并存）：
- census.py = **数量视角**：扫全库所有工单（含无 Status 的 `(none)` 与 resolved），
  按 feature 打印各状态计数——回答「还剩多少、分布如何」，不读标题与正文。
- 本脚本 = **清单视角**：只挑未完成状态（ready-for-agent / claimed / ready-for-human /
  needs-*），逐张打印状态 + feature/文件名 + 标题 + 要做什么 + 被谁阻塞——回答
  「剩下的这些是什么、卡在谁身上」。标题与阻塞字段是 census.py 不产出的内容。

位置：2026-09-09 从 `.scratch/library-audit/` 挪入本目录——它读的是 tracker 工单，
与 library-audit 域无关。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch/tracker-audit/list_open_tickets.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPEN_STATES = ("ready-for-agent", "claimed", "ready-for-human", "needs-")


def main() -> int:
    for path in sorted(ROOT.glob(".scratch/*/issues/*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        state = re.search(r"\*\*(?:Status|状态)：\*\*\s*([^\s（(]+)", text)
        if not state or not state.group(1).startswith(OPEN_STATES):
            continue
        title = next(
            (line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")),
            path.name,
        )
        what = re.search(r"\*\*要做什么：\*\*\s*(.*?)\n\n", text, re.S)
        blocked = re.search(r"\*\*被谁阻塞：\*\*\s*(.*?)\n", text)
        feature = path.parent.parent.name
        print(f"--- {state.group(1):16s} {feature}/{path.name}")
        print(f"    标题：{title[:110]}")
        if what:
            print(f"    要做什么：{' '.join(what.group(1).split())[:130]}")
        if blocked:
            print(f"    阻塞：{blocked.group(1).strip()[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
