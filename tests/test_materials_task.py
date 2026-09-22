"""资料库下载任务测试（工单 materials-update/04）。

覆盖：apply 参数校验（批次白名单 / 缺字段 / 非法 slug）、磁盘空间不足 400、
应用启动后台任务（monkeypatch 下载函数）、卷级断点续传（卷 1 成功卷 2 失败
→ 重试只下卷 2）、cancel 在卷边界停止、status 状态机（idle / downloading /
downloading+partial / done / failed / applying）、状态落盘节流与重启恢复、
ApplyTask 纯逻辑（不依赖网络）。

会话态归属（工单 webapp-state-into-ctx/02）：check 缓存与下载任务单例长在
**AppContext** 上，测试在**自己构造的那个 ctx** 上注入与断言——`_client()` 把 ctx
一起返回，不再有跨用例清扫夹具（每个用例一个新实例，天然隔离）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import contest_generator.materials_update as mu
from contest_generator import download_resume
from contest_generator.download_resume import resumable_download
from contest_generator.materials_task import (
    ApplyTask,
    TaskState,
    download_part,
    normalize_part,
    task_status,
    write_task_snapshot,
)
from contest_generator.webapp import AppContext, create_app
from tests._byte_server import ByteServer


# ---------------------------------------------------------------------------
# 契约数据
# ---------------------------------------------------------------------------


def _manifest(version: str, batches: list[dict]) -> dict[str, Any]:
    return {"version": version, "published_at": "2026-09-01T00:00:00Z", "batches": batches}


def _batch(slug: str, name: str, parts: list[dict]) -> dict[str, Any]:
    return {"slug": slug, "name": name, "size_bytes": sum(p.get("size_bytes", 0) for p in parts), "parts": parts}


def _part(url: str, size: int, sha: str, zip_name: str = "") -> dict[str, Any]:
    return {"zip_url": url, "size_bytes": size, "sha256": sha, "zip_name": zip_name}


def _sha_of(content: bytes) -> str:
    import hashlib
    return hashlib.sha256(content).hexdigest()


def _big_payload() -> bytes:
    """大于 MIN_RESUME_BYTES（64 KB）的确定性载荷：断点续传只在这个量级上启用。"""
    return bytes((i * 13 + 7) % 251 for i in range(300 * 1024))


def _capped_resumable(max_attempts: int):
    """缺省下载器 + 重试上限（单测里造「这一次没下完」的确定性手段）。

    产品的重试无上限（网络故障要自己扛到成功），所以造失败态必须显式封顶。
    """

    def download(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        return resumable_download(url, dest, on_progress,
                                  max_attempts=max_attempts, **kwargs)

    return download


def _cancellable_resumable(on_bytes):
    """缺省下载器 + 「读到第一块时点取消」：模拟用户中途取消。"""

    def download(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        fired = {"done": False}

        def progress(n: int) -> None:
            on_progress(n)
            if not fired["done"]:
                fired["done"] = True
                on_bytes(n)          # 写盘之后才置取消位 → 半成品真的落下了

        return resumable_download(url, dest, progress, **kwargs)

    return download


def _content_for(url: str) -> tuple[bytes, str]:
    """URL → (内容字节, 内容 SHA256)：测试内卷的一致性数据源。"""
    content = f"data-of-{url}".encode("utf-8")
    return content, _sha_of(content)


def _fake_download(log: list[str] | None = None, failures: dict[str, int] | None = None):
    """构造假下载函数：按 URL 写内容并返回其 SHA256；failures 控制失败次数。

    `dest.parent.mkdir(...)` 这一句不是摆设（工单 11 撞上的）：**真下载器**（
    `resumable_download`）自己会建目录，而假件若不建，`write_bytes` 就抛
    `FileNotFoundError`——于是任务转 failed、盘上什么都不留，**而按调用次数 / 状态的断言
    照样绿**（写没写盘根本没被看）。工单 11 新补的那条「改坏 → 重下」用例正是靠
    「盘上那份在不在、内容对不对」判的，于是把这个潜伏的假件缺陷照了出来。
    """
    def fake(url: str, dest: Path, on_progress) -> str:
        if failures and failures.get(url, 0) > 0:
            failures[url] -= 1
            raise OSError("connection reset")
        content, sha = _content_for(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        if log is not None:
            log.append(url)
        return sha

    return fake


def _check_result(batches: list[dict], total: int = 100) -> dict[str, Any]:
    return {
        "current_version": "v1.0.0",
        "latest_version": "v1.1.0",
        "update_available": True,
        "total_size_bytes": total,
        "batches": batches,
        "deleted_batches": [],
        "error": "",
        "message": "",
    }


def _release(batch_slugs: list[str]) -> list[dict[str, Any]]:
    return [{
        "tag_name": "materials-v1.1.0",
        "assets": [
            {
                "name": f"firstep-materials-v1.1.0-{slug}.zip",
                "browser_download_url": f"https://example.com/files/{slug}.zip",
                "size": 100,
            }
            for slug in batch_slugs
        ],
    }]


def _online_release(slug: str) -> list[dict[str, Any]]:
    """线上 releases 列表（check 端点的取数面）：一个 `materials-` release + 清单/卷两个资产。"""
    return [{
        "tag_name": "materials-v1.1.0",
        "assets": [
            {
                "name": "firstep-materials-v1.1.0.manifest.json",
                "browser_download_url": "https://example.com/firstep-materials-v1.1.0.manifest.json",
                "size": 100,
            },
            {
                "name": f"firstep-materials-v1.1.0-{slug}.zip",
                "browser_download_url": f"https://example.com/firstep-materials-v1.1.0-{slug}.zip",
                "size": 200,
            },
        ],
    }]


def _seed_check(ctx: AppContext, batches: list[dict]) -> None:
    """把一份 check 结果注入**本实例**的 ctx（apply 的白名单来源）。

    这是「check 结果 → 白名单」那条缝的注入形状（单源一处）：不走真 check 端点时用它，
    要连端点一起验的用例见 `test_check_then_apply_keeps_the_whitelist_on_this_instance`。
    """
    ctx.materials_last_check.update(_check_result(batches))


def _client(tmp_path: Path) -> tuple[TestClient, AppContext]:
    """本用例的客户端 + **它自己那个 AppContext**。

    资料库更新的会话态（check 缓存 / 下载任务）长在 ctx 上（工单 webapp-state-into-ctx/02）：
    要注入或断言就在这一个实例上做，不再伸手进 webapp 模块（也不再需要跨用例清扫夹具）。
    """
    ctx = AppContext(config_path=tmp_path / "config.json")
    return TestClient(create_app(ctx)), ctx


# ---------------------------------------------------------------------------
# normalize_part
# ---------------------------------------------------------------------------


def test_normalize_part_fills_zip_name() -> None:
    part = _part("https://x/a.zip", 10, "a" * 64)
    out = normalize_part(part)
    assert out["zip_name"] == ""
    assert out["size_bytes"] == 10


# ---------------------------------------------------------------------------
# ApplyTask 纯逻辑（不启动线程）
# ---------------------------------------------------------------------------


def test_apply_task_starts_idle(tmp_path: Path) -> None:
    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=[_batch("k230", "k230资料", [_part("https://x/k230.zip", 100, "a" * 64)])],
        download=lambda url, dest, on_progress: "a" * 64,
    )
    assert task.state == TaskState.IDLE
    assert task.total_bytes == 100


def test_apply_task_runs_and_downloads_all_parts(tmp_path: Path) -> None:
    _, sha_a = _content_for("https://x/k230.zip")
    _, sha_b = _content_for("https://x/wireless.zip")
    batches = [
        _batch("k230", "k230资料", [
            _part("https://x/k230.zip", 60, sha_a),
        ]),
        _batch("wireless", "无线串口模块资料", [
            _part("https://x/wireless.zip", 40, sha_b),
        ]),
    ]
    downloaded: list[str] = []
    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=_fake_download(log=downloaded),
    )
    task.run()
    assert task.state == TaskState.DONE
    assert len(downloaded) == 2
    # 卷级完成标记落盘
    marker = tmp_path / "updates" / "materials-task.json"
    assert marker.is_file()


def test_apply_task_invokes_on_complete_after_all_parts(tmp_path: Path) -> None:
    """全部卷就绪后调 on_complete（应用器挂钩）；挂钩抛错 = 失败态。"""
    _, sha_a = _content_for("https://x/k230.zip")
    batches = [
        _batch("k230", "k230资料", [_part("https://x/k230.zip", 60, sha_a)]),
    ]
    applied: list[str] = []
    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=_fake_download(),
        on_complete=lambda: applied.append("applied"),
    )
    task.run()
    assert task.state == TaskState.DONE
    assert applied == ["applied"]


def test_apply_task_on_complete_failure_is_failed_state(tmp_path: Path) -> None:
    _, sha_a = _content_for("https://x/k230.zip")
    batches = [
        _batch("k230", "k230资料", [_part("https://x/k230.zip", 60, sha_a)]),
    ]

    def boom() -> None:
        raise RuntimeError("应用失败：磁盘写入错误")

    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=_fake_download(),
        on_complete=boom,
    )
    task.run()
    assert task.state == TaskState.FAILED
    assert "应用失败" in (task.error or "")


def test_task_download_defaults_to_resumable(tmp_path: Path) -> None:
    """缺省下载器 = 可续下载（工单 03）：两条链路同源，别再退回单次尝试那版。"""
    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=[_batch("k230", "k230资料", [_part("https://x/k230.zip", 100, "a" * 64)])],
    )
    assert task._download is resumable_download
    assert task._resolve_download()[0] is resumable_download


def test_apply_task_keeps_partial_on_network_failure(tmp_path: Path, monkeypatch) -> None:
    """下载异常 → **保留半成品**（它就是断点）；**校验失败** → 删（重下也是坏的）。

    走**缺省下载器**（真 socket 打在本机桩服务器上，它发到一半就断流）：半成品留没留
    是任务层与下载器联手的行为，注入假下载器证明不了。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    content = _big_payload()
    batches = [_batch("k230", "k230资料",
                      [_part("", len(content), _sha_of(content), "k230.zip")])]
    target = tmp_path / "updates" / "materials" / "k230.zip"
    with ByteServer(content, cut_after=64 * 1024, cut_runs=999) as server:
        batches[0]["parts"][0]["zip_url"] = server.url
        task = ApplyTask(task_dir=tmp_path / "updates", batches=batches)
        task._download = _capped_resumable(1)      # 造「这次真没下完」
        task.run()
    assert task.state == TaskState.FAILED
    assert target.is_file(), "失败态下磁盘上要留着半成品（它就是断点）"
    assert 0 < target.stat().st_size < len(content)
    assert download_resume.is_resumable_partial(
        target, batches[0]["parts"][0]["zip_url"], len(content)
    ), "半成品必须带对得上的边车"

    # 换一份「下全了但内容不对」的：校验失败 → 半成品与边车都要清干净
    task2 = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=lambda url, dest, on_progress: "0" * 64,
    )
    task2.run()
    assert task2.state == TaskState.FAILED
    assert "校验失败" in task2.error
    assert not target.exists()
    assert not (target.parent / (target.name + ".partial.json")).exists()


def test_apply_task_rejects_tampered_local_file(tmp_path: Path) -> None:
    """快照记 ok、盘上文件也在，但**内容哈希与清单不符** → 恢复不认它，且**大声失败**。

    **为什么这条是补的**：工单 11 的错版注入探针（
    `.scratch/resumable-download/probe-11-guard-strength.py`）实测——把
    `_restore_snapshot` 的哈希校验整段去掉，full 侧有
    `tests/test_full_task.py::test_resume_rejects_tampered_local_file` 转红，
    **而资料库这一侧 47 passed**：同一段逻辑，一处有人看、一处没人看。
    两侧的实现现已收到 `task_download.restore_snapshot_parts` 一处，
    判据也必须两侧都在场。

    判据选的是**终态**（`failed` + 中文校验失败）而不是「重下了」：同尺寸改坏的文件
    会被 `download_and_verify` 的「长度到点 → 不发请求、直接校验」接住（工单 03 立的规则），
    于是**不会重下**，而是如实报校验失败——这一格在工单 11 的探针里栽过一次
    （当时写成「必须重下」，红了才看清真口径，见 `probe-11-resolve-seam.py`）。
    为什么这一格能抓到「恢复没做哈希校验」：去掉校验的实现会把改坏的卷标成 ok、
    于是直接 `done`（静默收下一份坏文件），终态断言立刻红。

    载荷要求：真字节 > MIN_RESUME_BYTES（64 KB），且**清单的 size / sha256 与它一致**
    （`_fake_download` 只写 24 字节的小内容，拿它配 300 KB 的清单会被如实判成校验失败）。
    """
    content = _big_payload()
    url = "https://x/k230.zip"
    batches = [_batch("k230", "k230资料",
                      [_part(url, len(content), _sha_of(content), "k230.zip")])]
    calls: list[str] = []

    def fake(touched_url: str, dest: Path, on_progress) -> str:  # noqa: ANN001
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        on_progress(len(content))
        calls.append(touched_url)
        return _sha_of(content)

    first = ApplyTask(task_dir=tmp_path / "updates", batches=batches, download=fake)
    first.run()
    assert first.state == TaskState.DONE, first.error
    assert calls == [url]

    target = tmp_path / "updates" / "materials" / "k230.zip"
    tampered = bytearray(content)
    tampered[len(tampered) // 2] ^= 0xFF          # 同尺寸、不同内容
    target.write_bytes(bytes(tampered))
    calls.clear()
    again = ApplyTask(task_dir=tmp_path / "updates", batches=batches, download=fake)
    again.run()
    assert again.state == TaskState.FAILED, "改坏的卷被静默当成已下好"
    assert "校验失败" in (again.error or ""), again.error

    # 修好之后必须还能正常收尾（坏件已被清掉，走真实重下）
    target.parent.mkdir(parents=True, exist_ok=True)
    calls.clear()
    third = ApplyTask(task_dir=tmp_path / "updates", batches=batches, download=fake)
    third.run()
    assert calls == [url], "坏件没被清掉 → 下一轮又被当成「长度到点」直接校验"
    assert third.state == TaskState.DONE, third.error
    assert target.read_bytes() == content


def test_apply_task_resumes_partial_instead_of_restarting(tmp_path: Path, monkeypatch) -> None:
    """跑到一半断了 → 重开任务**接着下**（服务器台账里的 Range 起点就是判据）。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    content = _big_payload()
    half = len(content) // 2
    batches = [_batch("k230", "k230资料",
                      [_part("", len(content), _sha_of(content), "k230.zip")])]
    target = tmp_path / "updates" / "materials" / "k230.zip"

    with ByteServer(content, cut_after=half, cut_runs=1) as server:
        batches[0]["parts"][0]["zip_url"] = server.url
        first = ApplyTask(task_dir=tmp_path / "updates", batches=batches)
        first._download = _capped_resumable(1)
        first.run()
        assert first.state == TaskState.FAILED
        assert target.stat().st_size == half
        assert download_resume.is_resumable_partial(
            target, batches[0]["parts"][0]["zip_url"], len(content)
        )

        mark = len(server.starts)
        second = ApplyTask(task_dir=tmp_path / "updates", batches=batches)
        second.run()
        second_starts = server.starts[mark:]

    assert second.state == TaskState.DONE, second.error
    assert second_starts == [half], "已落盘的半成品没被接着用（又从头下了）"
    assert target.read_bytes() == content
    assert not (target.parent / (target.name + ".partial.json")).exists()


def test_apply_task_cancel_writes_sidecar(tmp_path: Path, monkeypatch) -> None:
    """取消 → 边车写出（跨进程也知道这份半成品是谁的），任务态 = cancelled。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    content = _big_payload()
    batches = [_batch("k230", "k230资料",
                      [_part("", len(content), _sha_of(content), "k230.zip")])]
    target = tmp_path / "updates" / "materials" / "k230.zip"

    with ByteServer(content) as server:
        batches[0]["parts"][0]["zip_url"] = server.url
        task = ApplyTask(task_dir=tmp_path / "updates", batches=batches)
        # 取消发生在第一轮写盘**之后**（「读到一半点了取消」，不是「还没开始」）
        task._download = _cancellable_resumable(on_bytes=lambda n: task.cancel())
        task.run()

    assert task.state == TaskState.CANCELLED
    marker = target.parent / (target.name + ".partial.json")
    assert marker.is_file()
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["url"] == batches[0]["parts"][0]["zip_url"]
    assert data["expected_size"] == len(content)
    assert target.is_file() and 0 < target.stat().st_size < len(content)


def test_apply_task_retrying_flag_only_during_backoff(tmp_path: Path, monkeypatch) -> None:
    """`retrying` 只表示「正处在退避等待中」：续传启动那一下不算，进度也不许超算。

    资料库链路与完整包链路对称（同一个下载器、同一套字段），所以两条都要有这条判据。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    content = _big_payload()
    half = len(content) // 2
    batches = [_batch("k230", "k230资料",
                      [_part("", len(content), _sha_of(content), "k230.zip")])]
    target = tmp_path / "updates" / "materials" / "k230.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content[:half])

    seen: list[dict] = []
    with ByteServer(content) as server:
        batches[0]["parts"][0]["zip_url"] = server.url
        download_resume.write_partial_marker(
            target, batches[0]["parts"][0]["zip_url"], len(content))
        task = ApplyTask(task_dir=tmp_path / "updates", batches=batches)

        def spy(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
            seen.append(task_status(task))
            return resumable_download(url, dest, on_progress, **kwargs)

        task._download = spy  # type: ignore[attr-defined]
        task.run()

    assert task.state == TaskState.DONE, task.error
    assert seen and seen[0]["retrying"] is False, "「接着下」不是「正在重试」"
    assert seen[0]["retry_count"] == 0
    part = task.batches[0].parts[0]
    assert part.downloaded_bytes == len(content), "进度要把已落盘的一半算进去"
    assert part.downloaded_bytes <= len(content), "进度不许超算"


def test_apply_task_complete_file_is_verified_without_refetching(tmp_path: Path) -> None:
    """长度已到点 → 不发请求，直接校验（不许删了重下）。"""
    content = _big_payload()
    batches = [_batch("k230", "k230资料",
                      [_part("", len(content), _sha_of(content), "k230.zip")])]
    target = tmp_path / "updates" / "materials" / "k230.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    with ByteServer(content) as server:
        batches[0]["parts"][0]["zip_url"] = server.url
        task = ApplyTask(task_dir=tmp_path / "updates", batches=batches)
        task.run()

    assert task.state == TaskState.DONE, task.error
    assert server.starts == [], "长度已到点就不该再发请求"
    assert target.is_file()


def test_apply_task_resume_skips_done_parts(tmp_path: Path) -> None:
    """卷 1 成功（标记已写），卷 2 失败后重试 → 只重下卷 2。"""
    _, sha_a = _content_for("https://x/k230.zip")
    _, sha_b = _content_for("https://x/wireless.zip")
    batches = [
        _batch("k230", "k230资料", [
            _part("https://x/k230.zip", 60, sha_a),
            _part("https://x/wireless.zip", 40, sha_b),
        ]),
    ]
    downloaded: list[str] = []
    failures = {"https://x/wireless.zip": 1}  # 第一次失败，第二次成功

    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=_fake_download(log=downloaded, failures=failures),
    )
    task.run()  # 第一次：k230 成功，wireless 失败
    assert task.state == TaskState.FAILED
    assert "wireless" in (task.error or "")

    task2 = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=_fake_download(log=downloaded, failures=failures),
    )
    task2.run()  # 重试：只下 wireless
    assert task2.state == TaskState.DONE
    assert downloaded == ["https://x/k230.zip", "https://x/wireless.zip"]


def test_apply_task_cancel_stops_at_part_boundary(tmp_path: Path) -> None:
    _, sha_a = _content_for("https://x/a.zip")
    _, sha_b = _content_for("https://x/b.zip")
    batches = [
        _batch("k230", "k230资料", [
            _part("https://x/a.zip", 10, sha_a),
            _part("https://x/b.zip", 10, sha_b),
        ]),
    ]
    calls: list[str] = []

    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=_fake_download(log=calls),
    )
    task.cancel()
    task.run()
    assert task.state == TaskState.CANCELLED
    assert calls == []  # 取消在启动前生效


def test_task_status_shapes(tmp_path: Path) -> None:
    batches = [
        _batch("k230", "k230资料", [_part("https://x/k230.zip", 60, "a" * 64)]),
    ]
    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=lambda url, dest, on_progress: ("a" * 64),
    )
    status = task_status(task)
    assert status["state"] == "idle"
    assert status["total_bytes"] == 60
    assert status["parts"][0]["name"] == "k230.zip"
    assert status["parts"][0]["ok"] is False


# ---------------------------------------------------------------------------
# 状态落盘
# ---------------------------------------------------------------------------


def test_write_task_snapshot_roundtrip(tmp_path: Path) -> None:
    batches = [
        _batch("k230", "k230资料", [_part("https://x/k230.zip", 60, "a" * 64)]),
    ]
    task = ApplyTask(
        task_dir=tmp_path / "updates",
        batches=batches,
        download=lambda url, dest, on_progress: ("a" * 64),
    )
    write_task_snapshot(task)
    marker = tmp_path / "updates" / "materials-task.json"
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["state"] == "idle"
    assert data["batches"][0]["name"] == "k230资料"
    assert data["batches"][0]["slug"] == "k230"


# ---------------------------------------------------------------------------
# webapp 端点
# ---------------------------------------------------------------------------


def test_apply_endpoint_rejects_unknown_batch(tmp_path: Path) -> None:
    """批次 slug 白名单：不在 check 返回里的批次 → 400。"""
    client, _ = _client(tmp_path)
    resp = client.post("/api/update/materials/apply", json={"batches": ["evil-slug"]})
    assert resp.status_code == 400
    assert "未知批次" in resp.json()["detail"]


def test_apply_endpoint_rejects_missing_batches(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    resp = client.post("/api/update/materials/apply", json={})
    assert resp.status_code == 400


def test_apply_endpoint_runs_task_and_status_visible(tmp_path: Path) -> None:
    """apply 吃**本实例** ctx 上的 check 缓存（白名单来源）。"""
    client, ctx = _client(tmp_path)
    _seed_check(ctx, [
        _batch("k230", "k230资料", [_part("https://example.com/files/k230.zip", 100, "a" * 64, "k230.zip")]),
    ])
    resp = client.post("/api/update/materials/apply", json={"batches": ["k230"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["started"] is True


def test_check_then_apply_keeps_the_whitelist_on_this_instance(
    tmp_path: Path, monkeypatch
) -> None:
    """check → apply 的白名单缝在**同一个实例**内闭环（工单 webapp-state-into-ctx/02）。

    check 端点把结果写进本实例的 ctx，apply 从同一个 ctx 取白名单。让线上清单报一个
    「1 PB 的卷」→ apply 走过了批次校验、卡在磁盘空间那一关（400「磁盘空间不足」而不是
    400「未知批次」）——白名单确实来自这次 check，**且不真起下载**（卡在磁盘校验这一步）。
    """
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / mu.MANIFEST_FILENAME).write_text(
        json.dumps(_manifest("v1.0.0", []), ensure_ascii=False), encoding="utf-8"
    )
    online = _manifest("v1.1.0", [{
        "slug": "k230",
        "name": "k230资料",
        "files": [{"path": "k230资料/a.bin", "size": 3, "sha256": "x" * 64}],
        "removed": [],
        "parts": [{
            "zip_name": "firstep-materials-v1.1.0-k230.zip",
            "size": 10 ** 15,
            "sha256": "y" * 64,
        }],
    }])
    monkeypatch.setattr(mu, "_fetch_releases", lambda: _online_release("k230"))
    monkeypatch.setattr(mu, "_fetch_text", lambda url: json.dumps(online, ensure_ascii=False))
    # 端点内的资料库目录 = 工具根/sources/materials；monkeypatch 读取函数最薄
    monkeypatch.setattr(
        "contest_generator.webapp.materials_library_dir", lambda: materials_dir
    )

    client, _ = _client(tmp_path)
    check = client.get("/api/update/materials/check")
    assert check.status_code == 200
    assert [b["slug"] for b in check.json()["batches"]] == ["k230"]

    resp = client.post("/api/update/materials/apply", json={"batches": ["k230"]})
    assert resp.status_code == 400
    assert "磁盘空间不足" in resp.json()["detail"]


def test_two_app_instances_do_not_share_the_batch_whitelist(tmp_path: Path) -> None:
    """两个 app 实例互不可见（工单 webapp-state-into-ctx/02）：A 实例的 check 结果对
    **B 实例**的 apply 不是白名单——B 报「未知批次」，A 自己认（走过批次校验、卡在磁盘
    空间那一关）。

    收走前两边共用 webapp 的模块级全局，B 会认下 A 的批次（行为红读数：
    `.scratch/webapp-state-into-ctx/verify-00-sharing-before.txt`）。
    """
    client_a, ctx_a = _client(tmp_path / "a")
    client_b, _ = _client(tmp_path / "b")
    # 1 PB 的卷：两个实例都卡在「磁盘空间不足」，不真起下载
    _seed_check(ctx_a, [
        _batch("k230", "k230资料", [
            _part("https://example.com/files/k230.zip", 10 ** 15, "a" * 64, "k230.zip")
        ]),
    ])
    payload = {"batches": ["k230"]}

    resp_a = client_a.post("/api/update/materials/apply", json=payload)
    assert resp_a.status_code == 400
    assert "磁盘空间不足" in resp_a.json()["detail"]  # A：白名单认（判据没变）

    resp_b = client_b.post("/api/update/materials/apply", json=payload)
    assert resp_b.status_code == 400
    assert "未知批次" in resp_b.json()["detail"]  # B：看不见 A 的白名单


def test_status_endpoint_idle(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    resp = client.get("/api/update/materials/status")
    assert resp.status_code == 200
    assert resp.json()["state"] == "idle"
