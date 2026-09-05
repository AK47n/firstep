"""应用内一键更新：apply / status 端点测试（工单 auto-update/05）。

覆盖：apply 成功路径（下载 → 校验 → 写 pending → 拉起更新器 detached）、
SHA256 不匹配拦截（400 + 删半成品 + 不拉起）、缺字段 / 非法版本 400、下载
失败 400、removed 清单附带下载与透传、status 四态（idle / applying /
failed / done）。网络与真子进程不进测试：monkeypatch webapp.download_to /
spawn_updater。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import contest_generator.webapp as webapp_mod
from contest_generator.webapp import AppContext, create_app

SHA = "a" * 64
SHA_BAD = "b" * 64


def _client(tmp_path: Path) -> TestClient:
    ctx = AppContext(config_path=tmp_path / ".contest_generator" / "config.json")
    return TestClient(create_app(ctx))


def _patch_download(monkeypatch, sha: str = SHA, fail: bool = False) -> list[tuple[str, Path]]:
    """monkeypatch download_to：写目标文件 + 返回指定 sha；记录 (url, dest)。"""
    calls: list[tuple[str, Path]] = []

    def fake(url: str, dest: Path, timeout: float = 300.0) -> str:
        if fail:
            raise OSError("connection refused")
        calls.append((url, dest))
        dest.write_bytes(b"zip-bytes")
        return sha

    monkeypatch.setattr(webapp_mod, "download_to", fake)
    return calls


def _patch_spawn(monkeypatch) -> list[tuple[Path, Path, Path | None]]:
    calls: list[tuple[Path, Path, Path | None]] = []

    def fake(data_dir: Path, zip_path: Path, removed_path: Path | None) -> None:
        calls.append((data_dir, zip_path, removed_path))

    monkeypatch.setattr(webapp_mod, "spawn_updater", fake)
    return calls


def _payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "zip_url": "https://example.com/files/firstep-update-v1.1.0.zip",
        "sha256": SHA,
        "version": "v1.1.0",
        "removed_url": "",
    }
    base.update(overrides)
    return base


def test_apply_success_writes_pending_and_spawns(tmp_path, monkeypatch) -> None:
    download_calls = _patch_download(monkeypatch)
    spawn_calls = _patch_spawn(monkeypatch)
    client = _client(tmp_path)
    resp = client.post("/api/update/apply", json=_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["started"] is True
    assert "已开始更新" in body["message"]

    updates = tmp_path / ".contest_generator" / "updates"
    assert (updates / "firstep-update-v1.1.0.zip").read_bytes() == b"zip-bytes"
    pending = json.loads((updates / "pending-update.json").read_text(encoding="utf-8"))
    assert pending["version"] == "v1.1.0"
    assert pending["zip"].endswith("firstep-update-v1.1.0.zip")
    assert pending["removed"] == ""
    # 拉起更新器：data_dir = 配置目录（.contest_generator）
    assert len(spawn_calls) == 1
    data_dir, zip_path, removed_path = spawn_calls[0]
    assert data_dir == tmp_path / ".contest_generator"
    assert zip_path.name == "firstep-update-v1.1.0.zip"
    assert removed_path is None
    assert len(download_calls) == 1


def test_apply_downloads_removed_and_passes_path(tmp_path, monkeypatch) -> None:
    download_calls = _patch_download(monkeypatch)
    spawn_calls = _patch_spawn(monkeypatch)
    client = _client(tmp_path)
    resp = client.post(
        "/api/update/apply",
        json=_payload(removed_url="https://example.com/files/firstep-update-v1.1.0.removed.txt"),
    )
    assert resp.status_code == 200
    assert len(download_calls) == 2  # zip + removed
    assert spawn_calls[0][2].name == "firstep-update-v1.1.0.removed.txt"
    pending = json.loads(
        (tmp_path / ".contest_generator" / "updates" / "pending-update.json")
        .read_text(encoding="utf-8")
    )
    assert pending["removed"].endswith("firstep-update-v1.1.0.removed.txt")


def test_apply_sha_mismatch_400_and_cleans_zip(tmp_path, monkeypatch) -> None:
    _patch_download(monkeypatch, sha=SHA_BAD)
    spawn_calls = _patch_spawn(monkeypatch)
    client = _client(tmp_path)
    resp = client.post("/api/update/apply", json=_payload())
    assert resp.status_code == 400
    assert "校验失败" in resp.json()["detail"]
    updates = tmp_path / ".contest_generator" / "updates"
    assert not (updates / "firstep-update-v1.1.0.zip").exists()  # 半成品已删
    assert not (updates / "pending-update.json").exists()
    assert spawn_calls == []


def test_apply_download_failure_400(tmp_path, monkeypatch) -> None:
    _patch_download(monkeypatch, fail=True)
    spawn_calls = _patch_spawn(monkeypatch)
    client = _client(tmp_path)
    resp = client.post("/api/update/apply", json=_payload())
    assert resp.status_code == 400
    assert "下载失败" in resp.json()["detail"]
    assert spawn_calls == []


def test_apply_missing_fields_400(tmp_path, monkeypatch) -> None:
    _patch_download(monkeypatch)
    client = _client(tmp_path)
    assert client.post("/api/update/apply", json=_payload(zip_url="")).status_code == 400
    assert client.post("/api/update/apply", json=_payload(sha256="short")).status_code == 400
    assert client.post("/api/update/apply", json=_payload(version="")).status_code == 400
    # 版本号防路径注入
    assert (
        client.post("/api/update/apply", json=_payload(version="../evil")).status_code
        == 400
    )


# ---------------------------------------------------------------------------
# status 四态
# ---------------------------------------------------------------------------


def test_status_idle(tmp_path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/update/status")
    assert resp.status_code == 200
    assert resp.json()["state"] == "idle"


def test_status_applying_when_lock_exists(tmp_path) -> None:
    updates = tmp_path / ".contest_generator" / "updates"
    updates.mkdir(parents=True)
    (updates / "updating.lock").write_text("1", encoding="utf-8")
    client = _client(tmp_path)
    assert client.get("/api/update/status").json()["state"] == "applying"


def test_status_failed_when_pending_left(tmp_path) -> None:
    updates = tmp_path / ".contest_generator" / "updates"
    updates.mkdir(parents=True)
    (updates / "pending-update.json").write_text('{"version":"v1.1.0"}', encoding="utf-8")
    client = _client(tmp_path)
    body = client.get("/api/update/status").json()
    assert body["state"] == "failed"
    assert body["pending"]["version"] == "v1.1.0"


def test_status_done_with_result(tmp_path) -> None:
    updates = tmp_path / ".contest_generator" / "updates"
    updates.mkdir(parents=True)
    (updates / "last-update.json").write_text(
        json.dumps({"status": "ok", "version": "v1.1.0"}),
        encoding="utf-8",
    )
    client = _client(tmp_path)
    body = client.get("/api/update/status").json()
    assert body["state"] == "done"
    assert body["result"]["version"] == "v1.1.0"


def test_status_done_failed_result(tmp_path) -> None:
    updates = tmp_path / ".contest_generator" / "updates"
    updates.mkdir(parents=True)
    (updates / "last-update.json").write_text(
        json.dumps({"status": "failed", "error": "xx", "backup_dir": "C:/backup"}),
        encoding="utf-8",
    )
    client = _client(tmp_path)
    body = client.get("/api/update/status").json()
    assert body["state"] == "done"  # 结果文件存在 = 有一次更新记录
    assert body["result"]["status"] == "failed"
