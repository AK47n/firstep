# -*- coding: utf-8 -*-
"""工单 real-acceptance/08：词表数据增长对 select 请求预算的两条传导路径实测。

补词表 models 会同时改变两段：
1. 词表段本身（format_wordlist_prompt）；
2. **模块摘要段**——preselect_module_summaries 吃 wordlist 做词表挂接加分，
   词表变 → 预筛排序变 → 摘要段（MODULE_SUMMARY_BYTES 截断）字节变。

第 2 条是隐藏成本：只量词表段会低估预算影响数倍。本脚本把两条分开量。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from contest_generator.budget import (  # noqa: E402
    MODULE_SUMMARY_BYTES,
    wire_size,
)
from contest_generator.llm import (  # noqa: E402
    EMBEDDED_CONTENT_CAP,
    WORDLIST_PROMPT_BYTES,
    WORDLIST_TRUNCATION_NOTICE,
    _wordlist_prompt_segment,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    filter_manifests_by_platform,
    preselect_module_summaries,
)
from contest_generator.wordlist import (  # noqa: E402
    DEFAULT_WORDLIST,
    format_wordlist_prompt,
    load_wordlist,
)


def main() -> int:
    modules = list_modules(ROOT / "library" / "modules")
    problem = "设" * EMBEDDED_CONTENT_CAP
    fit_limit = WORDLIST_PROMPT_BYTES - wire_size(WORDLIST_TRUNCATION_NOTICE)
    old = load_wordlist(
        ROOT / ".scratch" / "recommend-domain-reject" / "wordlist-before-18.json",
        lib_slugs=None,
    )

    print(f"词表段预算={WORDLIST_PROMPT_BYTES}  fit 上限={fit_limit}")
    rows = {}
    for label, wl in (("HEAD词表", old), ("现状词表", DEFAULT_WORDLIST)):
        segment = _wordlist_prompt_segment(wl)
        filtered = filter_manifests_by_platform(modules, "mspm0")
        summaries = build_manifest_summaries(filtered)
        presel = preselect_module_summaries(
            summaries, problem, wl, MODULE_SUMMARY_BYTES
        )
        summary_wire = wire_size("\n".join(s.to_line() for s in presel.summaries))
        rows[label] = (wire_size(segment), summary_wire, len(presel.summaries))
        print(f"\n{label}：")
        print(f"  词表段实发   {rows[label][0]}B"
              f"{'（截断）' if rows[label][0] < wire_size(format_wordlist_prompt(wl)) else ''}")
        print(f"  摘要段       {rows[label][1]}B（预筛后 {rows[label][2]} 条）")

    d_seg = rows["现状词表"][0] - rows["HEAD词表"][0]
    d_sum = rows["现状词表"][1] - rows["HEAD词表"][1]
    print(f"\n增量：词表段 {d_seg:+d}B  摘要段 {d_sum:+d}B  合计 {d_seg + d_sum:+d}B")
    print("（摘要段是隐藏传导：词表挂接加分改变预筛排序/截断边界——只量词表段会低估数倍）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
