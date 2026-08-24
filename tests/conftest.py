"""pytest fixtures：假母版、假模块库、假 LLM、生成器调用助手。

生成流程经 contest_generator.generator 驱动：落盘接缝是 generate，完整流程
（选模块 → 母版 → 生成 → 摘要）的接缝是 generate_project。构造器与假件
本体在 tests/fakes.py。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._desktop_cleanup import cleanup_desktop_test_artifacts

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
        output_dir, _, _ = generate(
            platform=platform,
            manifests=stm32_selection if manifests is None else manifests,
            module_library_dir=fake_module_library,
            master_project_dir=master_project_dir or fake_master_project,
            output_dir=output_dir,
            main_c_content=main_c_content,
            registry=registry,
        )
        return output_dir

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
        output_dir, _, _ = generate(
            platform=platform,
            manifests=mspm0_selection if manifests is None else manifests,
            module_library_dir=fake_module_library,
            master_project_dir=master_project_dir or fake_ccs_master_project,
            output_dir=output_dir,
            main_c_content=main_c_content,
            registry=registry,
        )
        return output_dir

    return _make


# ---------------------------------------------------------------------------
# 桌面测试产物清理（收尾钩子）：见 _desktop_cleanup.py 的说明。
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _no_real_explorer(monkeypatch):
    """桌面模式生成成功会调 subprocess.Popen(explorer.exe) 聚焦工程目录
    （工单 generate-conflict-guard/04）——测试里不许真弹资源管理器窗口。
    subprocess 模块是全局单例（compile_runner 也用它跑编译器子进程），
    所以只吞 explorer.exe 调用、其余转发真 Popen（绝不整函数替换）。
    断言 explorer 调用的测试自行覆盖（monkeypatch 后设盖先设）。"""
    real_popen = subprocess.Popen

    def guarded_popen(*args, **kwargs):
        argv = args[0] if args else kwargs.get("args", ())
        if isinstance(argv, (list, tuple)) and argv and argv[0] == "explorer.exe":
            return None
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", guarded_popen)


def pytest_sessionfinish(session, exitstatus):
    """测试会话收尾：清理本会话生成到桌面的测试产物。"""
    removed = cleanup_desktop_test_artifacts(Path.home() / "Desktop")
    if removed:
        head = "、".join(removed[:5]) + ("…" if len(removed) > 5 else "")
        print(f"\n[conftest] 清理桌面测试产物 {len(removed)} 个：{head}")
