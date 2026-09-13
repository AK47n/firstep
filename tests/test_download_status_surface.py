"""下载任务状态面契约测试（工单 resumable-download/04）。

**这一份只管状态面**：`task_status` / `full_task_status` 的字段契约、三字段取值矩阵、
`message` 的语义边界。两条链路的**行为**（断点、半成品、重试）在
`tests/test_full_task.py` / `tests/test_materials_task.py` 里测——别把两件事混在一处。

为什么值得单独一个文件：状态面是**前端唯一的信息来源**（前端不许解析 `error` 文案来分类），
它的字段名与取值就是一份跨语言契约。契约测试要能一眼看全六态矩阵，散布在各行为用例里就看不全了。
"""

from __future__ import annotations

import ast
import json
import threading
import time
import warnings
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
# 12 个键的**全集**：两侧状态视图的载荷必须与它**严格相等**（工单 12）
STATUS_KEYS = EXISTING_KEYS | NEW_KEYS

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
def test_status_keys_are_the_contracted_set(flavor: str, tmp_path: Path) -> None:
    """结构守卫：状态载荷的键集合**就是**契约那 12 个（**严格相等**）。

    （名字原先叫 `..._contracted_eleven`，而契约是 **12** 个键——工单 12 评审指出名不符实，已改。）

    工单 12 把这条从「包含 8 个既有键 + 包含 4 个新增键」改成**严格相等**：
    多一个键与少一个键**同等致命**——前端是零分支契约（少一个键 → `undefined`），
    而多一个键意味着前端拿不到它、契约测试却全绿（那正是「判据比实际弱」的形状）。
    另一侧（`test_full_task.py::test_status_idle_shape`）本来就是严格相等；
    本单把**两侧拉齐**，并把两侧共用的这份键集合收成 `STATUS_KEYS`。

    两侧**分别**断言（不是一条循环）：漏改一侧必须指名道姓地红在哪一侧。

    **将来要加字段怎么办**（这条判据是有意收紧的，不是说「永远不许加」）：先在这条
    用例里改 `STATUS_KEYS`——`.scratch/resumable-download/spec.md` 起字段就是跨语言契约，
    改契约就该改这一处、并当场过一遍两侧；若哪天两侧**依法**要长得不一样，
    那也在这里显式分成两套键集合（让「不对称」成为一条写下来的决定，而不是漂出来的）。
    """
    status_fn, make_task = STATUS_FOR[flavor]
    for status in (status_fn(None), status_fn(make_task(tmp_path))):
        assert set(status) == STATUS_KEYS, (
            f"{flavor} 侧状态载荷的键与契约不一致："
            f"多 {sorted(set(status) - STATUS_KEYS)} / "
            f"少 {sorted(STATUS_KEYS - set(status))}"
        )


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
        assert set(body) == STATUS_KEYS, path
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


_RETRY_FIELDS = {"retry_count", "last_retry_at", "last_error_kind",
                 "retrying", "resume_percent", "message"}


def _ast_assign_targets(stmt: Any) -> list[str]:
    """一条语句的赋值目标名（属性名与裸名都算；非赋值 = 空表）。"""
    if isinstance(stmt, ast.Assign):
        targets = stmt.targets
    elif isinstance(stmt, ast.AnnAssign):
        targets = [stmt.target]
    else:
        return []
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Attribute):
            names.append(target.attr)
        elif isinstance(target, ast.Name):
            names.append(target.id)
    return names


def _assigned_retry_fields(path: str) -> set[str]:
    """该文件里被赋过值的重试观测字段名。"""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        found.update(n for n in _ast_assign_targets(node) if n in _RETRY_FIELDS)
    return found


def _reset_blocks(path: str) -> list[list[str]]:
    """找出「连续 ≥3 条赋值都写重试观测字段」的块 = **复位块**。

    判「重复有没有回来」要认的是这个形状：复位是把六个字段一起写回去，所以它必然
    表现为一个连续的赋值块。单条写某个字段（失败路径写 `last_error_kind`、
    下载完成时清 `message`）是正常的分散写入，不算重复。
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    blocks: list[list[str]] = []

    def scan(body: list[Any]) -> None:
        run: list[str] = []
        for stmt in body:
            hit = [n for n in _ast_assign_targets(stmt) if n in _RETRY_FIELDS]
            if hit:
                run.extend(hit)
                continue
            if len(run) >= 3:
                blocks.append(list(run))
            run = []
        if len(run) >= 3:
            blocks.append(list(run))

    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and all(
            isinstance(stmt, ast.stmt) for stmt in body
        ):
            scan(body)
    return blocks


def test_retry_observation_has_a_single_home() -> None:
    """结构守卫（工单 09）：重试观测的**规则**只许有一处实现。

    为什么值得钉：这套规则原本在两条链路上各写一遍，代价已经付过——
    「退避中取消要归零」工单 04 评审时**两边都漏了**，各补一次；
    「退避关窗要同时清摘要」也是两边各改一次。判定「重复有没有回来」不能靠人眼，
    故这里机械判三件事：

    1. 任务模块里不再有**成块的**重试观测赋值（复位块）；
    2. 那四个回调的**实现**不再长在任务模块上（`TaskRetryMixin` 只留调用转发）；
    3. 共享件仍是这六个字段的家（防「把规则挪走、守卫却留在原地」）。

    判据只看「赋值目标」——注释、docstring、以及状态面投影里的**读取**都不算
    （投影本来就要读；`task_retry` 自己的注释里也正大光明地讨论这些名字）。
    """
    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt
    from contest_generator import task_retry as tr

    # 1) 任务模块不许再有复位块
    for module in (ft, mt):
        blocks = _reset_blocks(module.__file__)
        assert not blocks, (
            f"{Path(module.__file__).name} 又出现成块的重试观测赋值：{blocks}"
            "（复位应走 TaskRetryState.reset / reset_for_cancelled）"
        )

    # 2) 那四个回调的实现只许有一处：任务模块上不该再有它们的 def
    callback_names = {"_on_progress", "_on_attempt_start",
                      "_on_retry_window_closed", "_on_retry"}
    for module in (ft, mt):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        defined = {
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name in callback_names
        }
        assert not defined, (
            f"{Path(module.__file__).name} 又重新定义了回调：{sorted(defined)}"
            "（共享实现在 task_retry）"
        )

    # 3) 共享件确实是字段的家
    assert _assigned_retry_fields(tr.__file__) >= _RETRY_FIELDS

    # 4) 两条链路**确实**继承了 mixin、并实现了取值入口
    #    （少了这条：有人把继承删掉，上面两条照样绿——它们只看「文件里没有重复」）
    from contest_generator.task_retry import TaskRetryMixin

    for cls, name in ((ft.FullDownloadTask, "FullDownloadTask"),
                      (mt.ApplyTask, "ApplyTask")):
        assert issubclass(cls, TaskRetryMixin), f"{name} 不再继承 TaskRetryMixin"
        # 取值入口真的接上了（不是继承来的那条抛 NotImplementedError 的桩）
        assert cls._retry_state is not TaskRetryMixin._retry_state, (
            f"{name} 没有实现 _retry_state（还在用 mixin 里的桩）"
        )

    # 5) 三条**规则**必须在共享件里、且各自写到该写的字段
    #    （第 3 条只看「有没有赋值」，被 mixin 的属性 setter 也能满足——那是个空断言；
    #     这一条改成按方法逐个查，才真的钉住「规则住在 TaskRetryState」）
    import inspect

    from contest_generator.task_retry import TaskRetryState

    def cleared_fields(method_name: str) -> set[str]:
        body = inspect.getsource(getattr(TaskRetryState, method_name))
        return {
            field for field in _RETRY_FIELDS
            if f"self.{field} =" in body
        }

    assert cleared_fields("reset") >= _RETRY_FIELDS, "reset 没把六个字段都复位"
    assert cleared_fields("reset_for_cancelled") >= {
        "retry_count", "last_error_kind", "retrying", "message",
    }, "取消复位漏了字段"
    assert cleared_fields("close_window") >= {"retrying", "message"}, (
        "关窗必须同时清 retrying 与 message（只清一个会留下自相矛盾的状态组合）"
    )


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


# ---------------------------------------------------------------------------
# 工单 12：分卷状态形状（两模块各一份）只许有一份契约
# ---------------------------------------------------------------------------


# 快照里那条契约的字段序列（顺序 = `to_dict` 的键序 = 快照 JSON 键序）。
# 顺序也算契约：`_write_snapshot` 一落盘，`restore_snapshot_parts` 就按这些键**按名**读，
# 所以这里钉的是「两侧同形且都在」，不是「恰好这几个字」。
PART_FIELDS = ("name", "url", "size", "sha256",
               "downloaded_bytes", "ok", "dest")


def _class_node(source: str, name: str) -> Any:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    pytest.fail(f"源码里找不到类 {name}（守卫的扫描面变了？）")


def _without_docstrings(node: ast.AST) -> ast.AST:
    """→ 抹掉 docstring 的等价节点（`ast.unparse` 会把类/方法 docstring 一起带出来）。

    为什么要规范化再比：docstring 是说明文字，两侧措辞本来就不同
    （materials 那份写着「与 full_task 同形」），**比形状不该把文字算进去**。
    """
    clone = ast.parse(ast.unparse(node)).body[0]
    for child in ast.walk(clone):
        body = getattr(child, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            child.body = body[1:]
    return clone


def _dataclass_shape(source: str, name: str) -> dict[str, Any]:
    """→ 一个 dataclass 的**形状**：字段 / 默认值 / 方法**正文** / `to_dict` 键序。

    为什么不直接 `import _PartState` 比：守的是**源码形状**（含方法的有无），
    而私有类没有实例可比；按 AST 取还能把「一侧多长出来一个方法」这种
    **漂移**抓住（那正是工单 12 删掉的那类东西）。

    方法那一轴比的是 **名字 → 规范化后的正文**（不是只比名字）：只比名字的话，
    「一侧把 `to_dict` 的取值改了」这种漂移不会红（工单 12 评审指出第一版就是这个毛病——
    判据比工单承诺的「五轴逐项相同」弱）。
    """
    node = _class_node(source, name)
    fields: list[str] = []
    defaults: list[str] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields.append(stmt.target.id)
            defaults.append(
                ast.unparse(stmt.value) if stmt.value is not None else "<必填>"
            )
    methods: dict[str, str] = {}
    for stmt in node.body:
        if isinstance(stmt, ast.FunctionDef):
            methods[stmt.name] = ast.unparse(_without_docstrings(stmt))
    keys: list[str] = []
    to_dict = next((s for s in node.body
                    if isinstance(s, ast.FunctionDef) and s.name == "to_dict"), None)
    if to_dict is not None:
        for child in ast.walk(to_dict):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) \
                    and child.value in PART_FIELDS and child.value not in keys:
                keys.append(child.value)
    return {"fields": fields, "defaults": defaults,
            "methods": methods, "to_dict_keys": keys}


def _shape_problems(full_source: str, mats_source: str) -> list[str]:
    """→ 形状漂移清单（空表 = 两侧同形）。**纯函数**：吃两段源码文本，好做反向验证。

    契约断言**两侧都查**（工单 12 评审指出第一版只查 full 侧：两侧同时改错就全绿——
    而「两侧一起漂」正是这套副本最可能的坏法）。
    """
    problems: list[str] = []
    full_shape = _dataclass_shape(full_source, "_PartState")
    mats_shape = _dataclass_shape(mats_source, "_PartState")
    for axis in ("fields", "defaults", "methods", "to_dict_keys"):
        if full_shape[axis] != mats_shape[axis]:
            problems.append(
                f"_PartState.{axis} 两侧不同形：full={full_shape[axis]!r} "
                f"materials={mats_shape[axis]!r}"
            )
    for flavor, shape in (("full", full_shape), ("materials", mats_shape)):
        if list(shape["fields"]) != list(PART_FIELDS):
            problems.append(
                f"{flavor} 侧 _PartState 字段与快照契约不一致：{shape['fields']}"
            )
        if list(shape["to_dict_keys"]) != list(PART_FIELDS):
            problems.append(
                f"{flavor} 侧 to_dict 键序与快照契约不一致：{shape['to_dict_keys']}"
            )
    return problems


def test_part_state_shape_has_a_single_contract() -> None:
    """结构守卫（工单 12）：两条链路的 `_PartState` 形状**逐项相同**，且它就是快照契约。

    为什么值得钉：这份形状是 `_write_snapshot` 的落盘内容 + `restore_snapshot_parts`
    的读入内容，两条链路各持一份**源码副本**。工单 12 量出来的漂移是
    **一侧多出一个从来没人调用的方法**（两处 `from_dict`），而不是字段不同——
    所以判据要覆盖「字段 / 默认值 / 方法集合 / `to_dict` 正文 / `to_dict` 键序」五个轴。

    判据本体是**纯函数**（`_shape_problems` 吃两段源码文本），
    反向验证直接喂「被人动过的源码副本」——真身源码一个字节都不碰
    （工单 11 立的铁律）。
    """
    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt

    problems = _shape_problems(
        Path(ft.__file__).read_text(encoding="utf-8"),
        Path(mt.__file__).read_text(encoding="utf-8"),
    )
    assert not problems, "两条链路的分卷状态形状漂了：" + "；".join(problems)
    # 两侧都**没有** from_dict（工单 12 删掉的就是它：零调用点）
    assert not hasattr(ft._PartState, "from_dict")
    assert not hasattr(mt._PartState, "from_dict")
    assert not hasattr(mt._BatchState, "from_dict")
    # `_BatchState` 是资料库独有（两层组织），但它的**方法集合**也该与 `_PartState` 同风格：
    # 只留 `to_dict`（读写不对称的另一半在工单 12 被证明没人用）
    batch = _dataclass_shape(Path(mt.__file__).read_text(encoding="utf-8"), "_BatchState")
    assert list(batch["methods"]) == ["to_dict"], list(batch["methods"])


def test_shape_guard_turns_red_on_drift() -> None:
    """**反向验证**：三种真实漂移，守卫必须指名道姓转红（否则它只是装饰）。

    三种漂移都是**改过源码文本**的产物，不是想象出来的：
    ① 只有一侧把 `from_dict` 加回来（工单 12 删掉的形状，正是本单要防的漂移）；
    ② 只有一侧漏掉 `dest` 字段（快照恢复读它，漏了 `part_paths()` 就交不出输入）；
    ③ 只有一侧把 `to_dict` 的键改名（快照读侧按名取，改名 = 静默丢字段）。
    """
    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt

    full_text = Path(ft.__file__).read_text(encoding="utf-8")
    mats_text = Path(mt.__file__).read_text(encoding="utf-8")
    assert _shape_problems(full_text, mats_text) == [], "干净的两份不该报问题"

    # ① 一侧把 from_dict 加回来
    re_added = mats_text.replace(
        "    def to_dict(self) -> dict[str, Any]:\n"
        "        return {\n"
        '            "name": self.name,',
        "    @staticmethod\n"
        "    def from_dict(data):\n"
        '        return _PartState(name="x")\n'
        "\n"
        "    def to_dict(self) -> dict[str, Any]:\n"
        "        return {\n"
        '            "name": self.name,',
        1,
    )
    assert re_added != mats_text, "阳性对照没造出来（①）：替换锚点没命中"
    problems = _shape_problems(full_text, re_added)
    assert any("methods" in p for p in problems), problems

    # ② 一侧漏掉 dest 字段（连默认值一起）
    dropped = mats_text.replace('    dest: str = ""  # 本地保存路径（快照恢复时校验存在与 sha）\n', "", 1)
    assert dropped != mats_text, "阳性对照没造出来（②）：替换锚点没命中"
    problems = _shape_problems(full_text, dropped)
    assert any("fields" in p for p in problems), problems

    # ③ 一侧把 to_dict 的键改名
    renamed = mats_text.replace('            "downloaded_bytes": self.downloaded_bytes,',
                               '            "已下载字节": self.downloaded_bytes,', 1)
    assert renamed != mats_text, "阳性对照没造出来（③）：替换锚点没命中"
    problems = _shape_problems(full_text, renamed)
    assert any("to_dict" in p for p in problems), problems


# ---------------------------------------------------------------------------
# 12 键契约只许有一个家（工单 15）
# ---------------------------------------------------------------------------

# 「这一份是契约副本」的判据 = 字面集合（或其联合）枚举了契约的 ≥8 个键。
# 阈值不是随手取的（工单 15 实测）：`_RETRY_FIELDS` 那条结构守卫的字段集与契约只重叠
# **4** 个（它是「重试观测」那件事的内部属性名，不是载荷键），而仓内真正的契约副本是
# **8 键**（`EXISTING_KEYS`，契约的前半）与 **12 键**（`STATUS_KEYS` = 前后半的联合）。
# 阈值卡在 8 是为了连「只抄了前半」也认出来，同时不误伤 4 键那类部分重叠。
CONTRACT_COPY_MIN_OVERLAP = 8


def _resolve_unions(tree: ast.AST, known: dict[str, set[str]]) -> dict[str, set[str]]:
    """模块级赋值两轮解析：先收字面量，再把 `A | B` 联合解出来（与书写顺序无关）。

    **为什么需要它**：契约常量自己就是 `STATUS_KEYS = EXISTING_KEYS | NEW_KEYS`
    （两个字面量拼的），只认 `ast.Set` 的守卫**连契约本体都认不出来**——
    评审实测：第一版在现状下只命中 `EXISTING_KEYS`（8 键），自证那句「本文件那份契约常量
    被认出来」名不副实。补上联合解析后，`STATUS_KEYS`（12 键）自己也在命中列表里，
    而「别处用 `A | B` 拼一份副本」这条绕过路径同时被堵上（反向验证里有这一格）。
    """
    consts = dict(known)
    assigns = [stmt for stmt in ast.walk(tree)
               if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)]
    for _ in range(2):
        for stmt in assigns:
            keys = _literal_keys(stmt.value, consts)
            if keys:
                consts[stmt.targets[0].id] = keys
    return consts


def _literal_keys(node: ast.AST, consts: dict[str, set[str]]) -> set[str] | None:
    """一个表达式能解出多少「字面键」：`{…}` / `A | B` / `名字`；解不出 → None。"""
    if isinstance(node, ast.Set):
        keys = {e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        return keys or None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _literal_keys(node.left, consts), _literal_keys(node.right, consts)
        if left is not None and right is not None:
            return left | right
        return None
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def _contract_literal_copies(root: Path) -> list[tuple[Path, int, int]]:
    """`root` 下**枚举了契约 ≥8 个键**的字面集合 / 联合 → [(文件, 行, 契约键数)]。

    为什么值得钉（工单 15 的账）：这条 12 键契约在仓里曾有三份副本——
    `STATUS_KEYS` 常量、`tests/test_full_task.py::test_status_idle_shape` 的内联字面、
    以及两侧产品投影各自的空态 / 有态键表（后者是**实现**，不归这条守卫管）。
    两份测试侧副本里那份内联的已收回：**量出来的取舍是「只少一格」**——
    键与态的那几格它本来就包含在 `STATUS_KEYS` 那条里（探针逐格证过），
    它真正多出来的唯一作用是「产品与共同常量一起改」时再红一次，
    而那正是本文件 docstring 写明的**加字段手续**。这条守卫钉「别又抄回来」。

    **判据面（已知边界，写在这儿免得被当成万能）**：只认 `{…}` 字面量与
    `A | B` 联合（含模块级名字解析）；`set([...])` / 集合推导 / 从别处 import 再改名
    这类写法**认不出来**。要收的口子是「又把 12 个键抄一遍」，那两种写法都不是它的形状。

    **读不了的 `.py` 一律大声失败，不许静默跳过**：第一版 `except (OSError, SyntaxError):
    continue`，于是真身实测时那个带 BOM 的文件（`utf-8` 读出 `\\ufeff` → `ast.parse` 抛错）
    被**悄悄跳过**，守卫照样绿——「守卫只是装饰」正是工单 10/12 反复记过的坑。
    现在 BOM 用 `utf-8-sig` 吃掉，真读不了 / 真解析不了就让用例红。
    """
    findings: list[tuple[Path, int, int]] = []
    for path in sorted(root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8-sig")   # BOM 吃掉，别让它变成解析失败
        except (OSError, UnicodeDecodeError) as exc:
            raise AssertionError(
                f"守卫扫到读不了的 .py：{path}（{exc}）——扫描面被藏起来了，"
                "先修文件或修守卫，别让这一格静默通过") from exc
        try:
            # 解析别人的源码会把他们字符串里的无效转义（`"\m"` 之类）翻成 SyntaxWarning
            # 打到本用例头上——与本守卫无关的噪声，就地静音（`ast.parse` 没有静音开关）。
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(text)
        except SyntaxError as exc:
            raise AssertionError(
                f"守卫扫到解析不了的 .py：{path}:{exc.lineno}（{exc.msg}）——"
                "静默跳过等于放它藏一份契约副本") from exc
        consts = _resolve_unions(tree, {})
        seen: set[int] = set()
        for node in ast.walk(tree):
            keys = _literal_keys(node, consts)
            if not keys:
                continue
            hits = len(keys & STATUS_KEYS)
            if hits >= CONTRACT_COPY_MIN_OVERLAP and id(node) not in seen:
                seen.add(id(node))
                findings.append((path, node.lineno, hits))
    return findings


def test_status_contract_has_a_single_home() -> None:
    """结构守卫：12 键契约的字面副本只许住在**本文件**。

    守卫面 = `tests/**/*.py`（不含产品侧：两侧投影的「空态 + 有态」两张键表是**实现**，
    它们的一致性由 `test_status_keys_are_the_contracted_set` 在**两个态上都查**兜着）。
    判定只看字面集合与它们的联合——JS 侧那些对象字面量是**渲染用例的输入**（只读不判），
    本来就不该被逼着写全 12 个键，故不在守卫面内。
    """
    here = Path(__file__).resolve()
    findings = _contract_literal_copies(here.parent)
    assert findings, "本文件里一份契约字面量都没被认出来（守卫的扫描面变了？）"
    # 自证锚在**契约本体**上，不是随便哪个集合：`STATUS_KEYS` 是 12 键，必须被认出来。
    # （第一版只认 `ast.Set`，于是只命中 `EXISTING_KEYS`（8 键）——那句自证名不副实。）
    assert any(hits == len(STATUS_KEYS) for path, _, hits in findings
               if path.resolve() == here), (
        "本文件里的 12 键契约本体没被认出来——守卫的判据面（字面量 / 联合）漏了它")
    others = [f"{path.name}:{line}（{hits} 个契约键）"
              for path, line, hits in findings if path.resolve() != here]
    assert not others, (
        "12 键契约在别处又出现了字面副本：" + "、".join(others)
        + "——契约的家是 tests/test_download_status_surface.py 的 STATUS_KEYS，"
          "要加字段就改那一处（本文件 docstring 写明的手续）")


def test_contract_home_guard_turns_red_on_a_second_copy(tmp_path: Path) -> None:
    """反向验证：喂一份**又抄了一遍 12 键**的假测试文件，守卫必须指名道姓转红。

    喂的是 `%TEMP%` 下的副本，真身一个字节不碰（工单 10/12 立的纪律）。
    另配**两条阴性对照**：只写 4 个键的文件不该被认出来（阈值是真的），
    `EXISTING_KEYS` 那种 8 键的半份**在同一文件里**也不该被当成「别处副本」。
    """
    import inspect

    guard_src = (
        f"CONTRACT_COPY_MIN_OVERLAP = {CONTRACT_COPY_MIN_OVERLAP}\n"
        f"CONTRACT_KEYS = {sorted(STATUS_KEYS)!r}\n"
        + inspect.getsource(_literal_keys)
        + inspect.getsource(_resolve_unions)
        + inspect.getsource(_contract_literal_copies).replace(
            "STATUS_KEYS", "set(CONTRACT_KEYS)")
    )
    assert "set(CONTRACT_KEYS)" in guard_src, "自造源码的替换锚点没命中（守卫换了写法？）"
    ns: dict[str, object] = {"ast": ast, "Path": Path, "warnings": warnings}
    exec(compile(guard_src, "<guard-copy>", "exec"), ns)   # noqa: S102 - 自造源码，仅测试
    guard = ns["_contract_literal_copies"]

    # 假副本的键**从契约现derive**，不写死 12 个：写死的话，将来按手续加字段时
    # 这条反向验证自己就会红（`findings[0][2] == len(STATUS_KEYS)` 不再成立）——
    # 那正是本单在收掉的那份内联字面身上批评过的毛病（测试跟着数字走）。
    keys = sorted(STATUS_KEYS)
    half = len(keys) // 2
    copy = tmp_path / "test_second_copy.py"
    copy.write_text(
        "def test_copy():\n"
        f"    assert set({set(keys)!r}) == set()\n",
        encoding="utf-8",
    )
    findings = guard(tmp_path)                       # type: ignore[operator]
    assert findings, "阳性对照没被认出来：守卫的判据失效"
    assert findings[0][0].name == "test_second_copy.py", findings
    assert findings[0][2] == len(STATUS_KEYS), findings

    # 阴性对照 ①：一个**联合**写的副本（`A | B`）也要被认出——这正是契约本体的形状。
    union = tmp_path / "test_union_copy.py"
    union.write_text(
        f"A = {set(keys[:half])!r}\n"
        f"B = {set(keys[half:])!r}\n"
        "def test_union():\n"
        "    assert A | B == set()\n",
        encoding="utf-8",
    )
    copy.unlink()
    findings = guard(tmp_path)                       # type: ignore[operator]
    assert any(f[0].name == "test_union_copy.py" and f[2] == len(STATUS_KEYS)
               for f in findings), findings

    # 阴性对照 ②：只重叠 4 个键的集合不该被误伤（阈值太低就会把 `_RETRY_FIELDS` 那类
    # 「另一件事的字段集」也判成副本）。
    partial = tmp_path / "test_partial_overlap.py"
    partial.write_text(
        "def test_partial():\n"
        "    assert set({'retry_count', 'retrying', 'error_kind', 'resume_percent'}) == set()\n",
        encoding="utf-8",
    )
    union.unlink()
    assert guard(tmp_path) == [], "阴性对照被误伤：阈值太低（4 个键的部分重叠不该算副本）"
