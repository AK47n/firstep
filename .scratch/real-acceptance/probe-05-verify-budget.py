# -*- coding: utf-8 -*-
"""单 05 验收探针：段级 wire 记账实测（只读）。

实施后状态：四条请求线的最坏形态 + 推荐侧段级分解 + 段级预算对照。
产出：verify-05-segment-budget.txt（可追溯证据，供 budget.py 注释引用）。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from contest_generator.budget import (  # noqa: E402
    MODULE_SUMMARY_BYTES,
    REFERENCE_FULLTEXT_BYTES,
    REFERENCE_SUGGESTIONS_MAX_WIRE_BYTES,
    REQUEST_RESERVE_BYTES,
    SKELETON_REFERENCE_TOTAL_BYTES,
    SKELETON_RELATED_LIMIT,
    payload_shell_wire_size,
    payload_wire_size,
    request_segments,
    wire_size,
)
from contest_generator.fix_errors import read_file_contexts  # noqa: E402
from contest_generator.llm import (  # noqa: E402
    CLARIFY_SYSTEM_PROMPT,
    CLARIFY_TOPIC_CAP,
    DEFAULT_WORDLIST,
    EMBEDDED_CONTENT_CAP,
    FIX_SYSTEM_PROMPT,
    MAX_REQUEST_BYTES,
    SELECT_SYSTEM_PROMPT,
    SKELETON_SYSTEM_PROMPT,
    WORDLIST_PROMPT_BYTES,
    _clarify_user_prompt,
    _fix_errors_user_prompt,
    _selection_user_prompt,
    _skeleton_user_prompt,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    REFERENCE_SOURCE_RELATED,
    filter_manifests_by_platform,
    preselect_module_summaries,
)
from test_llm import _measure_prompt_segments, _suggestion  # noqa: E402

OUT = Path(__file__).with_name("verify-05-segment-budget.txt")
LIMIT = MAX_REQUEST_BYTES
FLOOR = LIMIT - REQUEST_RESERVE_BYTES

lines: list[str] = []
try:
    sys.stdout.reconfigure(encoding=utf-8)
except Exception:
    pass


def emit(text: str = "") -> None:
    lines.append(text)
    print(text)


def select_payload(platform: str, *, note: bool = True) -> tuple[dict, dict]:
    modules = list_modules(ROOT / "library" / "modules")
    problem = "设" * EMBEDDED_CONTENT_CAP
    presel = preselect_module_summaries(
        build_manifest_summaries(filter_manifests_by_platform(modules, platform)),
        problem,
        DEFAULT_WORDLIST,
        MODULE_SUMMARY_BYTES,
    )
    preselect_note = (
        f"（按题面初筛 {len(presel.summaries)}/{presel.total} 条，"
        f"仅展示前 {MODULE_SUMMARY_BYTES} wire 字节）"
        if note and presel.truncated
        else ""
    )
    references = [
        _suggestion(
            f"关联例程{i:02d}", f"TI 外设例程 {i:02d}", "TI MPSM0 SDK 官方例程" * 8,
            source=REFERENCE_SOURCE_RELATED,
        )
        for i in range(15)
    ] + [_suggestion("big-ref", "大参考文件", "巨型参考")]
    clarifications = tuple((f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20))
    prompt = _selection_user_prompt(
        problem,
        presel.summaries,
        references=references,
        reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_BYTES},
        clarifications=clarifications,
        hardware_words=DEFAULT_WORDLIST,
        preselect_note=preselect_note,
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    return payload, {
        "prompt": prompt,
        "lib": presel.total,
        "kept": len(presel.summaries),
        "note": preselect_note,
    }


def main() -> int:
    emit("单 05 验收：请求预算段级记账实测（工单 real-acceptance/05）")
    emit(f"MAX_REQUEST_BYTES = {LIMIT}；统一余量 REQUEST_RESERVE_BYTES = {REQUEST_RESERVE_BYTES}"
         f"；断言下界 = {FLOOR}")
    emit(f"REFERENCE_FULLTEXT_BYTES = {REFERENCE_FULLTEXT_BYTES}"
         f"（工单 08 时为 25600）；WORDLIST_PROMPT_BYTES = {WORDLIST_PROMPT_BYTES}"
         f"；MODULE_SUMMARY_BYTES = {MODULE_SUMMARY_BYTES}")
    emit()

    emit("① 四条请求线最坏形态（实施后）")
    emit(f"{'线':<34}{'实发':>9}{'余量':>9}{'满足下界':>10}")
    rows: list[tuple[str, int]] = []

    for platform in (PLATFORM_MSPM0, PLATFORM_STM32):
        payload, _ = select_payload(platform)
        rows.append((f"select 真实库 {platform}（带预筛注记）", payload_wire_size(payload)))
    payload_no_note, _ = select_payload(PLATFORM_MSPM0, note=False)
    rows.append(("select 真实库 mspm0（不带注记，仅对照）", payload_wire_size(payload_no_note)))

    clarifications = tuple((f"问题{i}：" + "疑" * 200, "答" * 5000) for i in range(20))
    rows.append((
        "clarify（题面上限 + 20 条长历史）",
        payload_wire_size({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": CLARIFY_SYSTEM_PROMPT},
                {"role": "user", "content": _clarify_user_prompt("设" * CLARIFY_TOPIC_CAP, clarifications)},
            ],
            "response_format": {"type": "json_object"},
        }),
    ))

    skel_refs = {f"ref-{i}": "中" * REFERENCE_FULLTEXT_BYTES for i in range(SKELETON_RELATED_LIMIT)}
    rows.append((
        f"skeleton（{SKELETON_RELATED_LIMIT} 篇全文均分 {SKELETON_REFERENCE_TOTAL_BYTES}）",
        payload_wire_size({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SKELETON_SYSTEM_PROMPT},
                {"role": "user", "content": _skeleton_user_prompt(
                    "设" * EMBEDDED_CONTENT_CAP,
                    ["### 模块 m（h）\nvoid init(void);"] * 3,
                    skel_refs,
                    None,
                    {k: REFERENCE_SOURCE_RELATED for k in skel_refs},
                )},
            ],
        }),
    ))

    tmp = Path(tempfile.mkdtemp(prefix="verify05-"))
    (tmp / "big.c").write_text("\n".join("中" * 50 for _ in range(3000)), encoding="utf-8")
    contexts, dropped = read_file_contexts(tmp, ("big.c",))
    rows.append((
        "fix（文件上下文 + 全段上限）",
        payload_wire_size({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": FIX_SYSTEM_PROMPT},
                {"role": "user", "content": _fix_errors_user_prompt(
                    error_text="错" * 5000,
                    file_contexts=dict(contexts),
                    dropped_files=tuple(f"code/mod_{i}_driver.c" for i in range(200)),
                    problem_text="设" * 4000,
                    platform="stm32",
                    module_slugs=tuple(f"mod_{i}_driver" for i in range(40)),
                    main_c="主" * 5000,
                    previous_fixes=tuple(
                        {"file": f"code/mod_{i}.c", "line": 10 + i,
                         "status": "skipped", "reason": "未" * 200}
                        for i in range(60)
                    ),
                )},
            ],
            "response_format": {"type": "json_object"},
        }),
    ))

    for label, total in rows:
        emit(f"{label:<34}{total:>9}{LIMIT - total:>9}{'OK' if total <= FLOOR else 'FAIL':>10}")
    emit()

    emit("② 推荐侧段级分解与段级预算对照（真实库 mspm0，带注记）")
    payload, info = select_payload(PLATFORM_MSPM0)
    emit(f"库内 {info['lib']} 条 → 预筛 {info['kept']} 条；注记={info['note']!r}")
    emit(f"实发 total = {payload_wire_size(payload)}B；Σ段 + JSON壳 = "
         f"{sum(request_segments(payload).values()) + payload_shell_wire_size(payload)}B "
         f"（对账等式，逐字节）")
    base, segs = _measure_prompt_segments(info["prompt"])
    emit(f"system 提示词 = {wire_size(SELECT_SYSTEM_PROMPT)}B；JSON 壳 = "
         f"{payload_shell_wire_size(payload)}B")
    emit(f"基础段（不可裁：题面 + 清单行 + 注记 + 条件规则段 + 输出契约）= {base}B")
    budget_of = {
        "词表段": WORDLIST_PROMPT_BYTES,
        "参考清单段": REFERENCE_SUGGESTIONS_MAX_WIRE_BYTES + 2,
        "参考全文段": None,
        "澄清历史段": None,
    }
    for name, value in segs.items():
        budget = budget_of.get(name)
        if budget is None:
            emit(f"  {name:<14}{value:>8}B   （按实发形态记账）")
        else:
            emit(f"  {name:<14}{value:>8}B  段级预算 {budget}B  "
                 f"{'OK' if value <= budget else 'FAIL'}")
    emit()

    emit("③ 与工单 08 校准值的对照（账本 vs 实测）")
    emit("  工单 08 记账（budget.py 注释）：全文 25600、真实库最坏形态 mspm0 128293B、"
         "余量 731B（**不带预筛注记**）")
    emit(f"  本单实测（带注记，生产形态）：{payload_wire_size(payload)}B、余量 "
         f"{LIMIT - payload_wire_size(payload)}B")
    emit(f"  差额来源：预筛注记 +{wire_size(info['note'])}B（库/题面驱动，"
         f"生产必带而两条结构测试此前都没算）")
    emit()
    emit("④ 口径（本单定的硬约定，写进 budget.py 模块 docstring）")
    emit("  尺寸类断言/记账一律走**发送前 wire 字节**（wire_size / request_segments /")
    emit("  payload_wire_size），与 llm._chat_once 预检同一行同一对象；不得用快照函数")
    emit("  返回值或 JSON 增量估算代账——工单 08 立单时按 format_wordlist_prompt 估")
    emit("  +1942B、实发只 +770B；按 JSON 增量估则偏高，两个方向都错。")
    emit("  统一余量单源 = budget.REQUEST_RESERVE_BYTES（各线结构测试共用，改一处即全改）。")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
