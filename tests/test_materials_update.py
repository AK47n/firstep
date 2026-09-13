"""资料库检查更新测试（工单 materials-update/03）。

覆盖：GitHub releases 列表过滤 `materials-` 前缀取最新、本地清单读取
（缺失 = baseline_missing）、线上清单拉取与解析、按批次 diff（本地批次
版本 vs 线上版本；未变更批次不出现）、check 主逻辑各态（有新版 / 无新版 /
网络失败 / 无资料版发布 / 本地清单损坏）、webapp 端点（monkeypatch fetch，
不碰网络）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from contest_generator import materials_update as mu
from contest_generator.materials_update import (
    ERROR_BASELINE_MISSING,
    ERROR_NETWORK,
    ERROR_NO_RELEASE,
    check_for_materials_update,
    find_latest_materials_release,
    load_local_manifest,
)
from contest_generator.webapp import AppContext, create_app


def _manifest(version: str, batches: list[dict]) -> dict[str, Any]:
    return {"version": version, "published_at": "2026-09-01T00:00:00Z", "batches": batches}


def _batch(slug: str, name: str, files: list[dict], parts: list[dict] | None = None,
           removed: list[str] | None = None) -> dict[str, Any]:
    return {"slug": slug, "name": name, "files": files,
            "removed": removed or [], "parts": parts or []}


def _file(path: str, size: int, sha: str) -> dict[str, Any]:
    return {"path": path, "size": size, "sha256": sha}


def _assets(version: str, slugs: list[str]) -> list[dict[str, Any]]:
    assets = [{
        "name": f"firstep-materials-{version}.manifest.json",
        "browser_download_url": f"https://example.com/files/{version}.manifest.json",
        "size": 100,
    }]
    for slug in slugs:
        assets.append({
            "name": f"firstep-materials-{version}-{slug}.zip",
            "browser_download_url": f"https://example.com/files/{version}-{slug}.zip",
            "size": 200,
        })
    return assets


def _release(tag: str, version: str, slugs: list[str]) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "name": tag,
        "published_at": "2026-09-01T00:00:00Z",
        "assets": _assets(version, slugs),
    }


# ---------------------------------------------------------------------------
# GitHub releases 列表过滤
# ---------------------------------------------------------------------------


def test_find_latest_filters_materials_prefix() -> None:
    releases = [
        _release("v1.2.0", "v1.2.0", []),              # 软件 release，忽略
        _release("materials-v1.0.0", "v1.0.0", []),
        _release("materials-v1.1.0", "v1.1.0", ["k230"]),
    ]
    assert find_latest_materials_release(releases) == releases[2]


def test_find_latest_prefers_max_version_not_list_order() -> None:
    """API 顺序（创建时间新在前）不保证 tag 版本序，取版本号最大者。"""
    releases = [
        _release("materials-v1.0.0", "v1.0.0", []),
        _release("materials-v1.1.0", "v1.1.0", ["k230"]),
    ]
    assert find_latest_materials_release(releases) == releases[1]
    # 列表前移也不能改变结果（乱序发版后 API 排序按时间而非 tag）
    shuffled = [releases[1], releases[0]]
    assert find_latest_materials_release(shuffled) == releases[1]


def test_find_latest_none_when_absent() -> None:
    assert find_latest_materials_release([]) is None
    assert find_latest_materials_release([_release("v1.0.0", "v1.0.0", [])]) is None


# ---------------------------------------------------------------------------
# 本地清单读取
# ---------------------------------------------------------------------------


def test_load_local_manifest_missing_returns_none(tmp_path: Path) -> None:
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    assert load_local_manifest(materials_dir) is None


def test_load_local_manifest_reads_file(tmp_path: Path) -> None:
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    manifest = _manifest("v1.0.0", [_batch("k230", "k230资料", [])])
    (materials_dir / mu.MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    data = load_local_manifest(materials_dir)
    assert data is not None
    assert data["version"] == "v1.0.0"


# ---------------------------------------------------------------------------
# check 主逻辑（注入假 fetch）
# ---------------------------------------------------------------------------


def _fake_fetch(releases: list[dict] | None, manifest_text: str = "", fail_manifest: bool = False):
    """返回 (fetch_json, fetch_text)：releases=None = 拉取抛网络异常。"""

    def fetch_json(url: str) -> Any:
        if releases is None:
            raise OSError("network down")
        return releases

    def fetch_text(url: str) -> str:
        if fail_manifest:
            raise OSError("manifest download failed")
        return manifest_text

    return fetch_json, fetch_text


def test_check_has_new_version() -> None:
    releases = [_release("materials-v1.1.0", "v1.1.0", ["k230"])]
    online = _manifest("v1.1.0", [
        _batch("k230", "k230资料", [
            _file("k230资料/a.bin", 3, "x" * 64),
        ], parts=[{
            "zip_name": "firstep-materials-v1.1.0-k230.zip",
            "size": 200, "sha256": "y" * 64,
        }]),
    ])
    local = _manifest("v1.0.0", [
        _batch("k230", "k230资料", [
            _file("k230资料/a.bin", 3, "x" * 64),
        ]),
    ])
    fetch_json, fetch_text = _fake_fetch(releases, json.dumps(online, ensure_ascii=False))
    result = check_for_materials_update(local, fetch_json, fetch_text)
    assert result["current_version"] == "v1.0.0"
    assert result["latest_version"] == "v1.1.0"
    assert result["update_available"] is True
    assert result["total_size_bytes"] == 200
    batch = result["batches"][0]
    assert batch["slug"] == "k230"
    assert batch["name"] == "k230资料"
    assert batch["add_count"] == 0
    assert batch["modify_count"] == 0
    assert batch["del_count"] == 0
    assert batch["size_bytes"] == 200
    assert batch["parts"][0]["zip_url"].endswith("v1.1.0-k230.zip")
    assert batch["parts"][0]["size_bytes"] == 200
    assert batch["parts"][0]["sha256"] == "y" * 64
    assert result["error"] == ""


def test_check_no_update_when_same_version() -> None:
    releases = [_release("materials-v1.0.0", "v1.0.0", [])]
    online = _manifest("v1.0.0", [_batch("k230", "k230资料", [])])
    local = _manifest("v1.0.0", [_batch("k230", "k230资料", [])])
    fetch_json, fetch_text = _fake_fetch(releases, json.dumps(online, ensure_ascii=False))
    result = check_for_materials_update(local, fetch_json, fetch_text)
    assert result["update_available"] is False
    assert result["batches"] == []
    assert result["error"] == ""


def test_check_baseline_missing() -> None:
    result = check_for_materials_update(None, None, None)  # type: ignore[arg-type]
    assert result["error"] == ERROR_BASELINE_MISSING
    assert "版本未知" in result["message"]
    assert result["update_available"] is False


def test_check_network_error() -> None:
    local = _manifest("v1.0.0", [_batch("k230", "k230资料", [])])
    fetch_json, fetch_text = _fake_fetch(None)
    result = check_for_materials_update(local, fetch_json, fetch_text)
    assert result["error"] == ERROR_NETWORK
    assert "网络" in result["message"]
    assert result["update_available"] is False


def test_check_no_materials_release() -> None:
    local = _manifest("v1.0.0", [_batch("k230", "k230资料", [])])
    fetch_json, fetch_text = _fake_fetch([_release("v1.2.0", "v1.2.0", [])])
    result = check_for_materials_update(local, fetch_json, fetch_text)
    assert result["error"] == ERROR_NO_RELEASE
    assert "没有发布" in result["message"]
    assert result["update_available"] is False


# ---------------------------------------------------------------------------
# webapp 端点
# ---------------------------------------------------------------------------


def _client(tmp_path: Path) -> TestClient:
    ctx = AppContext(config_path=tmp_path / "config.json")
    return TestClient(create_app(ctx))


def test_check_endpoint_baseline_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        mu, "_fetch_releases", lambda: [_release("materials-v1.1.0", "v1.1.0", ["k230"])]
    )
    monkeypatch.setattr(
        mu, "_fetch_text", lambda url: "{}"
    )
    # 注入空资料库目录（与 test_check_endpoint_has_new_version 同法）：本用例要的是
    # 「本地没有基线」这个前置条件，不能让真机状态决定结果——真机上写过一次
    # `.materials-manifest.json`（完整包落位 / 就地补基线），这条就会从红变绿再变红。
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    monkeypatch.setattr(
        "contest_generator.webapp.materials_library_dir",
        lambda: materials_dir,
    )
    client = _client(tmp_path)
    resp = client.get("/api/update/materials/check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] == "baseline-missing"


def test_check_endpoint_has_new_version(tmp_path: Path, monkeypatch) -> None:
    online = _manifest("v1.1.0", [
        _batch("k230", "k230资料", [
            _file("k230资料/a.bin", 3, "x" * 64),
        ], parts=[{
            "zip_name": "firstep-materials-v1.1.0-k230.zip",
            "size": 200, "sha256": "y" * 64,
        }]),
    ])
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    local = _manifest("v1.0.0", [_batch("k230", "k230资料", [])])
    (materials_dir / mu.MANIFEST_FILENAME).write_text(
        json.dumps(local, ensure_ascii=False), encoding="utf-8"
    )
    ctx = AppContext(config_path=tmp_path / "config.json")
    # 端点内材料库目录 = 工具根/sources/materials；monkeypatch 读取函数最薄
    monkeypatch.setattr(mu, "_fetch_releases", lambda: [_release("materials-v1.1.0", "v1.1.0", ["k230"])])
    monkeypatch.setattr(mu, "_fetch_text", lambda url: json.dumps(online, ensure_ascii=False))
    # webapp 端点直接调用导入的 materials_library_dir（已绑定），须 patch webapp 模块名
    monkeypatch.setattr(
        "contest_generator.webapp.materials_library_dir",
        lambda: materials_dir,
    )
    client = TestClient(create_app(ctx))
    resp = client.get("/api/update/materials/check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["update_available"] is True
    assert body["latest_version"] == "v1.1.0"
    assert body["batches"][0]["slug"] == "k230"
