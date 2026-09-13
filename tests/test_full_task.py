"""完整包下载任务与端点测试（工单 full-download/03）。

覆盖：扁平分卷任务（下载 + 每卷 SHA256 + 卷级断点）、取消在分卷边界生效、
重启后快照恢复只补未完成卷、状态端点各字段（含速度 / 当前卷）、apply 端点
的白名单校验（防注入）、磁盘空间预检、已有任务在跑时拒绝、下载文件名与清单
逐字节一致（防「双后缀」类缺陷）。
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from contest_generator import download_resume
from contest_generator import full_task as ft
from contest_generator.download_resume import resumable_download
from contest_generator.full_task import (
    FullDownloadTask,
    full_task_status,
    write_full_snapshot,
)
from contest_generator.webapp import AppContext, create_app
from tests._byte_server import ByteServer
from tests.test_download_status_surface import STATUS_KEYS


def _payload(name: str) -> bytes:
    """这一卷的「内容」= 名字 + 一段确定性伪随机字节。

    为什么不是三个字的小串：真实分卷是几百 MB，而**断点续传只在卷 > 64 KB 时启用**
    （小卷整卷重下更省事）。用几字节的载荷测「续传」，测的其实是另一条分支
    （工单 02 的阈值判据就是这么被发现的）。
    """
    filler = bytes((i * 7 + 11) % 251 for i in range(300 * 1024))
    return f"内容-{name}".encode("utf-8") + filler


@pytest.fixture(autouse=True)
def _reset_full_state():
    """每个测试前后重置模块级单例（任务 + 上次检查）。

    这两个是全进程共享的（webapp 端点与测试同源），不复位会让相邻测试互相
    污染：上一个测试留下的白名单/任务态会让下一个测试的 400 分支不触发。
    """
    ft.set_last_check({})
    ft.set_full_task(None)
    yield
    ft.set_last_check({})
    ft.set_full_task(None)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# 本机桩服务器：真 socket，让**缺省的可续下载器**真的跑一遍
# ---------------------------------------------------------------------------
#
# 为什么单测里也要真 socket：工单 03 判的是「任务层 + 缺省下载器」联手的端到端行为
# （半成品留不留、边车写不写、下次从哪个偏移接着下）。注入假下载器之后这些行为
# 根本不发生——假下载器不会自己写边车，也不会真发 Range。实现见 `tests/_byte_server.py`。


def _byte_server(*, cut_after: int = 0, cut_runs: int = 0,
                 ignore_range: bool = False) -> ByteServer:
    """桩服务器：载荷固定 = v1.1.0 那一卷的字节（与清单 sha256 对得上，> 64 KB）。"""
    return ByteServer(_payload("firstep-full-v1.1.0.zip"), cut_after=cut_after,
                      cut_runs=cut_runs, ignore_range=ignore_range)


def _capped_resumable(max_attempts: int):
    """缺省下载器 + 重试上限（单测里造「这一次没下完」的确定性手段）。

    产品的重试是**无上限**的（网络故障要自己扛到成功），所以单测里要造「失败态」
    必须显式封顶——否则用例会一直重试下去（探针那边靠探针自己的次数上限兜底）。
    """

    def download(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        return resumable_download(url, dest, on_progress, max_attempts=max_attempts,
                                  **kwargs)

    return download


def _cancellable_resumable(on_bytes):
    """缺省下载器 + 「读到第 N 个字节时点取消」：模拟用户中途取消。"""

    def download(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        fired = {"done": False}

        def progress(n: int) -> None:
            on_progress(n)
            if not fired["done"]:
                fired["done"] = True
                on_bytes(n)          # 写盘之后才置取消位 → 半成品真的落下了

        return resumable_download(url, dest, progress, **kwargs)

    return download


def _parts(names: list[str], size: int | None = None) -> list[dict[str, Any]]:
    parts = []
    for name in names:
        data = _payload(name)
        parts.append(
            {
                "name": name,
                "size": len(data) if size is None else size,
                "sha256": _sha(data),
                "url": f"https://example.com/files/{name}",
            }
        )
    return parts


def _fake_download(calls: list[str], fail_on: set[str] | None = None):
    """假下载器：按 URL 尾段取内容写盘并回 SHA256；fail_on 里的卷直接抛。"""
    fail_on = fail_on or set()

    def download(url: str, dest: Path, on_progress) -> str:
        name = url.rsplit("/", 1)[-1]
        calls.append(name)
        if name in fail_on:
            raise OSError("模拟断网")
        data = _payload(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        on_progress(len(data))
        return _sha(data)

    return download


def _task(
    tmp_path: Path,
    parts: list[dict[str, Any]],
    download=None,
    on_complete=None,
    subdir: str = "updates",
) -> FullDownloadTask:
    """构造任务；`subdir` 让每个测试用独立任务目录——共用目录会让上一个测试
    写下的 full-task.json 被下一个测试读成断点（续传逻辑真的会生效）。"""
    return FullDownloadTask(
        task_dir=tmp_path / subdir,
        parts=parts,
        download=download,
        on_complete=on_complete,
        snapshot_interval=0.0,
    )


# ---------------------------------------------------------------------------
# 任务本体
# ---------------------------------------------------------------------------


def test_task_downloads_all_parts_and_marks_ok(tmp_path: Path) -> None:
    calls: list[str] = []
    parts = _parts(["firstep-full-v1.1.0.zip"])
    task = _task(tmp_path, parts, download=_fake_download(calls))
    task.run()
    assert task.state.value == "done"
    assert calls == ["firstep-full-v1.1.0.zip"]
    status = full_task_status(task)
    assert status["state"] == "done"
    assert status["total_downloaded_bytes"] == status["total_bytes"] == len(
        _payload("firstep-full-v1.1.0.zip")
    )
    assert status["parts"][0]["ok"] is True


def test_task_writes_file_under_manifest_name(tmp_path: Path) -> None:
    """落盘文件名必须与清单 zip_name 逐字节一致（应用器按它找文件）。"""
    parts = _parts(["firstep-full-v1.1.0.part1.zip"])
    task = _task(tmp_path, parts, download=_fake_download([]))
    task.run()
    assert (tmp_path / "updates" / "full" / "firstep-full-v1.1.0.part1.zip").is_file()
    # 不得出现带前缀 / 双后缀的名字
    names = sorted(p.name for p in (tmp_path / "updates" / "full").iterdir())
    assert names == ["firstep-full-v1.1.0.part1.zip"]


def test_task_download_defaults_to_resumable(tmp_path: Path) -> None:
    """缺省下载器必须换上可续下载（工单 03 的产品口径）。

    「换了没换」不能靠注入假下载器的用例来证明——那些用例注入之后走的根本不是
    缺省实现。所以这条直接看缺省值本身。
    """
    task = _task(tmp_path, _parts(["firstep-full-v1.1.0.zip"]))
    assert task._download is resumable_download
    assert task._resolve_download()[0] is resumable_download


def test_task_download_passes_manifest_size_and_sha(tmp_path: Path, monkeypatch) -> None:
    """缺省路径把清单的 size 与 sha256 **一起**交给下载器（工单 02 踩坑 2）。

    只给 size 会掉进实测过的死局：「尺寸到点但内容坏」时服务器见「起点=整卷大小」
    就不发字节，重试每轮收 0 字节。这里夹在调用点上把两个参数截下来看，
    同时**真的下完一次**（参数传错这条用例就红）。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    seen: list[dict[str, Any]] = []
    with _byte_server() as server:
        parts[0]["url"] = server.url

        def spy(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
            seen.append(kwargs)
            return resumable_download(url, dest, on_progress, **kwargs)

        task = _task(tmp_path, parts)
        task._download = spy  # type: ignore[attr-defined]
        task.run()
    assert task.state.value == "done", task.error
    assert seen[0]["expected_size"] == parts[0]["size"]
    assert seen[0]["expected_sha256"] == parts[0]["sha256"]
    assert seen[0]["cancel"] is task._cancel, "取消要传到下载器里（退避中也能停）"
    assert callable(seen[0]["before_retry"]), "重试要经 before_retry 如实上报"


def test_task_failure_keeps_partial_file(tmp_path: Path, monkeypatch) -> None:
    """下载异常 → **保留半成品**（它就是断点）；删了就等于每次断流都从 0 重来。

    走**缺省下载器**（真 socket 打在本机桩服务器上，它发到 40% 就断流），
    因为「半成品留不留」是任务层与下载器联手的行为，注入假下载器证明不了。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    monkeypatch.setattr("contest_generator.download_resume.MIN_RESUME_BYTES", 1)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    target = tmp_path / "updates" / "full" / parts[0]["name"]
    # 每次都断（cut_runs 给足）：这条要的是「失败态下盘上还剩什么」，
    # 所以必须一路断到无上限重试也下不完——探针的 stall/cut 用例就是这种形态。
    with _byte_server(cut_after=64 * 1024, cut_runs=999) as server:
        parts[0]["url"] = server.url
        task = _task(tmp_path, parts)
        task._download = _capped_resumable(max_attempts=2)  # 别真跑到天荒地老
        task.run()
        assert server.starts, "真发过请求"
    assert task.state.value == "failed"
    assert "下载失败" in task.error
    assert target.is_file(), "下载异常分支不许再删半成品（工单 resumable-download/03）"
    assert 0 < target.stat().st_size < parts[0]["size"]
    assert download_resume.is_resumable_partial(
        target, parts[0]["url"], parts[0]["size"]
    ), "半成品必须带对得上的边车，否则下次照样重下"


def test_task_retry_state_reported(tmp_path: Path, monkeypatch) -> None:
    """重试要如实计数、写进进行中的摘要（`message`）、终态清空。

    桩服务器**只断一次**（`cut_runs=1`）：这就是「坏一阵就好」的真实形态，
    于是这条同时判「断了能自己接上并下完」。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    target = tmp_path / "updates" / "full" / parts[0]["name"]
    with _byte_server(cut_after=64 * 1024, cut_runs=1) as server:
        parts[0]["url"] = server.url
        task = _task(tmp_path, parts)
        task.run()
    assert task.state.value == "done", task.error
    # 第一次 0 起（发到 64 KB 就断），第二次从断点起 ← 两次请求的起始偏移就是判据
    assert server.starts[0] == 0, server.starts
    assert server.starts[1] == 64 * 1024, server.starts
    assert task.retry_count >= 1, "重试次数要如实计数"
    assert task.last_retry_at > 0
    assert task.last_error_kind == "network"
    assert task._message == "", "终态清空进行中的摘要（终态原因只走 error）"
    assert _sha(target.read_bytes()) == parts[0]["sha256"]


def test_status_shows_retrying_message_during_backoff(tmp_path: Path, monkeypatch) -> None:
    """退避等待期间，`full_task_status` 真的透出「正在重试」的摘要。

    这是工单 04 的预览，但判据必须走**真路径**（缺省下载器 + 真 socket）：
    前端的「慢 / 卡 / 失败」三态就靠 `message` / `retrying` 区分，注入假下载器的
    用例证明不了这条链路通。退避拉长到 0.2 秒，好在等待窗口里轮询。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.2)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    seen: list[dict[str, Any]] = []
    with _byte_server(cut_after=64 * 1024, cut_runs=1) as server:
        parts[0]["url"] = server.url
        task = _task(tmp_path, parts)
        worker = threading.Thread(target=task.run, daemon=True)
        worker.start()
        deadline = time.time() + 10
        while worker.is_alive() and time.time() < deadline:
            status = full_task_status(task)
            if status["retrying"]:
                seen.append(status)
            time.sleep(0.01)
        worker.join(timeout=10)
    assert task.state.value == "done", task.error
    assert seen, "退避等待期间状态面必须能看到「正在重试」"
    # 三件事各在自己的字段里（工单 05 起前端直接拼，不再解析任何文案）
    assert seen[0]["retry_count"] >= 1
    assert "连接中断" in seen[0]["message"], seen[0]["message"]
    assert seen[0]["resume_percent"] >= 0, seen[0]["resume_percent"]
    assert seen[0]["error"] == "", "重试中不算失败（终态原因才进 error）"


def test_task_checksum_mismatch_fails(tmp_path: Path) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    parts[0]["sha256"] = "0" * 64  # 清单期望值不对

    def download(url: str, dest: Path, on_progress) -> str:
        data = _payload("firstep-full-v1.1.0.zip")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        on_progress(len(data))
        return _sha(data)

    task = _task(tmp_path, parts, download=download)
    task.run()
    assert task.state.value == "failed"
    assert "校验失败" in task.error
    assert not (tmp_path / "updates" / "full" / "firstep-full-v1.1.0.zip").exists()
    assert not (tmp_path / "updates" / "full" / "firstep-full-v1.1.0.zip.partial.json").exists()


def test_verify_failure_discards_stale_partial(tmp_path: Path) -> None:
    """校验失败过的半成品不该被接着用：**要么删掉、要么从头下**，不许续着坏字节写。

    盘上是一份「长度不足 + 有边车」的陈旧半成品；它上次其实是校验失败。
    一个从 0 重下的下载器会**覆盖**它（`wb`），续写的实现则会在尾部追加。
    """
    parts = _parts(["firstep-full-v1.1.0.zip"])
    name = "firstep-full-v1.1.0.zip"
    target = tmp_path / "updates" / "full" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"stale-bytes")
    download_resume.write_partial_marker(target, parts[0]["url"], parts[0]["size"])

    def download(url: str, dest: Path, on_progress) -> str:
        payload = _payload(name)
        dest.write_bytes(payload)          # 覆盖写：续写的实现写不出正确结果
        on_progress(len(payload))
        return _sha(payload)

    task = _task(tmp_path, parts, download=download)
    task.run()
    assert task.state.value == "done"
    assert _sha(target.read_bytes()) == parts[0]["sha256"]


def test_task_resumes_partial_file_instead_of_restarting(tmp_path: Path, monkeypatch) -> None:
    """跑到一半断了 → 下次 `run()` **接着下**（服务器台账里的 Range 起点就是判据）。

    两段都跑在**同一个**桩服务器上（同一个 URL）：第二次 `run()` 拿到的半成品
    必须被认下来——判它「边车对得上就接着用」这条真的生效。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    payload = _payload(parts[0]["name"])
    half = len(payload) // 2
    target = tmp_path / "updates" / "full" / parts[0]["name"]

    with _byte_server(cut_after=half, cut_runs=1) as server:
        parts[0]["url"] = server.url
        first = _task(tmp_path, parts)
        first._download = _capped_resumable(1)     # 这一次就断在这儿，别自动接完
        first.run()
        assert first.state.value == "failed"
        assert target.stat().st_size == half
        assert download_resume.is_resumable_partial(
            target, parts[0]["url"], parts[0]["size"]
        ), "断掉的半成品必须带对得上的边车，否则下次照样重下"

        mark = len(server.starts)                 # 只看第二次 run 的请求
        second = _task(tmp_path, parts)
        second.run()
        second_starts = server.starts[mark:]

    assert second.state.value == "done", second.error
    assert second_starts == [half], "已落盘的半成品没被接着用（又从头下了）"
    assert _sha(target.read_bytes()) == parts[0]["sha256"]
    assert not (target.parent / (target.name + ".partial.json")).exists()


def test_cancel_progress_counts_resumed_bytes(tmp_path: Path, monkeypatch) -> None:
    """进度语义：续传时进度 = 盘上已有字节 + 本次连接读到的字节（别把已有部分丢掉）。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    payload = _payload(parts[0]["name"])
    half = len(payload) // 2
    target = tmp_path / "updates" / "full" / parts[0]["name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload[:half])
    download_resume.write_partial_marker(target, parts[0]["url"], parts[0]["size"])

    with _byte_server() as server:
        parts[0]["url"] = server.url
        # 边车里的 URL 与任务现在用的 URL 一致（否则正是「来路不明」那种情形）
        download_resume.write_partial_marker(target, parts[0]["url"], parts[0]["size"])
        task = _task(tmp_path, parts)
        task.run()
    assert task.state.value == "done", task.error
    assert task.parts[0].downloaded_bytes == parts[0]["size"], (
        "进度没把已落盘的那一半算进去"
    )


def test_cancel_writes_sidecar_and_keeps_partial(tmp_path: Path, monkeypatch) -> None:
    """取消 → 半成品与边车都留下（下次接着下），任务态 = cancelled。

    取消由下载器内部的 `cancel` 事件判出（退避中也能立刻停），任务层据此转
    `cancelled`——这条同时证明「任务层真的把 cancel 传进了下载器」。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    target = tmp_path / "updates" / "full" / parts[0]["name"]

    with _byte_server(cut_after=64 * 1024) as server:
        parts[0]["url"] = server.url
        task = _task(tmp_path, parts)
        # 取消发生在第一轮写盘**之后**（取消是「读到一半点了取消」，不是「还没开始」）：
        # 半成品与边车因此都该在盘上留着。
        task._download = _cancellable_resumable(  # type: ignore[attr-defined]
            on_bytes=lambda n: task.cancel()
        )
        task.run()

    assert task.state.value == "cancelled"
    marker = target.parent / (target.name + ".partial.json")
    assert marker.is_file(), "取消必须写边车（跨进程也要知道这份半成品是谁的）"
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["url"] == parts[0]["url"]
    assert data["expected_size"] == parts[0]["size"]
    assert target.is_file() and 0 < target.stat().st_size < parts[0]["size"]


def test_status_retrying_false_while_resuming_message_present(
    tmp_path: Path, monkeypatch
) -> None:
    """`retrying` 只表示「正处在退避等待中」：续传启动那一下的摘要不算重试。

    少了这条区分，「本次是接着下」会被界面说成「正在重试」（两者混在一个字段里）。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    payload = _payload(parts[0]["name"])
    half = len(payload) // 2
    target = tmp_path / "updates" / "full" / parts[0]["name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload[:half])

    observed: list[dict[str, Any]] = []
    with _byte_server() as server:
        parts[0]["url"] = server.url
        download_resume.write_partial_marker(target, parts[0]["url"], parts[0]["size"])
        task = _task(tmp_path, parts)

        def spy(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
            observed.append(full_task_status(task))     # 下载器被调用的那一刻
            return resumable_download(url, dest, on_progress, **kwargs)

        task._download = spy  # type: ignore[attr-defined]
        task.run()

    assert task.state.value == "done", task.error
    assert observed, "假下载器没被调到"
    assert "接着" in observed[0]["message"], observed[0]["message"]
    assert observed[0]["retrying"] is False, "「接着下」不是「正在重试」"
    assert observed[0]["retry_count"] == 0


def test_complete_file_is_verified_without_refetching(tmp_path: Path) -> None:
    """盘上已是一整卷（长度到点）→ **不发请求**直接进校验，不许删了重下。

    旧行为（`unlink` 后重下）会让任何「快照没记 ok 但文件已下完」的卷白下几百 MB；
    探针/桩服务器一次请求都不该收到。
    """
    parts = _parts(["firstep-full-v1.1.0.zip"])
    target = tmp_path / "updates" / "full" / parts[0]["name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_payload(parts[0]["name"]))

    with _byte_server() as server:
        parts[0]["url"] = server.url
        task = _task(tmp_path, parts)
        task.run()

    assert task.state.value == "done", task.error
    assert server.starts == [], "长度已到点就不该再发请求"
    assert task.parts[0].downloaded_bytes == parts[0]["size"]
    assert target.is_file()


def test_server_ignoring_range_restarts_progress_without_overcounting(
    tmp_path: Path, monkeypatch
) -> None:
    """服务器忽略 Range（恒 200 整份）→ 丢弃半成品从 0 重下，**进度不许超算**。

    进度基准原来取「调用前盘上有多少」：忽略 Range 时那部分已被丢弃，却还留在进度里
    → 会出现「进度 > 卷大小」。现在基准由下载器每轮开始时报（`on_start`）。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    payload = _payload(parts[0]["name"])
    half = len(payload) // 2
    target = tmp_path / "updates" / "full" / parts[0]["name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload[:half])

    seen: list[int] = []
    with _byte_server(ignore_range=True) as server:
        parts[0]["url"] = server.url
        download_resume.write_partial_marker(target, parts[0]["url"], parts[0]["size"])
        task = _task(tmp_path, parts)
        task._download = lambda url, dest, on_progress, **kw: (  # type: ignore[attr-defined]
            resumable_download(url, dest, on_progress, **kw),
            seen.append(task.parts[0].downloaded_bytes),
        )[0]
        task.run()

    assert task.state.value == "done", task.error
    assert server.starts == [half], "确实带了 Range（然后被服务器忽略）"
    assert seen and seen[0] <= parts[0]["size"], f"进度超算：{seen}"
    assert _sha(target.read_bytes()) == parts[0]["sha256"]


def test_ignored_range_retry_message_says_from_zero(tmp_path: Path, monkeypatch) -> None:
    """「服务器不支持续传」要在重试消息里说出来（spec 的断点契约表）。

    剧本 = 真实顺序：先带 Range 请求（被忽略 → 200 整份）→ 又断一次 → 重试。
    重试那一刻的摘要必须写「从 0 重新下」，而不是「从 X% 接着下」。

    读的时刻 = **开窗那一刻**（`before_retry` 里、任务自己写完状态之后）：
    窗口一关（退避结束）摘要是要被清掉的，所以不能在下一轮开始后读。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    payload = _payload(parts[0]["name"])
    target = tmp_path / "updates" / "full" / parts[0]["name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload[: len(payload) // 2])

    observed: list[tuple[str, bool]] = []
    with _byte_server(ignore_range=True, cut_runs=1, cut_after=64 * 1024) as server:
        parts[0]["url"] = server.url
        download_resume.write_partial_marker(target, parts[0]["url"], parts[0]["size"])
        task = _task(tmp_path, parts)

        def spy(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
            # 包装（不能另传 before_retry：适配层已经传了一个）
            original = kwargs["before_retry"]

            def watcher(*args):        # noqa: ANN002 —— 开窗：先让任务写完状态再读
                result = original(*args)
                observed.append((task._message, task._retrying,
                                 full_task_status(task)["resume_percent"]))
                return result

            kwargs["before_retry"] = watcher
            return resumable_download(url, dest, on_progress, **kwargs)

        task._download = spy  # type: ignore[attr-defined]
        task.run()

    assert task.state.value == "done", task.error
    assert observed, "没有重试发生（前提是「先被忽略 Range，再断一次」）"
    message, retrying, resume_percent = observed[0]
    # 「从 0 重新下」现在是**字段**（工单 05 的整改：前端不再解析文案）：
    # 服务器没让我们接上 → 本轮的起始百分比如实是 0，而不是拿旧进度骗人。
    assert resume_percent == 0, resume_percent
    assert "连接中断" in message, message
    assert retrying is True, "开窗那一刻就该是「正在重试」"


def test_cancel_leaves_error_kind_empty(tmp_path: Path, monkeypatch) -> None:
    """取消不是失败态分类：`error_kind` 该保持空（spec 的词表只有 ""|network|verify）。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    parts = _parts(["firstep-full-v1.1.0.zip"])
    with _byte_server() as server:
        parts[0]["url"] = server.url
        task = _task(tmp_path, parts)
        task._download = _cancellable_resumable(  # type: ignore[attr-defined]
            on_bytes=lambda n: task.cancel()
        )
        task.run()
    assert task.state.value == "cancelled"
    assert task.last_error_kind == ""
    assert full_task_status(task)["error_kind"] == ""


def test_resume_skips_verified_parts(tmp_path: Path) -> None:
    """第 1 卷已成功、第 2 卷失败 → 重试只下第 2 卷。"""
    calls: list[str] = []
    names = ["firstep-full-v1.1.0.part1.zip", "firstep-full-v1.1.0.part2.zip"]
    parts = _parts(names)

    first = _task(tmp_path, parts, download=_fake_download(calls, fail_on={names[1]}))
    first.run()
    assert first.state.value == "failed"
    assert calls == names  # 两卷都尝试过

    calls.clear()
    retry = _task(tmp_path, parts, download=_fake_download(calls))
    retry.run()
    assert retry.state.value == "done"
    assert calls == [names[1]], "已校验通过的卷不该重下"


def test_resume_rejects_tampered_local_file(tmp_path: Path) -> None:
    """本地已下载文件被改坏 → 恢复时不认，重下该卷。"""
    calls: list[str] = []
    names = ["firstep-full-v1.1.0.zip"]
    parts = _parts(names)
    _task(tmp_path, parts, download=_fake_download(calls)).run()

    target = tmp_path / "updates" / "full" / names[0]
    target.write_bytes(b"tampered")
    calls.clear()
    again = _task(tmp_path, parts, download=_fake_download(calls))
    again.run()
    assert calls == names
    assert again.state.value == "done"


def test_cancel_stops_at_part_boundary_and_keeps_done_parts(tmp_path: Path) -> None:
    calls: list[str] = []
    names = ["firstep-full-v1.1.0.part1.zip", "firstep-full-v1.1.0.part2.zip"]
    parts = _parts(names)
    task = _task(tmp_path, parts)

    def download(url: str, dest: Path, on_progress) -> str:
        name = url.rsplit("/", 1)[-1]
        calls.append(name)
        if name == names[0]:
            task.cancel()  # 第 1 卷下完就请求取消
        data = _payload(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        on_progress(len(data))
        return _sha(data)

    task._download = download  # type: ignore[attr-defined]
    task.run()
    assert task.state.value == "cancelled"
    assert calls == [names[0]]
    status = full_task_status(task)
    assert status["parts"][0]["ok"] is True


def test_on_complete_failure_marks_failed(tmp_path: Path) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    received: list[list[dict]] = []

    def boom(done_parts: list[dict]) -> None:
        received.append(done_parts)
        raise RuntimeError("替换失败")

    task = _task(tmp_path, parts, download=_fake_download([]), on_complete=boom)
    task.run()
    assert task.state.value == "failed"
    assert "替换失败" in task.error
    assert received[0][0]["name"] == "firstep-full-v1.1.0.zip"
    assert received[0][0]["path"], "应用编排要拿到本地分卷路径"
    assert received[0][0]["sha256"] == parts[0]["sha256"]


def test_status_idle_shape() -> None:
    status = full_task_status(None)
    assert status["state"] == "idle"
    assert status["parts"] == []
    assert status["total_bytes"] == 0
    # 键集合**不在这里再抄一遍**（工单 15）：它的家是
    # `tests/test_download_status_surface.py` 的 `STATUS_KEYS`——那条断言查**两侧 ×
    # 空态 + 有态**，还查两个端点，本处那份内联字面在「键 × 侧 × 态」上没有一格是它独有的。
    # **取值断言（上面三行）留在这里**：它们是本处独有的（探针实测：只改空态 `total_bytes`
    # 时，`STATUS_KEYS` 那条绿、只有本用例红）。收口前后的逐格对照（同一支探针在基线提交
    # 与现状各跑一遍）只差一格：内联字面会在「产品与共同常量一起改」时再红一次——
    # 而那正是加字段的**规定手续**（见 `test_status_keys_are_the_contracted_set` 的 docstring），
    # 不是多覆盖了哪一格载荷。
    assert set(status) == STATUS_KEYS


def test_status_reports_speed_and_current_part(tmp_path: Path) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    task = _task(tmp_path, parts, download=_fake_download([]), subdir="finished")
    task.run()
    status = full_task_status(task)
    assert status["current_part_name"] == ""
    assert isinstance(status["speed_bps"], int)

    # 下载中：当前卷名与新增字节 → 速度非负（瞬时估算）
    downloading = _task(tmp_path / "second", parts)
    downloading._state = ft.TaskState.DOWNLOADING  # type: ignore[attr-defined]
    downloading._current_part_name = parts[0]["name"]
    downloading.parts[0].downloaded_bytes = parts[0]["size"]
    live = full_task_status(downloading)
    assert live["state"] == "downloading"
    assert live["current_part_name"] == "firstep-full-v1.1.0.zip"
    assert live["total_downloaded_bytes"] == parts[0]["size"]
    assert live["speed_bps"] >= 0


def test_snapshot_written_and_recoverable(tmp_path: Path) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    task = _task(tmp_path, parts, download=_fake_download([]))
    task.run()
    write_full_snapshot(task)
    snapshot = json.loads((tmp_path / "updates" / ft.SNAPSHOT_FILENAME).read_text(encoding="utf-8"))
    assert snapshot["state"] == "done"
    assert snapshot["parts"][0]["ok"] is True


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(AppContext(config_path=tmp_path / "config.json")))


def _seed_check(parts: list[dict[str, Any]]) -> None:
    ft._LAST_CHECK.clear()
    ft._LAST_CHECK.update(
        {
            "latest_version": "v1.1.0",
            "total_bytes": sum(p["size"] for p in parts),
            "parts": parts,
        }
    )


def test_apply_rejects_unknown_part_name(tmp_path: Path, monkeypatch) -> None:
    """未知分卷：先兜底自查一次（白名单可能过期）；自查后仍不匹配 → 400。

    这里桩掉自查用的 check（否则会真打 GitHub），断言走的是「未知分卷」这条。
    """
    parts = _parts(["firstep-full-v1.1.0.zip"])
    _seed_check(parts)
    monkeypatch.setattr(
        "contest_generator.webapp.check_for_full_update",
        lambda installed: {
            "latest_version": "v1.1.0",
            "total_bytes": parts[0]["size"],
            "parts": parts,
            "error": "",
            "message": "",
            "manifest_url": "https://example.com/firstep-full-v1.1.0.manifest.json",
        },
    )
    monkeypatch.setattr("contest_generator.webapp.free_bytes", lambda path: 10 * 1024**3)
    client = _client(tmp_path)
    resp = client.post("/api/update/full/apply", json={"parts": ["../evil.zip"]})
    assert resp.status_code == 400
    assert "未知分卷" in resp.json()["detail"]


def test_apply_rejects_empty_list(tmp_path: Path) -> None:
    _seed_check(_parts(["firstep-full-v1.1.0.zip"]))
    client = _client(tmp_path)
    assert client.post("/api/update/full/apply", json={"parts": []}).status_code == 400
    assert client.post("/api/update/full/apply", json={}).status_code == 400


def test_apply_without_check_first_is_400(tmp_path: Path, monkeypatch) -> None:
    """白名单空 → 兜底自查一次；仍无可下（真实 GitHub 上还没有完整包资产）→ 400 中文。"""
    ft._LAST_CHECK.clear()
    monkeypatch.setattr(
        "contest_generator.webapp.check_for_full_update",
        lambda installed: {
            "current_version": "",
            "latest_version": "",
            "update_available": False,
            "total_bytes": 0,
            "parts": [],
            "reason": "",
            "error": "no-asset",
            "message": "该版本的 Release 上没有完整包资产，请联系发布者",
            "manifest_url": "",
        },
    )
    client = _client(tmp_path)
    resp = client.post("/api/update/full/apply", json={"parts": ["a.zip"]})
    assert resp.status_code == 400
    assert "完整包" in resp.json()["detail"]


def test_apply_insufficient_disk_is_400(tmp_path: Path, monkeypatch) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    _seed_check(parts)
    monkeypatch.setattr("contest_generator.webapp.free_bytes", lambda path: 1024)
    client = _client(tmp_path)
    resp = client.post("/api/update/full/apply", json={"parts": [parts[0]["name"]]})
    assert resp.status_code == 400
    assert "磁盘空间不足" in resp.json()["detail"]


def test_apply_starts_and_status_reports_progress(tmp_path: Path, monkeypatch) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    _seed_check(parts)
    monkeypatch.setattr("contest_generator.webapp.free_bytes", lambda path: 10 * 1024**3)
    ran = {"count": 0}

    def fake_start(task) -> None:
        ran["count"] += 1
        task.run()  # 同步执行：测试里不等待后台线程

    monkeypatch.setattr("contest_generator.webapp.start_full_update", fake_start)
    # 下载函数也要注入：测试不碰网络（缺省实现是可续下载，最终仍是 urllib 真下载）。
    # 注入点是 **任务类的 `_download`**——`download_part` 已经不再是缺省实现，
    # patch 它改不到任务真正调用的那个函数（工单 03）。
    monkeypatch.setattr(FullDownloadTask, "_download", _fake_download([]))
    # 应用编排要注入：真实现会起独立进程跑更新器（测试不真起进程）
    monkeypatch.setattr(
        "contest_generator.webapp.apply_full_package",
        lambda **kwargs: __import__(
            "contest_generator.full_apply", fromlist=["FullApplyResult"]
        ).FullApplyResult(ok=True, version="v1.1.0", message="已开始应用"),
    )
    client = _client(tmp_path)
    resp = client.post("/api/update/full/apply", json={"parts": [parts[0]["name"]]})
    assert resp.status_code == 200
    assert resp.json()["started"] is True
    assert "1 卷" in resp.json()["message"]
    assert ran["count"] == 1

    status = client.get("/api/update/full/status").json()
    assert status["state"] == "done"  # 下载 + 应用编排（已注入）全部走通
    assert status["error"] == ""
    assert status["total_bytes"] == parts[0]["size"]
    assert status["parts"][0]["ok"] is True
    # 分卷文件落盘名 = 清单 zip_name（应用器按它找文件）
    assert (tmp_path / "updates" / "full" / parts[0]["name"]).is_file()


def test_apply_dry_run_does_not_start_task_or_spawn(tmp_path: Path, monkeypatch) -> None:
    """演练模式：真机冒烟用——不下载、不起进程、只回成功文案。"""
    parts = _parts(["firstep-full-v1.1.0.zip"])
    _seed_check(parts)
    monkeypatch.setattr("contest_generator.webapp.free_bytes", lambda path: 10 * 1024**3)
    spawned: list[str] = []

    def spy(url, dest, on_progress):  # noqa: ANN001
        spawned.append(url)
        return ""

    monkeypatch.setattr(FullDownloadTask, "_download", spy)
    client = _client(tmp_path)
    resp = client.post(
        "/api/update/full/apply", json={"parts": [parts[0]["name"]], "dry_run": True}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["started"] is True and body["dry_run"] is True
    assert "演练" in body["message"]
    assert spawned == [], "演练不该真下载"
    assert ft.get_full_task() is None, "演练不该登记任务"


def test_status_idle_before_any_task(tmp_path: Path) -> None:
    ft._FULL_TASK = None
    client = _client(tmp_path)
    body = client.get("/api/update/full/status").json()
    assert body["state"] == "idle"
    assert body["parts"] == []


def test_cancel_without_task_is_noop(tmp_path: Path) -> None:
    ft._FULL_TASK = None
    client = _client(tmp_path)
    body = client.post("/api/update/full/cancel").json()
    assert body["cancelled"] is False
    assert "没有进行中的下载" in body["message"]


def test_apply_rejects_when_task_running(tmp_path: Path, monkeypatch) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    _seed_check(parts)
    monkeypatch.setattr("contest_generator.webapp.free_bytes", lambda path: 10 * 1024**3)
    running = FullDownloadTask(
        task_dir=tmp_path / "updates", parts=parts, download=_fake_download([])
    )
    running._state = ft.TaskState.DOWNLOADING  # type: ignore[attr-defined]
    ft._FULL_TASK = running
    client = _client(tmp_path)
    resp = client.post("/api/update/full/apply", json={"parts": [parts[0]["name"]]})
    assert resp.status_code == 400
    assert "进行中" in resp.json()["detail"]
