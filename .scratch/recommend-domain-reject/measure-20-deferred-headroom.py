# -*- coding: utf-8 -*-
"""工单 real-acceptance/08 顺延批预算复核（只读，零写入）。

**权威口径 = `tests/test_llm.py::test_recommend_real_library_budget` 的完整载荷构造**
（真实库 + 题面截断上限 + 生产带预筛注记 + 15 条关联参考候选 + 1 篇满额全文 +
20 条长澄清历史）。⚠️ 早期版本的 `measure-18-wordlist-coverage.py` ② 节与一个
只传 `reference_fulltexts` 的简化探针都**漏了那 15 条参考候选**，实测少算约 27KB
（97959B vs 权威 125476B）——**预算结论只认本脚本**。

为什么有这个脚本：单 08 收口时「27 条规则可入的裸名」被**预算不足**顺延，当时前提是
全文段 25600、边界只剩 731B；**单 05 之后全文段降到 23400（-2200B）**，且单 05 把段级
记账改成可执行 —— 顺延批的前提变了，需按同一把尺子重量。

跑法（仓库根）：

    $env:PYTHONPATH='src'; python .scratch/recommend-domain-reject/measure-20-deferred-headroom.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from contest_generator.budget import (  # noqa: E402
    MODULE_SUMMARY_BYTES,
    REFERENCE_FULLTEXT_BYTES,
    REQUEST_RESERVE_BYTES,
    payload_wire_size,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.llm import (  # noqa: E402
    DEFAULT_WORDLIST,
    EMBEDDED_CONTENT_CAP,
    MAX_REQUEST_BYTES,
    REFERENCE_SOURCE_RELATED,
    SELECT_SYSTEM_PROMPT,
    _selection_user_prompt,
)
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    ReferenceSuggestion,
    filter_manifests_by_platform,
    preselect_module_summaries,
)
from contest_generator.wordlist import HardwareWordGroup  # noqa: E402

DEFERRED = ROOT / ".scratch" / "recommend-domain-reject" / "deferred-18.txt"
# 顺延批的实际落点（单 08 裁定：规则可入的名字都归这两行的品类）
TARGET_CATEGORIES = ("感知传感器", "执行机构")
# 判「还收得下」的活动余量：不是 0，留 512B 给后续小改动（自设，非契约）
ACTIVITY_MARGIN = 512


def deferred_names() -> list[str]:
    """deferred-18.txt 里的顺延名（首行是说明，名字按「、」分隔）。"""
    text = DEFERRED.read_text(encoding="utf-8")
    body = text.split("：", 1)[-1] if "：" in text else text
    return [p.strip() for p in body.replace("\n", "").split("、") if p.strip()]


def _fixtures():
    """权威口径的参考候选 / 澄清历史 / 题库（与真实库预算测试逐字同构）。"""
    references = [
        ReferenceSuggestion(
            id=f"关联例程{i:02d}",
            title=f"TI 外设例程 {i:02d}",
            description="TI MSPM0 SDK 官方例程" * 8,
            source=REFERENCE_SOURCE_RELATED,
        )
        for i in range(15)
    ]
    references.append(
        ReferenceSuggestion(id="big-ref", title="大参考文件", description="巨型参考")
    )
    clarifications = tuple(
        (f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20)
    )
    return references, clarifications


def worst_case_total(groups, platform: str = "mspm0") -> int:
    """按权威口径算某平台的最坏形态 select payload wire 字节。"""
    modules = list_modules(ROOT / "library" / "modules")
    problem = "设" * EMBEDDED_CONTENT_CAP
    references, clarifications = _fixtures()
    filtered = filter_manifests_by_platform(modules, platform)
    summaries = build_manifest_summaries(filtered)
    presel = preselect_module_summaries(
        summaries, problem, groups, MODULE_SUMMARY_BYTES
    )
    note = (
        f"（按题面初筛 {len(presel.summaries)}/{presel.total} 条，"
        f"仅展示前 {MODULE_SUMMARY_BYTES} wire 字节）"
        if presel.truncated
        else ""
    )
    prompt = _selection_user_prompt(
        problem,
        presel.summaries,
        references=references,
        reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_BYTES},
        clarifications=clarifications,
        hardware_words=groups,
        preselect_note=note,
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    return payload_wire_size(payload)


def with_names(names: list[str]) -> list[HardwareWordGroup]:
    """把名字加进顺延批的落点两行 models（去重保序，其余行原样）。"""
    out = []
    for group in DEFAULT_WORDLIST:
        models = list(group.models)
        if group.category in TARGET_CATEGORIES:
            for name in names:
                if name not in models:
                    models.append(name)
        out.append(HardwareWordGroup(group.category, tuple(models), group.solutions))
    return out


def main() -> int:
    limit = MAX_REQUEST_BYTES - REQUEST_RESERVE_BYTES
    print(f"上限 MAX_REQUEST_BYTES={MAX_REQUEST_BYTES}  统一余量={REQUEST_RESERVE_BYTES}"
          f"  ⇒ 断言边界={limit}")
    print(f"全文段={REFERENCE_FULLTEXT_BYTES}  摘要段={MODULE_SUMMARY_BYTES}  "
          f"活动余量自设={ACTIVITY_MARGIN}\n")

    base = {p: worst_case_total(DEFAULT_WORDLIST, p) for p in ("mspm0", "stm32")}
    for platform, total in base.items():
        print(f"现状最坏形态 {platform}: {total}B  余量 {limit - total}B")

    names = deferred_names()
    print(f"\n顺延名 {len(names)} 条")
    # 逐条试加（mspm0 是更紧的平台），只为估容量，不是最终入选顺序
    taken: list[str] = []
    for name in names:
        if limit - worst_case_total(with_names(taken + [name])) >= ACTIVITY_MARGIN:
            taken.append(name)
    after = worst_case_total(with_names(taken))
    per = (after - base["mspm0"]) / max(len(taken), 1)
    print(f"逐条试加：可收 {len(taken)}/{len(names)} 条（活动余量 ≥{ACTIVITY_MARGIN}B）")
    print(f"收下后 mspm0={after}B  余量={limit - after}B")
    print(f"实测每条均摊 {per:.0f}B（全收 ≈{per * len(names):.0f}B）")
    print("\n可收：" + "、".join(taken))
    rest = [n for n in names if n not in taken]
    print("仍放不下：" + ("、".join(rest) if rest else "（无）"))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
