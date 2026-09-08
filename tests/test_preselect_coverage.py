"""预筛覆盖率守卫（工单 preselect-recall-visibility/02）：关键模块必须可见。

背景：模块库长到 93 个后，题面预筛把摘要行截断到预算内的前 N 条（真实库
stm32 86 条只进 32–42 条），而得分并列的模块按 slug 字典序截断——小车、循迹、
PID 这类赛题的执行/交互核心模块常常整类落在截断线外。实测 2024H（自动行驶
小车）可见 34/86，`motor` 排名 71、`pid` 76、`servo` 78、`led` 67、`key` 65
全部不可见；模型若凭常识写出 `motor`，还会被判成幻觉中断推荐（该行为已由
工单 01 修复，本测试守的是「可见性」这一层）。

本文件用**真实题库 + 真实模块库**跑预筛，把「关键模块可见」钉成断言：

- 当前必然失败（预筛评分与匹配粒度未改），故整组用 `xfail(strict=True)`
  标记为预期失败——缺口被记录在案，而不是静默绿着。
- 预筛修好后自动转绿；`strict=True` 保证「修好了却没摘标记」也会报错提醒。
- 下方另有一条不依赖具体题面的结构不变量测试（子集 ⊆ 全量、截断标记自洽），
  它现在就绿，防止预筛契约在重构中被破坏。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.budget import MODULE_SUMMARY_BYTES
from contest_generator.library import list_modules
from contest_generator.manifest import build_manifest_summaries
from contest_generator.selection import preselect_module_summaries
from contest_generator.wordlist import load_wordlist

ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = ROOT / "library" / "modules"
TOPICS_DIR = ROOT / "library" / "topics"

# 覆盖率用例：(题面, 平台, 必须出现在预筛结果里的模块)
# 选取口径：题面明确要「跑起来/动起来/亮起来」时，执行与交互核心件是刚性需求，
# 不是可选配件——它们缺席意味着 AI 这一步看不见正解。
COVERAGE_CASES = (
    ("2024H", "stm32", ("motor", "pid", "servo", "led", "key")),
    ("2024H", "mspm0", ("motor", "pid", "servo", "led", "key")),
    ("2021F", "stm32", ("motor", "pid", "xunji", "key", "oled")),
    ("2026C", "stm32", ("led", "beep", "key", "oled")),
    ("2026A", "mspm0", ("motor", "servo", "led", "key")),
    ("2022C", "stm32", ("motor", "oled")),
)


def _preselect_for(topic: str, platform: str):
    """真实题面 × 真实模块库 → 预筛结果（与网页推荐路由同参同源）。"""
    manifests = list_modules(MODULES_DIR)
    summaries = build_manifest_summaries(
        [m for m in manifests if platform in m.platforms]
    )
    text = (TOPICS_DIR / topic / "topic.md").read_text(encoding="utf-8", errors="replace")
    return preselect_module_summaries(
        summaries, text, load_wordlist(), MODULE_SUMMARY_BYTES
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "预筛评分/预算截断导致关键模块落在截断线外（2024H/stm32 可见 34/86，"
        "motor 排名 71、pid 76、servo 78）——待预筛评分与匹配粒度修复后自动转绿，"
        "转绿时摘掉本标记（.scratch/library-audit/probe_guard_cases.py 可复测）"
    ),
)
@pytest.mark.parametrize("topic, platform, required", COVERAGE_CASES)
def test_preselect_keeps_key_modules_visible(topic, platform, required):
    """关键模块必须出现在预筛结果内（真实题库 × 真实库，库再涨就红）。"""
    result = _preselect_for(topic, platform)

    visible = {summary.slug for summary in result.summaries}
    missing = [slug for slug in required if slug not in visible]
    assert not missing, (
        f"{topic}/{platform} 预筛后关键模块不可见：{'、'.join(missing)}"
        f"（可见 {len(result.summaries)}/{result.total} 条，预算 "
        f"{MODULE_SUMMARY_BYTES} wire 字节）"
    )


def test_preselect_subset_is_contained_in_full_library():
    """预筛契约（不依赖具体题面）：子集 ⊆ 全量、条数自洽、截断标记与条数一致。"""
    result = _preselect_for("2024H", "stm32")

    visible = [summary.slug for summary in result.summaries]
    full = [summary.slug for summary in result.library_summaries]
    assert result.total == len(full)
    assert len(set(visible)) == len(visible)  # 子集无重复
    assert set(visible) <= set(full)
    assert result.truncated == (len(visible) < result.total)
    assert len(visible) <= result.total
    # 截断确实发生（真实库 stm32 86 条装不进 40000B 预算）——否则上面几条
    # 在同一条目集上自证，测不出契约
    assert result.truncated and "motor" in set(full) - set(visible)
