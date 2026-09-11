"""量出「哪一题 / 哪一平台」的 select 请求 = 56980 wire 字节（工单 real-acceptance/05 尾巴）。

背景：webapp 最近两次 recommend 都在 select 失败，`request_bytes=56980`、
`http_status=200` / `parse_status=parse_error` / `error_kind=client`。要复现就得
知道是哪一题——本脚本按 webapp 同款装配（瘦身清单行 → 预筛 → 同款提示词函数）
逐题算 select 请求的 wire 字节，把与 56980 相等的挑出来。

用法：$env:PYTHONPATH='src'; python .scratch/real-acceptance/probe-05-find-topic.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator import llm as llm_mod  # noqa: E402
from contest_generator.budget import MODULE_SUMMARY_BYTES  # noqa: E402
from contest_generator.config import load_config  # noqa: E402
from contest_generator.generator import resolve_topic_context  # noqa: E402
from contest_generator.selection import preselect_module_summaries  # noqa: E402

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 56980
ROOT = REPO / "library"
cfg = load_config()
llm = llm_mod.build_llm(cfg)


def wire(obj: object) -> int:
    return len(json.dumps(obj).encode("utf-8"))


hits: list[str] = []
for platform in ("mspm0", "stm32"):
    for topic_dir in sorted((ROOT / "topics").iterdir()):
        md = topic_dir / "topic.md"
        if not md.is_file():
            continue
        try:
            topic = resolve_topic_context(
                llm=None,
                topic_key=topic_dir.name,
                problem_text=md.read_text(encoding="utf-8"),
                module_library_dir=ROOT / "modules",
                topic_library_dir=ROOT / "topics",
                reference_library_dir=ROOT / "references",
                platform=platform,
            )
            topic = replace(
                topic,
                manifest_summaries=tuple(s.lean_copy() for s in topic.manifest_summaries),
            )
            presel = preselect_module_summaries(
                topic.manifest_summaries, topic.problem_text,
                llm_mod.DEFAULT_WORDLIST, MODULE_SUMMARY_BYTES,
            )
            note = ""
            if presel.truncated:
                topic = replace(topic, manifest_summaries=presel.summaries)
                note = (
                    f"（按题面初筛 {len(presel.summaries)}/{presel.total} 条，"
                    f"仅展示前 {MODULE_SUMMARY_BYTES} wire 字节）"
                )
            user = llm_mod._selection_user_prompt(
                topic.problem_text,
                topic.manifest_summaries,
                topic.suggestions,
                None,
                None,
                llm_mod.DEFAULT_WORDLIST,
                (),
                None,
                preselect_note=note,
            )
        except Exception as exc:  # noqa: BLE001 - 探针
            print(f"{platform:6} {topic_dir.name:8} 装配失败：{type(exc).__name__}: {exc}")
            continue
        total = wire({
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": llm_mod.SELECT_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": llm_mod.SELECT_MAX_OUTPUT_TOKENS,
            "thinking": {"type": "disabled"},
        })
        flag = "  <== 命中" if total == TARGET else ""
        if total == TARGET:
            hits.append(f"{topic_dir.name}/{platform}")
        if abs(total - TARGET) <= 250 or total == TARGET:
            print(f"{platform:6} {topic_dir.name:8} select={total}{flag}")

print("\n命中清单：", hits or "（无——说明该题面不在库内 / 装配口径不同）")
