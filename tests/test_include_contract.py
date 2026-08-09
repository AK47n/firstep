"""include 解析契约（工单 01）：共享核心单测 + 结构自证。

keil._find_uvprojx / ccs._find_cproject 孪生查找器与 include 条目解析核心
收进 projectfile.py 底座后，行为由本文件单测直接钉住（三态 + 文案逐字 +
噪音跳过 / 绝对保留 / 相对基准 / 去重保序 / 归一 / 空条目）；结构自证保证
共享原语单址、keil/ccs 不再自定义孪生查找器。keil/ccs 既有 fixture 零改动
（行为逐字由原测试全量通过证明）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.projectfile import (
    find_project_file,
    resolve_include_entries,
)

# 错误类型只做载体：文案从 pattern 派生，与具体错误类无关
class _FakeError(Exception):
    pass


# ---------------------------------------------------------------------------
# find_project_file：三态 + 文案逐字 + 噪音跳过
# ---------------------------------------------------------------------------


def test_find_project_file_zero_raises_with_pattern_derived_message(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(_FakeError, match=r"工程目录里没有 \.uvprojx 文件："):
        find_project_file(empty, "*.uvprojx", _FakeError)


def test_find_project_file_multiple_raises_with_joined_names(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "a.uvprojx").write_text("<Project/>", encoding="utf-8")
    (project / "b.uvprojx").write_text("<Project/>", encoding="utf-8")

    with pytest.raises(
        _FakeError,
        match=r"工程目录里有多个 \.uvprojx，无法确定改哪个：a\.uvprojx、b\.uvprojx",
    ):
        find_project_file(project, "*.uvprojx", _FakeError)


def test_find_project_file_single_returns_path(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "proj.uvprojx"
    target.write_text("<Project/>", encoding="utf-8")

    assert find_project_file(project, "*.uvprojx", _FakeError) == target


def test_find_project_file_finds_nested_any_level(tmp_path):
    """任意层级定位（正点原子风格 .uvprojx 在 USER/ 子目录）。"""
    project = tmp_path / "proj"
    user = project / "USER"
    user.mkdir(parents=True)
    target = user / "proj.uvprojx"
    target.write_text("<Project/>", encoding="utf-8")

    assert find_project_file(project, "*.uvprojx", _FakeError) == target


def test_find_project_file_skips_git_noise(tmp_path):
    """.git 里的工程文件不算数（treewalk 噪音规则，与 master 扫描同一套）。"""
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    (project / ".git" / "proj.uvprojx").write_text("<Project/>", encoding="utf-8")

    with pytest.raises(_FakeError, match=r"没有 \.uvprojx"):
        find_project_file(project, "*.uvprojx", _FakeError)


# ---------------------------------------------------------------------------
# resolve_include_entries：绝对保留 / 相对基准 / 去重保序 / 归一 / 空条目
# ---------------------------------------------------------------------------


def test_resolve_include_entries_keeps_absolute_joins_relative(tmp_path):
    base = tmp_path / "proj"
    abs_inc = tmp_path / "sdk" / "include"

    dirs = resolve_include_entries(
        [str(abs_inc), "sdk/headers", "./inc"], base
    )

    assert dirs == [abs_inc, base / "sdk" / "headers", base / "inc"]


def test_resolve_include_entries_dedupes_in_first_appearance_order(tmp_path):
    base = tmp_path / "proj"
    entries = ["inc", "./inc", str(base / "inc"), "driverlib", "inc"]

    dirs = resolve_include_entries(entries, base)

    assert dirs == [base / "inc", base / "driverlib"]


def test_resolve_include_entries_dedupes_case_insensitive(tmp_path):
    base = tmp_path / "proj"
    dirs = resolve_include_entries(["inc", "INC"], base)
    assert dirs == [base / "inc"]


def test_resolve_include_entries_skips_empty_after_strip(tmp_path):
    base = tmp_path / "proj"
    dirs = resolve_include_entries(["", "  ", "inc"], base)
    assert dirs == [base / "inc"]


def test_resolve_include_entries_normalizes_backslashes(tmp_path):
    """反斜杠归一：Windows 上 Path 行为等价，显式归一更稳（keil 既有语义
    带入共享核心，ccs 同缝受益）。"""
    base = tmp_path / "proj"
    dirs = resolve_include_entries(["sdk\\headers", "sdk/headers"], base)
    assert dirs == [base / "sdk" / "headers"]


# ---------------------------------------------------------------------------
# 结构自证（grep 式先例，见 test_generator.py）：共享原语单址 + keil/ccs
# 不再自定义孪生查找器
# ---------------------------------------------------------------------------


def test_shared_primitives_single_origin():
    """find_project_file / resolve_include_entries 定义单址 = projectfile.py。"""
    import contest_generator.projectfile as projectfile

    src_root = Path(projectfile.__file__).parent
    for primitive in ("find_project_file", "resolve_include_entries"):
        hits = [
            path.name
            for path in sorted(src_root.glob("*.py"))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(f"def {primitive}")
        ]
        assert hits == ["projectfile.py"], f"{primitive} 应单址 projectfile.py"


def test_no_twin_finder_definitions_in_platform_modules():
    """keil/ccs 模块内无 _find_uvprojx / _find_cproject 定义（已收进底座）。"""
    import contest_generator.ccs as ccs
    import contest_generator.keil as keil

    for module in (keil, ccs):
        text = Path(module.__file__).read_text(encoding="utf-8")
        assert "def _find_uvprojx" not in text
        assert "def _find_cproject" not in text
