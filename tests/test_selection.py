"""模块选择与依赖解析：递归展开、无环、生成前的平台可用性警告；模块推荐域
（工单 10）：题面逐句编号、收敛轮提示词与收敛循环驱动（两轮一致即停 / 轮数
上限 / 补问暂停 / 两级注入）；推荐两阶段编排（工单 recommend-orchestration-
homing/01）：澄清先行 → 收敛 → done 载荷组装（run_recommendation）。

解析与警告都是纯函数（不碰磁盘），直接构造 manifest 驱动；收敛驱动用
FakeLLM 记录调用形状断言（不碰网络）。
"""

from pathlib import Path
from queue import Queue
from typing import Mapping, Sequence

import pytest

from contest_generator.events import (
    EVENT_CONVERGED,
    EVENT_DONE,
    EVENT_QUESTION,
    EVENT_ROUND,
    ProgressEvent,
)
from contest_generator.generator import TopicContext
from contest_generator.manifest import ManifestSummary, ModuleManifest, PlatformEntry
from contest_generator.reference_library import PLATFORM_ANY, ReferenceEntry, add_reference
from contest_generator.selection import (
    WARNING_HARDWARE_BOUND,
    WARNING_MISSING,
    WARNING_UNVERIFIED,
    DependencyCycleError,
    FunctionRequirement,
    ManualReferenceError,
    ModuleInstance,
    ModuleSelection,
    OutOfLibrarySuggestion,
    PlatformWarning,
    REFERENCE_SOURCE_AUTO,
    REFERENCE_SOURCE_MANUAL,
    ReferenceSuggestion,
    SelectionError,
    UnknownModuleError,
    _functional_layer_key,
    _number_topic_sentences,
    _revision_prompt,
    associated_references,
    build_module_selection,
    check_platform_warnings,
    filter_manifests_by_platform,
    manual_reference_admission,
    reference_suggestions,
    resolve_dependencies,
    resolve_selection,
    run_recommendation,
    select_modules_convergent,
)
from contest_generator.sse import SseEmitter
from contest_generator.wordlist import HardwareWordGroup
from tests.fakes import FakeLLM
from tests.generate_wiring_fakes import (
    KIT_REFERENCE_ID,
    OTHER_REFERENCE_ID,
    TOPIC_REFERENCE_ID,
    UWB_REFERENCE_ID,
    make_fake_reference_library,
    make_kit_candidate_module,
    make_topic_specific_module,
)

PLATFORM_STM32 = "stm32"
PLATFORM_MSPM0 = "mspm0"


def _manifest(
    slug: str, deps: tuple[str, ...] = (), platforms: dict | None = None
) -> ModuleManifest:
    return ModuleManifest(
        slug=slug,
        description=f"{slug} 功能说明",
        dependencies=deps,
        platforms=platforms or {},
    )


def _entry(verified: bool = True, hardware_bound: bool = False) -> PlatformEntry:
    return PlatformEntry(files=("a.c", "a.h"), verified=verified, hardware_bound=hardware_bound)


def _by_slug(*manifests: ModuleManifest) -> dict[str, ModuleManifest]:
    return {m.slug: m for m in manifests}


# ---------------------------------------------------------------------------
# resolve_dependencies：按 manifest 递归展开依赖
# ---------------------------------------------------------------------------


def test_resolve_includes_transitive_dependencies_in_dependency_first_order():
    a = _manifest("a")
    b = _manifest("b", deps=("a",))
    c = _manifest("c", deps=("a", "b"))  # a 经两条路径到达，只出现一次

    result = resolve_dependencies(["c"], _by_slug(a, b, c))

    assert [m.slug for m in result] == ["a", "b", "c"]


def test_resolve_preserves_chosen_order_between_independent_modules():
    a = _manifest("a")
    b = _manifest("b", deps=("a",))
    x = _manifest("x")

    result = resolve_dependencies(["x", "b"], _by_slug(a, b, x))

    assert [m.slug for m in result] == ["x", "a", "b"]


def test_resolve_chosen_slug_that_is_already_a_dependency_not_duplicated():
    a = _manifest("a")
    b = _manifest("b", deps=("a",))

    result = resolve_dependencies(["b", "a"], _by_slug(a, b))

    assert [m.slug for m in result] == ["a", "b"]


def test_resolve_empty_selection_returns_empty():
    assert resolve_dependencies([], {}) == ()


def test_resolve_detects_dependency_cycle_with_path():
    a = _manifest("a", deps=("b",))
    b = _manifest("b", deps=("a",))

    with pytest.raises(DependencyCycleError, match="a -> b -> a"):
        resolve_dependencies(["a"], _by_slug(a, b))


def test_resolve_detects_self_dependency_cycle():
    a = _manifest("a", deps=("a",))

    with pytest.raises(DependencyCycleError, match="a -> a"):
        resolve_dependencies(["a"], _by_slug(a))


def test_resolve_unknown_chosen_slug_raises():
    with pytest.raises(UnknownModuleError, match="ghost"):
        resolve_dependencies(["ghost"], {})


def test_resolve_unknown_dependency_slug_raises():
    a = _manifest("a", deps=("ghost",))

    with pytest.raises(UnknownModuleError, match="ghost"):
        resolve_dependencies(["a"], _by_slug(a))


# ---------------------------------------------------------------------------
# check_platform_warnings：生成前的平台可用性检查
# ---------------------------------------------------------------------------


def test_verified_module_gives_no_warning():
    dht11 = _manifest("dht11", platforms={PLATFORM_STM32: _entry(verified=True)})

    assert check_platform_warnings(["dht11"], PLATFORM_STM32, _by_slug(dht11)) == ()


def test_embedded_in_master_entry_gives_no_missing_warning():
    """空 files 平台条目（实现内嵌母版）= 该平台有版本：不再误报 missing。"""
    oled = _manifest(
        "oled",
        platforms={PLATFORM_STM32: PlatformEntry(files=(), verified=True)},
    )

    assert check_platform_warnings(["oled"], PLATFORM_STM32, _by_slug(oled)) == ()


def test_module_missing_target_platform_version_warns():
    oled = _manifest("oled", platforms={PLATFORM_STM32: _entry()})

    warnings = check_platform_warnings(["oled"], PLATFORM_MSPM0, _by_slug(oled))

    assert warnings == (
        PlatformWarning("oled", WARNING_MISSING, "模块 oled 缺少平台 mspm0 的版本，生成将失败——请移除或换模块"),
    )


def test_unverified_module_warns():
    dht11 = _manifest("dht11", platforms={PLATFORM_STM32: _entry(verified=False)})

    warnings = check_platform_warnings(["dht11"], PLATFORM_STM32, _by_slug(dht11))

    assert len(warnings) == 1
    assert warnings[0].kind == WARNING_UNVERIFIED
    assert warnings[0].slug == "dht11"
    assert "未验证" in warnings[0].message


def test_hardware_bound_module_warns():
    lcd = _manifest("lcd", platforms={PLATFORM_STM32: _entry(hardware_bound=True)})

    warnings = check_platform_warnings(["lcd"], PLATFORM_STM32, _by_slug(lcd))

    assert len(warnings) == 1
    assert warnings[0].kind == WARNING_HARDWARE_BOUND
    assert warnings[0].slug == "lcd"
    assert "硬件绑定" in warnings[0].message


def test_unverified_and_hardware_bound_produce_two_warnings():
    gps = _manifest(
        "gps", platforms={PLATFORM_STM32: _entry(verified=False, hardware_bound=True)}
    )

    warnings = check_platform_warnings(["gps"], PLATFORM_STM32, _by_slug(gps))

    assert {w.kind for w in warnings} == {WARNING_UNVERIFIED, WARNING_HARDWARE_BOUND}


def test_warnings_follow_input_order():
    ok = _manifest("ok", platforms={PLATFORM_STM32: _entry()})
    bad = _manifest("bad", platforms={})

    warnings = check_platform_warnings(
        ["bad", "ok", "bad"], PLATFORM_STM32, _by_slug(ok, bad)
    )

    assert [w.slug for w in warnings] == ["bad", "bad"]


def test_warnings_unknown_slug_raises():
    with pytest.raises(UnknownModuleError, match="ghost"):
        check_platform_warnings(["ghost"], PLATFORM_STM32, {})


# ---------------------------------------------------------------------------
# resolve_selection：加载库 + 展开依赖 + 平台警告的组合操作
# ---------------------------------------------------------------------------


def test_resolve_selection_composes_library_resolution_and_warnings(
    fake_module_library,
):
    resolved = resolve_selection(
        fake_module_library, PLATFORM_MSPM0, ["dht11", "oled"]
    )

    # 依赖 delay 被带入，排序与 resolve_dependencies 一致（依赖先于使用者）
    assert [m.slug for m in resolved.manifests] == ["delay", "dht11", "oled"]
    # oled 缺 mspm0 版本 → missing 警告；dht11 依赖的 delay 双平台都有
    assert {w.slug for w in resolved.warnings} == {"oled"}
    assert next(w for w in resolved.warnings).kind == WARNING_MISSING


def test_resolve_selection_propagates_unknown_module(fake_module_library):
    with pytest.raises(UnknownModuleError, match="ghost"):
        resolve_selection(fake_module_library, PLATFORM_STM32, ["ghost"])


# ---------------------------------------------------------------------------
# 工单 03：候选清单带参考文件（两级注入第一级）+ 全文回读（第二级）
# ---------------------------------------------------------------------------


def test_associated_references_matches_topic_and_kit_anchors(tmp_path):
    """候选清单的参考段：锚定该赛题编号或模块套件的条目都带上，无关锚定不
    出现（套件锚定从候选模块的 kit 词表收集）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    make_topic_specific_module(tmp_path / "modules")

    entries = associated_references(
        reference_root,
        topic_key="2026C",
        manifests=[ModuleManifest.load(tmp_path / "modules" / "lock_control")],
    )

    assert [e.id for e in entries] == [TOPIC_REFERENCE_ID, KIT_REFERENCE_ID]
    assert OTHER_REFERENCE_ID not in [e.id for e in entries]


def test_associated_references_includes_candidate_kits(tmp_path):
    """普通候选模块（非该题专用）的套件锚定同样进清单：候选 = 模块库全量，
    该题没有专用模块时套件参考文件不缺失（评审 c2 修复的回归锚点）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    make_topic_specific_module(tmp_path / "modules")
    make_kit_candidate_module(tmp_path / "modules")

    entries = associated_references(
        reference_root,
        topic_key="2026C",
        manifests=[
            ModuleManifest.load(tmp_path / "modules" / "lock_control"),
            ModuleManifest.load(tmp_path / "modules" / "uwb"),
        ],
    )

    assert [e.id for e in entries] == [
        TOPIC_REFERENCE_ID,
        KIT_REFERENCE_ID,
        UWB_REFERENCE_ID,
    ]


def _platform_anchored_references(reference_root) -> Path:
    """三条同锚定（topic=2024H）不同平台的条目：mspm0 / stm32 / any。"""
    for platform in ("mspm0", "stm32", "any"):
        add_reference(
            reference_root,
            title=f"巡线模板（{platform}）",
            type="参考例程",
            description=f"{platform} 平台配套例程",
            anchor_kind="topic",
            anchor_value="2024H",
            platform=platform,
            files={"xunji.c": f"/* {platform} */\n"},
            kit_vocabulary=(),
        )
    return reference_root


def test_associated_references_filters_topic_hits_by_platform(tmp_path):
    """topic 命中按平台统一过滤（工单 01）：不匹配跳过、any 全进、空串不过滤。"""
    reference_root = _platform_anchored_references(tmp_path / "references")

    mspm0 = associated_references(
        reference_root, topic_key="2024H", platform="mspm0"
    )
    assert [e.id for e in mspm0] == ["巡线模板-any", "巡线模板-mspm0"]

    stm32 = associated_references(
        reference_root, topic_key="2024H", platform="stm32"
    )
    assert [e.id for e in stm32] == ["巡线模板-any", "巡线模板-stm32"]

    unfiltered = associated_references(reference_root, topic_key="2024H")
    assert [e.id for e in unfiltered] == [
        "巡线模板-any",
        "巡线模板-mspm0",
        "巡线模板-stm32",
    ]


def test_associated_references_filters_kit_hits_by_platform(tmp_path):
    """kit 命中同样按平台过滤（双保险：topic 与 kit 锚定统一判据）。"""
    reference_root = tmp_path / "references"
    reference_root.mkdir()
    add_reference(
        reference_root,
        title="ALX 串口例程",
        type="例程工程",
        description="STM32F1 串口例程",
        anchor_kind="kit",
        anchor_value=KIT_REFERENCE_ID,
        platform="stm32",
        files={"uart.c": "/* 串口 */\n"},
        kit_vocabulary=(KIT_REFERENCE_ID,),
    )
    add_reference(
        reference_root,
        title="地猛星例程",
        type="例程工程",
        description="mspm0 例程",
        anchor_kind="kit",
        anchor_value=KIT_REFERENCE_ID,
        platform="mspm0",
        files={"m0.c": "/* m0 */\n"},
        kit_vocabulary=(KIT_REFERENCE_ID,),
    )

    # manifests 提供套件 → kit 命中；platform 过滤对 kit 命中同样生效
    manifest = ModuleManifest(
        slug="alx_uart",
        description="ALX 套件串口模块",
        platforms={
            "stm32": PlatformEntry(files=("uart.c",), kit=KIT_REFERENCE_ID)
        },
    )
    stm32 = associated_references(
        reference_root, manifests=[manifest], platform="stm32"
    )
    assert [e.id for e in stm32] == ["ALX-串口例程"]

    mspm0 = associated_references(
        reference_root, manifests=[manifest], platform="mspm0"
    )
    assert [e.id for e in mspm0] == ["地猛星例程"]

    # 空串 = 不过滤（向后兼容，skeleton / generate 传缺省）
    all_entries = associated_references(reference_root, manifests=[manifest])
    assert [e.id for e in all_entries] == ["ALX-串口例程", "地猛星例程"]


def test_associated_references_old_entries_without_platform_always_pass(tmp_path):
    """旧条目（无 platform 字段，缺省 any）：任何平台过滤都进清单（兼容）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")

    for platform in ("mspm0", "stm32"):
        entries = associated_references(
            reference_root, topic_key="2026C", platform=platform
        )
        assert [e.id for e in entries] == [
            TOPIC_REFERENCE_ID,
            KIT_REFERENCE_ID,
        ]


def test_associated_references_empty_without_matches(tmp_path):
    assert (
        associated_references(
            tmp_path / "references", topic_key="2021F", manifests=()
        )
        == ()
    )


def test_associated_references_missing_root_is_empty(tmp_path):
    assert associated_references(tmp_path / "nonexistent", topic_key="2026C") == ()


def test_filter_manifests_by_platform_keeps_only_available_platforms():
    """模块候选按平台过滤（工单 ref-platform-filter 模块侧对偶）：mspm0 请求
    只留 platforms 含 mspm0 的条目（stm32-only 模块不再作为可勾选候选）。"""
    dual = _manifest("dual", platforms={"stm32": _entry(), "mspm0": _entry()})
    stm32_only = _manifest("stm32_only", platforms={"stm32": _entry()})
    mspm0_only = _manifest("mspm0_only", platforms={"mspm0": _entry()})

    mspm0 = filter_manifests_by_platform([dual, stm32_only, mspm0_only], "mspm0")
    assert [m.slug for m in mspm0] == ["dual", "mspm0_only"]

    stm32 = filter_manifests_by_platform([dual, stm32_only, mspm0_only], "stm32")
    assert [m.slug for m in stm32] == ["dual", "stm32_only"]


def test_filter_manifests_by_platform_empty_string_is_no_filter():
    """platform 空串 = 不过滤（向后兼容，骨架 / 生成传缺省）——与参考库
    associated_references 的 platform 判据同款语义。"""
    manifests = [_manifest("dual", platforms={"stm32": _entry(), "mspm0": _entry()})]
    assert filter_manifests_by_platform(manifests, "") == tuple(manifests)


def test_filter_manifests_by_platform_no_platform_version_excluded():
    """无任何平台版本（空 platforms）的条目：平台过滤下不列为候选（生成必
    失败，推荐出来是浪费模型视线）；空串不过滤时保持现状（不引入新行为）。"""
    bare = _manifest("bare")  # platforms 缺省空
    dual = _manifest("dual", platforms={"stm32": _entry(), "mspm0": _entry()})

    assert filter_manifests_by_platform([bare, dual], "stm32") == (dual,)
    assert [m.slug for m in filter_manifests_by_platform([bare, dual], "")] == [
        "bare",
        "dual",
    ]


def test_reference_suggestions_carry_title_and_one_line_description(tmp_path):
    reference_root = make_fake_reference_library(tmp_path / "references")
    entries = associated_references(reference_root, topic_key="2026C")

    suggestions = reference_suggestions(entries)

    assert suggestions[0].id == TOPIC_REFERENCE_ID
    assert suggestions[0].title == "2026C 数字钥匙参考例程"
    assert suggestions[0].description == "2026C 钥匙题配套例程"


def _suggestion(
    entry_id: str, title: str = "参考标题", description: str = "一句话简介"
) -> ReferenceSuggestion:
    return ReferenceSuggestion(id=entry_id, title=title, description=description)


# ---------------------------------------------------------------------------
# 工单 10：题面逐句编号 + 收敛轮提示词
# ---------------------------------------------------------------------------


def test_number_topic_sentences_splits_on_sentence_breaks():
    text = "设计并制作送药小车。它需要识别数字；并声光提示。能避障？\n请按要求完成。"

    numbered = _number_topic_sentences(text)

    assert numbered == (
        "1. 设计并制作送药小车。\n"
        "2. 它需要识别数字；\n"
        "3. 并声光提示。\n"
        "4. 能避障？\n"
        "5. 请按要求完成。"
    )


def test_number_topic_sentences_single_sentence_and_empty():
    assert _number_topic_sentences("只有一句") == "1. 只有一句"
    assert _number_topic_sentences("   ") == "   "  # 无可分句子原样返回


def test_revision_prompt_carries_previous_layer_and_verification_instruction():
    numbered = "1. 设计送药小车。"
    previous = (
        FunctionRequirement(
            requirement="识别数字",
            sentence_index=2,
            modules=("ml_mpu6050",),
            suggestions=(OutOfLibrarySuggestion(name="视觉模块", examples=("K230",)),),
        ),
    )

    prompt = _revision_prompt(numbered, previous)

    assert prompt.startswith(numbered)
    assert "上一轮功能需求层" in prompt
    assert "句子2「识别数字」" in prompt
    assert "库内命中：ml_mpu6050" in prompt
    assert "库外建议：视觉模块" in prompt
    # 核验式指令在场（工单 recommend-speedup/01）：题面原文是唯一裁判，仅
    # 确凿证据才改、无证据条目逐字照抄（句子编号照抄不改）——旧"自检修订"
    # 让模型每轮都改、永不收敛
    assert "逐条核验" in prompt
    assert "题面原文是唯一裁判" in prompt
    assert "逐字照抄上一轮原文输出" in prompt
    assert "句子编号照抄不改" in prompt
    assert "无证据支持的改动（改写措辞也算）本身是脑补" in prompt


# ---------------------------------------------------------------------------
# 工单 10：收敛循环驱动（多轮调用 / 轮数上限 / 补问 / 两级注入）
# ---------------------------------------------------------------------------


class _RecordingConvergenceLLM(FakeLLM):
    """记录型假 LLM：按脚本返回选择序列，记录每次调用（问题文本 / 清单 / 全文 /
    clarifications）。"""

    def __init__(self, selections: Sequence[ModuleSelection]) -> None:
        super().__init__()
        self._queue = list(selections)
        self.calls: list[
            tuple[
                str,
                tuple[ManifestSummary, ...],
                tuple[str, ...],
                dict[str, str],
                dict[str, str],
            ]
        ] = []
        self.clarifications: list[tuple[tuple[str, str], ...]] = []

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
    ) -> ModuleSelection:
        self.calls.append(
            (
                problem_text,
                tuple(manifest_summaries),
                tuple(reference.id for reference in references),
                dict(reference_fulltexts or {}),
                dict(manual_fulltexts or {}),
            )
        )
        self.clarifications.append(tuple(clarifications))
        return self._queue.pop(0)


def _requirement(text: str, sentence: int = 1) -> FunctionRequirement:
    return FunctionRequirement(requirement=text, sentence_index=sentence)


def _selection_with(
    requirement: str,
    *,
    sentence: int = 1,
    modules: tuple[str, ...] = (),
    suggestions: tuple[str, ...] = (),
    questions: tuple[str, ...] = (),
) -> ModuleSelection:
    return ModuleSelection(
        modules=modules,
        reasons={slug: "" for slug in modules},
        requirements=(
            FunctionRequirement(
                requirement=requirement,
                sentence_index=sentence,
                modules=modules,
                suggestions=tuple(
                    OutOfLibrarySuggestion(name=name) for name in suggestions
                ),
            ),
        ),
        questions=questions,
    )


def test_convergent_stops_after_two_identical_rounds():
    """收敛命中：两轮功能需求层一致 → 第 2 轮即收敛，结果 = 第 2 轮产物。"""
    fake = _RecordingConvergenceLLM(
        [_selection_with("识别数字", suggestions=("视觉模块",))] * 2
    )
    events: list[ProgressEvent] = []

    result = select_modules_convergent(
        fake, "送药小车题", ["- dht11: 温湿度"], progress_emitter=events.append
    )

    assert len(fake.calls) == 2
    assert result.requirements == (
        FunctionRequirement(
            requirement="识别数字",
            sentence_index=1,
            suggestions=(OutOfLibrarySuggestion(name="视觉模块"),),
        ),
    ) and result.questions == ()
    assert [e.type for e in events] == [EVENT_ROUND, EVENT_ROUND, EVENT_CONVERGED]
    assert events[2].round == 2
    assert [e.round for e in events] == [1, 2, 2]
    assert all(e.round_total == 4 for e in events[:2])


def test_convergent_reaches_round_limit_without_convergence():
    """轮数上限：每轮功能需求层都变 → 4 轮后以最后一轮为准（不再多问）。"""
    fake = _RecordingConvergenceLLM(
        [
            _selection_with("需求一"),
            _selection_with("需求二"),
            _selection_with("需求三"),
            _selection_with("需求四"),
        ]
    )
    events: list[ProgressEvent] = []

    result = select_modules_convergent(
        fake, "题面", ["- dht11: 温湿度"], progress_emitter=events.append
    )

    assert len(fake.calls) == 4
    assert result.requirements == (_requirement("需求四"),)
    assert [e.type for e in events] == [EVENT_ROUND] * 4  # 未收敛，无 converged 事件


def test_convergent_second_round_carries_previous_layer_with_stable_numbering():
    """第 2 轮带上一轮功能需求层（自检修订依据）且题面编号跨轮稳定（收敛判定的
    对照句编号依赖它——编号漂移会让两轮"同一句"对不上号）。"""
    fake = _RecordingConvergenceLLM(
        [_selection_with("识别数字", sentence=2), _selection_with("识别数字", sentence=2)]
    )

    select_modules_convergent(fake, "送药小车。识别数字。", ["- dht11: 温湿度"])

    assert fake.calls[0][0] == "1. 送药小车。\n2. 识别数字。"
    round2_topic = fake.calls[1][0]
    assert round2_topic.startswith("1. 送药小车。\n2. 识别数字。\n")  # 编号未漂移
    assert "上一轮功能需求层" in round2_topic
    assert "句子2「识别数字」" in round2_topic


def test_convergent_short_marker_stops_with_previous_result():
    """核验轮短标记（工单 recommend-speedup-v2/01）：模型自报无修订
    （converged=True）→ 用上一轮结果提前停——省掉全量输出的核验轮。"""
    first = _selection_with("识别数字", suggestions=("视觉模块",))
    fake = _RecordingConvergenceLLM(
        [first, ModuleSelection(modules=(), reasons={}, converged=True)]
    )
    events: list[ProgressEvent] = []

    result = select_modules_convergent(
        fake, "送药小车题", ["- dht11: 温湿度"], progress_emitter=events.append
    )

    assert len(fake.calls) == 2  # 核验轮仍是真实调用（短输出），但不再需要第 3 轮
    assert result is first  # 自报一致 → 上一轮结果原样
    assert [e.type for e in events] == [EVENT_ROUND, EVENT_ROUND, EVENT_CONVERGED]


def test_convergent_short_marker_on_round_one_ignored():
    """第 1 轮出现 converged 标记（模型违反"仅核验轮可输出"指令）→ 当空结果
    忽略该字段，继续正常收敛比较（不提前停、不炸）。"""
    fake = _RecordingConvergenceLLM(
        [
            ModuleSelection(modules=(), reasons={}, converged=True),
            _selection_with("识别数字"),
            _selection_with("识别数字"),
        ]
    )

    result = select_modules_convergent(fake, "题面", ["- dht11: 温湿度"])

    assert len(fake.calls) == 3  # 轮1 当空结果，轮2/3 两轮一致收敛
    assert result.requirements == (_requirement("识别数字"),)


def test_convergent_respects_max_rounds_parameter():
    """max_rounds 参数（设置项透传）：未收敛时按上限停（默认 4，可调 2）。"""
    fake = _RecordingConvergenceLLM(
        [_selection_with("需求一"), _selection_with("需求二")]
    )

    result = select_modules_convergent(
        fake, "题面", ["- dht11: 温湿度"], max_rounds=2
    )

    assert len(fake.calls) == 2
    assert result.requirements == (_requirement("需求二"),)


def test_convergent_question_stops_immediately():
    """补问路径：模型拿不准（questions 非空）→ 本轮即停，不再收敛确认。"""
    fake = _RecordingConvergenceLLM(        [
            ModuleSelection(
                modules=(),
                reasons={},
                questions=("题面没有说明识别方式，用摄像头还是传感器？",),
            )
        ]
    )
    events: list[ProgressEvent] = []

    result = select_modules_convergent(
        fake, "题面", ["- dht11: 温湿度"], progress_emitter=events.append
    )

    assert len(fake.calls) == 1  # 补问后暂停，没有第 2 轮
    assert result.questions == ("题面没有说明识别方式，用摄像头还是传感器？",)
    assert [e.type for e in events] == [EVENT_ROUND]


def test_convergent_four_leds_with_instances_converges():
    """多实例收敛（工单 module-multi-instance/06）：「4 个指示灯」→ led×4
    （红/黄/绿/状态灯）两轮一致即收敛；实例清单随选择结果带出。"""
    instances = {
        "led": (
            ModuleInstance(name="红", variant="red"),
            ModuleInstance(name="黄", variant="yellow"),
            ModuleInstance(name="绿", variant="green"),
            ModuleInstance(name="状态灯", variant=""),
        )
    }
    selection = ModuleSelection(
        modules=("led",),
        reasons={"led": "4 个指示灯"},
        requirements=(
            FunctionRequirement(
                requirement="声光提示", sentence_index=4, modules=("led",)
            ),
        ),
        instances=instances,
    )
    fake = _RecordingConvergenceLLM([selection, selection])
    events: list[ProgressEvent] = []

    result = select_modules_convergent(
        fake, "作品需要 4 个指示灯。", ["- led: 指示灯"], progress_emitter=events.append
    )

    assert len(fake.calls) == 2  # 两轮一致即收敛
    assert result.instances == instances
    assert [e.type for e in events] == [EVENT_ROUND, EVENT_ROUND, EVENT_CONVERGED]


def test_functional_layer_key_distinguishes_instance_lists():
    """收敛判定键纳入实例清单（名称+变体）：实例变化 = 功能需求层变化
    （否则 led×4 与 led×3 会被判为一致提前收敛，实例猜测被第一轮锁死）。"""

    def make(instances: dict) -> ModuleSelection:
        return ModuleSelection(
            modules=("led",),
            reasons={},
            requirements=(
                FunctionRequirement(
                    requirement="指示灯", sentence_index=1, modules=("led",)
                ),
            ),
            instances=instances,
        )

    four = make(
        {
            "led": (
                ModuleInstance(name="红", variant="red"),
                ModuleInstance(name="状态灯", variant=""),
            )
        }
    )
    three = make({"led": (ModuleInstance(name="红", variant="red"),)})
    renamed = make(
        {
            "led": (
                ModuleInstance(name="红灯", variant="red"),
                ModuleInstance(name="状态灯", variant=""),
            )
        }
    )

    assert _functional_layer_key(four) != _functional_layer_key(three)  # 数量不同
    assert _functional_layer_key(four) != _functional_layer_key(renamed)  # 名称不同
    assert _functional_layer_key(four) == _functional_layer_key(four)


def test_convergent_round_one_two_level_fulltexts_carried_into_round_two():
    """两级注入在收敛循环内：第 1 轮点名全文 → 回读；第 2 轮收敛确认仍带已读
    全文（全文上下文不丢；恰好两级，不再注入新全文）。"""
    refs = [_suggestion("a", "A", "a")]
    fake = _RecordingConvergenceLLM(
        [
            ModuleSelection(
                modules=("dht11",),
                reasons={},
                reference_ids=("a",),
                requirements=(_requirement("识别数字"),),
            ),
            ModuleSelection(
                modules=("dht11",),
                reasons={},
                reference_ids=("a",),
                requirements=(_requirement("识别数字"),),
            ),
            ModuleSelection(
                modules=("dht11",),
                reasons={},
                reference_ids=("a",),
                requirements=(_requirement("识别数字"),),
            ),
        ]
    )
    read: list[str] = []

    def reader(entry_id: str) -> str:
        read.append(entry_id)
        return f"全文{entry_id}"

    select_modules_convergent(
        fake,
        "题面",
        ["- dht11: 温湿度"],
        references=refs,
        reader=reader,
    )

    assert read == ["a"]  # 只在第一级点名时回读一次
    assert fake.calls[0][3] == {}  # 第一级：只有清单
    assert fake.calls[1][3] == {"a": "全文a"}  # 第二级：带全文
    assert fake.calls[2][3] == {"a": "全文a"}  # 第 2 轮：已读全文照旧带上


def test_convergent_without_references_uses_old_signature():
    """无参考文件清单时退化：全程旧签名（2 参）调用——既有假 LLM（fakes.py
    只读）无需改动即可服务收敛循环（webapp 无历史赛题的基线）。"""
    fake = FakeLLM(selection=ModuleSelection(modules=(), reasons={}))

    result = select_modules_convergent(fake, "赛题", ["- dht11: 温湿度"])

    assert result.modules == ()
    # 收敛照常工作（旧契约无需求层 → 第 2 轮一致即收敛），旧签名假 LLM 未触发异常


def test_convergent_passes_clarifications_every_round():
    """收敛透传（工单 clarify-history-in-convergence）：澄清问答历史每轮
    select_modules 都收到同一份——收敛阶段补问的答案在用户回答重推后进入收敛
    prompt（题面后的独立段），不再换措辞反复问同一问题。"""
    history = (("识别方式？", "摄像头"), ("序号2缺失？", "已补全"))
    fake = _RecordingConvergenceLLM(
        [
            _selection_with("识别数字"),
            _selection_with("识别数字"),  # 第 2 轮一致 → 收敛
        ]
    )

    select_modules_convergent(
        fake, "送药小车。识别数字。", ["- dht11: 温湿度"], clarifications=history
    )

    assert len(fake.calls) == 2
    assert fake.clarifications == [history, history]  # 每轮同一份、保序


def test_convergent_without_clarifications_keeps_old_signature():
    """向后兼容：clarifications 缺省空 → 不传该关键字（旧签名调用，既有假
    LLM 零改动）；记录到的历史为空元组 = 旧行为。"""
    fake = _RecordingConvergenceLLM(
        [_selection_with("识别数字"), _selection_with("识别数字")]
    )

    select_modules_convergent(fake, "赛题", ["- dht11: 温湿度"])

    assert fake.clarifications == [(), ()]


def test_convergent_round_events_tolerate_failing_emitter():
    """发射器抛异常（旁路）→ 收敛主流程不受影响（与提炼进度同款 seam）。"""
    fake = _RecordingConvergenceLLM(
        [_selection_with("识别数字"), _selection_with("识别数字")]
    )

    def exploding(_event: ProgressEvent) -> None:
        raise RuntimeError("UI 消费失败")

    result = select_modules_convergent(
        fake, "题面", ["- dht11: 温湿度"], progress_emitter=exploding
    )

    assert result.requirements == (_requirement("识别数字"),)
    assert len(fake.calls) == 2



class _BudgetedRecommendationLLM:
    """推荐工作流假件：按调用数模拟共享累计预算。"""

    def __init__(self, *, max_attempts: int | None = None) -> None:
        self.max_attempts = max_attempts
        self.attempts = 0
        self.clarify_calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []
        self.select_calls: list[str] = []

    def _consume(self) -> None:
        if self.max_attempts is not None and self.attempts >= self.max_attempts:
            from contest_generator.llm import LLMError
            raise LLMError("LLM 工作流累计尝试次数预算已耗尽")
        self.attempts += 1

    def clarify(self, problem_text: str, clarifications: Sequence[tuple[str, str]]) -> tuple[str, ...]:
        self._consume()
        self.clarify_calls.append((problem_text, tuple(clarifications)))
        return ()

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
    ) -> ModuleSelection:
        self._consume()
        self.select_calls.append(problem_text)
        return _selection_with("识别数字", modules=("dht11",))


def test_run_recommendation_budget_accumulates_across_clarify_and_convergence():
    """推荐入口共享预算：clarify 与后续全部 select 调用累计记账。"""
    topic = TopicContext(
        key="",
        problem_text="送药小车。识别数字。",
        references=(),
        manifest_summaries=(ManifestSummary("dht11", "温湿度"),),
        suggestions=(),
        read_fulltext=lambda _entry_id: "",
    )
    llm = _BudgetedRecommendationLLM(max_attempts=2)
    events: Queue = Queue()
    emit = SseEmitter(events, terminal_timeout=1.0)

    from contest_generator.llm import LLMError
    with pytest.raises(LLMError, match="累计尝试次数预算已耗尽"):
        run_recommendation(topic, llm, emit=emit)

    assert llm.attempts == 2
    assert len(llm.clarify_calls) == 1
    assert len(llm.select_calls) == 1
    assert not [event for event in _drain_events(events) if not isinstance(event, ProgressEvent) and event[0] == "done"]


def test_run_recommendation_default_budget_compatibility_still_reaches_done():
    """缺省无限预算保持既有成功路径：clarify + 两轮收敛后正常 done。"""
    topic = TopicContext(
        key="",
        problem_text="送药小车。识别数字。",
        references=(),
        manifest_summaries=(ManifestSummary("dht11", "温湿度"),),
        suggestions=(),
        read_fulltext=lambda _entry_id: "",
    )
    llm = _BudgetedRecommendationLLM()
    events: Queue = Queue()
    emit = SseEmitter(events, terminal_timeout=1.0)

    run_recommendation(topic, llm, emit=emit)

    assert llm.attempts == 3
    done = [event[1] for event in _drain_events(events) if not isinstance(event, ProgressEvent) and event[0] == "done"]
    assert done and done[0]["modules"] == [{"slug": "dht11", "reason": ""}]

# ---------------------------------------------------------------------------
# 工单 06：模型输出 → ModuleSelection 解释链（域判决单址，随 build_module_selection
# 从 llm.py 迁入；断言与 match 文案随迁前逐字一致，错误类型 LLMError → SelectionError）
# ---------------------------------------------------------------------------

# 测试专用小词表（与包内默认词表解耦，契约测试自足）
WORDS = (
    HardwareWordGroup(category="视觉模块", models=("K230", "OpenMV")),
    HardwareWordGroup(category="声光提示器件", models=("LED", "蜂鸣器")),
)

REQUIREMENTS_RAW = {
    "requirements": [
        {
            "requirement": "识别数字",
            "sentence": 3,
            "modules": [
                {"slug": "dht11", "reason": "测温湿度"},
                {"slug": "oled", "reason": "显示结果"},
            ],
            "suggestions": [{"name": "视觉模块", "examples": ["K230", "OpenMV"]}],
        },
        {
            "requirement": "声光提示",
            "sentence": 5,
            "modules": [],
            "suggestions": [{"name": "蜂鸣器", "examples": []}],
        },
    ]
}


def test_build_selection_accepts_multiple_modules_with_reasons():
    result = build_module_selection(
        {
            "modules": [
                {"slug": "dht11", "reason": "测温湿度"},
                {"slug": "oled", "reason": "显示数据"},
            ]
        },
        known_slugs=("dht11", "oled"),
    )

    assert result.modules == ("dht11", "oled")
    assert result.reasons == {"dht11": "测温湿度", "oled": "显示数据"}


def test_build_selection_rejects_unknown_slug():
    with pytest.raises(SelectionError, match="不存在"):
        build_module_selection(
            {"modules": [{"slug": "wifi", "reason": "通信"}]},
            known_slugs=("dht11",),
        )


def test_build_selection_rejects_duplicate_slug():
    with pytest.raises(SelectionError, match="重复"):
        build_module_selection(
            {
                "modules": [
                    {"slug": "dht11", "reason": "a"},
                    {"slug": "dht11", "reason": "b"},
                ]
            },
            known_slugs=("dht11",),
        )


@pytest.mark.parametrize(
    "bad_raw",
    [
        {"modules": "dht11"},
        {"modules": [{"reason": "缺 slug"}]},
        {"modules": [{"slug": "dht11", "reason": 42}]},
    ],
)
def test_build_selection_rejects_malformed_module_entries(bad_raw):
    with pytest.raises(SelectionError):
        build_module_selection(bad_raw, known_slugs=("dht11",))


def test_build_selection_accepts_reference_ids():
    result = build_module_selection(
        {
            "modules": [{"slug": "dht11", "reason": "测温湿度"}],
            "references": ["key-example"],
        },
        known_slugs=("dht11",),
        known_reference_ids=("key-example",),
    )

    assert result.reference_ids == ("key-example",)


def test_build_selection_without_references_field_is_empty():
    result = build_module_selection({"modules": []}, known_slugs=())
    assert result.reference_ids == ()


def test_build_selection_rejects_reference_outside_suggestion_list():
    with pytest.raises(SelectionError, match="清单外"):
        build_module_selection(
            {"modules": [], "references": ["ghost"]},
            known_slugs=(),
            known_reference_ids=("key-example",),
        )


def test_build_selection_rejects_references_without_suggestion_list():
    """没给参考文件清单时模型报 references = 幻觉：大声失败。"""
    with pytest.raises(SelectionError, match="未提供"):
        build_module_selection(
            {"modules": [], "references": ["ghost"]},
            known_slugs=(),
        )


def test_build_selection_rejects_duplicate_reference_ids():
    with pytest.raises(SelectionError, match="重复"):
        build_module_selection(
            {"modules": [], "references": ["a", "a"]},
            known_slugs=(),
            known_reference_ids=("a",),
        )


def test_build_selection_requirements_derive_top_modules():
    """新契约：顶层 modules 由功能需求层机械派生（库内命中并集，保序、首见理由）
    ——模块必有需求支撑，顶层与需求层永不漂移。"""
    result = build_module_selection(
        REQUIREMENTS_RAW, known_slugs=("dht11", "oled"), hardware_words=WORDS
    )

    assert result.modules == ("dht11", "oled")
    assert result.reasons == {"dht11": "测温湿度", "oled": "显示结果"}
    assert result.requirements[0] == FunctionRequirement(
        requirement="识别数字",
        sentence_index=3,
        modules=("dht11", "oled"),
        suggestions=(
            OutOfLibrarySuggestion(name="视觉模块", examples=("K230", "OpenMV")),
        ),
    )
    assert result.requirements[1].suggestions == (
        OutOfLibrarySuggestion(name="蜂鸣器", examples=()),
    )


def test_build_selection_requirements_dedup_shared_module_across_requirements():
    """同一模块出现在两条需求里：顶层去重（首见理由保留），需求各自保留命中。"""
    raw = {
        "requirements": [
            {
                "requirement": "采集温湿度",
                "sentence": 1,
                "modules": [{"slug": "dht11", "reason": "测温"}],
            },
            {
                "requirement": "显示",
                "sentence": 2,
                "modules": [{"slug": "dht11", "reason": "数据来源"}],
            },
        ]
    }

    result = build_module_selection(raw, known_slugs=("dht11",), hardware_words=WORDS)

    assert result.modules == ("dht11",)
    assert result.reasons == {"dht11": "测温"}  # 首见理由
    assert [r.modules for r in result.requirements] == [("dht11",), ("dht11",)]


def test_build_selection_requirements_reject_unknown_module_slug():
    """需求层里的库外 slug 同样大声失败（与顶层 modules 校验同款严格）。"""
    with pytest.raises(SelectionError, match="不存在"):
        build_module_selection(
            {
                "requirements": [
                    {
                        "requirement": "识别数字",
                        "sentence": 1,
                        "modules": [{"slug": "k230_cam", "reason": "视觉"}],
                    }
                ]
            },
            known_slugs=("dht11",),
            hardware_words=WORDS,
        )


@pytest.mark.parametrize(
    "bad_raw",
    [
        {"requirements": "not a list"},
        {"requirements": [{"sentence": 1}]},  # 缺 requirement
        {"requirements": [{"requirement": "  ", "sentence": 1}]},
        {"requirements": [{"requirement": "需求"}]},  # 缺 sentence
        {"requirements": [{"requirement": "需求", "sentence": 0}]},
        {"requirements": [{"requirement": "需求", "sentence": -2}]},
        {"requirements": [{"requirement": "需求", "sentence": "0"}]},  # 数字字符串但非正数
        {"requirements": [{"requirement": "需求", "sentence": "abc"}]},  # 非数字字符串
        {"requirements": [{"requirement": "需求", "sentence": "1.5"}]},  # 非整数数字字符串
        {"requirements": [{"requirement": "需求", "sentence": 1.0}]},  # 浮点
        {"requirements": [{"requirement": "需求", "sentence": True}]},
        {"requirements": [{"requirement": "需求", "sentence": 1, "modules": "x"}]},
        {"requirements": [{"requirement": "需求", "sentence": 1, "modules": [{"reason": "缺 slug"}]}]},
        {"requirements": [{"requirement": "需求", "sentence": 1, "modules": [{"slug": "dht11", "reason": 42}]}]},
        {"requirements": [{"requirement": "需求", "sentence": 1, "modules": [{"slug": "dht11"}, {"slug": "dht11"}]}]},  # 需求内重复
    ],
)
def test_build_selection_rejects_malformed_requirements(bad_raw):
    with pytest.raises(SelectionError):
        build_module_selection(bad_raw, known_slugs=("dht11",), hardware_words=WORDS)


def test_build_selection_coerces_digit_string_sentence():
    """数字字符串 sentence 按语义无损强转 int（sentence 语义 = 正整数，不是形状）。

    真机实测：DeepSeek json_object 模式把数字标量序列化为字符串（24/24 条需求
    全是 "1" 这种形状），严格类型校验让整轮收敛当场失败——"1" 语义上就是正整数，
    强转不引入任何脑补风险；非数字字符串照旧大声失败（见 reject 参数化）。
    """
    raw = {
        "requirements": [
            {"requirement": "识别数字", "sentence": "1", "modules": []},
            {"requirement": "定位", "sentence": " 3 ", "modules": []},
        ]
    }

    result = build_module_selection(raw, known_slugs=(), hardware_words=WORDS)

    assert [r.sentence_index for r in result.requirements] == [1, 3]


def test_build_selection_requirements_parse_multi_instances():
    """多实例推荐（工单 module-multi-instance/06）：需求层模块条目带 instances
    数组（{name, variant}）→ ModuleSelection.instances（slug → 实例元组）；
    pin 不参与（AI 不猜，恒空串）。"""
    raw = {
        "requirements": [
            {
                "requirement": "声光提示",
                "sentence": 4,
                "modules": [
                    {
                        "slug": "led",
                        "reason": "4 个指示灯",
                        "instances": [
                            {"name": "红", "variant": "red"},
                            {"name": "黄", "variant": "yellow"},
                            {"name": "绿", "variant": "green"},
                            {"name": "状态灯", "variant": ""},
                        ],
                    }
                ],
            }
        ]
    }

    result = build_module_selection(
        raw,
        known_slugs=("led",),
        hardware_words=WORDS,
        multi_instance_slugs=("led",),
    )

    assert result.modules == ("led",)
    assert result.instances == {
        "led": (
            ModuleInstance(name="红", variant="red"),
            ModuleInstance(name="黄", variant="yellow"),
            ModuleInstance(name="绿", variant="green"),
            ModuleInstance(name="状态灯", variant=""),
        )
    }


def test_build_selection_plain_modules_parse_instances():
    """旧契约（无需求层）：顶层 modules 条目同样可带 instances（形状同需求层）。"""
    raw = {
        "modules": [
            {
                "slug": "led",
                "reason": "4 个指示灯",
                "instances": [{"name": "红", "variant": "red"}, {"name": "状态灯"}],
            }
        ]
    }

    result = build_module_selection(
        raw, known_slugs=("led",), multi_instance_slugs=("led",)
    )

    assert result.instances == {
        "led": (
            ModuleInstance(name="红", variant="red"),
            ModuleInstance(name="状态灯"),
        )
    }


def test_build_selection_instances_conflicting_across_requirements_rejected():
    """同一模块在两条需求里带了不同的实例清单 = 模型自相矛盾 → 大声失败
    （不一致比首见者赢更诚实——用户拿到的一定是自洽的猜测）。"""
    raw = {
        "requirements": [
            {
                "requirement": "状态显示",
                "sentence": 1,
                "modules": [
                    {
                        "slug": "led",
                        "reason": "指示灯",
                        "instances": [{"name": "红", "variant": "red"}],
                    }
                ],
            },
            {
                "requirement": "报警",
                "sentence": 2,
                "modules": [
                    {
                        "slug": "led",
                        "reason": "报警灯",
                        "instances": [
                            {"name": "红", "variant": "red"},
                            {"name": "黄", "variant": "yellow"},
                        ],
                    }
                ],
            },
        ]
    }

    with pytest.raises(SelectionError, match="不一致"):
        build_module_selection(
            raw, known_slugs=("led",), multi_instance_slugs=("led",)
        )


def test_build_selection_instances_identical_across_requirements_ok():
    """同一模块在两条需求里带相同实例清单：幂等接受（模型常把同一灯挂在
    多条需求下，不误伤）。"""
    same = [
        {"name": "红", "variant": "red"},
        {"name": "绿", "variant": "green"},
    ]
    raw = {
        "requirements": [
            {
                "requirement": "状态显示",
                "sentence": 1,
                "modules": [
                    {"slug": "led", "reason": "指示灯", "instances": list(same)}
                ],
            },
            {
                "requirement": "报警",
                "sentence": 2,
                "modules": [
                    {"slug": "led", "reason": "报警灯", "instances": list(same)}
                ],
            },
        ]
    }

    result = build_module_selection(
        raw, known_slugs=("led",), multi_instance_slugs=("led",)
    )

    assert result.instances == {
        "led": (
            ModuleInstance(name="红", variant="red"),
            ModuleInstance(name="绿", variant="green"),
        )
    }


@pytest.mark.parametrize(
    "bad_raw, multi_slugs, match",
    [
        # 非多实例模块带 instances = 能力校验拒绝（宁严勿假绿）
        (
            {
                "requirements": [
                    {
                        "requirement": "需求",
                        "sentence": 1,
                        "modules": [
                            {
                                "slug": "dht11",
                                "reason": "x",
                                "instances": [{"name": "红"}],
                            }
                        ],
                    }
                ]
            },
            ("led",),
            "不支持多实例",
        ),
        # 未提供能力清单（空）= 没有能力证据，同样大声失败
        (
            {
                "requirements": [
                    {
                        "requirement": "需求",
                        "sentence": 1,
                        "modules": [
                            {
                                "slug": "led",
                                "reason": "x",
                                "instances": [{"name": "红"}],
                            }
                        ],
                    }
                ]
            },
            (),
            "不支持多实例",
        ),
        # 旧契约顶层模块同样受能力校验
        (
            {"modules": [{"slug": "dht11", "reason": "x", "instances": [{"name": "红"}]}]},
            ("led",),
            "不支持多实例",
        ),
        (
            {
                "requirements": [
                    {
                        "requirement": "需求",
                        "sentence": 1,
                        "modules": [
                            {"slug": "led", "reason": "x", "instances": "x"}
                        ],
                    }
                ]
            },
            ("led",),
            "instances 必须是数组",
        ),
        (
            {
                "requirements": [
                    {
                        "requirement": "需求",
                        "sentence": 1,
                        "modules": [
                            {"slug": "led", "reason": "x", "instances": ["红"]}
                        ],
                    }
                ]
            },
            ("led",),
            r"instances\[0\] 必须是对象",
        ),
        (
            {
                "requirements": [
                    {
                        "requirement": "需求",
                        "sentence": 1,
                        "modules": [
                            {
                                "slug": "led",
                                "reason": "x",
                                "instances": [{"variant": "red"}],
                            }
                        ],
                    }
                ]
            },
            ("led",),
            "缺 name 或为空",
        ),
        (
            {
                "requirements": [
                    {
                        "requirement": "需求",
                        "sentence": 1,
                        "modules": [
                            {
                                "slug": "led",
                                "reason": "x",
                                "instances": [{"name": "  ", "variant": "red"}],
                            }
                        ],
                    }
                ]
            },
            ("led",),
            "缺 name 或为空",
        ),
        (
            {
                "requirements": [
                    {
                        "requirement": "需求",
                        "sentence": 1,
                        "modules": [
                            {
                                "slug": "led",
                                "reason": "x",
                                "instances": [{"name": "红", "variant": 42}],
                            }
                        ],
                    }
                ]
            },
            ("led",),
            "variant 必须是字符串",
        ),
    ],
)
def test_build_selection_rejects_invalid_instances(bad_raw, multi_slugs, match):
    with pytest.raises(SelectionError, match=match):
        build_module_selection(
            bad_raw,
            known_slugs=("led", "dht11"),
            multi_instance_slugs=multi_slugs,
        )


def test_build_selection_suggestion_name_hits_wordlist_model_or_category():
    """词表内型号与类别名都直接显示（命中 → 显示）。"""
    raw = {
        "requirements": [
            {
                "requirement": "识别数字",
                "sentence": 1,
                "modules": [],
                "suggestions": [
                    {"name": "K230", "examples": ["K230 模组"]},  # 型号条目
                    {"name": "视觉模块", "examples": ["OpenMV"]},  # 类别条目
                ],
            }
        ]
    }

    result = build_module_selection(raw, known_slugs=(), hardware_words=WORDS)

    suggestions = result.requirements[0].suggestions
    assert suggestions[0].name == "K230" and suggestions[0].degraded is False
    assert suggestions[1].name == "视觉模块" and suggestions[1].degraded is False


def test_build_selection_suggestion_off_wordlist_degrades_to_category():
    """词表外型号（模型给出词表内类别名）→ 降级为类别名显示（degraded）。"""
    raw = {
        "requirements": [
            {
                "requirement": "识别数字",
                "sentence": 1,
                "modules": [],
                "suggestions": [
                    {"name": "K210", "category": "视觉模块", "examples": ["OpenMV"]}
                ],
            }
        ]
    }

    result = build_module_selection(raw, known_slugs=(), hardware_words=WORDS)

    suggestion = result.requirements[0].suggestions[0]
    assert suggestion.name == "视觉模块"  # 降级后的类别名
    assert suggestion.degraded is True
    assert suggestion.examples == ("OpenMV",)


@pytest.mark.parametrize(
    "suggestion",
    [
        {"name": "K210"},  # 词表外且无 category
        {"name": "K210", "category": "随便什么"},  # category 不在词表
        {"name": "K210", "category": 42},
    ],
)
def test_build_selection_suggestion_off_wordlist_rejected(suggestion):
    """词表外型号无法降级（缺合法类别）→ 拒收（大声失败，与库内 slug 校验同源）。"""
    raw = {
        "requirements": [
            {
                "requirement": "识别数字",
                "sentence": 1,
                "modules": [],
                "suggestions": [suggestion],
            }
        ]
    }

    with pytest.raises(SelectionError, match="硬件词表"):
        build_module_selection(raw, known_slugs=(), hardware_words=WORDS)


def test_build_selection_suggestions_without_wordlist_rejected():
    """没给硬件词表时模型报库外建议 = 无法校验的编造：大声失败。"""
    raw = {
        "requirements": [
            {
                "requirement": "识别数字",
                "sentence": 1,
                "modules": [],
                "suggestions": [{"name": "视觉模块"}],
            }
        ]
    }

    with pytest.raises(SelectionError, match="词表"):
        build_module_selection(raw, known_slugs=())


def test_build_selection_questions_accepted():
    """拿不准向用户补问：questions 数组解析；纯补问输出（无需求层无模块）合法。"""
    raw = {"questions": ["题面没有说明识别方式，用摄像头还是传感器？"]}

    result = build_module_selection(raw, known_slugs=())

    assert result.questions == ("题面没有说明识别方式，用摄像头还是传感器？",)
    assert result.modules == ()


@pytest.mark.parametrize(
    "bad_questions",
    [
        {"questions": "不是数组"},
        {"questions": [42]},
        {"questions": [""]},
    ],
)
def test_build_selection_rejects_malformed_questions(bad_questions):
    with pytest.raises(SelectionError, match="questions"):
        build_module_selection(bad_questions, known_slugs=())


def test_build_selection_requirements_present_ignores_plain_modules():
    """模型同时输出 requirements 与顶层 modules（冗余）→ 以需求层派生的为准。"""
    raw = {
        "modules": [{"slug": "oled", "reason": "冗余"}],  # 与需求层不一致，应被忽略
        "requirements": [
            {
                "requirement": "采集温湿度",
                "sentence": 1,
                "modules": [{"slug": "dht11", "reason": "测温"}],
            }
        ],
    }

    result = build_module_selection(
        raw, known_slugs=("dht11", "oled"), hardware_words=WORDS
    )

    assert result.modules == ("dht11",)  # 派生为准


# ---------------------------------------------------------------------------
# 结构测试（防回退，先例 errors.py / 04 / 05 工单）：域判决归 selection 的边界 pin
# ---------------------------------------------------------------------------


def test_build_module_selection_consumed_by_llm():
    """消费 pin：域判决单址 = selection.build_module_selection；llm 侧只有机械
    提取 extract_module_selection_data（等号引用侧）。"""
    import contest_generator.llm as llm
    import contest_generator.selection as selection

    assert hasattr(selection, "build_module_selection")
    assert hasattr(llm, "extract_module_selection_data")


def test_validation_result_single_origin():
    """ValidationResult 定义单址 = library.py（llm 运行时同对象，import 源已切）。"""
    import contest_generator.library as library
    import contest_generator.llm as llm
    from pathlib import Path

    assert llm.ValidationResult is library.ValidationResult
    src_root = Path(llm.__file__).parent
    hits = [
        (path.name, line_no)
        for path in sorted(src_root.glob("*.py"))
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "class ValidationResult" in line
    ]
    assert [name for name, _ in hits] == ["library.py"]  # ValidationResult 的定义文件（唯一出处）


def test_domain_judgment_text_single_origin():
    """域判决文案单址：'不在硬件词表中' 唯一出处 = selection.py（llm 只做机械提取）。"""
    import contest_generator.llm as llm
    from pathlib import Path

    src_root = Path(llm.__file__).parent
    hits = [
        path.name
        for path in sorted(src_root.glob("*.py"))
        if "不在硬件词表中" in path.read_text(encoding="utf-8")
    ]
    assert hits == ["selection.py"]




# ---------------------------------------------------------------------------
# 工单 01：手动选参考资料（追加准入 + 全文直读 + 来源标注）
# ---------------------------------------------------------------------------


def test_manual_reference_admission_resolves_real_ids_preserving_order(tmp_path):
    """手动准入：请求的 id → 完整条目，保序返回（幻觉 id / 重复 id 大声失败）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")

    entries = manual_reference_admission(
        reference_root, [UWB_REFERENCE_ID, TOPIC_REFERENCE_ID]
    )

    assert [e.id for e in entries] == [UWB_REFERENCE_ID, TOPIC_REFERENCE_ID]
    assert entries[0].title == "UWB 套件例程"


def test_manual_reference_admission_rejects_unknown_id(tmp_path):
    """幻觉 id（库中不存在）大声失败：不猜测、不静默忽略（对齐严格校验精神）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")

    with pytest.raises(ManualReferenceError, match="不存在"):
        manual_reference_admission(reference_root, ["幻觉 id"])


def test_manual_reference_admission_rejects_duplicate_id(tmp_path):
    """同一次请求重复 id 大声失败（与 _parse_reference_ids 拒绝重复同款）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")

    with pytest.raises(ManualReferenceError, match="重复"):
        manual_reference_admission(
            reference_root, [TOPIC_REFERENCE_ID, TOPIC_REFERENCE_ID]
        )


def test_manual_reference_admission_empty_is_empty(tmp_path):
    assert manual_reference_admission(tmp_path / "references", ()) == ()


def test_reference_suggestions_carry_source_marker(tmp_path):
    """来源标注：手动准入的条目转建议带 manual 标记（prompt 清单行按它标注）；
    缺省 = auto（既有形状不变）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entries = manual_reference_admission(reference_root, [TOPIC_REFERENCE_ID])

    suggestions = reference_suggestions(entries, source=REFERENCE_SOURCE_MANUAL)

    assert suggestions[0].source == REFERENCE_SOURCE_MANUAL
    assert suggestions[0].id == TOPIC_REFERENCE_ID
    assert reference_suggestions(entries)[0].source == REFERENCE_SOURCE_AUTO


def test_convergent_manual_fulltexts_carried_into_every_round():
    """手动全文直读（工单 01）：第 1 轮第一级就带（全文直读强制，无需模型点名）；
    第 2 轮确认轮照旧带上（全文上下文不丢）。"""
    refs = [_suggestion("a", "A", "a")]
    fake = _RecordingConvergenceLLM(
        [_selection_with("识别数字", modules=("dht11",))] * 2
    )
    manual = {"m": "手动条目全文"}

    select_modules_convergent(
        fake,
        "题面",
        ["- dht11: 温湿度"],
        references=refs,
        reader=lambda entry_id: f"全文{entry_id}",
        manual_fulltexts=manual,
    )

    assert [call[4] for call in fake.calls] == [manual, manual]  # 每轮都带手动全文
    assert fake.calls[0][3] == {}  # 第一级：手动全文已带，锚定全文未点名（selection 无 reference_ids）


def test_convergent_manual_and_anchored_fulltexts_coexist():
    """手动全文与锚定两级并存：第一级带手动全文，点名锚定条目回读进第二级（两级
    协议照旧），手动全文在各次调用都带上。"""
    refs = [_suggestion("a", "A", "a")]
    fake = _RecordingConvergenceLLM(
        [
            ModuleSelection(
                modules=("dht11",),
                reasons={},
                reference_ids=("a",),
                requirements=(_requirement("识别数字"),),
            ),
            _selection_with("识别数字", modules=("dht11",)),
            _selection_with("识别数字", modules=("dht11",)),  # 第 2 轮收敛确认
        ]
    )
    manual = {"m": "手动全文"}
    read: list[str] = []

    def reader(entry_id: str) -> str:
        read.append(entry_id)
        return f"全文{entry_id}"

    select_modules_convergent(
        fake,
        "题面",
        ["- dht11: 温湿度"],
        references=refs,
        reader=reader,
        manual_fulltexts=manual,
    )

    assert read == ["a"]  # 只有锚定条目被点名回读（手动条目已全文）
    assert fake.calls[0][4] == manual  # 第一级（先清单）带手动全文
    assert fake.calls[1][3] == {"a": "全文a"}  # 第二级：点名回读全文
    assert fake.calls[1][4] == manual  # 第二级手动全文照旧
    assert fake.calls[2][4] == manual  # 第 2 轮确认轮照旧


def test_convergent_manual_only_without_references_uses_extended_signature():
    """no-topic + 手动：references 恒空时手动全文仍进上下文（扩展签名调用）；
    不传 manual_fulltexts = 旧 2 参签名（既有假 LLM 兼容）。"""
    fake = _RecordingConvergenceLLM(
        [_selection_with("识别数字"), _selection_with("识别数字")]
    )
    manual = {"m": "手动全文"}

    select_modules_convergent(fake, "题面", ["- dht11: 温湿度"], manual_fulltexts=manual)

    assert len(fake.calls) == 2
    assert all(call[2] == () for call in fake.calls)  # 清单恒空（无锚定）
    assert all(call[4] == manual for call in fake.calls)


# ---------------------------------------------------------------------------
# 推荐两阶段编排（run_recommendation，工单 recommend-orchestration-homing/01）：
# 澄清先行 → 收敛 → done 载荷组装。用真实 SseEmitter + Queue 记录事件序列断言
# 逐字形状（进度事件 = ProgressEvent，终态 = (kind, dict) 与运行器队列一致）。
# ---------------------------------------------------------------------------


def _run_recommendation(
    topic: TopicContext,
    llm: FakeLLM,
    clarifications: Sequence[tuple[str, str]] = (),
) -> tuple[SseEmitter, Queue]:
    """直调 run_recommendation，返回 (emitter, 事件队列)（同线程无竞态）。"""
    events: Queue = Queue()
    emit = SseEmitter(events, terminal_timeout=1.0)
    run_recommendation(topic, llm, clarifications, emit=emit)
    return emit, events


def _drain_events(events: Queue) -> list:
    items = []
    while not events.empty():
        items.append(events.get_nowait())
    return items


def _event_kinds(items: list) -> list[str]:
    """事件序列的类型词表：进度事件取 type，终态取 kind。"""
    return [
        item.type if isinstance(item, ProgressEvent) else item[0] for item in items
    ]


def _topic(
    key: str = "",
    *,
    references: Sequence[ReferenceEntry] = (),
    manual_references: Sequence[ReferenceEntry] = (),
) -> TopicContext:
    """最小装配素材：收敛与载荷组装够用的字段，其余取安全缺省。"""
    return TopicContext(
        key=key,
        problem_text="送药小车。识别数字。",
        references=tuple(references),
        manifest_summaries=(),
        suggestions=(),
        read_fulltext=lambda entry_id: "",
        manual_references=tuple(manual_references),
    )


def _reference(
    entry_id: str, title: str, *, platform: str = PLATFORM_ANY
) -> ReferenceEntry:
    return ReferenceEntry(
        id=entry_id,
        title=title,
        type="例程工程",
        description="",
        anchor_kind="topic",
        anchor_value="2021F",
        files=(),
        platform=platform,
    )


def test_run_recommendation_clarify_questions_end_with_question_only():
    """首跑无历史澄清阶段先行：clarify 仍有疑问 → 只发 question 终态、无 round
    事件（澄清阶段不属于收敛轮次，补问不再作废已跑轮次）。"""
    llm = FakeLLM(clarify_questions=("具体要识别什么数字？",))

    _, events = _run_recommendation(_topic(), llm)

    assert llm.clarify_calls == [("送药小车。识别数字。", ())]
    assert _drain_events(events) == [
        ("question", {"questions": ["具体要识别什么数字？"]})
    ]


def test_run_recommendation_with_history_skips_clarify_gate():
    """有澄清历史（工单 recommend-speedup/01）：跳过 clarify 门——零 clarify
    调用，直进收敛循环（select 每轮带历史 kwarg）；两轮一致即收敛。"""
    history = (("识别方式？", "摄像头"),)
    fake = _RecordingConvergenceLLM(
        [_selection_with("识别数字"), _selection_with("识别数字")]
    )

    _, events = _run_recommendation(_topic(), fake, history)

    assert fake.clarify_calls == []  # 有历史：clarify 门被跳过（省一次串行调用）
    assert len(fake.calls) == 2  # 直进收敛循环（两轮一致收敛）
    assert fake.clarifications == [history, history]  # 每轮 kwarg 原样透传历史
    assert _event_kinds(_drain_events(events)) == [
        EVENT_ROUND,
        EVENT_ROUND,
        EVENT_CONVERGED,
        EVENT_DONE,
    ]


def test_run_recommendation_convergence_questions_end_with_question_event():
    """澄清空 + 收敛循环内模型拿不准（questions 非空）→ round 进度照发、
    question 收尾（不以 done 结束）。"""
    llm = FakeLLM(
        selection=ModuleSelection(
            modules=(),
            reasons={},
            questions=("题面没有说明识别方式，用摄像头还是传感器？",),
        )
    )

    _, events = _run_recommendation(_topic(), llm)

    items = _drain_events(events)
    assert _event_kinds(items) == [EVENT_ROUND, EVENT_QUESTION]
    assert items[-1] == (
        "question",
        {"questions": ["题面没有说明识别方式，用摄像头还是传感器？"]},
    )


def test_run_recommendation_done_payload_verbatim():
    """收敛成功 → done 载荷逐字：modules/reasons、requirements（to_dict 形状）、
    topic.key 非空带 topic_id、references = auto ∪ manual 并集去重（同一条目
    只出现一次，手动优先标注）platform 随条目带出。"""
    llm = FakeLLM(
        selection=ModuleSelection(
            modules=("dht11",),
            reasons={"dht11": "测温湿度"},
            requirements=(
                FunctionRequirement(
                    requirement="温湿度采集",
                    sentence_index=2,
                    modules=("dht11",),
                    suggestions=(
                        OutOfLibrarySuggestion(
                            name="视觉模块", examples=("K230", "OpenMV")
                        ),
                    ),
                ),
            ),
        )
    )
    auto = _reference("ref-auto", "锚定参考", platform=PLATFORM_STM32)
    overlap = _reference("ref-both", "双重参考", platform=PLATFORM_MSPM0)
    manual = _reference("ref-manual", "手动参考", platform=PLATFORM_ANY)

    _, events = _run_recommendation(
        _topic(
            key="2021F",
            references=(auto, overlap),
            manual_references=(manual, overlap),  # ref-both 既锚定又手动
        ),
        llm,
    )

    items = _drain_events(events)
    assert _event_kinds(items) == [EVENT_ROUND, EVENT_ROUND, EVENT_CONVERGED, EVENT_DONE]
    data = items[-1][1]
    assert data == {
        "modules": [{"slug": "dht11", "reason": "测温湿度"}],
        "requirements": [
            {
                "requirement": "温湿度采集",
                "sentence": 2,
                "modules": ["dht11"],
                "suggestions": [
                    {"name": "视觉模块", "examples": ["K230", "OpenMV"], "degraded": False}
                ],
            }
        ],
        "topic_id": "2021F",
        "references": [
            {"id": "ref-auto", "title": "锚定参考", "source": "auto", "platform": PLATFORM_STM32},
            {"id": "ref-manual", "title": "手动参考", "source": "manual", "platform": PLATFORM_ANY},
            {"id": "ref-both", "title": "双重参考", "source": "manual", "platform": PLATFORM_MSPM0},
        ],
    }


def test_run_recommendation_no_topic_key_omits_topic_fields():
    """no-topic 形（key 空）：done 载荷无 topic_id；references 清单恒空时为 []
    （键常驻，前端透明闭环照常消费）。"""
    llm = FakeLLM(
        selection=ModuleSelection(modules=("dht11",), reasons={"dht11": "测温湿度"})
    )

    _, events = _run_recommendation(_topic(), llm)

    data = _drain_events(events)[-1][1]
    assert data == {
        "modules": [{"slug": "dht11", "reason": "测温湿度"}],
        "requirements": [],
        "references": [],
    }


def test_run_recommendation_done_payload_includes_instances():
    """done 载荷带 instances（工单 module-multi-instance/06）：slug → 实例
    数组（{name, variant, pin}，pin 恒空 = 自动分配）——前端据此回填实例卡；
    无实例的选择不落 instances 键（旧载荷逐字节不变，见 verbatim 测试）。"""
    llm = FakeLLM(
        selection=ModuleSelection(
            modules=("led",),
            reasons={"led": "4 个指示灯"},
            instances={
                "led": (
                    ModuleInstance(name="红", variant="red"),
                    ModuleInstance(name="状态灯", variant=""),
                )
            },
        )
    )

    _, events = _run_recommendation(_topic(), llm)

    data = _drain_events(events)[-1][1]
    assert data["instances"] == {
        "led": [
            {"name": "红", "variant": "red", "pin": ""},
            {"name": "状态灯", "variant": "", "pin": ""},
        ]
    }
