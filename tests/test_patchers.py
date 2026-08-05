"""平台修改器注册表：按平台名解析修改器，核心只依赖注册表。"""

import pytest

from contest_generator.keil import KeilPatcher
from contest_generator.patchers import (
    PLATFORM_MSPM0,
    PLATFORM_STM32,
    NullPatcher,
    PatcherRegistry,
    UnknownPlatformError,
    default_registry,
)


def test_register_and_get_returns_same_patcher():
    registry = PatcherRegistry()
    patcher = NullPatcher()

    registry.register(PLATFORM_STM32, patcher)

    assert registry.get(PLATFORM_STM32) is patcher


def test_late_registration_overwrites_previous():
    registry = PatcherRegistry()
    registry.register(PLATFORM_STM32, NullPatcher())
    replacement = NullPatcher()

    registry.register(PLATFORM_STM32, replacement)

    assert registry.get(PLATFORM_STM32) is replacement


def test_get_unknown_platform_raises_and_lists_known_platforms():
    registry = PatcherRegistry()
    registry.register(PLATFORM_STM32, NullPatcher())

    with pytest.raises(UnknownPlatformError, match=PLATFORM_STM32):
        registry.get("nonexistent")


def test_default_registry_wires_keil_patcher_for_stm32():
    registry = default_registry()

    assert isinstance(registry.get(PLATFORM_STM32), KeilPatcher)
    assert isinstance(registry.get(PLATFORM_MSPM0), NullPatcher)
