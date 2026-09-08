"""预算分配校准（工单 module-preselect/02）：测 (MODULE_SUMMARY_BYTES,
REFERENCE_FULLTEXT_BYTES) 组合下的最坏形态总字节，找 ≤ 129024 的最优分配。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.budget import REFERENCE_FULLTEXT_BYTES as _OLD_FT
from contest_generator.llm import (
    _selection_user_prompt,
    SELECT_SYSTEM_PROMPT,
    MAX_REQUEST_BYTES,
    EMBEDDED_CONTENT_CAP,
    DEFAULT_WORDLIST,
)
from contest_generator.library import list_modules
from contest_generator.manifest import build_manifest_summaries
from contest_generator.selection import filter_manifests_by_platform
from contest_generator.selection import preselect_module_summaries
from contest_generator.selection import REFERENCE_SOURCE_RELATED, ReferenceSuggestion
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

LIB = Path(__file__).resolve().parents[2] / "library" / "modules"
MODS = list_modules(LIB)
TARGET = MAX_REQUEST_BYTES - 2 * 1024


def _suggestion(entry_id, title, description, source="auto"):
    return ReferenceSuggestion(id=entry_id, title=title, description=description, source=source)


def payload_bytes(prompt):
    return len(json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }).encode("utf-8"))


def worst(platform, summaries, ft_budget, ms_budget):
    problem = "设" * EMBEDDED_CONTENT_CAP
    clarifications = tuple((f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20))
    refs = [
        _suggestion(f"关联例程{i:02d}", f"TI 外设例程 {i:02d}", "TI MSPM0 SDK 官方例程" * 8, source=REFERENCE_SOURCE_RELATED)
        for i in range(15)
    ] + [_suggestion("big-ref", "大参考文件", "巨型参考")]
    presel = preselect_module_summaries(summaries, problem, DEFAULT_WORDLIST, ms_budget)
    prompt = _selection_user_prompt(
        problem, presel.summaries,
        references=refs,
        reference_fulltexts={"big-ref": "中" * ft_budget},
        clarifications=clarifications,
        hardware_words=DEFAULT_WORDLIST,
    )
    return payload_bytes(prompt), len(presel.summaries), presel.total


for platform in (PLATFORM_MSPM0, PLATFORM_STM32):
    filtered = filter_manifests_by_platform(MODS, platform)
    summaries = build_manifest_summaries(filtered)
    print(f"== {platform}（全量 {len(summaries)} 条）")
    for ms_budget in (40000, 36000, 32000, 30000):
        ft = TARGET - 61005 - ms_budget  # 固定段 ≈ 61005（从 160705 反推）
        ft = min(ft, 60100)
        # 先跑现行 ft 看基线
        base, n, total = worst(platform, summaries, _OLD_FT, ms_budget)
        print(f"  摘要预算 {ms_budget:>6} + 全文 60100（现状）: {base} B, 预筛 {n}/{total} 条  [目标 {TARGET}]")
        adjusted_ft = (TARGET - base + _OLD_FT)  # 需要的全文预算 = 现状 − 超量
        adjusted_ft = min(adjusted_ft, 60100)
        got, n2, _ = worst(platform, summaries, adjusted_ft, ms_budget)
        print(f"  摘要预算 {ms_budget:>6} + 全文 {adjusted_ft}      : {got} B, 预筛 {n2}/{total} 条  [目标 {TARGET}]")
