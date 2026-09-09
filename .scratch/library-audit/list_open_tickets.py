"""列出 tracker 里状态仍为未完成的工单（标题 + 要做什么 + 阻塞），供人工盘点。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/list_open_tickets.py
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
