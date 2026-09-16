# -*- coding: utf-8 -*-
"""提交闸门的钩子守卫（工单 commit-gate/02）。

闸门的失效方式有两种，都要挡住：
① **钩子没被执行**（没配 `core.hooksPath` / 文件不可执行 / 名字不对）→ 静默放行；
② **钩子执行了但契约不对**（读不到 refs / 推 tag 不整套 / 测试红却退出 0）→ 假绿。

所以这里既断言钩子文件的存在与关键行为，也**真跑一次钩子**（喂 pre-push 协议的 stdin）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".githooks" / "pre-push"


def find_shell() -> tuple[str, str | None] | None:
    """找得到 POSIX shell 就返回 (可执行文件, 需要补的 PATH 目录)。

    Windows 上本机 PATH 里没有 `sh`（git for Windows 自带的是
    `<Git>/usr/bin/bash.exe`，与它同目录的 `sh.exe`）；git 自己跑钩子用的就是它。
    找不到 shell 时用例跳过并说明——**不假装绿**。
    """
    for name in ("sh", "bash"):
        found = shutil.which(name)
        if found:
            return found, None
    git = shutil.which("git")
    if git:
        usr_bin = Path(git).resolve().parents[1] / "usr" / "bin"
        for name in ("sh.exe", "bash.exe"):
            candidate = usr_bin / name
            if candidate.is_file():
                return str(candidate), str(usr_bin)
    return None


SHELL = find_shell()
needs_shell = pytest.mark.skipif(
    SHELL is None, reason="本机找不到 POSIX shell（git 自带的也没有），无法真跑钩子"
)


def _run_hook(stdin_text: str, extra_env: dict | None = None,
              timeout: int = 300, select_only: bool = True) -> subprocess.CompletedProcess:
    """跑真钩子。

    `select_only=True`（默认）给钩子一个 `FIRSTEP_PREPUSH=select-only`：钩子照旧读 refs、
    照旧判断、照旧按判据设退出码，但**不真跑 pytest**——钩子契约（读到什么、判成什么、
    退出码怎么传）全都能验，而不会把用例拖进一整套 58 秒里（实测第一版就是这么超时的）。
    """
    assert SHELL is not None
    executable, path_extra = SHELL
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("PYTHON", None)  # 免得外面设的 PYTHON 指向别的解释器
    if select_only:
        env["FIRSTEP_PREPUSH"] = "select-only"
    if path_extra:
        env["PATH"] = path_extra + os.pathsep + env.get("PATH", "")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [executable, str(HOOK)], cwd=str(REPO), input=stdin_text, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env,
    )


def _head_pair() -> tuple[str, str]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                          capture_output=True, text=True).stdout.strip()
    return head, head


# ---------------------------------------------------------------------------
# 钩子存在性与内容契约
# ---------------------------------------------------------------------------


def test_hook_exists_and_is_executable():
    """钩子在、且被标成可执行（git 只在可执行时调用它）。"""
    assert HOOK.is_file(), ".githooks/pre-push 不存在——闸门根本没接上"
    mode = subprocess.run(
        ["git", "ls-files", "-s", ".githooks/pre-push"], cwd=str(REPO),
        capture_output=True, text=True,
    ).stdout.split()
    assert mode, "钩子没被 git 跟踪（新 clone 拿不到它）"
    assert mode[0].startswith("1007"), f"钩子索引模式不是可执行：{mode[0]}"


def test_hooks_path_points_at_dot_githooks():
    """本仓库的钩子目录配置正确（否则钩子文件在也不生效）。"""
    out = subprocess.run(["git", "config", "core.hooksPath"], cwd=str(REPO),
                         capture_output=True, text=True).stdout.strip()
    assert out == ".githooks", f"core.hooksPath = {out!r}（应为 .githooks）"


def test_hook_delegates_to_prepush_and_pins_pythonpath():
    """钩子必须把 refs 交给 prepush.py，并把 PYTHONPATH 钉到仓库 src。

    钉 PYTHONPATH 防的是本机那个坑：全局 site-packages 里的 editable 安装指向
    **另一个**源码路径（local-environment.md 2.5），裸 pytest 会跑错源码。
    """
    text = HOOK.read_text(encoding="utf-8", errors="replace")
    assert "tools/prepush.py" in text
    assert "--stdin-refs" in text, "钩子没把 pre-push 的 refs 传进去，推 tag 就不会整套跑"
    assert 'PYTHONPATH="$root/src' in text, "没钉 PYTHONPATH——可能跑的不是这份源码"
    assert "exit 0" in text, "找不到解释器时没有放行分支"


# ---------------------------------------------------------------------------
# 真跑钩子：契约必须成立
# ---------------------------------------------------------------------------


def test_hook_runs_and_picks_subset_for_real_refs():
    """喂真实 refs（HEAD..HEAD 无改动）→ 钩子自己决定了什么、并如实退出 0。"""
    head, _ = _head_pair()
    result = _run_hook(f"refs/heads/main {head} refs/heads/main {head}\n")
    assert result.returncode == 0, f"钩子非 0 退出：{result.stdout}\n{result.stderr}"
    assert "[prepush]" in result.stdout, f"钩子没跑到 prepush.py：{result.stdout[:300]}"


def test_hook_treats_tag_push_as_full_suite():
    """推 tag（发版）→ 整套跑（这是闸门最重要的一次触发）。

    真跑一整套要 58 秒、且这里重复跑没有信息量，故用 `FIRSTEP_PREPUSH=off` 让钩子
    停在判定那一步——本用例验的是「钩子读到了环境变量、并且真的走进了 prepush.py」，
    「tag → 整套」的判据在下面一条用纯函数级断言覆盖。
    """
    head, _ = _head_pair()
    result = _run_hook(f"refs/tags/v0.0.0-test {head} refs/tags/v0.0.0-test {head}\n",
                       extra_env={"FIRSTEP_PREPUSH": "off"})
    assert "[prepush]" in result.stdout
    assert "跳过闸门" in result.stdout  # off 模式确实生效（钩子读到了环境变量）


def test_hook_reports_full_suite_for_tag_push_dry():
    """不带 off：钩子应当把 tag 推送判成「整套跑」（只跑到判定那一步就够）。

    为了让这条不真跑一整套（58 秒的重复劳动），借 prepush 的 dry-run 语义：
    钩子本身不传 dry-run，所以这里改为断言「选择器对 tag 的态度」——
    即 `changed_from_refs` 的返回值 + main 的整套分支。两者都是纯函数级判据。
    """
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location("prepush_hook_test", REPO / "tools" / "prepush.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    _sys.modules["prepush_hook_test"] = module
    spec.loader.exec_module(module)

    head, _ = _head_pair()
    changed, has_tag = module.changed_from_refs(
        f"refs/tags/v0.0.0-test {head} refs/tags/v0.0.0-test {head}\n"
    )
    assert has_tag is True, "推 tag 没被识别成发版动作 → 发版当天的闸门等于没有"

    # 认不出远端状态（远端 sha 本地没有）时也必须倒向整套
    changed2, tag2 = module.changed_from_refs(
        f"refs/heads/x {head} refs/heads/x {'f' * 40}\n"
    )
    assert tag2 is True and changed2 == [], "远端 sha 本地没有时没有倒向整套"


def test_hook_bypass_is_explicit_and_warned():
    """FIRSTEP_PREPUSH=off → 跳过，但必须出声（不许静默绕过）。"""
    head, _ = _head_pair()
    result = _run_hook(f"refs/heads/main {head} refs/heads/main {head}\n",
                       extra_env={"FIRSTEP_PREPUSH": "off"})
    assert result.returncode == 0
    assert "跳过闸门" in result.stdout


def test_hook_passes_when_selector_cannot_read_refs():
    """喂垃圾 stdin → 钩子不许崩、也不许拦人（闸门故障放行）。"""
    result = _run_hook("这不是 pre-push 协议的内容\n")
    assert result.returncode == 0, f"闸门读了垃圾输入就拦人：{result.stdout}"


@needs_shell
def test_hook_blocks_push_when_tests_fail(tmp_path):
    """**闸门的核心契约**：测试红 → 非 0 退出（真 push 会被拒）。

    做法：在临时副本里把 `tools/prepush.py` 换成「必然失败」的假件，再跑钩子——
    验的是钩子的**退出码透传**（真红时 git 会不会被拦下），不必真等一整套。
    """
    work = tmp_path / "repo"
    (work / "tools").mkdir(parents=True)
    (work / ".githooks").mkdir(parents=True)
    shutil.copy2(HOOK, work / ".githooks" / "pre-push")

    # 一个「必然红」的假 prepush.py：直接返回 1（模拟测试红的结局）
    (work / "tools" / "prepush.py").write_text(
        "import sys\n"
        "print('[prepush] 假选择器：模拟测试红')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=str(work), capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(work), capture_output=True)

    executable, path_extra = SHELL  # type: ignore[misc]
    env = dict(os.environ)
    env.pop("PYTHON", None)
    if path_extra:
        env["PATH"] = path_extra + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [executable, str(work / ".githooks" / "pre-push")], cwd=str(work),
        input="", capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, env=env,
    )
    assert result.returncode != 0, "测试红时钩子却放行了——闸门形同虚设"
