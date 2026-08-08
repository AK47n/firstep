"""模块选择与依赖解析：递归展开、无环、生成前的平台可用性警告；模块推荐域
（工单 10）：题面逐句编号、收敛轮提示词与收敛循环驱动（两轮一致即停 / 轮数
上限 / 补问暂停 / 两级注入）。

解析与警告都是纯函数（不碰磁盘），直接构造 manifest 驱动；收敛驱动用
FakeLLM 记录调用形状断言（不碰网络）。
"""

import json
from typing import Mapping, Sequence

import pytest

from contest_generator.events import EVENT_CONVERGED, EVENT_ROUND, ProgressEvent
from contest_generator.manifest import ModuleManifest, PlatformEntry
from contest_generator.reference_library import ReferenceError, get_reference
from contest_generator.selection import (
    WARNING_HARDWARE_BOUND,
    WARNING_MISSING,
    WARNING_UNVERIFIED,
    DependencyCycleError,
    FunctionRequirement,
    ModuleSelection,
    OutOfLibrarySuggestion,
    PlatformWarning,
    ReferenceSuggestion,
    UnknownModuleError,
    _number_topic_sentences,
    _revision_prompt,
    associated_references,
    check_platform_warnings,
    read_reference_fulltext,
    reference_suggestions,
    resolve_dependencies,
    resolve_selection,
    select_modules_convergent,
)
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


def test_associated_references_empty_without_matches(tmp_path):
    assert (
        associated_references(
            tmp_path / "references", topic_key="2021F", manifests=()
        )
        == ()
    )


def test_associated_references_missing_root_is_empty(tmp_path):
    assert associated_references(tmp_path / "nonexistent", topic_key="2026C") == ()


def test_reference_suggestions_carry_title_and_one_line_description(tmp_path):
    reference_root = make_fake_reference_library(tmp_path / "references")
    entries = associated_references(reference_root, topic_key="2026C")

    suggestions = reference_suggestions(entries)

    assert suggestions[0].id == TOPIC_REFERENCE_ID
    assert suggestions[0].title == "2026C 数字钥匙参考例程"
    assert suggestions[0].description == "2026C 钥匙题配套例程"


def test_read_reference_fulltext_assembles_files_with_headers(tmp_path):
    """两级注入第二级的素材形状：带文件名标注的拼接文本。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entry = get_reference(reference_root, TOPIC_REFERENCE_ID)

    text = read_reference_fulltext(reference_root, entry)

    assert "// ---- key_example.c ----" in text
    assert "/* 数字钥匙例程 */" in text


def test_read_reference_fulltext_skips_binary_files_with_note(tmp_path):
    """二进制素材（说明书 PDF 等）读不了文本：跳过并标注，不让生成流程整体失败。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entry_dir = reference_root / KIT_REFERENCE_ID
    meta = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    meta["files"] = ["manual.txt", "manual.pdf"]
    (entry_dir / "manual.pdf").write_bytes(b"%PDF\x00\x01\x02binary")
    (entry_dir / "reference.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    text = read_reference_fulltext(
        reference_root, get_reference(reference_root, KIT_REFERENCE_ID)
    )

    assert "套件接线与使用说明全文" in text
    assert "manual.pdf" in text  # 二进制素材带标注而非静默消失


def test_read_reference_fulltext_missing_file_raises(tmp_path):
    """条目素材文件缺失 = 库损坏：大声失败（宁可大声失败也不带病进上下文）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    (reference_root / TOPIC_REFERENCE_ID / "key_example.c").unlink()

    with pytest.raises(ReferenceError, match="无法读取"):
        read_reference_fulltext(
            reference_root, get_reference(reference_root, TOPIC_REFERENCE_ID)
        )


def test_read_reference_fulltext_rejects_unsafe_path(tmp_path):
    """坏条目（files 含 .. 越界路径）借条目 id 逃出库目录：入口拦截大声失败。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entry_dir = reference_root / TOPIC_REFERENCE_ID
    meta = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    meta["files"] = ["../evil.c"]
    (entry_dir / "reference.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ReferenceError, match="路径非法"):
        read_reference_fulltext(
            reference_root, get_reference(reference_root, TOPIC_REFERENCE_ID)
        )


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


def test_revision_prompt_carries_previous_layer_and_self_check_instruction():
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
    assert "自检修订" in prompt  # 自检指令在场


# ---------------------------------------------------------------------------
# 工单 10：收敛循环驱动（多轮调用 / 轮数上限 / 补问 / 两级注入）
# ---------------------------------------------------------------------------


class _RecordingConvergenceLLM(FakeLLM):
    """记录型假 LLM：按脚本返回选择序列，记录每次调用（问题文本 / 清单 / 全文）。"""

    def __init__(self, selections: Sequence[ModuleSelection]) -> None:
        super().__init__()
        self._queue = list(selections)
        self.calls: list[tuple[str, tuple[str, ...], tuple[str, ...], dict[str, str]]] = []

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[str],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
    ) -> ModuleSelection:
        self.calls.append(
            (
                problem_text,
                tuple(manifest_summaries),
                tuple(reference.id for reference in references),
                dict(reference_fulltexts or {}),
            )
        )
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


def test_convergent_question_stops_immediately():
    """补问路径：模型拿不准（questions 非空）→ 本轮即停，不再收敛确认。"""
    fake = _RecordingConvergenceLLM(
        [
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


