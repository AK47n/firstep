# -*- coding: utf-8 -*-
"""工单 real-acceptance/10 权威口径复核（只读）：DEFAULT_WORDLIST 现状是否 = 落盘词表。

对账（`probe-21-reconcile-deltas.py`）暴露一处口径要点，必须查清才能收口：

- 词表段生产路径**不截断**时（现状：全量 10994 < 预算 12150），段增量 = payload
  增量，逐字节一致（实测 +1375 ↔ +1375）。
- `measure-20-deferred-headroom.py` 的「逐条试加」会先把 27 条**重复加到
  感知传感器 + 执行机构 两行**（`with_names`）——该形态下词表段**超过 12150 被
  截断**，于是「再加一条」的边际字节被截断吃掉，估出的「均摊 94B / 全收 ≈2529B」
  是**截断记账的假数**；同时它的「现状最坏形态」仍按**未补数据**的词表算（脚本
  打印的 125476 与补数据前逐字节相同）——即该脚本现状下是「旧词表基线 + 2 行重放」，
  不能直接当补数据后的现状读。

本脚本给出**补数据后的真实现状**（同一权威载荷构造），并验证
`DEFAULT_WORDLIST` 与落盘词表逐字节一致（同进程内同源，避免「基线是旧对象」的
误读）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".scratch" / "recommend-domain-reject"))

from contest_generator.budget import (  # noqa: E402
    REQUEST_RESERVE_BYTES,
    payload_wire_size,
    wire_size,
)
from contest_generator.llm import (  # noqa: E402
    DEFAULT_WORDLIST,
    WORDLIST_PROMPT_BYTES,
    _wordlist_prompt_segment,
)
from contest_generator.wordlist import (  # noqa: E402
    format_wordlist_prompt,
    load_wordlist,
)

# 权威载荷构造复用对账脚本（文件名带连字符，不能按模块名 import）
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "reconcile_deltas",
    ROOT / ".scratch" / "recommend-domain-reject" / "probe-21-reconcile-deltas.py",
)
_reconcile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reconcile)
worst_payload = _reconcile.worst_payload

AFTER = ROOT / "src" / "contest_generator" / "wordlist.json"
BEFORE = ROOT / ".scratch" / "recommend-domain-reject" / "wordlist-before-21.json"


def main() -> int:
    disk = load_wordlist(AFTER, lib_slugs=None)
    before = load_wordlist(BEFORE, lib_slugs=None)

    # 同源检查：进程内 DEFAULT_WORDLIST 必须就是落盘词表（models+solutions 逐条相等）
    same = len(disk) == len(DEFAULT_WORDLIST) and all(
        d.category == w.category and d.models == w.models and d.solutions == w.solutions
        for d, w in zip(disk, DEFAULT_WORDLIST)
    )
    print(f"DEFAULT_WORDLIST == 落盘词表：{same}")
    added_total = sum(len(g.models) for g in disk) - sum(len(g.models) for g in before)
    print(f"models 条目总数：{sum(len(g.models) for g in before)} → "
          f"{sum(len(g.models) for g in disk)}（+{added_total}）")

    # 词表段：全量 / 实发 / 截断
    for label, groups in (("补数据前", before), ("补数据后", disk)):
        full = format_wordlist_prompt(groups)
        sent = _wordlist_prompt_segment(groups)
        print(f"词表段[{label}]：全量={wire_size(full)}B 实发={wire_size(sent)}B "
              f"预算={WORDLIST_PROMPT_BYTES}B 截断={sent != full}")

    # 权威口径 worst-case payload（真实落盘词表）
    limit_hard = 131072
    limit = limit_hard - REQUEST_RESERVE_BYTES
    for platform in ("mspm0", "stm32"):
        for label, groups in (("补数据前", before), ("补数据后", disk)):
            total = payload_wire_size(worst_payload(groups, platform))
            mark = "✅" if limit - total >= REQUEST_RESERVE_BYTES else "❌"
            print(f"{mark} worst-case {platform} [{label}]：{total}B  "
                  f"余量(距{limit})={limit - total}B  "
                  f"在统一余量内={limit - total >= REQUEST_RESERVE_BYTES}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
