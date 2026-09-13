"""下载任务状态面契约测试（工单 resumable-download/04）。

**这一份只管状态面**：`task_status` / `full_task_status` 的字段契约、三字段取值矩阵、
`message` 的语义边界。两条链路的**行为**（断点、半成品、重试）在
`tests/test_full_task.py` / `tests/test_materials_task.py` 里测——别把两件事混在一处。

为什么值得单独一个文件：状态面是**前端唯一的信息来源**（前端不许解析 `error` 文案来分类），
它的字段名与取值就是一份跨语言契约。契约测试要能一眼看全六态矩阵，散布在各行为用例里就看不全了。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from contest_generator import download_resume
from contest_generator.download_resume import resumable_download
from contest_generator.full_task import FullDownloadTask, full_task_status
from contest_generator.materials_task import ApplyTask, TaskState, task_status
from tests._byte_server import ByteServer

# 八个既有字段（前端契约：一个都不许改名、不许缺席）
EXISTING_KEYS = {
    "state",
    "parts",
    "total_downloaded_bytes",
    "total_bytes",
    "speed_bps",
    "current_part_name",
    "error",
    "message",
}
# 本单新增的三个（工单 04）+ 重试百分比（工单 05）
NEW_KEYS = {"retry_count", "retrying", "error_kind", "resume_percent"}

PAYLOAD = bytes((i * 7 + 11) % 251 for i in range(300 * 1024))


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _full_task(tmp_path: Path, payload: bytes = PAYLOAD) -> FullDownloadTask:
    return FullDownloadTask(
        task_dir=tmp_path / "updates",
        parts=[{"name": "firstep-full-v1.1.0.zip", "url": "http://127.0.0.1:1/part",
                "size": len(payload), "sha256": _sha(payload)}],
        snapshot_interval=0.0,
    )


def _materials_task(tmp_path: Path, payload: bytes = PAYLOAD) -> ApplyTask:
    return ApplyTask(
        task_dir=tmp_path / "updates",
        batches=[{
            "slug": "k230", "name": "k230资料",
            "parts": [{"zip_url": "http://127.0.0.1:1/k230.zip",
                       "zip_name": "k230.zip", "size_bytes": len(payload),
                       "sha256": _sha(payload)}],
        }],
        snapshot_interval=0.0,
    )


STATUS_FOR = {
    "full": (full_task_status, _full_task),
    "materials": (task_status, _materials_task),
}


# ---------------------------------------------------------------------------
# 字段契约
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_status_keys_are_the_contracted_eleven(flavor: str, tmp_path: Path) -> None:
    """结构守卫：**包含** 8 个既有键（防改名）+ **包含** 3 个新增键。

    用「包含」而不是「集合相等」：工单要守的是「既有名字不许动、新字段必须在场」，
    不是「永远不许再加字段」——相等断言会让将来合法的第四个字段无缘无故转红。
    """
    status_fn, make_task = STATUS_FOR[flavor]
    for status in (status_fn(None), status_fn(make_task(tmp_path))):
        assert EXISTING_KEYS <= set(status), sorted(EXISTING_KEYS - set(status))
        assert NEW_KEYS <= set(status), sorted(NEW_KEYS - set(status))


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_idle_empty_state_has_neutral_values(flavor: str, tmp_path: Path) -> None:
    """空态的三字段要有中性值（前端零分支：不用判「字段在不在」）。"""
    status_fn, _ = STATUS_FOR[flavor]
    idle = status_fn(None)
    assert idle["state"] == "idle"
    assert idle["retry_count"] == 0
    assert idle["retrying"] is False
    assert idle["error_kind"] == ""
    assert idle["message"] == ""


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_downloading_state_is_not_retrying(flavor: str, tmp_path: Path) -> None:
    """下载中（没在退避）→ `retrying` 为假、无摘要、无错误分类。"""
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)
    task._state = TaskState.DOWNLOADING
    task._current_part_name = "卷.zip"
    status = status_fn(task)
    assert status["state"] == "downloading"
    assert status["current_part_name"] == "卷.zip"
    assert status["retry_count"] == 0
    assert status["retrying"] is False
    assert status["error_kind"] == ""
    assert status["message"] == ""


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_retrying_state_during_backoff(flavor: str, tmp_path: Path, monkeypatch) -> None:
    """退避等待中 → `retrying` 为真 + `message` 是进行中的摘要 + `retry_count` ≥ 1。

    观测方式 = **在 `before_retry` 那一刻抓快照**（不是轮询）：轮询要跟 0.3 秒的
    退避窗口赛跑，worker 起跑到主线程第一次采样之间窗口可能已经关了——本用例第一版
    就这么假绿过（`retrying` 恒 False，而 `retry_count` 已是 1）。
    窗口是「`before_retry` 开、退避结束关」，所以在开的那一刻抓是确定性的。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.3)
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)
    during_backoff: list[dict[str, Any]] = []

    def capture_on_retry(attempt, exc, on_disk, restarted):  # noqa: ANN001
        during_backoff.append(status_fn(task))

    def spy(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        original = kwargs.get("before_retry")

        def watcher(*args):                # noqa: ANN002
            # 先让任务自己的回调把状态写好，再抓快照（抓早了看到的是开窗前的样子）
            result = original(*args) if original is not None else None
            capture_on_retry(*args)
            return result

        kwargs["before_retry"] = watcher
        return resumable_download(url, dest, on_progress, **kwargs)

    with ByteServer(PAYLOAD, cut_after=64 * 1024, cut_runs=1) as server:
        if flavor == "full":
            task.parts[0].url = server.url
        else:
            task.batches[0].parts[0].url = server.url
        task._download = spy
        task.run()

    assert task.state is TaskState.DONE, task.error
    assert during_backoff, "没有重试发生"
    mid = during_backoff[0]
    assert mid["retrying"] is True, mid
    assert mid["retry_count"] >= 1, mid
    assert "连接中断" in mid["message"], mid["message"]
    assert mid["resume_percent"] >= 0, mid["resume_percent"]
    assert mid["error"] == "", "重试中不算失败（终态原因才进 error）"
    assert mid["error_kind"] == "network"
    # 终态：摘要在场 = 谎报「还在重试」
    done = status_fn(task)
    assert done["state"] == "done"
    assert done["message"] == "" and done["retrying"] is False
    assert done["error"] == ""


def test_retry_window_closes_when_backoff_ends(tmp_path: Path, monkeypatch) -> None:
    """窗口的关闭时刻：退避等待**结束**（不是下一轮开始）、且摘要在同一次调用里清空。

    合成断言（不赛跑）：直接调任务的两个窗口回调，断言「开 → 关」的字段变化。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    task = _full_task(tmp_path)
    task._state = TaskState.DOWNLOADING
    part = task.parts[0]
    half = part.size // 2
    task._on_retry(part)(2, OSError("连接重置"), half, False)     # 开窗（正常续传）
    opened = full_task_status(task)
    assert opened["retrying"] is True and opened["retry_count"] == 2
    assert "连接重置" in opened["message"]
    assert opened["resume_percent"] == 50, opened["resume_percent"]
    task._on_retry_window_closed()                               # 关窗（退避结束）
    closed = full_task_status(task)
    assert closed["retrying"] is False
    assert closed["message"] == "", "关窗必须连摘要一起清（不许自相矛盾）"
    assert closed["retry_count"] == 2, "计数是「本卷累计」，关窗不清零"


def test_retry_resume_percent_is_zero_when_server_forced_restart(
    tmp_path: Path, monkeypatch
) -> None:
    """服务器没让我们接上（`restarted=True`）→ 本轮起点就是 **0%**（如实，不是「不知道」）。

    说 -1（不知道）会让界面拿不到「从 0 重新下」这个事实；说上一份的进度则是撒谎
    ——那份半成品已经被丢弃了。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    task = _full_task(tmp_path)
    task._state = TaskState.DOWNLOADING
    part = task.parts[0]
    task._on_retry(part)(1, OSError("连接重置"), part.size - 1, True)   # 几乎下完但被丢弃
    status = full_task_status(task)
    assert status["resume_percent"] == 0, status["resume_percent"]


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_failed_network_kind(flavor: str, tmp_path: Path, monkeypatch) -> None:
    """网络失败终态：`error_kind == "network"`、`message` 清空、`retrying` 归假。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)

    def capped(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        return resumable_download(url, dest, on_progress, max_attempts=1, **kwargs)

    with ByteServer(PAYLOAD, cut_after=64 * 1024, cut_runs=99) as server:
        if flavor == "full":
            task.parts[0].url = server.url
        else:
            task.batches[0].parts[0].url = server.url
        task._download = capped
        task.run()

    status = status_fn(task)
    assert status["state"] == "failed"
    assert status["error_kind"] == "network"
    assert status["retrying"] is False
    assert status["message"] == ""
    assert "下载失败" in status["error"]


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_failed_verify_kind(flavor: str, tmp_path: Path) -> None:
    """校验失败终态：`error_kind == "verify"`（前端据此说「重下也不会有变化」）。"""
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)
    # 假下载器：写一份与清单不符的内容（长度对、内容不对）并自称它的 sha
    task._download = lambda url, dest, on_progress: (  # type: ignore[attr-defined]
        dest.write_bytes(b"x" * len(PAYLOAD)), on_progress(len(PAYLOAD)), "0" * 64
    )[2]
    task.run()

    status = status_fn(task)
    assert status["state"] == "failed"
    assert status["error_kind"] == "verify"
    assert "校验失败" in status["error"]
    assert status["retrying"] is False
    assert status["message"] == ""


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_cancelled_state_has_no_error_kind(flavor: str, tmp_path: Path) -> None:
    """取消不是失败态分类：`error_kind` 保持空串（词表 = "" / network / verify）。"""
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)
    task.cancel()
    task.run()
    status = status_fn(task)
    assert status["state"] == "cancelled"
    assert status["error_kind"] == ""
    assert status["retrying"] is False
    assert status["message"] == ""


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_cancel_during_backoff_clears_retry_state(
    flavor: str, tmp_path: Path, monkeypatch
) -> None:
    """**退避等待中被取消** → 取消态里不许残留「重试 1 次 / 网络错误」。

    这是本矩阵最容易假绿的一格：`run()` 开头就取消时那两项本来就是 0，怎么断言都过；
    真正难的是「先失败一次、进了退避、这时用户点取消」——不清就会把用户自己点的取消
    报成网络故障（前端照 network 话术说「点重试会接着下」，而任务已经取消了）。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.3)
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)

    def cancel_on_retry(attempt, exc, on_disk, restarted):  # noqa: ANN001
        task.cancel()                      # 模拟「用户趁退避那几秒点了取消」

    def cancelable(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        # 包装（不能另传 before_retry：适配层已经传了一个）
        original = kwargs.get("before_retry")

        def watcher(*args):                # noqa: ANN002
            cancel_on_retry(*args)
            if original is not None:
                return original(*args)
            return None

        kwargs["before_retry"] = watcher
        return resumable_download(url, dest, on_progress, **kwargs)

    with ByteServer(PAYLOAD, cut_after=64 * 1024, cut_runs=99) as server:
        if flavor == "full":
            task.parts[0].url = server.url
        else:
            task.batches[0].parts[0].url = server.url
        task._download = cancelable
        task.run()

    status = status_fn(task)
    assert status["state"] == "cancelled", status["error"]
    assert status["retry_count"] == 0, "取消态不该残留重试计数"
    assert status["error_kind"] == "", "取消不是网络失败"
    assert status["retrying"] is False
    assert status["message"] == ""
    assert status["error"] == ""


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_message_cleared_when_backoff_window_closes(
    flavor: str, tmp_path: Path, monkeypatch
) -> None:
    """退避窗口一关，摘要就要跟着空——不许「重试第 2 次」挂满剩下整段下载。

    `retrying=False` 而 `message` 还写着「正在自动重试」，是个自相矛盾的状态组合：
    前端只能靠解析文案去猜，而那正是 spec 明禁的事。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.1)
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)
    observed: list[tuple[bool, str]] = []

    def spy(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        original = on_progress
        calls = {"n": 0}

        def watcher(nbytes: int) -> None:
            calls["n"] += 1
            if calls["n"] >= 2:            # 第 2 次回调 = 重试那一轮已经在读数据
                status = status_fn(task)
                observed.append((status["retrying"], status["message"]))
            return original(nbytes)

        return resumable_download(url, dest, watcher, **kwargs)

    with ByteServer(PAYLOAD, cut_after=64 * 1024, cut_runs=1) as server:
        if flavor == "full":
            task.parts[0].url = server.url
        else:
            task.batches[0].parts[0].url = server.url
        task._download = spy
        task.run()

    assert task.state is TaskState.DONE, task.error
    assert observed, "没有重试发生"
    for retrying, message in observed:
        assert retrying is False, (retrying, message)
        assert message == "", f"退避窗口关了，摘要还挂着：{message!r}"


@pytest.mark.parametrize("flavor", ["full", "materials"])
def test_apply_phase_failure_has_no_error_kind(flavor: str, tmp_path: Path) -> None:
    """应用阶段失败（解压 / 磁盘写入）**不是** network：分类留空，前端走通用话术。

    spec 的词表只有 `"" | "network" | "verify"`；把「磁盘写满」讲成网络失败
    （「点击重试会从这里接着下」）正是这套分类想消灭的那种误导。
    """
    status_fn, make_task = STATUS_FOR[flavor]
    task = make_task(tmp_path)

    def boom(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        raise OSError("磁盘写满")

    def download(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        payload = PAYLOAD
        dest.write_bytes(payload)
        on_progress(len(payload))
        return _sha(payload)

    if flavor == "full":
        task._on_complete = boom
    else:
        task._on_complete = boom
    task._download = download
    task.run()

    status = status_fn(task)
    assert status["state"] == "failed"
    assert "应用失败" in status["error"]
    assert status["error_kind"] == "", "应用阶段失败不该被塞进 network"


def test_error_kind_vocabulary_is_closed() -> None:
    """词表收口：`error_kind` 只产出四个已知值（下载域单源，不靠标记字符串）。"""
    from contest_generator.download_resume import (
        DownloadCancelledError,
        DownloadLocalCorruptError,
        DownloadSizeMismatchError,
        DownloadTruncatedError,
        DownloadVerifyError,
        error_kind,
    )

    cases = {
        DownloadCancelledError("x"): "cancelled",
        DownloadSizeMismatchError("x"): "verify",
        DownloadLocalCorruptError("x"): "verify",
        DownloadVerifyError("x"): "verify",
        DownloadTruncatedError("x"): "network",
        OSError("x"): "network",
    }
    allowed = {"", "network", "verify", "cancelled"}
    for exc, expected in cases.items():
        got = error_kind(exc)
        assert got == expected, (type(exc).__name__, got)
        assert got in allowed


# ---------------------------------------------------------------------------
# 端点：不加新协议，字段直接透出
# ---------------------------------------------------------------------------


def test_retry_state_resets_per_part(tmp_path: Path) -> None:
    """多卷：上一卷的重试计数与错误分类**不许漏到下一卷**。

    `retry_count` 的语义是「**本卷**累计自动重试次数」（spec 原话），所以换卷即清零；
    `error_kind` 同理（上一卷验失败过，不该让下一卷一上来就是 verify）。
    """
    first_payload = b"a" * 300  # 小卷：走「整卷重下」那条分支（不折腾 Range）
    second_payload = PAYLOAD
    task = FullDownloadTask(
        task_dir=tmp_path / "updates",
        parts=[
            {"name": "part1.zip", "url": "https://x/part1.zip",
             "size": len(first_payload), "sha256": _sha(first_payload)},
            {"name": "part2.zip", "url": "https://x/part2.zip",
             "size": len(second_payload), "sha256": _sha(second_payload)},
        ],
        snapshot_interval=0.0,
    )
    task.retry_count = 5                       # 脏状态（模拟上一卷留下的）
    task.last_error_kind = "verify"
    task._retrying = True
    task._message = "上一卷的摘要"

    seen: list[dict[str, Any]] = []

    def download(url: str, dest: Path, on_progress, **kwargs):  # noqa: ANN001, ANN003
        seen.append(full_task_status(task))    # 每一卷开始时看一眼
        payload = first_payload if url.endswith("part1.zip") else second_payload
        dest.write_bytes(payload)
        on_progress(len(payload))
        return _sha(payload)

    task._download = download  # type: ignore[attr-defined]
    task.run()
    assert task.state is TaskState.DONE, task.error
    assert len(seen) == 2, "两卷各看一次"
    for snapshot in seen:
        assert snapshot["retry_count"] == 0, snapshot
        assert snapshot["error_kind"] == "", snapshot
        assert snapshot["retrying"] is False, snapshot
        assert snapshot["message"] == "", snapshot


def test_endpoints_expose_new_fields(tmp_path: Path) -> None:
    """两条 status 端点直接透出新字段（不加新端点、不包一层）。"""
    from fastapi.testclient import TestClient

    from contest_generator import full_task as ft
    from contest_generator.webapp import AppContext, create_app

    ft.set_full_task(None)
    client = TestClient(create_app(AppContext(config_path=tmp_path / "config.json")))
    for path in ("/api/update/full/status", "/api/update/materials/status"):
        body = client.get(path).json()
        assert set(body) == EXISTING_KEYS | NEW_KEYS, path
        assert body["retry_count"] == 0 and body["retrying"] is False
        assert body["error_kind"] == ""


def test_snapshot_does_not_carry_retry_state(tmp_path: Path) -> None:
    """重试观测是**内存态**：不落快照（重启后从 0 重新计更诚实）。"""
    task = _full_task(tmp_path)
    task.retry_count = 7
    task.last_retry_at = 123.0
    task.last_error_kind = "network"
    task._retrying = True
    task._write_snapshot(force=True)
    snapshot = json.loads(
        (tmp_path / "updates" / "full-task.json").read_text(encoding="utf-8")
    )
    assert "retry_count" not in snapshot
    assert snapshot["parts"][0]["downloaded_bytes"] == 0


def test_download_resume_module_has_no_status_knowledge() -> None:
    """分层守卫：下载域的**代码**不碰状态面字段（词表归任务层投影）。

    为什么值得钉：`error_kind` 这个名字在同一份代码里有两层含义——下载域的**分类函数**
    与状态面的**字段**。哪天有人把状态字段的取值逻辑塞回下载域，这两层就会开始互相污染。

    判据只看**代码里真的用到这几个名字的地方**（赋值目标 / 属性访问 / 下标键），
    不看注释、docstring 与函数名：本模块的注释里正大光明地讨论这几个字段
    （说明为什么不在这里定义它们），而 `retry_resume_percent` 这个**函数名**也含
    `resume_percent` 三个字——拿子串判会把这两件正常事一起判违规。
    """
    import ast

    tree = ast.parse(Path(download_resume.__file__).read_text(encoding="utf-8"))
    fields = {"retrying", "retry_count", "resume_percent", "last_error_kind"}
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in fields:
            offenders.append(f"属性 {node.attr}")
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in fields:
                    offenders.append(f"赋值 {target.id}")
                if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) \
                        and target.slice.value in fields:
                    offenders.append(f"下标 {target.slice.value}")
    assert not offenders, offenders
