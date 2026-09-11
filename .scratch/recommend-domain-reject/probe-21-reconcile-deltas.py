# -*- coding: utf-8 -*-
"""工单 real-acceptance/10 对账探针（只读）：两把尺子的口径差从哪来。

现象：`measure-20-deferred-headroom.py`（权威口径）报「27 条均摊 43B / 全收
≈1156B」，而补丁脚本按**词表段实发**记账报 +1375B。两个数都来自同一条生产
路径，差 219B 必须查清再收口——否则「余量够不够」的结论建立在一个说不清的
数上。

本脚本逐项分解：
1. 词表段实发（生产路径 `_wordlist_prompt_segment`）补数据前后 + 全量 + 截断态；
2. 权威口径 worst-case payload 补数据前后 + 段级分解（`request_segments`）；
3. 把 27 条**照 measure-20 的做法**（TARGET_CATEGORIES 两行）重放一遍，看差
   是否来自落点行数不同（7 行 vs 2 行）与**段截断**（models 段被 fit 砍掉时
   增量被低估）。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".scratch" / "recommend-domain-reject"))

from contest_generator.budget import (  # noqa: E402
    MODULE_SUMMARY_BYTES,
    REQUEST_RESERVE_BYTES,
    payload_wire_size,
    request_segments,
    wire_size,
)
from contest_generator.llm import (  # noqa: E402
    DEFAULT_WORDLIST,
    EMBEDDED_CONTENT_CAP,
    MAX_REQUEST_BYTES,
    REFERENCE_SOURCE_RELATED,
    SELECT_SYSTEM_PROMPT,
    WORDLIST_PROMPT_BYTES,
    _selection_user_prompt,
    _wordlist_prompt_segment,
)
from contest_generator.library import list_modules  # noqa: E402
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

DIR = ROOT / ".scratch" / "recommend-domain-reject"
BEFORE = DIR / "wordlist-before-21.json"
AFTER = ROOT / "src" / "contest_generator" / "wordlist.json"
DEFERRED = DIR / "deferred-18.txt"

# measure-20 的做法（对账用）：目标行 + 名字源
TARGET_CATEGORIES = ("感知传感器", "执行机构")


def groups_of(path: Path) -> tuple:
    handle = tempfile.NamedTemporaryFile("wb", suffix="-wl.json", delete=False)
    try:
        handle.write(path.read_bytes())
        handle.close()
        return load_wordlist(Path(handle.name), lib_slugs=None)
    finally:
        Path(handle.name).unlink(missing_ok=True)


def deferred_names() -> list[str]:
    text = DEFERRED.read_text(encoding="utf-8")
    body = text.split("：", 1)[-1] if "：" in text else text
    return [p.strip() for p in body.replace("\n", "").split("、") if p.strip()]


def _fixtures():
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
    clarifications = tuple((f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20))
    return references, clarifications


def worst_payload(groups, platform: str = "mspm0"):
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
        reference_fulltexts={"big-ref": "中" * 23400},
        clarifications=clarifications,
        hardware_words=groups,
        preselect_note=note,
    )
    return {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }


def replay(groups, names: list[str], targets=TARGET_CATEGORIES) -> tuple:
    """照 measure-20 的做法把 names 加到 targets 行（去重保序）。"""
    out = []
    for group in groups:
        models = list(group.models)
        if group.category in targets:
            for name in names:
                if name not in models:
                    models.append(name)
        out.append(HardwareWordGroup(group.category, tuple(models), group.solutions))
    return tuple(out)


def main() -> int:
    names = deferred_names()
    gb, ga = groups_of(BEFORE), groups_of(AFTER)
    print("== 1. 词表段实发（生产路径） ==")
    sb, sa = _wordlist_prompt_segment(gb), _wordlist_prompt_segment(ga)
    fb, fa = format_wordlist_prompt(gb), format_wordlist_prompt(ga)
    print(f"  全量 wire : {wire_size(fb)} → {wire_size(fa)}")
    print(f"  实发 wire : {wire_size(sb)} → {wire_size(sa)}  (+{wire_size(sa)-wire_size(sb)})"
          f"  预算 {WORDLIST_PROMPT_BYTES}")
    print(f"  截断      : before={sb != fb}  after={sa != fa}")
    print(f"  词表行数  : before={len(gb)} 行 / after={len(ga)} 行")

    print("\n== 2. 权威口径 worst-case payload ==")
    pb, pa = worst_payload(gb), worst_payload(ga)
    tb, ta = payload_wire_size(pb), payload_wire_size(pa)
    limit = MAX_REQUEST_BYTES - REQUEST_RESERVE_BYTES
    print(f"  mspm0: {tb} → {ta}  (+{ta-tb})  余量 {limit-tb} → {limit-ta}"
          f"  （余量须 ≥ {REQUEST_RESERVE_BYTES}）")
    print(f"  within_reserve: {limit - ta >= REQUEST_RESERVE_BYTES}")

    print("\n== 3. 重放 measure-20 做法（2 行 vs 7 行） ==")
    rp = worst_payload(replay(ga, names))
    tr = payload_wire_size(rp)
    print(f"  已落盘(7 行) {ta}  |  再加到 2 行(measure-20 重放) {tr}  (+{tr-ta})")
    segs = request_segments(rp)
    for key in sorted(segs, key=lambda k: -segs[k])[:6]:
        print(f"    {key} = {segs[key]}B")
    print(f"  JSON 壳 = {tr - sum(segs.values())}B")

    print("\n== 4. 段截断对增量记账的影响（measure-20 的模型段是否被 fit 砍） ==")
    both = replay(ga, names)
    seg_both = _wordlist_prompt_segment(both)
    print(f"  2 行形态词表段实发={wire_size(seg_both)}  全量={wire_size(format_wordlist_prompt(both))}"
          f"  截断={seg_both != format_wordlist_prompt(both)}")
    print(f"  7 行形态词表段实发={wire_size(sa)}  全量={wire_size(fa)}  截断={sa != fa}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
