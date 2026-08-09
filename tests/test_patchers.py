"""平台修改器注册表：按平台名解析修改器，核心只依赖注册表。"""

import pytest

from contest_generator.ccs import CcsPatcher, include_search_dirs as ccs_include_search_dirs
from contest_generator.keil import KeilPatcher, include_search_dirs as keil_include_search_dirs
from contest_generator.patchers import (
    PLATFORM_MSPM0,
    PLATFORM_STM32,
    PatcherRegistry,
    UnknownPlatformError,
    default_registry,
    include_search_dirs,
)
from tests.fakes import (
    RecordingPatcher,
    make_fake_ccs_master_project,
    make_fake_master_project,
)


def test_register_and_get_returns_same_patcher():
    registry = PatcherRegistry()
    patcher = RecordingPatcher()

    registry.register(PLATFORM_STM32, patcher)

    assert registry.get(PLATFORM_STM32) is patcher


def test_late_registration_overwrites_previous():
    registry = PatcherRegistry()
    registry.register(PLATFORM_STM32, RecordingPatcher())
    replacement = RecordingPatcher()

    registry.register(PLATFORM_STM32, replacement)

    assert registry.get(PLATFORM_STM32) is replacement


def test_get_unknown_platform_raises_and_lists_known_platforms():
    registry = PatcherRegistry()
    registry.register(PLATFORM_STM32, RecordingPatcher())

    with pytest.raises(UnknownPlatformError, match=PLATFORM_STM32):
        registry.get("nonexistent")


def test_default_registry_wires_real_patchers_for_both_platforms():
    registry = default_registry()

    assert isinstance(registry.get(PLATFORM_STM32), KeilPatcher)
    assert isinstance(registry.get(PLATFORM_MSPM0), CcsPatcher)


def test_include_search_dirs_dispatches_stm32_to_keil(tmp_path):
    project = make_fake_master_project(tmp_path / "keil_proj")

    assert include_search_dirs(PLATFORM_STM32, project) == keil_include_search_dirs(project)


def test_include_search_dirs_dispatches_mspm0_to_ccs(tmp_path):
    project = make_fake_ccs_master_project(tmp_path / "ccs_proj")

    assert include_search_dirs(PLATFORM_MSPM0, project) == ccs_include_search_dirs(project)


def test_include_search_dirs_unknown_platform_raises(tmp_path):
    with pytest.raises(UnknownPlatformError, match="未知平台.*esp32"):
        include_search_dirs("esp32", tmp_path)
