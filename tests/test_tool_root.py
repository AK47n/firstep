"""工具根判定单源测试（工单 full-download/09）。

真机演练实测三处同类缺陷（源码直跑时全部算成 `<根>/src`）：更新器路径、
资料库基线路径、版本记录路径。本测试把「四条引用同一单源」钉住。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator import tool_root as tr
from contest_generator.materials_update import materials_library_dir
from contest_generator.tool_root import find_tool_root, tool_root
from contest_generator.webapp import tool_root as webapp_tool_root
from contest_generator.wordlist import _SOURCE_MODULES_DIR

REPO = Path(__file__).resolve().parent.parent


def test_tool_root_is_repo_root() -> None:
    root = tool_root()
    assert root == REPO
    assert (root / "tools" / "update-app.py").is_file()
    assert (root / "start-app.vbs").is_file()


def test_tool_root_never_src_dir() -> None:
    assert tool_root().name != "src"


def test_source_direct_run_layout() -> None:
    """源码直跑布局：<根>/src/contest_generator/ 也须判定为 <根>。"""
    fake = REPO / "src" / "contest_generator" / "webapp.py"
    assert find_tool_root(fake) == REPO


def test_installed_layout_falls_back_predictably(tmp_path: Path) -> None:
    """站点包布局（site-packages/contest_generator/）→ 三级候选都不像根时回退第一候选。"""
    pkg = tmp_path / "site-packages" / "contest_generator" / "webapp.py"
    pkg.parent.mkdir(parents=True)
    pkg.write_text("# fake\n", encoding="utf-8")
    assert find_tool_root(pkg) == tmp_path / "site-packages"


def test_materials_dir_under_tool_root() -> None:
    assert materials_library_dir() == REPO / "sources" / "materials"


def test_webapp_and_package_agree() -> None:
    assert webapp_tool_root() == tool_root() == tr.tool_root()


def test_wordlist_source_modules_under_tool_root() -> None:
    assert _SOURCE_MODULES_DIR == REPO / "library" / "modules"
    assert _SOURCE_MODULES_DIR.is_dir(), "源码树模块库必须真存在（词表引用校验靠它）"


def test_root_markers_include_key_dirs() -> None:
    assert set(tr.ROOT_MARKERS) >= {"tools", "library", "sources"}
