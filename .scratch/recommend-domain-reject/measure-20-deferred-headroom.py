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

    # 落盘词表（本批落地后：27 条已在盘上 → 工具自证「已入 27」，不再虚报成本）
    $env:PYTHONPATH='src'; python .scratch/recommend-domain-reject/measure-20-deferred-headroom.py

    # 补数据前形态（单 08 存档词表）——复现本批真实成本 +1375B / 51B 一条
    ... measure-20-deferred-headroom.py --base .scratch/recommend-domain-reject/wordlist-before-18.json

**修正说明（2026-09-17，两处 bug 由单 10 实施会话抓出，已修）**：

1. `with_names` 曾把 27 条**一律塞进「感知传感器 + 执行机构」两行**（真实落点跨 7 行）
   → 该形态下词表段被 `WORDLIST_PROMPT_BYTES` **截断**，「再加一条」的边际字节被截断
   吃掉，量出 **94B/条**的假账。现改为按 `landing_rows()` 机械反查落点逐行落，
   并新增「收下后词表段实发 / 全文」对照（实发 < 全文 = 已截断 = 边际读数不可信）。
   修正后复现真值：**51B/条、27 条合计 +1375B**。
2. 基线曾用 `from ... import DEFAULT_WORDLIST`（import 时固化的常量）当「现状」，
   与落盘词表**不同源** → 报「现状 125476 / 收下后 128007」，而真实落盘形态是
   **126851**。现基线一律走 `load_wordlist()`（同一次加载、与被测形态同源），
   并支持 `--base` 指向历史词表；另加 `already_present()` 自证哪些名字已在盘上。
"""

from __future__ import annotations

import re
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
    wire_size,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.llm import (  # noqa: E402
    EMBEDDED_CONTENT_CAP,
    MAX_REQUEST_BYTES,
    REFERENCE_SOURCE_RELATED,
    SELECT_SYSTEM_PROMPT,
    _selection_user_prompt,
    _wordlist_prompt_segment,
)
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    ReferenceSuggestion,
    filter_manifests_by_platform,
    preselect_module_summaries,
)
from contest_generator.wordlist import (  # noqa: E402
    HardwareWordGroup,
    format_wordlist_prompt,
    load_wordlist,
)

DEFERRED = ROOT / ".scratch" / "recommend-domain-reject" / "deferred-18.txt"
# 判「还收得下」的活动余量：不是 0，留 512B 给后续小改动（自设，非契约）
ACTIVITY_MARGIN = 512


def deferred_names() -> list[str]:
    """deferred-18.txt 里的顺延名（首行是说明，名字按「、」分隔）。"""
    text = DEFERRED.read_text(encoding="utf-8")
    body = text.split("：", 1)[-1] if "：" in text else text
    return [p.strip() for p in body.replace("\n", "").split("、") if p.strip()]


def landing_rows(groups) -> dict[str, str]:
    """顺延名 → 落点行 category 的机械反查（判据单源，与单 08 裁定同款）：
    name 命中某行 `solutions[].name` 或它的**去括号裸名** → 落该行。

    **为什么必须反查**（单 10 实施记录第 1 条）：第一版把 27 条一律塞进
    「感知传感器 + 执行机构」两行——而真实落点是**跨 7 行**。错落点会让词表段
    被 `WORDLIST_PROMPT_BYTES` **截断**，于是「再加一条」的边际字节被截断吃掉，
    量出 94B/条（真值 51B/条）的**假账**。反查不到落点的名字会在 main 里报错，
    不静默。
    """
    landing: dict[str, str] = {}
    for name in deferred_names():
        for group in groups:
            for option in group.solutions:
                full = option.name
                bare = re.sub(r"（[^）]*）", "", full).strip()
                if name in (full, bare):
                    landing[name] = group.category
    return landing


def segment_wire(groups) -> tuple[int, int]:
    """(词表段实发, 词表段全文) wire 字节——实发 < 全文 = 被截断（预算已顶死，
    此时任何「边际字节」读数都不可信，见 landing_rows 注释）。"""
    return wire_size(_wordlist_prompt_segment(groups)), wire_size(
        format_wordlist_prompt(groups)
    )


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


def with_names(names: list[str], landing: dict[str, str], base_groups) -> list[HardwareWordGroup]:
    """按**机械反查的落点**把名字加进各自行的 models（去重保序，其余行原样）。

    base_groups 由调用方给（**必须是同一次 load 的落盘词表**）：基线与被测形态
    同源，杜绝「import 时固化的 DEFAULT_WORDLIST 当现状」那类自相矛盾读数
    （单 10 实施记录第 2 条）。
    """
    out = []
    for group in base_groups:
        models = list(group.models)
        for name in names:
            if landing.get(name) == group.category and name not in models:
                models.append(name)
        out.append(HardwareWordGroup(group.category, tuple(models), group.solutions))
    return out


def already_present(name: str, landing: dict[str, str], base_groups) -> bool:
    """该名字是否已在落点行的 models 里（本批已落地 = True）。

    必要：本脚本要用**落盘词表**当基线（见 with_names 注释），而落盘词表在单 10
    落地后**已经包含这 27 条** —— 此时「再加一遍」的边际字节恒为 0，若不做这个
    判定，读数会被误读成「补数据不要钱」。
    """
    cat = landing.get(name)
    for group in base_groups:
        if group.category == cat:
            return name in group.models
    return False


def main() -> int:
    # --base <词表 json>：用指定词表当基线（如单 08 存的 wordlist-before-18.json =
    # 补这批之前的形态）。缺省 = 落盘词表。**基线与被测形态必须同源**（同一个
    # 对象加载出来），否则读数自相矛盾——单 10 实施记录第 2 条就是这么错的。
    argv = sys.argv[1:]
    base_path: Path | None = None
    if "--base" in argv:
        idx = argv.index("--base")
        base_path = Path(argv[idx + 1])
        if not base_path.is_file():
            print(f"✗ --base 指定的词表不存在：{base_path}")
            return 2
    limit = MAX_REQUEST_BYTES - REQUEST_RESERVE_BYTES
    base_groups = load_wordlist(base_path) if base_path else load_wordlist()
    print(f"上限 MAX_REQUEST_BYTES={MAX_REQUEST_BYTES}  统一余量={REQUEST_RESERVE_BYTES}"
          f"  ⇒ 断言边界={limit}")
    print(f"全文段={REFERENCE_FULLTEXT_BYTES}  摘要段={MODULE_SUMMARY_BYTES}  "
          f"活动余量自设={ACTIVITY_MARGIN}")
    print(f"基线词表：{'落盘 ' if base_path is None else str(base_path) + '（历史形态）'}")
    seg_now, seg_full = segment_wire(base_groups)
    print(f"基线词表段：实发 {seg_now}B / 全文 {seg_full}B"
          f"{'（⚠ 已截断：边际字节读数不可信）' if seg_now < seg_full else '（未截断）'}\n")

    base = {p: worst_case_total(base_groups, p) for p in ("mspm0", "stm32")}
    for platform, total in base.items():
        print(f"基线最坏形态 {platform}: {total}B  余量 {limit - total}B")

    names = deferred_names()
    landing = landing_rows(base_groups)
    missing = [n for n in names if n not in landing]
    if missing:
        print(f"⚠ 反查不到落点（需人工裁，本次跳过）：{missing}")
        names = [n for n in names if n in landing]
    present = [n for n in names if already_present(n, landing, base_groups)]
    absent = [n for n in names if n not in present]
    print(f"\n顺延名 {len(names)} 条：落盘词表里**已入 {len(present)} 条**、未入 {len(absent)} 条")
    if present:
        print("  已入（本批已落地，边际成本记 0）" if len(present) == len(names)
              else "  已入：" + "、".join(present[:6]) + ("…" if len(present) > 6 else ""))

    # 只有**未入**的名字才需要试加（已入的加不进去，边际恒 0，会污染均摊读数）
    taken: list[str] = []
    for name in absent:
        trial = with_names(present + taken + [name], landing, base_groups)
        if limit - worst_case_total(trial) >= ACTIVITY_MARGIN:
            taken.append(name)
    after_groups = with_names(present + taken, landing, base_groups)
    after = worst_case_total(after_groups, "mspm0")
    seg_after, seg_after_full = segment_wire(after_groups)
    print(f"\n本次试加（只对未入项）：可收 {len(taken)}/{len(absent)} 条"
          f"（活动余量 ≥{ACTIVITY_MARGIN}B）")
    print(f"收下后 mspm0={after}B  余量={limit - after}B")
    if taken:
        per = (after - base["mspm0"]) / len(taken)
        print(f"边际成本 实测 {per:.0f}B/条（{len(taken)} 条合计 {after - base['mspm0']:+d}B）")
    else:
        print("边际成本 无（未入项为空：本批已全部落地，成本见工单 10 实施记录）")
    print(f"收下后词表段实发 {seg_after}B / 全文 {seg_after_full}B"
          f"{'（⚠ 截断）' if seg_after < seg_after_full else '（未截断）'}")
    if absent:
        print("\n本次可收：" + ("、".join(taken) if taken else "（无）"))
        rest = [n for n in absent if n not in taken]
        print("仍放不下：" + ("、".join(rest) if rest else "（无）"))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
