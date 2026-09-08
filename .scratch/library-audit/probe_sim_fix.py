"""临时探针：模拟几种预筛修复方案对 2024H 可见性的影响（只读，不改源码）。

方案对照：
A 现状
B 收紧 _term_matches_topic 的反向滑窗（方案名 2 字片段不再命中题面）
C B + PERIPHERAL_TERMS 补运动控制词族（小车/车模/行驶/循迹/编码器/测速）
D C + 执行机构词族入 MODULE_PERIPHERAL_TERMS（motor/pid/servo/xunji/step_motor）

用法：python .scratch/library-audit/probe_sim_fix.py 2024H stm32
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.budget import MIN_PRESELECT, MODULE_SUMMARY_BYTES, wire_size  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    MODULE_PERIPHERAL_TERMS,
    PERIPHERAL_SYNONYM_GROUPS,
    _synonym_group,
    _term_matches_token,
)
from contest_generator.selection import _activated_terms, _preselect_score, _text_has_term  # noqa: E402

topic = sys.argv[1] if len(sys.argv) > 1 else "2024H"
platform = sys.argv[2] if len(sys.argv) > 2 else "stm32"
text = (ROOT / "library" / "topics" / topic / "topic.md").read_text(
    encoding="utf-8", errors="replace"
)
words = wordlist_mod.load_wordlist()
summaries = build_manifest_summaries(
    [m for m in list_modules(ROOT / "library" / "modules") if platform in m.platforms]
)

PROBES = ("motor", "pid", "servo", "xunji", "step_motor", "led", "key", "beep", "oled")

MOTION_TERMS = ("小车", "车模", "行驶", "循迹", "编码器", "测速", "避障")
MOTION_MODULE_TERMS = {
    "motor": ("motor", "小车", "电机"),
    "pid": ("pid", "循迹", "巡线"),
    "servo": ("servo", "舵机"),
    "xunji": ("循迹", "巡线"),
    "step_motor": ("step", "电机"),
}


def term_matches_topic_strict(text_lower: str, term: str, strict: bool) -> bool:
    """现状 _term_matches_topic；strict=True 时禁用「方案名片段 → 题面」方向。"""
    term = term.strip()
    if not term:
        return False
    lower_term = term.lower()
    if lower_term.isascii():
        return _text_has_term(text_lower, lower_term)
    if lower_term in text_lower:
        return True
    for seg in re.findall(r"[a-z0-9]+", lower_term):
        if _text_has_term(text_lower, seg):
            return True
    if strict:
        return False
    for seg in re.findall(r"[\u4e00-\u9fff]{2,}", lower_term):
        for width in (2, 3, 4):
            for index in range(max(0, len(seg) - width + 1)):
                if seg[index:index + width] in text_lower:
                    return True
    return False


def wordlist_hits(text: str, strict: bool, extra_terms: tuple[str, ...]) -> frozenset[str]:
    hits: set[str] = set()
    text_lower = text.lower()
    for group in words:
        terms = (group.category, *group.models, *extra_terms)
        row_hit = any(term_matches_topic_strict(text_lower, t, strict) for t in terms)
        named = [s for s in group.solutions if term_matches_topic_strict(text_lower, s.name, strict)]
        if named:
            for s in named:
                hits.update(s.lib_modules)
        elif row_hit:
            for s in group.solutions:
                hits.update(s.lib_modules)
    return frozenset(hits)


def score(summary, activated, boost, module_terms) -> int:
    match_text = " ".join((summary.description, *summary.kits)).lower()
    value = 0
    for term in activated:
        synonyms = _synonym_group(term)
        if any(_text_has_term(match_text, syn) for syn in synonyms):
            value += 1
            continue
        if any(_term_matches_token(syn, summary.slug) for syn in synonyms):
            value += 1
    if summary.slug in boost:
        value += 1
    if summary.slug in module_terms:
        for extra in module_terms[summary.slug]:
            if extra.lower() in text.lower():
                value += 1
                break
    return value


def run(label: str, strict: bool, extra_terms: tuple[str, ...], module_terms: dict) -> None:
    activated = _activated_terms(text, ()) | {t for t in extra_terms if t in text}
    boost = wordlist_hits(text, strict, extra_terms)
    scored = [(score(s, activated, boost, module_terms), s) for s in summaries]
    scored.sort(key=lambda it: (-it[0], it[1].slug))
    kept: list = []
    total = 0
    for sc, s in scored:
        w = wire_size(s.to_line())
        if total + w > MODULE_SUMMARY_BYTES and kept:
            break
        kept.append(s)
        total += w + 1
    if len(kept) < MIN_PRESELECT:
        kept = [s for _, s in scored[:MIN_PRESELECT]]
    kept_slugs = {s.slug for s in kept}
    marks = " ".join(
        f"{p}{'✓' if p in kept_slugs else '✗'}" for p in PROBES
    )
    print(f"{label:<28} 可见 {len(kept)}/{len(summaries)}  激活 {len(activated)}  挂接 {len(boost)}  {marks}")


print(f"题面 {topic} / {platform}（候选 {len(summaries)}）\n")
run("A 现状", False, (), {})
run("B 收紧反向滑窗", True, (), {})
run("C B+运动控制词族", True, MOTION_TERMS, {})
run("D C+执行机构模块词", True, MOTION_TERMS, MOTION_MODULE_TERMS)

print("\nD 方案下各关键模块的得分与排名：")
activated = _activated_terms(text, ()) | {t for t in MOTION_TERMS if t in text}
boost = wordlist_hits(text, True, MOTION_TERMS)
scored = [(score(s, activated, boost, MOTION_MODULE_TERMS), s) for s in summaries]
scored.sort(key=lambda it: (-it[0], it[1].slug))
for probe in PROBES:
    hit = [(sc, s) for sc, s in scored if s.slug == probe]
    if not hit:
        print(f"  {probe:<12} 不在候选内")
        continue
    sc, _ = hit[0]
    rank = [i for i, (_, x) in enumerate(scored) if x.slug == probe][0] + 1
    print(f"  {probe:<12} 得分 {sc:2d}  排名 {rank}/{len(scored)}")
