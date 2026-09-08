"""临时探针：最坏形态请求字节与余量（评估 WORDLIST_PROMPT_BYTES 上调空间）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from contest_generator.budget import (  # noqa: E402
    MODULE_SUMMARY_BYTES,
    REFERENCE_FULLTEXT_BYTES,
    wire_size,
)
from contest_generator.llm import (  # noqa: E402
    EMBEDDED_CONTENT_CAP,
    MAX_REQUEST_BYTES,
    SELECT_SYSTEM_PROMPT,
    WORDLIST_PROMPT_BYTES,
    _selection_user_prompt,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    REFERENCE_SOURCE_RELATED,
    filter_manifests_by_platform,
    preselect_module_summaries,
)
from contest_generator.wordlist import DEFAULT_WORDLIST, format_wordlist_prompt  # noqa: E402
from tests.test_llm import _suggestion  # noqa: E402

lib = ROOT / "library" / "modules"
modules = list_modules(lib)
problem = "设" * EMBEDDED_CONTENT_CAP
clarifications = tuple((f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20))
references = [
    _suggestion(
        f"关联例程{i:02d}", f"TI 外设例程 {i:02d}",
        "TI MSPM0 SDK 官方例程" * 8, source=REFERENCE_SOURCE_RELATED,
    )
    for i in range(15)
] + [_suggestion("big-ref", "大参考文件", "巨型参考")]

print(f"MAX_REQUEST_BYTES={MAX_REQUEST_BYTES} 边界={MAX_REQUEST_BYTES - 2 * 1024}")
print(f"WORDLIST_PROMPT_BYTES={WORDLIST_PROMPT_BYTES}")
print(f"词表段全量 wire={wire_size(format_wordlist_prompt(DEFAULT_WORDLIST))}\n")

for platform in ("mspm0", "stm32"):
    filtered = filter_manifests_by_platform(modules, platform)
    summaries = build_manifest_summaries(filtered)
    presel = preselect_module_summaries(
        summaries, problem, DEFAULT_WORDLIST, MODULE_SUMMARY_BYTES
    )
    prompt = _selection_user_prompt(
        problem,
        presel.summaries,
        references=references,
        reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_BYTES},
        clarifications=clarifications,
        hardware_words=DEFAULT_WORDLIST,
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"system": "x", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    total = len(json.dumps(payload).encode("utf-8"))
    print(
        f"{platform}: 最坏形态 {total}B，距边界 {MAX_REQUEST_BYTES - 2 * 1024 - total}B "
        f"（距硬限 {MAX_REQUEST_BYTES - total}B）"
    )
