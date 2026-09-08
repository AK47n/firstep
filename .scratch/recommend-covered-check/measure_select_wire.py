"""实测：真实模块库下 select（模块推荐）最坏形态载荷的 wire 字节。

对照测试样例（tests/test_llm.py::test_selection_prompt_worst_case_fits_request_budget
用的是 14 条摘要固定样例）与真实库（mspm0 84 条 / stm32 24 条）的差异，
验证摘要段增长是否已撑破 MAX_REQUEST_BYTES 预算。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.budget import REFERENCE_FULLTEXT_BYTES
from contest_generator.llm import (
    _selection_user_prompt,
    SELECT_SYSTEM_PROMPT,
    MAX_REQUEST_BYTES,
    EMBEDDED_CONTENT_CAP,
    DEFAULT_WORDLIST,
)
from contest_generator.library import list_modules
from contest_generator.manifest import build_manifest_summaries
from contest_generator.selection import (
    filter_manifests_by_platform,
    REFERENCE_SOURCE_RELATED,
    ReferenceSuggestion,
)


def _suggestion(entry_id: str, title: str, description: str, source: str = "auto") -> ReferenceSuggestion:
    return ReferenceSuggestion(id=entry_id, title=title, description=description, source=source)

LIB = Path(__file__).resolve().parents[2] / "library" / "modules"
mods = list_modules(LIB)


def payload_bytes(prompt: str) -> int:
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    return len(json.dumps(payload).encode("utf-8"))


def wire_b(content: str) -> int:
    return len(json.dumps(content, ensure_ascii=True)) - 2


def worst_prompt(summaries) -> str:
    problem = "设" * EMBEDDED_CONTENT_CAP
    clarifications = tuple((f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20))
    refs = [
        _suggestion(
            f"关联例程{i:02d}", f"TI 外设例程 {i:02d}", "TI MSPM0 SDK 官方例程" * 8,
            source=REFERENCE_SOURCE_RELATED,
        )
        for i in range(15)
    ] + [_suggestion("big-ref", "大参考文件", "巨型参考")]
    return _selection_user_prompt(
        problem,
        summaries,
        references=refs,
        reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_BYTES},
        clarifications=clarifications,
        hardware_words=DEFAULT_WORDLIST,
    )


def lean_prompt(summaries) -> str:
    """无参考全文、无澄清历史的现实形态（只题面 + 摘要 + 词表 + 清单段）。"""
    problem = "设" * EMBEDDED_CONTENT_CAP
    refs = [
        _suggestion(
            f"关联例程{i:02d}", f"TI 外设例程 {i:02d}", "TI MSPM0 SDK 官方例程" * 8,
            source=REFERENCE_SOURCE_RELATED,
        )
        for i in range(15)
    ] + [_suggestion("big-ref", "大参考文件", "巨型参考")]
    return _selection_user_prompt(
        problem,
        summaries,
        references=refs,
        hardware_words=DEFAULT_WORDLIST,
    )


for platform in ("stm32", "mspm0"):
    filtered = filter_manifests_by_platform(mods, platform)
    summaries = build_manifest_summaries(filtered)
    body = sum(len(s.to_line().encode("utf-8")) for s in summaries)
    body_wire = sum(wire_b(s.to_line()) for s in summaries)
    worst = payload_bytes(worst_prompt(summaries))
    lean = payload_bytes(lean_prompt(summaries))
    print(f"[{platform}] 摘要 {len(summaries)} 条 / utf8 {body} B / wire {body_wire} B")
    print(f"  最坏形态（全文+历史+清单）: {worst} B   [limit 131072, 余 {131072 - worst}]")
    print(f"  现实形态（无全文无历史）: {lean} B   [limit 131072, 余 {131072 - lean}]")
