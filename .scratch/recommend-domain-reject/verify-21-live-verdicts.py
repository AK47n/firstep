# -*- coding: utf-8 -*-
"""工单 real-acceptance/10 真机验收证据（只读，零 LLM 调用）。

读两次真机复跑的现场件（`verify-21-recommend-*.txt` + `done-21-*.json`），机械核
两条验收标准：

1. **域拒绝 0 条「硬件名不在硬件词表中」**——扫日志里的 `[PROBE16][域拒绝]` 行，
   计数并按类型分组（多实例 / 词表 / 其它）。词表类必须为 0。
2. **done 载荷里的库外建议名全部合法**——把 `done-21-*.json` 里每条
   `requirements[].suggestions[].name` 过一遍 `_solution_group`，未命中即「本批该
   收没收」，直接指认是哪个名字（不用等下一轮真机）。

用法（仓库根）：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/recommend-domain-reject/verify-21-live-verdicts.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.llm import DEFAULT_WORDLIST  # noqa: E402
from contest_generator.selection import _solution_group  # noqa: E402

DIR = ROOT / ".scratch" / "recommend-domain-reject"
WORDLIST_REJECT_MARK = "硬件名不在硬件词表中"
RUNS = (
    ("2022C-stm32", DIR / "verify-21-recommend-2022C-stm32.txt",
     DIR / "done-21-2022C-stm32.json"),
    ("2026H-mspm0", DIR / "verify-21-recommend-2026H-mspm0.txt",
     DIR / "done-21-2026H-mspm0.json"),
)


def category_of(reason: str) -> str:
    if WORDLIST_REJECT_MARK in reason:
        return "词表名"
    if "多实例" in reason:
        return "多实例"
    return "其它"


def main() -> int:
    bad = 0
    for label, log_path, done_path in RUNS:
        print(f"== {label} ==")
        if not log_path.exists():
            print(f"  ⚠ 日志缺失：{log_path}")
            bad += 1
            continue
        text = log_path.read_text(encoding="utf-8")
        terminals = re.findall(r"\[结果\] 终态 (\w+)；收敛轮次 (\[[^\]]*\])", text)
        rejects = re.findall(r"\[PROBE16\]\[域拒绝\] SelectionError → (.+)", text)
        kinds: dict[str, int] = {}
        for reason in rejects:
            key = category_of(reason)
            kinds[key] = kinds.get(key, 0) + 1
        print(f"  终态：{terminals or '（无）'}")
        print(f"  域拒绝 {len(rejects)} 条：{kinds or '无'}")
        for reason in rejects:
            print(f"    · [{category_of(reason)}] {reason.strip()}")
        wordlist_rejects = kinds.get("词表名", 0)
        print(f"  ⇒ 「硬件名不在硬件词表中」拒收 = {wordlist_rejects} 条 "
              f"{'✅' if wordlist_rejects == 0 else '❌'}")

        if not done_path.exists():
            print(f"  ⚠ done 载荷缺失：{done_path}（未收敛到 done）")
            bad += 1
            continue
        data = json.loads(done_path.read_text(encoding="utf-8"))
        names: list[tuple[str, str]] = []
        for req in data.get("requirements") or []:
            for sug in req.get("suggestions") or []:
                name = sug.get("name")
                if isinstance(name, str) and name:
                    names.append((name, "degraded" if sug.get("degraded") else "命中"))
        unmatched = [
            n for n, _ in names if _solution_group(n, DEFAULT_WORDLIST) is None
        ]
        print(f"  库外建议 {len(names)} 条："
              f"{'、'.join(f'{n}（{v}）' for n, v in names) or '（无）'}")
        print(f"  ⇒ 未命中词表行的建议名 = {len(unmatched)} 条 "
              f"{'✅' if not unmatched else '❌ ' + '、'.join(unmatched)}")
        if wordlist_rejects or unmatched:
            bad += 1
        print()
    print("总体：" + ("✅ 两条验收标准全绿" if bad == 0 else f"❌ {bad} 处不达标"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
