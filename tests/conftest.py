"""pytest fixtures：假母版、假模块库、假 LLM、生成器调用助手。

生成流程经 contest_generator.generator 驱动：落盘接缝是 generate，完整流程
（选模块 → 母版 → 生成 → 摘要）的接缝是 generate_project。构造器与假件
本体在 tests/fakes.py。
"""

from __future__ import annotations

import re
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
# 引脚符号重名的回归现场（工单 hwcheck-acceptance/02）
# ---------------------------------------------------------------------------
#
# 02 把母版里 14 组同名的引脚符号（`SCL`/`SDA`/`LED`/`OUT`…）改成
# `<实例名>_<原符号>`，于是**真母版不再有重名**——而"同名引脚符号必须在生成前
# 被拦下"这条判据（工单 hwcheck-unknown-device/11）仍要有人守：SysConfig 的
# `$name` 全局唯一约束还在，将来任何一件新模块把引脚起成同名，工程就会在 CCS 里
# 编不过。下面几个夹具把**改名撤回一处**，造出"将来又撞名"的现场——判据必须在这
# 份现场上变红（真母版上则必须放行）。

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_MSPM0_MASTER = REPO_ROOT / "library" / "masters" / "mspm0" / "mspm0.syscfg"

# 撤回的那两处：OLED_SPI 与 JY61P 的 SCL/SDA 还原成撞名的 `SCL`/`SDA`——正是
# 工单 11 实测的那一组（其余 64 个符号保持 02 之后的样子）。两边都要撤：只撤一边
# 就不撞了（对面已叫 `JY61P_SCL`）。
_REVERTED_PIN_NAMES = (
    ("OLED_SPI", "OLED_SPI_SCL", "SCL"),
    ("OLED_SPI", "OLED_SPI_SDA", "SDA"),
    ("JY61P", "JY61P_SCL", "SCL"),
    ("JY61P", "JY61P_SDA", "SDA"),
)


def _revert_pin_names(text: str) -> str:
    """母版文本 → 把工单 02 的那几处改名撤回（造重名现场）。

    按「实例 + 当前符号名」定位（不是抄一整行字面量）：母版哪天重排 / 改缩进，
    夹具不会跟着碎。找不齐就是母版漂移——当场大声失败，不静默造出一个"不撞"的
    假现场（第一版按整行字面量匹配，行内空格一改就废）。
    """
    for instance, current, reverted in _REVERTED_PIN_NAMES:
        pattern = re.compile(
            r'(?m)^(?P<head>\s*' + re.escape(instance)
            + r'\.associatedPins\[\d+\]\.\$name\s*=\s*)"' + re.escape(current) + r'";'
        )
        text, count = pattern.subn('\\g<head>"' + reverted + '";', text)
        assert count == 1, (
            f"母版里找不到 {(instance, current)} 这个改名落点（命中 {count} 处）"
        )
    return text


@pytest.fixture
def mspm0_master_syscfg_text() -> str:
    """真母版 `mspm0.syscfg` 全文（判据按文本吃的那些入口用）。"""
    return REAL_MSPM0_MASTER.read_text(encoding="utf-8")


@pytest.fixture
def collision_reverted_syscfg(mspm0_master_syscfg_text) -> str:
    """真母版 + **把 02 的改名撤回一处** = 重名回归现场（`SCL`/`SDA` 又撞上）。"""
    return _revert_pin_names(mspm0_master_syscfg_text)


@pytest.fixture
def collision_reverted_masters_dir(tmp_path) -> Path:
    """整棵母版库的临时副本，其中 `mspm0/mspm0.syscfg` 是上面那份回归现场。

    整树拷贝（不是只放一个 syscfg 文件）：检测页投影还会读母版里其它文件
    （配方接口清单要母版工程头），只放一个文件会造出另一种失败。
    """
    import shutil

    target = tmp_path / "masters"
    shutil.copytree(REPO_ROOT / "library" / "masters", target)
    syscfg = target / "mspm0" / "mspm0.syscfg"
    syscfg.write_text(
        _revert_pin_names(syscfg.read_text(encoding="utf-8")), encoding="utf-8"
    )
    return target


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


def pytest_collection_modifyitems(config, items):
    """本仓 `xfail` 一律 strict：XPASS 直接判失败，逼标记随数据落地被摘掉。

    背景（工单 identity-fields/02）：待补器件的身份字段守卫用 xfail 表达「已知缺口」，
    只有 XPASS 判失败才能保证补齐数据后标记被摘掉。先例口径 = 工单
    preselect-visibility「从 xfail 转 XPASS 并摘掉标记」。不设全局 `xfail_strict`
    （历史用例可能依赖宽松语义），只给显式 xfail 补默认 strict。
    """
    for item in items:
        for mark in item.iter_markers(name="xfail"):
            mark.kwargs.setdefault("strict", True)


def pytest_sessionfinish(session, exitstatus):
    """测试会话收尾：清理本会话生成到桌面的测试产物。"""
    removed = cleanup_desktop_test_artifacts(Path.home() / "Desktop")
    if removed:
        head = "、".join(removed[:5]) + ("…" if len(removed) > 5 else "")
        print(f"\n[conftest] 清理桌面测试产物 {len(removed)} 个：{head}")
