# -*- coding: utf-8 -*-
"""工单 real-acceptance/10 前置（只读）：顺延批 27 条的机械反查落点 + 现状判决。

两件事，都**不许手抄**：

1. **落点反查**（工单「27 条的落点」表由本脚本机械产出，不手抄）：对每条顺延名，
   按判据「name 命中某行 `solutions[].name`，或该方案名的**去括号裸名**」→ 落该行
   `category`。要求每条**恰好命中一个类别**（0 个 = 无落点要人工裁，>1 个 = 归属
   歧义），否则大声失败——这正是本脚本存在的理由（单 08 那批按「感知传感器 +
   执行机构」两行的经验在本批不成立，本批跨 7 行）。
2. **现状判决**（工单验收标准 ①「红证」）：逐条真跑 `build_module_selection`，
   现状应**全部拒收**（`SelectionError`，理由「硬件名不在硬件词表中」）；对照
   `TI MSPM0 主控板` 同样拒收（闸没被放宽）。

判据单源：命中判定复用生产路径的 `selection._solution_group`，去括号裸名复用
`re.sub(r"（[^）]*）", "", name).strip()`（与 patch-18 同款）。

跑法（仓库根）：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/recommend-domain-reject/probe-21-deferred-placement.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import wire_size  # noqa: E402
from contest_generator.llm import (  # noqa: E402
    DEFAULT_WORDLIST,
    WORDLIST_PROMPT_BYTES,
    _wordlist_prompt_segment,
)
from contest_generator.selection import (  # noqa: E402
    SelectionError,
    build_module_selection,
)
from contest_generator.wordlist import format_wordlist_prompt  # noqa: E402

DEFERRED = ROOT / ".scratch" / "recommend-domain-reject" / "deferred-18.txt"

# 对照：平台/主控本身（裁定规则①）——补数据前后都必须拒收
MUST_STAY_REJECTED = ("TI MSPM0 主控板",)


def deferred_names() -> list[str]:
    """deferred-18.txt 里的顺延名（首行是说明，名字按「、」分隔）。"""
    text = DEFERRED.read_text(encoding="utf-8")
    body = text.split("：", 1)[-1] if "：" in text else text
    return [p.strip() for p in body.replace("\n", "").split("、") if p.strip()]


def bare(name: str) -> str:
    """方案名的去括号裸名（判据的单源写法，与 patch-18 / adjudicate-18 同款）。"""
    return re.sub(r"（[^）]*）", "", name).strip()


def placements() -> dict[str, set[str]]:
    """机械反查：顺延名 → 命中它的类别行集合（判据 = 全名 或 去括号裸名）。"""
    found: dict[str, set[str]] = {name: set() for name in deferred_names()}
    for group in DEFAULT_WORDLIST:
        for option in group.solutions:
            for candidate in (option.name, bare(option.name)):
                if candidate in found:
                    found[candidate].add(group.category)
    return found


def verdict(name: str) -> str:
    """现算一条库外建议名的判决（真跑 build_module_selection，不模拟判据）。"""
    raw = {
        "requirements": [
            {
                "requirement": "占位需求",
                "sentence": 1,
                "modules": [],
                "suggestions": [{"name": name}],
            }
        ]
    }
    try:
        build_module_selection(raw, known_slugs=(), hardware_words=DEFAULT_WORDLIST)
    except SelectionError as exc:
        return f"拒收（{exc}）"
    return "合法"


def main() -> int:
    names = deferred_names()
    print(f"顺延批：{len(names)} 条（源 {DEFERRED.name}）\n")

    # ---- 1. 机械反查落点 ----
    found = placements()
    empty = [name for name, cats in found.items() if not cats]
    ambiguous = [name for name, cats in found.items() if len(cats) > 1]
    if empty:
        raise SystemExit(f"反查无落点（需人工裁）：{'、'.join(empty)}")
    if ambiguous:
        detail = "；".join(f"{n} → {'/'.join(sorted(found[n]))}" for n in ambiguous)
        raise SystemExit(f"反查歧义（命中多行）：{detail}")

    by_category: dict[str, list[str]] = {}
    for name in names:  # 保序：按 deferred-18.txt 出现序
        category = next(iter(found[name]))
        by_category.setdefault(category, []).append(name)

    print(f"落点反查（跨 {len(by_category)} 行）：")
    for category, group_names in sorted(
        by_category.items(), key=lambda item: -len(item[1])
    ):
        print(f"  {category}：{len(group_names)} 条 —— {'、'.join(group_names)}")
    print()

    # ---- 2. 现状判决（红证：应全部拒收）----
    accepted: list[str] = []
    for name in names:
        result = verdict(name)
        legal = not result.startswith("拒收")
        if legal:
            accepted.append(name)
        print(f"  [{'合法' if legal else '拒收'}] {name}   ← {result}")
    print(f"\n现状：合法 {len(accepted)} / 拒收 {len(names) - len(accepted)}"
          f"（全部拒收 = 红证成立）")
    if accepted:
        print(f"**异常**：这些名字现状已合法（不该在顺延批里）：{'、'.join(accepted)}")

    # ---- 3. 对照 + 词表段现状 ----
    print("\n对照（补数据前后都必须拒收）：")
    for name in MUST_STAY_REJECTED:
        print(f"  {name} → {verdict(name)}")

    segment = _wordlist_prompt_segment(DEFAULT_WORDLIST)
    full = format_wordlist_prompt(DEFAULT_WORDLIST)
    print(f"\n词表段现状：全量 wire={wire_size(full)}B  实发={wire_size(segment)}B  "
          f"预算={WORDLIST_PROMPT_BYTES}B  "
          f"截断={'是' if segment != full else '否'}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
