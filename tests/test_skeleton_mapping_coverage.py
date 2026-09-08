"""骨架「模块 → 例程」映射守卫（工单 preselect-visibility/03-05）。

背景：骨架阶段按选中模块自动关联参考例程，依据是 `reference_library.
MODULE_PERIPHERAL_TERMS`（slug → 词项，词项经 `PERIPHERAL_TERMS` 激活条目）。
修复前 93 个模块里只有 18 个有映射、其中 6 个是死映射（词项在参考库标题 0
命中），选中其余模块时一条例程都关联不到。

本文件钉住三条契约（全部现在就绿）：

1. **映射的硬契约**：每个映射的词项必须在 `PERIPHERAL_TERMS` 里（词表单源）；
   映射的 slug 必须在库内（防手改漂移）。
2. **映射不是死的**：每个有映射的模块至少有一个词项（含同义词组）命中至少
   一条参考条目标题——按模块算，不按词项算（`step_motor` 的 `step` 0 命中、
   `motor` 2 命中 = 有效）。
3. **不留沉默缺口**：全库每个模块要么有映射、要么在库内数据
   `MODULE_REFERENCE_EXEMPT` 里显式豁免并写明理由；豁免与映射不得同时存在。

复测探针：`.scratch/library-audit/probe_term_effect.py`、`probe_term_titles.py`、
`probe_unmapped.py`、`probe_exempt_facts.py`、`probe_sweep_terms.py`。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.library import list_modules
from contest_generator.reference_library import (
    MODULE_PERIPHERAL_TERMS,
    MODULE_REFERENCE_EXEMPT,
    PERIPHERAL_TERMS,
    _entry_score,
    _synonym_group,
    list_references,
)

ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = ROOT / "library" / "modules"
REFERENCES_DIR = ROOT / "library" / "references"


def _all_slugs() -> set[str]:
    return {m.slug for m in list_modules(MODULES_DIR)}


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


def test_every_mapped_module_hits_at_least_one_reference_title():
    """每个有映射的模块至少有一个词项（含同义词组）命中参考条目标题。

    判据按**模块**算而不是按词项算：关联的判据是「激活词项 ∩ 条目标题」，
    模块只要有一个词项能关联到例程，这条映射就不是死的（`step_motor` 的
    `step` 0 命中、`motor` 2 命中 = 有效；全部词项 0 命中 = 死映射）。

    命中判定**走生产路径**（`_entry_score`，与 `related_references` 同一实现：
    标题按 `[-_\\s()（）]` 拆 token 后 `_term_matches_token`）——不用
    `_text_has_term` 另立一套（两者在 `adc12 单次转换` 这类前缀 + 数字尾巴
    形态上不等价，测试会比生产更严、工单 04 补条目后出假红）。
    """
    entries = list_references(REFERENCES_DIR)
    dead: list[str] = []
    for slug, terms in sorted(MODULE_PERIPHERAL_TERMS.items()):
        activated = frozenset(_synonym_group(term)[0] for term in terms)
        if any(_entry_score(entry, activated) > 0 for entry in entries):
            continue
        dead.append(f"{slug}（{'、'.join(terms)} 全 0 命中）")
    assert not dead, (
        "以下模块的映射词项（含同义词组）在参考库标题里全部 0 命中，"
        "选中它关联不到任何例程：" + "；".join(dead)
    )


def test_exempt_slugs_exist_in_library():
    """豁免表引用的模块必须真实存在（防手改漂移）。"""
    slugs = _all_slugs()
    unknown = sorted(slug for slug in MODULE_REFERENCE_EXEMPT if slug not in slugs)
    assert not unknown, f"豁免表引用了库中不存在的模块：{'、'.join(unknown)}"


def test_exempt_entries_state_a_reason():
    """豁免必须写明理由（空理由 = 沉默缺口，等于没声明）。"""
    blank = sorted(
        slug for slug, reason in MODULE_REFERENCE_EXEMPT.items() if not reason.strip()
    )
    assert not blank, f"豁免必须写明理由，以下为空：{'、'.join(blank)}"


def test_exempt_and_mapping_are_mutually_exclusive():
    """同一模块不得既豁免又有映射（两边打架 = 库错误）。"""
    both = sorted(
        slug for slug in MODULE_REFERENCE_EXEMPT if slug in MODULE_PERIPHERAL_TERMS
    )
    assert not both, (
        f"以下模块既有映射又声明豁免（两边打架，库错误）：{'、'.join(both)}"
    )


def test_every_module_is_mapped_or_explicitly_exempt():
    """全库模块要么有映射、要么在库内豁免表里（缺口 = 选中它时关联不到例程）。"""
    slugs = _all_slugs()
    unmapped = sorted(
        slug
        for slug in slugs
        if slug not in MODULE_PERIPHERAL_TERMS and slug not in MODULE_REFERENCE_EXEMPT
    )
    assert not unmapped, (
        f"{len(unmapped)}/{len(slugs)} 个模块无映射且未声明豁免："
        f"{'、'.join(unmapped)}"
    )


def test_mapping_slugs_exist_in_library():
    """映射的 slug 必须命中库内模块（防手改漂移——库删模块后映射成了死引用）。"""
    slugs = _all_slugs()
    problems = [slug for slug in MODULE_PERIPHERAL_TERMS if slug not in slugs]
    assert not problems, f"映射引用了库中不存在的模块：{'、'.join(sorted(problems))}"
