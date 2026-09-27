"""共享原子写原语（工单 record-write-hardening/01）的判据。

形状照同一族的先例 `tests/test_hwcheck_triage.py:554-645`：判据取**最终落盘内容**与
**目录里有没有多余文件**，不断言内部实现。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from contest_generator import atomic_io
from contest_generator.atomic_io import atomic_write_text, path_lock


def _residue(directory: Path, keep: str) -> list[str]:
    """目录里除目标文件外的东西（`iterdir` 而不是 `glob("*.tmp")`——临时名带 pid + 计数后
    那个 glob 匹配不到新名字，等于断言空转；`hwcheck-hygiene/03` 被评审抓过一次）。"""
    return [p.name for p in directory.iterdir() if p.name != keep]


def test_atomic_write_text_leaves_no_tmp(tmp_path):
    """落盘后目录里除目标文件外一个文件都没有。"""
    target = tmp_path / "record.json"
    atomic_write_text(target, "{}\n")
    assert target.read_text(encoding="utf-8") == "{}\n"
    assert _residue(tmp_path, target.name) == []


def test_atomic_write_text_failure_leaves_no_residue(tmp_path):
    """坏写不许留半成品：替换失败时临时文件必须被清掉，且**原异常照抛**。"""
    target = tmp_path / "record.json"
    target.mkdir()  # 目标是**目录** → 替换必然失败
    with pytest.raises(OSError):
        atomic_write_text(target, "{}")
    assert _residue(tmp_path, target.name) == []


def test_concurrent_writes_share_no_tmp_file(tmp_path, monkeypatch):
    """两个写者并发：**不许抢同一个临时名**（确定性做法 = 把第一个 `replace` 卡住）。

    补丁**只打在目标模块看到的 `os` 上**（不是全局 `os.replace`）：本机同时跑着别的测试线程时，
    全局补丁会被"第一发 `replace`"这种跨用例噪音消费掉（同族先例实测过一次偶发）。
    """
    first_inside = threading.Event()
    release = threading.Event()
    calls = {"n": 0}
    real_replace = os.replace

    def slow_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            first_inside.set()
            assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return real_replace(src, dst)

    monkeypatch.setattr(
        atomic_io,
        "os",
        SimpleNamespace(path=os.path, getpid=os.getpid, replace=slow_replace),
    )

    target = tmp_path / "record.json"
    errors: list[BaseException] = []

    def writer(tag: str) -> None:
        try:
            atomic_write_text(target, tag)
        except BaseException as exc:  # noqa: BLE001 —— 线程里的异常要带回主线程断言
            errors.append(exc)

    first = threading.Thread(target=writer, args=("先到的\n",), daemon=True)
    first.start()
    assert first_inside.wait(timeout=30), "第一个写者没走到替换那一步"
    second = threading.Thread(target=writer, args=("后到的\n",), daemon=True)
    second.start()
    # 先让第二个写者**整趟走完**（它不卡，直接落盘），再放行第一个：
    # 这样两次**真实** `os.replace` 不重叠——Windows 上并发 replace 同一个目标本身会抛
    # `PermissionError`（共享冲突），那是"谁先落盘"的另一回事，混进来这条判据就测不准了。
    # 本用例要测的是"临时名互抢"：固定名时第二个写者会把第一个的临时文件挪走/截断，
    # 第一个放行后 `replace` 的源文件已经不在 → 报错。
    second.join(timeout=30)
    assert not second.is_alive(), "第二个写者没跑完——判据自己失败，别挂住整场"
    release.set()
    first.join(timeout=30)

    assert errors == [], f"并发写报错（临时名互抢）：{errors!r}"
    assert _residue(tmp_path, target.name) == []
    assert target.read_text(encoding="utf-8") in {"先到的\n", "后到的\n"}


def test_path_lock_is_shared_for_normalised_spellings_of_one_path(tmp_path):
    """同一路径的不同写法恒同一把锁（正反斜杠；Windows 上还有盘符/路径大小写）。"""
    target = tmp_path / "record.json"
    variants = [Path(str(target).replace("\\", "/"))]
    if os.path.normcase("A") == "a":  # 仅 Windows：大小写不敏感
        variants.append(Path(str(target).upper()))
    for other in variants:
        assert path_lock(other) is path_lock(target), f"{other} 拿到的是另一把锁"


def test_path_lock_distinguishes_filenames_in_the_same_directory(tmp_path):
    """键含文件名：同一目录下的两份记录（全局商量 / 参数商量）各拿一把锁，互不阻塞。"""
    assert path_lock(tmp_path / "idea_chat.json") is not path_lock(
        tmp_path / "params_chat.json"
    )
