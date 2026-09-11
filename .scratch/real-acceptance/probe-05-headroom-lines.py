# -*- coding: utf-8 -*-
"""单 05 探针 A：四条请求线的余量现状（只读）。

问的是单 05 的关键决策问题：自设「2KB 边界」只有推荐侧两个用例在用，
其余三条线（fix / skeleton / clarify）用 10KB。统一 reserve 单源之前，
先把四条线的真实余量测出来——否则「统一口径」会变成把某条线偷偷放宽或改严。

产出：probe-05-headroom-all-lines.txt
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from contest_generator.budget import (  # noqa: E402
    SKELETON_REFERENCE_TOTAL_BYTES,
    SKELETON_RELATED_LIMIT,
    wire_size,
)
from contest_generator.llm import (  # noqa: E402
    CLARIFY_SYSTEM_PROMPT,
    CLARIFY_TOPIC_CAP,
    EMBEDDED_CONTENT_CAP,
    FIX_SYSTEM_PROMPT,
    MAX_REQUEST_BYTES,
    REFERENCE_FULLTEXT_BYTES,
    SKELETON_SYSTEM_PROMPT,
    SELECT_SYSTEM_PROMPT,
    _clarify_user_prompt,
    _fix_errors_user_prompt,
    _selection_user_prompt,
    _skeleton_user_prompt,
)
from contest_generator.llm import DEFAULT_WORDLIST  # noqa: E402
from contest_generator.manifest import ManifestSummary  # noqa: E402
from contest_generator.selection import REFERENCE_SOURCE_RELATED  # noqa: E402
from test_llm import _suggestion  # noqa: E402

OUT = Path(__file__).with_name("probe-05-headroom-lines.txt")
LIMIT = MAX_REQUEST_BYTES


def wire_of(payload: dict) -> int:
    return len(json.dumps(payload).encode("utf-8"))


def main() -> int:
    lines: list[str] = []

    def emit(text: str = "") -> None:
        lines.append(text)
        print(text)

    emit("单 05 探针 A：四条请求线余量现状（只读，HEAD 19f4590e）")
    emit(f"MAX_REQUEST_BYTES = {LIMIT}")
    emit()

    # ① select 合成（tests 结构测试原样）
    problem = "设" * EMBEDDED_CONTENT_CAP
    summaries = [ManifestSummary(f"mod{i}", "温湿度传感器采集与显示" * 8) for i in range(14)]
    clarifications = tuple((f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20))
    refs = [
        _suggestion(
            f"关联例程{i:02d}",
            f"TI 外设例程 {i:02d}",
            "TI MSPM0 SDK 官方例程，演示外设初始化与中断配置流程" * 8,
            source=REFERENCE_SOURCE_RELATED,
        )
        for i in range(15)
    ] + [_suggestion("big-ref", "大参考文件", "巨型参考")]
    prompt = _selection_user_prompt(
        problem,
        summaries,
        references=refs,
        reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_BYTES},
        clarifications=clarifications,
        hardware_words=DEFAULT_WORDLIST,
    )
    sel = wire_of({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    })
    emit(f"① select 合成最坏（14 条假摘要）    {sel:>7}B  余量 {LIMIT - sel:>7}B "
         f"({(LIMIT - sel) / 1024:.1f}KB)")

    # ② clarify
    c_prompt = _clarify_user_prompt("设" * CLARIFY_TOPIC_CAP, clarifications)
    clar = wire_of({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": CLARIFY_SYSTEM_PROMPT},
            {"role": "user", "content": c_prompt},
        ],
        "response_format": {"type": "json_object"},
    })
    emit(f"② clarify 最坏（12000 字题面+历史）  {clar:>7}B  余量 {LIMIT - clar:>7}B "
         f"({(LIMIT - clar) / 1024:.1f}KB)")

    # ③ skeleton（4 篇 related 全文）
    refs_sk = {f"ref-{i}": "中" * REFERENCE_FULLTEXT_BYTES for i in range(SKELETON_RELATED_LIMIT)}
    sources = {f"ref-{i}": REFERENCE_SOURCE_RELATED for i in range(SKELETON_RELATED_LIMIT)}
    s_prompt = _skeleton_user_prompt(
        problem, ["### 模块 m（h）\nvoid init(void);"] * 3, refs_sk, None, sources
    )
    skel = wire_of({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SKELETON_SYSTEM_PROMPT},
            {"role": "user", "content": s_prompt},
        ],
    })
    emit(f"③ skeleton 最坏（4 篇全文均分）     {skel:>7}B  余量 {LIMIT - skel:>7}B "
         f"({(LIMIT - skel) / 1024:.1f}KB)  段预算 {SKELETON_REFERENCE_TOTAL_BYTES}")

    # ④ fix（与 tests/test_llm.py::test_fix_prompt_worst_case_fits_request_budget 同源）
    import tempfile

    from contest_generator.fix_errors import read_file_contexts

    tmp = Path(tempfile.mkdtemp(prefix="probe05-"))
    (tmp / "big.c").write_text("\n".join("中" * 50 for _ in range(3000)), encoding="utf-8")
    contexts, dropped = read_file_contexts(tmp, ("big.c",))
    fix_prompt = _fix_errors_user_prompt(
        error_text="错" * 5000,
        file_contexts=dict(contexts),
        dropped_files=tuple(f"code/mod_{i}_driver.c" for i in range(200)),
        problem_text="设" * 4000,
        platform="stm32",
        module_slugs=tuple(f"mod_{i}_driver" for i in range(40)),
        main_c="主" * 5000,
        previous_fixes=tuple(
            {
                "file": f"code/mod_{i}.c",
                "line": 10 + i,
                "status": "skipped",
                "reason": "未" * 200,
            }
            for i in range(60)
        ),
    )
    fix = wire_of({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": FIX_SYSTEM_PROMPT},
            {"role": "user", "content": fix_prompt},
        ],
        "response_format": {"type": "json_object"},
    })
    emit(f"④ fix 最坏（结构测试原样）          {fix:>7}B  余量 {LIMIT - fix:>7}B "
         f"({(LIMIT - fix) / 1024:.1f}KB)")

    emit()
    emit(
        "现状口径（tests 断言）："
        "select 合成 / select 真实库 / clarify / skeleton / fix = 距上限 2KB / 2KB / 10KB / 10KB / 10KB"
    )
    emit("→ 统一 reserve 单源后，四条线都必须满足同一 reserve；")
    emit("  取 2KB 会让 clarify/skeleton 变严（现状 36-37KB 余量，仍远超）；")
    emit("  取 10KB 会让 select 真实库变严（现状 0.7KB，本轮必须靠重分配腾出来）。")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
