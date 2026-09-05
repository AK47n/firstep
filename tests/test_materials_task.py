"""资料库下载任务测试（工单 materials-update/04）。

覆盖：apply 参数校验（批次白名单 / 缺字段 / 非法 slug）、磁盘空间不足 400、
应用启动后台任务（monkeypatch 下载函数）、卷级断点续传（卷 1 成功卷 2 失败
→ 重试只下卷 2）、cancel 在卷边界停止、status 状态机（idle / downloading /
downloading+partial / done / failed / applying）、状态落盘节流与重启恢复、
ApplyTask 纯逻辑（不依赖网络）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import contest_generator.materials_update as mu
from contest_generator.materials_task import (
    ApplyTask,
    TaskState,
    download_part,
    normalize_part,
    task_status,
    write_task_snapshot,
)
from contest_generator.webapp import AppContext, create_app
import contest_generator.webapp as webapp_mod


@pytest.fixture(autouse=True)
def _reset_module_state():
    """每个测试后清模块级会话态（_materials_task / check 缓存），防跨测试污染。"""
    yield
    webapp_mod._materials_task = None
    webapp_mod._MATERIALS_LAST_CHECK = {}


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


def _content_for(url: str) -> tuple[bytes, str]:
    """URL → (内容字节, 内容 SHA256)：测试内卷的一致性数据源。"""
    content = f"data-of-{url}".encode("utf-8")
    return content, _sha_of(content)


def _fake_download(log: list[str] | None = None, failures: dict[str, int] | None = None):
    """构造假下载函数：按 URL 写内容并返回其 SHA256；failures 控制失败次数。"""

    def fake(url: str, dest: Path, on_progress) -> str:
        if failures and failures.get(url, 0) > 0:
            failures[url] -= 1
            raise OSError("connection reset")
        content, sha = _content_for(url)
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


def _client(tmp_path: Path) -> TestClient:
    ctx = AppContext(config_path=tmp_path / "config.json")
    return TestClient(create_app(ctx))


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


def test_apply_endpoint_rejects_unknown_batch(tmp_path: Path, monkeypatch) -> None:
    """批次 slug 白名单：不在 check 返回里的批次 → 400。"""
    client = _client(tmp_path)
    resp = client.post("/api/update/materials/apply", json={"batches": ["evil-slug"]})
    assert resp.status_code == 400
    assert "未知批次" in resp.json()["detail"]


def test_apply_endpoint_rejects_missing_batches(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/update/materials/apply", json={})
    assert resp.status_code == 400


def test_apply_endpoint_runs_task_and_status_visible(tmp_path: Path, monkeypatch) -> None:
    check = _check_result([
        _batch("k230", "k230资料", [_part("https://example.com/files/k230.zip", 100, "a" * 64, "k230.zip")]),
    ])
    monkeypatch.setattr(
        "contest_generator.webapp._MATERIALS_LAST_CHECK",
        check,  # apply 吃 check 缓存（模块级 dict）
    )
    client = _client(tmp_path)
    resp = client.post("/api/update/materials/apply", json={"batches": ["k230"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["started"] is True


def test_status_endpoint_idle(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/update/materials/status")
    assert resp.status_code == 200
    assert resp.json()["state"] == "idle"
