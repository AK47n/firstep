"""模块选择与依赖解析：递归展开、无环、生成前的平台可用性警告。

解析与警告都是纯函数（不碰磁盘），直接构造 manifest 驱动。
"""

import pytest

from contest_generator.manifest import ModuleManifest, PlatformEntry
from contest_generator.selection import (
    WARNING_HARDWARE_BOUND,
    WARNING_MISSING,
    WARNING_UNVERIFIED,
    DependencyCycleError,
    PlatformWarning,
    UnknownModuleError,
    check_platform_warnings,
    resolve_dependencies,
    resolve_selection,
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
