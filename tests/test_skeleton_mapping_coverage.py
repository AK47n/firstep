"""骨架「模块 → 例程」映射守卫（第 3 批第 3 项的缺口记录）。

背景：骨架阶段按选中模块自动关联参考例程，依据是 `reference_library.
MODULE_PERIPHERAL_TERMS`（slug → 词项，词项经 `PERIPHERAL_TERMS` 激活条目）。
实测只有 **18/93** 个模块有映射，其余模块选中后关联不到任何例程。

本文件把两件事分开钉住：

1. **映射的硬契约（现在就绿）**：每个映射的词项必须在 `PERIPHERAL_TERMS` 里
   （词表单源），且**每个词项必须至少命中一条参考条目标题**——写进去却关联不到
   任何例程的映射等于没写。这条对既有 18 个映射成立，也是后续扩映射的验收线。
2. **覆盖率缺口（当前 xfail）**：全库模块要么有映射、要么在「明确不映射」名单里。
   当前 75 个模块既没映射也不在名单里，故标记 `xfail(strict=True)`。

为什么覆盖率缺口没在本轮修：扩映射需要词项，而 75 个未映射模块需要的词项
（气压/称重/颜色/气体/光照/指纹/语音/触摸/摇杆…）大部分不在 `PERIPHERAL_TERMS`，
且参考库 148 条标题里 29/57 个词项 0 命中（oled/lcd/key/led/beep/servo 全 0）——
扩词表属「预筛评分与匹配粒度」批次，两者同批做才有意义（见
`.scratch/library-hookup-and-invariants/spec.md`「范围外」）。复测探针：
`.scratch/library-audit/probe_term_effect.py`、`probe_term_titles.py`。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.library import list_modules
from contest_generator.reference_library import (
    MODULE_PERIPHERAL_TERMS,
    PERIPHERAL_TERMS,
    _synonym_group,
    _text_has_term,
    list_references,
)

ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = ROOT / "library" / "modules"
REFERENCES_DIR = ROOT / "library" / "references"

# 明确「不映射」的模块：内部件（库内以头文件/工具形态存在，不是用户会挑的
# 器件，也不该把例程关联引到它们身上）。名单与词表挂接判据同口径
# （tests/test_wordlist.py::_INTERNAL_SLUGS）。
NO_MAPPING_SLUGS = (
    "adc", "delay", "filter", "uart", "config", "debug_uart", "digit_uart",
    "imu_uart", "zigbee_uart", "zigbee_uart_key", "huidu", "ntb_time",
)


def _all_slugs() -> set[str]:
    return {m.slug for m in list_modules(MODULES_DIR)}


def _titles() -> list[str]:
    return [entry.title for entry in list_references(REFERENCES_DIR)]


def test_module_mapping_terms_are_in_vocabulary():
    """映射的词项必须在 PERIPHERAL_TERMS 内（词表单源，既有断言同款但独立成条：
    扩映射时先加词项再写映射，顺序错了这里就红）。"""
    problems = [
        f"{slug} → {term}"
        for slug, terms in sorted(MODULE_PERIPHERAL_TERMS.items())
        for term in terms
        if term not in PERIPHERAL_TERMS
    ]
    assert not problems, f"映射词项不在词表内：{'、'.join(problems)}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "既有 18 个映射里有 9 个词项在参考库标题 0 命中（beep/key/led/oled/servo/"
        "step 及中文同义词——参考库缺这些器件的例程条目），选中这些模块时骨架"
        "关联不到任何例程。修法是补参考条目内容或改映射口径，属后续批次；"
        "修好后自动转绿，转绿时摘掉本标记（复测：probe_term_titles.py）"
    ),
)
def test_module_mapping_terms_hit_at_least_one_reference_title():
    """映射的每个词项（或其同义词组）必须至少命中一条参考条目标题。

    骨架关联的判据是「激活词项 ∩ 条目标题」——词项在参考库里 0 命中时，这条
    映射永远关联不到例程，等于没写。命中判定按词项所属同义词组整体算（题面
    「循迹」经组桥接到标题「巡线」是设计内的命中形态）。扩映射时按此逐项验证
    （探针：`.scratch/library-audit/probe_term_titles.py`）。"""
    titles = [title.lower() for title in _titles()]
    problems = [
        f"{slug} → {term}"
        for slug, terms in sorted(MODULE_PERIPHERAL_TERMS.items())
        for term in terms
        if not any(
            _text_has_term(title, synonym)
            for synonym in _synonym_group(term)
            for title in titles
        )
    ]
    assert not problems, (
        "映射词项（含同义词组）在参考库标题里 0 命中（关联不到例程）："
        + "、".join(problems)
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "骨架映射只覆盖 18/93 个模块：75 个模块既无映射也不在「不映射」名单里。"
        "扩映射依赖词表项扩展（属预筛评分与匹配粒度批次）——修好后自动转绿，"
        "转绿时摘掉本标记（复测：.scratch/library-audit/probe_term_effect.py）"
    ),
)
def test_every_module_is_mapped_or_explicitly_exempt():
    """全库模块要么有映射、要么在明确「不映射」名单里（缺口 = 选中它时关联不到例程）。"""
    slugs = _all_slugs()
    unmapped = sorted(
        slug
        for slug in slugs
        if slug not in MODULE_PERIPHERAL_TERMS and slug not in NO_MAPPING_SLUGS
    )
    assert not unmapped, (
        f"{len(unmapped)}/{len(slugs)} 个模块无骨架映射且未声明豁免："
        f"{'、'.join(unmapped)}"
    )


def test_mapping_slugs_exist_in_library():
    """映射的 slug 必须命中库内模块（防手改漂移——库删模块后映射成了死引用）。"""
    slugs = _all_slugs()
    problems = [slug for slug in MODULE_PERIPHERAL_TERMS if slug not in slugs]
    assert not problems, f"映射引用了库中不存在的模块：{'、'.join(sorted(problems))}"
