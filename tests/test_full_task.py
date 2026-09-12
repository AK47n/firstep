"""完整包下载任务与端点测试（工单 full-download/03）。

覆盖：扁平分卷任务（下载 + 每卷 SHA256 + 卷级断点）、取消在分卷边界生效、
重启后快照恢复只补未完成卷、状态端点各字段（含速度 / 当前卷）、apply 端点
的白名单校验（防注入）、磁盘空间预检、已有任务在跑时拒绝、下载文件名与清单
逐字节一致（防「双后缀」类缺陷）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from contest_generator import full_task as ft
from contest_generator.full_task import (
    FullDownloadTask,
    full_task_status,
    write_full_snapshot,
)
from contest_generator.webapp import AppContext, create_app


def _payload(name: str) -> bytes:
    return f"内容-{name}".encode("utf-8")


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


def test_task_failure_cleans_partial_file(tmp_path: Path) -> None:
    parts = _parts(["firstep-full-v1.1.0.zip"])
    task = _task(tmp_path, parts, download=_fake_download([], fail_on={"firstep-full-v1.1.0.zip"}))
    task.run()
    assert task.state.value == "failed"
    assert "模拟断网" in task.error or "下载失败" in task.error
    assert not (tmp_path / "updates" / "full" / "firstep-full-v1.1.0.zip").exists()


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
    assert set(status) == {
        "state",
        "parts",
        "total_downloaded_bytes",
        "total_bytes",
        "speed_bps",
        "current_part_name",
        "error",
        "message",
    }


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
    _seed_check(_parts(["firstep-full-v1.1.0.zip"]))
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
    # 下载函数也要注入：测试不碰网络（默认实现是 urllib 真下载）
    monkeypatch.setattr("contest_generator.full_task.download_part", _fake_download([]))
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
