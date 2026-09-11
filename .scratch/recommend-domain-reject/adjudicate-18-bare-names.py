# -*- coding: utf-8 -*-
"""工单 real-acceptance/08 裁定辅助：逐行列出「裸名未入 models」清单（只读）。

输出每条：类别 / 序号 / 裸名 / 是否与全名相同。供实施会话逐条裁定用，
结论写进工单 08「修复方向 2 裁定规则」下方（不另开文档）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator import wordlist as W  # noqa: E402


def bare(name: str) -> str:
    return re.sub(r"（[^）]*）", "", name).strip()


def main() -> int:
    groups = W.load_wordlist()
    total = 0
    for group in groups:
        rows: list[tuple[str, str]] = []
        seen: set[str] = set()
        for option in group.solutions:
            name = bare(option.name)
            if name and name not in group.models and name not in seen:
                seen.add(name)
                rows.append((name, option.name))
        if not rows:
            continue
        print(f"### {group.category}（{len(rows)} 条）")
        for index, (name, full) in enumerate(rows, 1):
            same = "=" if name == full else "≠"
            print(f"{index:>3}. {name}   [全名{same}]")
        print()
        total += len(rows)
    print(f"TOTAL={total}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
