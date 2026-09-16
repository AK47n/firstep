# -*- coding: utf-8 -*-
"""发版前自检的守卫（工单 commit-gate/03）。

**为什么值得单独立一套**：`tools/preflight.py` 的判据都指向"发版那一刻才看"的事实
（版本号三处、母版编码钉、README 入口），平时谁也不会去跑它——于是它坏掉的方式同样是
**静默**：判据写错一个正则，就永远报全绿。所以这里既验"真仓库全绿"，也验**每一项在
被破坏时真的会红**（用临时副本注入破坏，不碰真仓库）。
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREFLIGHT = REPO / "tools" / "preflight.py"


def load_preflight(root: Path | None = None):
    """加载 preflight 模块（`root` 给临时副本用；模块级 REPO_ROOT 会被改指过去）。"""
    spec = importlib.util.spec_from_file_location("preflight_under_test", PREFLIGHT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["preflight_under_test"] = module
    spec.loader.exec_module(module)
    if root is not None:
        module.REPO_ROOT = root
        module.MASTER_SETTINGS_DIR = module.MASTER_SETTINGS_DIR  # 保持不变（相对路径）
    return module


@pytest.fixture(scope="module")
def preflight():
    return load_preflight()


def make_copy(tmp_path: Path) -> Path:
    """造一份「仓库副本」：只复制 preflight 需要的文件（不复制 800 MB 的库）。"""
    root = tmp_path / "repo"
    (root / "src" / "contest_generator").mkdir(parents=True)
    (root / "tools").mkdir(parents=True)
    (root / "library" / "masters" / "mspm0" / ".settings").mkdir(parents=True)
    shutil.copy2(REPO / "src" / "contest_generator" / "__init__.py",
                 root / "src" / "contest_generator" / "__init__.py")
    shutil.copy2(REPO / "src" / "contest_generator" / "changelog.py",
                 root / "src" / "contest_generator" / "changelog.py")
    for name in ("pyproject.toml", "VERSIONS.md", "README.md"):
        shutil.copy2(REPO / name, root / name)
    for name in ("org.eclipse.cdt.codan.core.prefs", "org.eclipse.core.resources.prefs"):
        shutil.copy2(REPO / "library" / "masters" / "mspm0" / ".settings" / name,
                     root / "library" / "masters" / "mspm0" / ".settings" / name)
    return root


# ---------------------------------------------------------------------------
# 真仓库：全绿（防线本体）
# ---------------------------------------------------------------------------


def test_real_repo_passes(preflight, capsys):
    """真仓库现在必须是全绿——这条红了，说明发版前的账没结清。"""
    code = preflight.main([])
    out = capsys.readouterr().out
    assert code == 0, f"发版自检在真仓库上红了：\n{out}"
    assert "全绿" in out


def test_version_parsers_agree_with_module_constants(preflight):
    """三处版本号解析出来的必须彼此相等（用真仓库的事实，不喂假数据）。"""
    assert preflight.tool_version() == preflight.pyproject_version()
    head_version, head_date = preflight.versions_head()
    assert head_version == f"v{preflight.tool_version()}"
    assert head_date, "首个版本块没解析出日期"
    assert preflight.readme_current_version() == preflight.tool_version()


# ---------------------------------------------------------------------------
# 反向验证：每一项被破坏时必须红，并点名是哪一处
# ---------------------------------------------------------------------------


def test_wrong_pyproject_version_is_red(tmp_path, capsys):
    """pyproject 版本号与 __init__ 不一致 → 红，且说明改哪个文件。"""
    root = make_copy(tmp_path)
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    (root / "pyproject.toml").write_text(
        text.replace('version = "1.2.1"', 'version = "9.9.9"'), encoding="utf-8")

    module = load_preflight(root)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "pyproject.toml" in out and "9.9.9" in out


def test_broken_versions_header_is_red(tmp_path, capsys):
    """**重演 2026-09-14 那次真事故**：版本头日期段混进中文 → 整块被解析器跳过 → 必须红。"""
    root = make_copy(tmp_path)
    text = (root / "VERSIONS.md").read_text(encoding="utf-8")
    (root / "VERSIONS.md").write_text(
        text.replace("## v1.2.1 (2026-09-16)", "## v1.2.1 (2026-09-16，重发)"),
        encoding="utf-8")

    module = load_preflight(root)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "VERSIONS.md" in out
    assert "整块被静默跳过" in out or "首个版本块" in out


def test_readme_version_line_is_checked(tmp_path, capsys):
    """README 当前版本行写旧了也要红（新用户最先看的就是那一行）。"""
    root = make_copy(tmp_path)
    text = (root / "README.md").read_text(encoding="utf-8")
    (root / "README.md").write_text(
        text.replace("当前版本：**v1.2.1**", "当前版本：**v1.2.0**"), encoding="utf-8")

    module = load_preflight(root)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "README.md" in out


def test_missing_encoding_pin_is_red(tmp_path, capsys):
    """编码钉文件不在盘上 → 红（这正是 2026-09-15 误删那件事的守卫）。"""
    root = make_copy(tmp_path)
    (root / "library" / "masters" / "mspm0" / ".settings"
     / "org.eclipse.core.resources.prefs").unlink()

    module = load_preflight(root)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "盘上缺" in out


def test_settings_without_pin_content_is_red(tmp_path, capsys):
    """文件在但内容里没有编码钉 → 同样红（防「文件回来了、内容却是别的」）。"""
    root = make_copy(tmp_path)
    pin = (root / "library" / "masters" / "mspm0" / ".settings"
           / "org.eclipse.core.resources.prefs")
    pin.write_text("eclipse.preferences.version=1\n", encoding="utf-8")

    module = load_preflight(root)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "编码钉不在" in out


def test_report_lists_every_red_item(tmp_path, capsys):
    """多项同时坏时逐条列出（别只报第一条就退）。"""
    root = make_copy(tmp_path)
    (root / "README.md").write_text(
        (root / "README.md").read_text(encoding="utf-8").replace(
            "当前版本：**v1.2.1**", "当前版本：**v0.0.1**"), encoding="utf-8")
    (root / "library" / "masters" / "mspm0" / ".settings"
     / "org.eclipse.core.resources.prefs").unlink()

    module = load_preflight(root)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "README.md" in out and "盘上缺" in out


# ---------------------------------------------------------------------------
# PowerShell 入口（发版清单里写的是这条）
# ---------------------------------------------------------------------------


def test_powershell_entry_exists_with_bom():
    """`tools/preflight.ps1` 必须存在且是 UTF-8 with BOM（硬性约定，5.1 会按 GBK 解码）。"""
    ps1 = REPO / "tools" / "preflight.ps1"
    assert ps1.is_file(), "发版清单里指的 tools/preflight.ps1 不见了"
    head = ps1.read_bytes()[:3]
    assert head == b"\xef\xbb\xbf", f"缺 UTF-8 BOM（前 3 字节 {head!r}）"


def test_powershell_entry_does_not_duplicate_criteria():
    """薄壳原则：判据只在 python 侧，ps1 里不许再写一份版本号/路径判据。"""
    text = (REPO / "tools" / "preflight.ps1").read_text(encoding="utf-8-sig")
    assert "preflight.py" in text, "ps1 没转发给 python 侧"
    for forbidden in ("VERSIONS.md", "org.eclipse.core.resources.prefs", "pyproject.toml"):
        assert forbidden not in text, f"ps1 里出现了判据 {forbidden}——判据该只有一份"
