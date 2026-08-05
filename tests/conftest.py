"""pytest fixtures：假母版、假模块库、假 LLM、生成器调用助手。

生成流程经 contest_generator.generator 驱动：落盘接缝是 generate，完整流程
（选模块 → 母版 → 生成 → 摘要）的接缝是 generate_project。构造器与假件
本体在 tests/fakes.py。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.generator import generate
from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32, PatcherRegistry
from tests.fakes import (
    MAIN_SKELETON,
    FakeLLM,
    make_fake_ccs_master_project,
    make_fake_master_project,
    make_fake_module_library,
    make_fake_stm32_projects,
)


@pytest.fixture
def fake_module_library(tmp_path) -> Path:
    return make_fake_module_library(tmp_path / "module_library")


@pytest.fixture
def fake_master_project(tmp_path) -> Path:
    return make_fake_master_project(tmp_path / "master")


@pytest.fixture
def fake_ccs_master_project(tmp_path) -> Path:
    return make_fake_ccs_master_project(tmp_path / "ccs_master")


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_stm32_projects(tmp_path) -> tuple[Path, Path]:
    """母版提炼素材：proj-a / proj-b 两个同平台旧工程（见 fakes.py 构造）。"""
    return make_fake_stm32_projects(tmp_path / "old_projects")


@pytest.fixture
def fake_masters_dir(tmp_path) -> Path:
    """母版库目录（母版提炼结果入库的地方）。"""
    return tmp_path / "masters"


@pytest.fixture
def stm32_selection(fake_module_library) -> list[ModuleManifest]:
    """stm32 生成的默认选中集：dht11 + oled。"""
    return [
        ModuleManifest.load(fake_module_library / slug) for slug in ("dht11", "oled")
    ]


@pytest.fixture
def mspm0_selection(fake_module_library) -> list[ModuleManifest]:
    """mspm0 生成的默认选中集：dht11 + delay（都有 mspm0 版本）。"""
    return [
        ModuleManifest.load(fake_module_library / slug) for slug in ("dht11", "delay")
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


@pytest.fixture
def make_ccs_project(fake_ccs_master_project, fake_module_library, mspm0_selection):
    """生成器核心调用助手：默认 mspm0 + dht11/delay + 假 CCS 母版。"""

    def _make(
        *,
        platform: str = PLATFORM_MSPM0,
        manifests: list[ModuleManifest] | None = None,
        master_project_dir: Path | None = None,
        output_dir: Path,
        main_c_content: str = MAIN_SKELETON,
        registry: PatcherRegistry | None = None,
    ) -> Path:
        return generate(
            platform=platform,
            manifests=mspm0_selection if manifests is None else manifests,
            module_library_dir=fake_module_library,
            master_project_dir=master_project_dir or fake_ccs_master_project,
            output_dir=output_dir,
            main_c_content=main_c_content,
            registry=registry,
        )

    return _make
