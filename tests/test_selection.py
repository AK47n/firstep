"""模块选择与依赖解析：递归展开、无环、生成前的平台可用性警告。

解析与警告都是纯函数（不碰磁盘），直接构造 manifest 驱动。
"""

import json

import pytest

from contest_generator.manifest import ModuleManifest, PlatformEntry
from contest_generator.reference_library import ReferenceError, get_reference
from contest_generator.selection import (
    WARNING_HARDWARE_BOUND,
    WARNING_MISSING,
    WARNING_UNVERIFIED,
    DependencyCycleError,
    PlatformWarning,
    UnknownModuleError,
    associated_references,
    check_platform_warnings,
    read_reference_fulltext,
    reference_suggestions,
    resolve_dependencies,
    resolve_selection,
)
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
