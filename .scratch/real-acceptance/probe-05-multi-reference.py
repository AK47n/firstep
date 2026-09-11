# -*- coding: utf-8 -*-
"""单 05 复核探针：多篇参考全文是否各自吃满预算（只读）。

规格评审指出的关键缺口：`_fit_segment_wire(fulltext)` 在 `_selection_user_prompt`
里**逐篇**调用（manual_fulltexts 与 reference_fulltexts 两个循环各自独立），
所以 N 篇 = N × 预算。本探针复算真实值。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import REFERENCE_FULLTEXT_BYTES as FB  # noqa: E402
from contest_generator.budget import payload_wire_size  # noqa: E402
from contest_generator.llm import (  # noqa: E402
    EMBEDDED_CONTENT_CAP,
    MAX_REQUEST_BYTES,
    SELECT_SYSTEM_PROMPT,
    _selection_user_prompt,
)
from contest_generator.manifest import ManifestSummary  # noqa: E402
from contest_generator.selection import ReferenceSuggestion  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REFS = [
    ReferenceSuggestion(id=f"r{i}", title=f"参考{i}", description="简介", source="auto")
    for i in range(4)
]
SUMMARY = [ManifestSummary("dht11", "温湿度")]
PROBLEM = "设" * EMBEDDED_CONTENT_CAP


def size(n: int, kw: str) -> int:
    fulltexts = {f"r{i}": "中" * FB for i in range(n)}
    prompt = _selection_user_prompt(
        PROBLEM, SUMMARY, references=REFS[:n], **{kw: fulltexts}
    )
    return payload_wire_size({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    })


for kw in ("manual_fulltexts", "reference_fulltexts"):
    print(f"=== {kw}（{FB}B/篇）===")
    for n in (1, 2, 3, 4):
        total = size(n, kw)
        over = total - MAX_REQUEST_BYTES
        flag = "超硬限" if over > 0 else "OK"
        print(f"  {n} 篇满额: {total:>7}B  {over:>+8}  {flag}")
