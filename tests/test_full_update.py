"""完整包检查更新测试（工单 full-download/02）。

覆盖：线上完整包 release 选取（软件 tag 前缀过滤 + 版本最大）、完整包清单
资产定位、已装版本标记读取（缺失 / 损坏 = 未知）、check 主逻辑各态（有新
完整包 / 已是最新 / 该 release 无完整包资产 / 网络失败 / 清单损坏 / 分卷表
为空）、分卷下载地址拼接，以及 webapp 端点（注入假 fetch，不碰网络）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from contest_generator import full_update as fu
from contest_generator.full_update import (
    ERROR_BAD_MANIFEST,
    ERROR_NETWORK,
    ERROR_NO_ASSET,
    ERROR_NO_RELEASE,
    REASON_NO_INSTALLED,
    REASON_OUTDATED,
    REASON_UP_TO_DATE,
    check_for_full_update,
    find_latest_full_release,
    full_manifest_asset_name,
    load_installed_marker,
    resolve_part_url,
)
from contest_generator.webapp import AppContext, create_app


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------


def _part(name: str, size: int = 1000, sha: str = "a" * 64) -> dict[str, Any]:
    return {"zip_name": name, "size": size, "sha256": sha}


def _full_manifest(
    version: str,
    parts: list[dict[str, Any]] | None = None,
    total_bytes: int = 1000,
) -> dict[str, Any]:
    return {
        "version": version,
        "published_at": "2026-09-13T00:00:00Z",
        "total_bytes": total_bytes,
        "parts": parts if parts is not None else [_part(f"firstep-full-{version}.zip")],
        "materials_manifest": {"version": version, "published_at": "", "batches": []},
        "files": [{"path": "README.md", "size": 10, "sha256": "b" * 64}],
    }


def _release(
    tag: str,
    parts: list[str] | None = None,
    manifest: bool = True,
    prefix: str = "firstep-full-",
) -> dict[str, Any]:
    """Release 夹具：清单资产名按检查端点的口径（`firstep-full-<version>.manifest.json`，
    version = tag 去掉 `v` 前的软件版本串——端点用 tag 原样构造，故两者一致）。"""
    assets: list[dict[str, Any]] = []
    if manifest:
        assets.append(
            {
                "name": f"{prefix}{tag}.manifest.json",
                "browser_download_url": f"https://example.com/files/{tag}.manifest.json",
                "size": 5000,
            }
        )
    for name in parts or [f"{prefix}{tag}.zip"]:
        assets.append(
            {
                "name": name,
                "browser_download_url": f"https://example.com/files/{name}",
                "size": 900,
            }
        )
    return {"tag_name": tag, "assets": assets}


def _public_asset(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "browser_download_url": f"https://example.com/files/{name}",
        "size": 900,
    }


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(AppContext(config_path=tmp_path / "config.json")))


# ---------------------------------------------------------------------------
# 资产名与已装标记
# ---------------------------------------------------------------------------


def test_asset_naming() -> None:
    assert full_manifest_asset_name("v1.1.0") == "firstep-full-v1.1.0.manifest.json"


def test_load_installed_marker(tmp_path: Path) -> None:
    updates = tmp_path / "updates"
    updates.mkdir()
    marker = updates / "full-installed.json"
    assert load_installed_marker(updates) is None  # 缺失 = 未知

    marker.write_text(json.dumps({"version": "v1.1.0"}), encoding="utf-8")
    assert load_installed_marker(updates) == "v1.1.0"

    marker.write_text("{ 坏 json", encoding="utf-8")
    assert load_installed_marker(updates) is None  # 损坏 = 未知，不抛

    marker.write_text(json.dumps({"version": ""}), encoding="utf-8")
    assert load_installed_marker(updates) is None


# ---------------------------------------------------------------------------
# release 选取
# ---------------------------------------------------------------------------


def test_find_latest_full_release_skips_materials_tags() -> None:
    releases = [
        _release("materials-v9.9.9"),
        _release("v1.1.0"),
        _release("v1.0.9"),
    ]
    found = find_latest_full_release(releases)
    assert found is not None
    assert found["tag_name"] == "v1.1.0"


def test_find_latest_full_release_none_when_only_materials() -> None:
    assert find_latest_full_release([_release("materials-v1.0.0")]) is None


def test_find_latest_full_release_picks_max_version() -> None:
    releases = [_release("v1.0.9"), _release("v1.10.0"), _release("v1.2.0")]
    found = find_latest_full_release(releases)
    assert found is not None and found["tag_name"] == "v1.10.0"


def test_resolve_part_url() -> None:
    release = _release("v1.1.0", parts=["firstep-full-v1.1.0.zip"])
    assert (
        resolve_part_url(release, "firstep-full-v1.1.0.zip")
        == "https://example.com/files/firstep-full-v1.1.0.zip"
    )
    assert resolve_part_url(release, "不存在.zip") == ""


# ---------------------------------------------------------------------------
# check 主逻辑
# ---------------------------------------------------------------------------


def test_check_reports_update_with_parts_and_total() -> None:
    releases = [_release("v1.1.0", parts=["firstep-full-v1.1.0.zip"])]
    manifest = _full_manifest("v1.1.0", total_bytes=123456)
    result = check_for_full_update(
        installed="v1.0.0",
        fetch_json=lambda url: releases,
        fetch_text=lambda url: json.dumps(manifest, ensure_ascii=False),
    )
    assert result["error"] == ""
    assert result["update_available"] is True
    assert result["current_version"] == "v1.0.0"
    assert result["latest_version"] == "v1.1.0"
    assert result["total_bytes"] == 123456
    assert result["reason"] == REASON_OUTDATED
    assert result["parts"][0]["name"] == "firstep-full-v1.1.0.zip"
    assert result["parts"][0]["url"] == "https://example.com/files/firstep-full-v1.1.0.zip"
    assert result["parts"][0]["sha256"] == "a" * 64
    assert "v1.1.0" in result["message"]


def test_check_up_to_date_still_offers_download() -> None:
    releases = [_release("v1.1.0")]
    manifest = _full_manifest("v1.1.0")
    result = check_for_full_update(
        installed="v1.1.0",
        fetch_json=lambda url: releases,
        fetch_text=lambda url: json.dumps(manifest, ensure_ascii=False),
    )
    assert result["update_available"] is False
    assert result["reason"] == REASON_UP_TO_DATE
    assert result["total_bytes"] == 1000
    assert result["parts"], "已是最新也应保留分卷表（供主动重下）"
    assert "已是最新" in result["message"]


def test_check_unknown_installed_version_reports_reason() -> None:
    releases = [_release("v1.1.0")]
    manifest = _full_manifest("v1.1.0")
    result = check_for_full_update(
        installed=None,
        fetch_json=lambda url: releases,
        fetch_text=lambda url: json.dumps(manifest, ensure_ascii=False),
    )
    assert result["reason"] == REASON_NO_INSTALLED
    assert result["update_available"] is True
    assert result["current_version"] == ""


def test_check_network_failure_is_200_level() -> None:
    def boom(url: str) -> Any:
        raise OSError("network down")

    result = check_for_full_update(installed="v1.0.0", fetch_json=boom, fetch_text=lambda url: "")
    assert result["error"] == ERROR_NETWORK
    assert result["update_available"] is False
    assert result["parts"] == []
    assert "网络" in result["message"]


def test_check_no_release_is_200_level() -> None:
    result = check_for_full_update(
        installed="v1.0.0", fetch_json=lambda url: [], fetch_text=lambda url: ""
    )
    assert result["error"] == ERROR_NO_RELEASE
    assert result["message"]


def test_check_release_without_manifest_asset() -> None:
    releases = [_release("v1.1.0", manifest=False)]
    result = check_for_full_update(
        installed="v1.0.0",
        fetch_json=lambda url: releases,
        fetch_text=lambda url: "",
    )
    assert result["error"] == ERROR_NO_ASSET
    assert "完整包" in result["message"] or "资产" in result["message"]


def test_check_bad_manifest_is_200_level() -> None:
    releases = [_release("v1.1.0")]
    result = check_for_full_update(
        installed="v1.0.0",
        fetch_json=lambda url: releases,
        fetch_text=lambda url: "{ 不是 json",
    )
    assert result["error"] == ERROR_BAD_MANIFEST
    assert result["parts"] == []


def test_check_empty_parts_is_200_level() -> None:
    releases = [_release("v1.1.0")]
    manifest = _full_manifest("v1.1.0", parts=[])
    result = check_for_full_update(
        installed="v1.0.0",
        fetch_json=lambda url: releases,
        fetch_text=lambda url: json.dumps(manifest, ensure_ascii=False),
    )
    assert result["error"] == ERROR_NO_ASSET
    assert result["parts"] == []


def test_check_part_url_missing_marked_unavailable() -> None:
    """清单列了分卷但 release 上没有该资产 → 该卷标记不可下（不静默给空 URL）。"""
    releases = [_release("v1.1.0", parts=["firstep-full-v1.1.0.zip"])]
    manifest = _full_manifest("v1.1.0", parts=[_part("firstep-full-v1.1.0.part9.zip")])
    result = check_for_full_update(
        installed="v1.0.0",
        fetch_json=lambda url: releases,
        fetch_text=lambda url: json.dumps(manifest, ensure_ascii=False),
    )
    assert result["error"] == ERROR_NO_ASSET
    assert result["parts"] == []


def test_check_result_shape_is_stable() -> None:
    releases = [_release("v1.1.0")]
    manifest = _full_manifest("v1.1.0")
    result = check_for_full_update(
        installed="v1.0.0",
        fetch_json=lambda url: releases,
        fetch_text=lambda url: json.dumps(manifest, ensure_ascii=False),
    )
    assert set(result) == {
        "current_version",
        "latest_version",
        "update_available",
        "total_bytes",
        "parts",
        "reason",
        "error",
        "message",
        "manifest_url",
    }
    assert result["manifest_url"] == "https://example.com/files/v1.1.0.manifest.json"


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


def test_endpoint_reports_update(tmp_path: Path, monkeypatch) -> None:
    releases = [_release("v1.1.0", parts=["firstep-full-v1.1.0.zip"])]
    manifest = _full_manifest("v1.1.0", total_bytes=2048)
    updates = tmp_path / "updates"
    updates.mkdir()
    (updates / "full-installed.json").write_text(
        json.dumps({"version": "v1.0.0"}), encoding="utf-8"
    )
    monkeypatch.setattr(fu, "_fetch_releases", lambda: releases)
    monkeypatch.setattr(fu, "_fetch_text", lambda url: json.dumps(manifest, ensure_ascii=False))

    client = _client(tmp_path)
    resp = client.get("/api/update/full/check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["update_available"] is True
    assert body["current_version"] == "v1.0.0"
    assert body["latest_version"] == "v1.1.0"
    assert body["total_bytes"] == 2048
    assert body["parts"][0]["name"] == "firstep-full-v1.1.0.zip"


def test_endpoint_unknown_installed_is_200(tmp_path: Path, monkeypatch) -> None:
    releases = [_release("v1.1.0")]
    manifest = _full_manifest("v1.1.0")
    monkeypatch.setattr(fu, "_fetch_releases", lambda: releases)
    monkeypatch.setattr(fu, "_fetch_text", lambda url: json.dumps(manifest, ensure_ascii=False))

    client = _client(tmp_path)
    resp = client.get("/api/update/full/check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reason"] == REASON_NO_INSTALLED
    assert body["parts"], "未知版本也要能下完整包"


def test_endpoint_network_failure_never_500(tmp_path: Path, monkeypatch) -> None:
    def boom() -> Any:
        raise OSError("no network")

    monkeypatch.setattr(fu, "_fetch_releases", boom)
    client = _client(tmp_path)
    resp = client.get("/api/update/full/check")
    assert resp.status_code == 200
    assert resp.json()["error"] == ERROR_NETWORK
