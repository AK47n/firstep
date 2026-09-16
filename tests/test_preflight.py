# -*- coding: utf-8 -*-
"""发版前自检的守卫（工单 commit-gate/03）。

**为什么值得单独立一套**：`tools/preflight.py` 的判据都指向"发版那一刻才看"的事实
（版本号三处、母版编码钉、README 入口），平时谁也不会去跑它——于是它坏掉的方式同样是
**静默**：判据写错一个正则，就永远报全绿。所以这里既验"判据在完整工作区上全绿"，
也验**每一项在被破坏时真的会红**。

**判据基准 = 临时完整副本，不是本机工作区**（2026-09-16 CI 教的）：本机是完整工作树
（有 `.git`、有没入包的 `sources/materials`、有全部 assets），CI 的 checkout 不是——
拿真仓库当基准，就会在 CI 上报成"自检红了"，而真因是判据读到了本机才有的东西。
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREFLIGHT = REPO / "tools" / "preflight.py"


def load_preflight(root: Path | None = None):
    """加载 preflight 模块；`root` 给临时副本用（改指 REPO_ROOT 与打包脚本路径）。"""
    spec = importlib.util.spec_from_file_location("preflight_under_test", PREFLIGHT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["preflight_under_test"] = module
    spec.loader.exec_module(module)
    if root is not None:
        module.REPO_ROOT = root
        shutil.copy2(REPO / "tools" / "preflight.py", root / "tools" / "preflight.py")
    return module


def make_full_copy(tmp_path: Path) -> Path:
    """造一份**自足**的仓库副本：跑 preflight 需要的每样东西都在（含一个真 git 仓库）。

    复制的是判据真正读的路径：`src/contest_generator`（版本号 + VERSIONS 解析器）、
    顶层四个文件、`library/.../.settings` 两件、`tools/check-download-docs.py`、
    包内要有的 `00-START-HERE.txt`，外加 `git init` + 把 `.settings` 登记进索引。
    """
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copytree(REPO / "src" / "contest_generator", root / "src" / "contest_generator",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "VERSIONS.md", "README.md", "00-START-HERE.txt"):
        shutil.copy2(REPO / name, root / name)
    shutil.copy2(REPO / "tools" / "check-download-docs.py", root / "tools" / "check-download-docs.py")
    settings = root / "library" / "masters" / "mspm0" / ".settings"
    settings.mkdir(parents=True)
    for name in ("org.eclipse.cdt.codan.core.prefs", "org.eclipse.core.resources.prefs"):
        shutil.copy2(REPO / "library" / "masters" / "mspm0" / ".settings" / name,
                     settings / name)
    subprocess.run(["git", "init", "-q"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "add", "library"], cwd=str(root), capture_output=True)
    return root


@pytest.fixture()
def copy_repo(tmp_path):
    return make_full_copy(tmp_path)


# ---------------------------------------------------------------------------
# 完整工作区上：全绿（防线本体；副本 = 不依赖本机状态）
# ---------------------------------------------------------------------------


def test_full_copy_passes(copy_repo, capsys):
    """一份自足的仓库副本上必须全绿——这条红了，说明判据本身坏了或漏了依赖。"""
    module = load_preflight(copy_repo)
    code = module.main([])
    out = capsys.readouterr().out
    assert code == 0, f"发版自检在完整副本上红了：\n{out}"
    assert "全绿" in out


def test_version_parsers_agree_with_module_constants(copy_repo):
    """三处版本号解析出来的必须彼此相等（副本上的事实，不喂合成数据）。"""
    module = load_preflight(copy_repo)
    assert module.tool_version() == module.pyproject_version()
    head_version, head_date = module.versions_head()
    assert head_version == f"v{module.tool_version()}"
    assert head_date, "首个版本块没解析出日期"
    assert module.readme_current_version() == module.tool_version()


def test_real_repo_files_are_readable_from_a_clean_checkout():
    """**新 clone 上没有本机夹具**（2026-09-16 CI 抓到的真问题）。

    有些用例把 `.scratch/real-run/` 下的真机产物当夹具读——那些文件必须**入库**，
    否则只有本机跑得过。这里直接用 `git ls-files` 判：测试读的路径必须在索引里。
    """
    required = [
        ".scratch/real-run/verify-16-A8-mspm0-2026H-buildlog.txt",
        ".scratch/real-run/cache/recommend_2026C.json",
        ".scratch/real-run/generate_check.py",
    ]
    tracked = subprocess.run(
        ["git", "ls-files", *required], cwd=str(REPO),
        capture_output=True, text=True, encoding="utf-8",
    ).stdout.split()
    missing = [p for p in required if p not in tracked]
    assert not missing, (
        f"这些被测试当夹具读的文件没入库：{missing}——"
        "CI 与任何新 clone 上会 FileNotFoundError（本机却全绿）"
    )


# ---------------------------------------------------------------------------
# 反向验证：每一项被破坏时必须红，并点名是哪一处
# ---------------------------------------------------------------------------


def test_wrong_pyproject_version_is_red(copy_repo, capsys):
    """pyproject 版本号与 __init__ 不一致 → 红，且说明改哪个文件。"""
    text = (copy_repo / "pyproject.toml").read_text(encoding="utf-8")
    (copy_repo / "pyproject.toml").write_text(
        text.replace('version = "1.2.1"', 'version = "9.9.9"'), encoding="utf-8")

    module = load_preflight(copy_repo)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "pyproject.toml" in out and "9.9.9" in out


def test_broken_versions_header_is_red(copy_repo, capsys):
    """**重演 2026-09-14 那次真事故**：版本头日期段混进中文 → 整块被解析器跳过 → 必须红。"""
    text = (copy_repo / "VERSIONS.md").read_text(encoding="utf-8")
    import re

    current = re.search(r"^## (v[0-9][0-9A-Za-z.\-]*) \(([0-9]{4}-[0-9]{2}-[0-9]{2})\)",
                        text, re.MULTILINE)
    assert current, "VERSIONS.md 里找不到规范的版本头——用例前提不成立"
    broken = f"## {current.group(1)} ({current.group(2)}，重发)"
    (copy_repo / "VERSIONS.md").write_text(
        text.replace(current.group(0), broken), encoding="utf-8")

    module = load_preflight(copy_repo)
    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "VERSIONS.md" in out


def test_readme_version_line_is_checked(copy_repo, capsys):
    """README 当前版本行写旧了也要红（新用户最先看的就是那一行）。"""
    text = (copy_repo / "README.md").read_text(encoding="utf-8")
    module = load_preflight(copy_repo)
    current = module.readme_current_version()
    assert current, "README 里没有「当前版本」行——用例前提不成立"
    (copy_repo / "README.md").write_text(
        text.replace(f"当前版本：**v{current}**", "当前版本：**v0.0.1**"), encoding="utf-8")

    assert module.main([]) == 1
    out = capsys.readouterr().out
    assert "README.md" in out


def test_missing_encoding_pin_is_red(copy_repo, capsys):
    """编码钉文件不在盘上 → 红（这正是 2026-09-15 误删那件事的守卫）。"""
    (copy_repo / "library" / "masters" / "mspm0" / ".settings"
     / "org.eclipse.core.resources.prefs").unlink()

    module = load_preflight(copy_repo)
    assert module.main([]) == 1
    assert "盘上缺" in capsys.readouterr().out


def test_settings_without_pin_content_is_red(copy_repo, capsys):
    """文件在但内容里没有编码钉 → 同样红（防「文件回来了、内容却是别的」）。"""
    pin = (copy_repo / "library" / "masters" / "mspm0" / ".settings"
           / "org.eclipse.core.resources.prefs")
    pin.write_text("eclipse.preferences.version=1\n", encoding="utf-8")

    module = load_preflight(copy_repo)
    assert module.main([]) == 1
    assert "编码钉不在" in capsys.readouterr().out


def test_settings_not_tracked_by_git_is_red(copy_repo, capsys):
    """盘上有、git 没跟踪 → 红（不修这条 = 文件在本地但发布包不会带）。"""
    subprocess.run(["git", "rm", "--cached", "-q",
                    "library/masters/mspm0/.settings/org.eclipse.core.resources.prefs"],
                   cwd=str(copy_repo), capture_output=True)

    module = load_preflight(copy_repo)
    assert module.main([]) == 1
    assert "未被 git 跟踪" in capsys.readouterr().out


def test_report_lists_every_red_item(copy_repo, capsys):
    """多项同时坏时逐条列出（别只报第一条就退）。"""
    (copy_repo / "README.md").write_text(
        (copy_repo / "README.md").read_text(encoding="utf-8").replace(
            "当前版本：**", "当前版本：**v0.0.1（旧**"), encoding="utf-8")
    (copy_repo / "library" / "masters" / "mspm0" / ".settings"
     / "org.eclipse.core.resources.prefs").unlink()

    module = load_preflight(copy_repo)
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
