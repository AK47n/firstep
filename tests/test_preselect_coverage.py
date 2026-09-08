"""预筛覆盖率守卫（工单 preselect-recall-visibility/02）：关键模块必须可见。

背景：模块库长到 93 个后，题面预筛把摘要行截断到预算内的前 N 条（真实库
stm32 86 条只进 33–41 条），而得分并列的模块按 slug 字典序截断——小车、循迹、
PID 这类赛题的执行/交互核心模块常常整类落在截断线外。实测 2024H（自动行驶
小车）可见 34/86，`motor` 排名 71、`pid` 76、`servo` 78、`led` 67、`key` 65
全部不可见。

根因是**行太长**而非预算太小：完整行含套件段（占摘要字节 23.5%，带采购链接
噪声），全库 stm32 86598B / mspm0 78668B；一级清单行改瘦身形态（工单
preselect-visibility/01-02，`ManifestSummary.lean_copy`）后 28071B / 28062B，
全库装得进 MODULE_SUMMARY_BYTES=40000 → **截断消失、全库可见**。

本文件用**真实题库 + 真实模块库**跑预筛，把「关键模块可见」钉成断言（工单 02
落地时这 6 组从 xfail 转 XPASS 并摘掉标记——本批的验收口径）。另有两条不依赖
具体题面的结构不变量（子集 ⊆ 全量、全库可见 / 截断标记自洽），防止预筛契约
在重构中被破坏、或库长大到重新截断却静默降级。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.budget import MODULE_SUMMARY_BYTES, wire_size
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
    # 2021F 的循迹核心在 stm32 侧由 pid（灰度读取 + 加权质心巡线）承担——
    # xunji 只有 mspm0 条目（原用例把 xunji 写成 stm32 必需项，xfail 期间
    # 被预期失败掩盖，转绿后暴露为不可能满足的断言，工单 02 修正）。
    ("2021F", "stm32", ("motor", "pid", "key", "oled")),
    ("2026C", "stm32", ("led", "beep", "key", "oled")),
    ("2026A", "mspm0", ("motor", "servo", "led", "key")),
    ("2022C", "stm32", ("motor", "oled")),
)


def _preselect_for(topic: str, platform: str):
    """真实题面 × 真实模块库 → 预筛结果（与网页推荐路由同参同源）。

    行形态取瘦身形态（`lean_copy`）——路由在预筛前把清单行换成瘦身行，探针
    `.scratch/library-audit/probe_guard_cases.py` 同款，否则这里测的不是生产路径。
    """
    manifests = list_modules(MODULES_DIR)
    summaries = build_manifest_summaries(
        [m for m in manifests if platform in m.platforms]
    )
    lean = [s.lean_copy() for s in summaries]
    text = (TOPICS_DIR / topic / "topic.md").read_text(encoding="utf-8", errors="replace")
    return preselect_module_summaries(
        lean, text, load_wordlist(), MODULE_SUMMARY_BYTES
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


def test_preselect_whole_library_visible_for_real_topics():
    """真实库全库可见不变量（工单 02 的核心）：瘦身行让 86/84 条全进预算，
    预筛不再截断——「关键模块靠排名挤进前 N」变成「全库都在」，可见性不再
    依赖题面词命中。库长大到装不下时这条红（重新记账或再瘦身），不会静默
    回退成「部分模块不可见」。
    """
    for topic in ("2024H", "2021F", "2026C"):
        result = _preselect_for(topic, "stm32")
        assert not result.truncated, (
            f"{topic}/stm32 预筛仍截断：可见 {len(result.summaries)}/{result.total} 条"
        )
        assert len(result.summaries) == result.total
        # 全库瘦身行确实在预算内（与 manifest 层字节账同口径，双保险）
        total = sum(wire_size(s.to_line()) + 1 for s in result.summaries)
        assert total <= MODULE_SUMMARY_BYTES
