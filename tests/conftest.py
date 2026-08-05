"""pytest fixtures：假母版、假模块库、假 LLM、生成器调用助手。

全功能只通过一个接缝测试——生成器核心（contest_generator.generator.generate）。
构造器与假件本体在 tests/fakes.py。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.generator import generate
from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_STM32, PatcherRegistry
from tests.fakes import MAIN_SKELETON, FakeLLM, make_fake_master_project, make_fake_module_library


@pytest.fixture
def fake_module_library(tmp_path) -> Path:
    return make_fake_module_library(tmp_path / "module_library")


@pytest.fixture
def fake_master_project(tmp_path) -> Path:
    return make_fake_master_project(tmp_path / "master")


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def stm32_selection(fake_module_library) -> list[ModuleManifest]:
    """stm32 生成的默认选中集：dht11 + oled。"""
    return [
        ModuleManifest.load(fake_module_library / slug) for slug in ("dht11", "oled")
    ]


@pytest.fixture
def make_project(fake_master_project, fake_module_library, stm32_selection):
    """生成器核心调用助手：默认 stm32 + dht11/oled + 假母版，测试用关键字覆盖。"""

    def _make(
        *,
        platform: str = PLATFORM_STM32,
        manifests: list[ModuleManifest] | None = None,
        master_project_dir: Path | None = None,
        output_dir: Path,
        main_c_content: str = MAIN_SKELETON,
        registry: PatcherRegistry | None = None,
    ) -> Path:
        return generate(
            platform=platform,
            manifests=stm32_selection if manifests is None else manifests,
            module_library_dir=fake_module_library,
            master_project_dir=master_project_dir or fake_master_project,
            output_dir=output_dir,
            main_c_content=main_c_content,
            registry=registry,
        )

    return _make
