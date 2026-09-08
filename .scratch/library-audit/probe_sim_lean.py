"""临时探针：摘要行瘦身后全库能否装进预算（只读，不改源码）。

对比三种行形态的全量 wire 字节：
- 现状 to_line()
- 极简：slug + 首句简介截断
- 中等：slug + 首句 + 依赖 + 多实例标记
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import MODULE_SUMMARY_BYTES, wire_size  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402


def first_sentence(text: str) -> str:
    for sep in ("。", "；", "：", "，"):
        if sep in text:
            return text.split(sep)[0]
    return text


def lean_line(s, desc_chars: int, with_deps: bool, with_multi: bool) -> str:
    parts = [s.slug, first_sentence(s.description)[:desc_chars]]
    if with_deps and s.dependencies:
        parts.append("依赖:" + "/".join(s.dependencies))
    if with_multi and s.multi_instance:
        parts.append("多实例")
    return " ".join(parts)


for platform in ("stm32", "mspm0"):
    summaries = build_manifest_summaries(
        [m for m in list_modules(ROOT / "library" / "modules") if platform in m.platforms]
    )
    print(f"=== {platform}（{len(summaries)} 条）预算 {MODULE_SUMMARY_BYTES}B ===")
    now = sum(wire_size(s.to_line()) + 1 for s in summaries)
    print(f"  现状 to_line()            {now:>7}B  均值 {now // len(summaries):>4}B")
    for desc in (24, 32, 40):
        for deps, multi in ((False, False), (True, True)):
            total = sum(
                wire_size(lean_line(s, desc, deps, multi)) + 1 for s in summaries
            )
            tag = f"  瘦身 简介{desc}字 依赖{'有' if deps else '无'} 多实例{'有' if multi else '无'}"
            print(
                f"{tag:<44}{total:>7}B  均值 {total // len(summaries):>4}B  "
                f"{'全库可装' if total <= MODULE_SUMMARY_BYTES else f'超 {total - MODULE_SUMMARY_BYTES}B'}"
            )
    print()
