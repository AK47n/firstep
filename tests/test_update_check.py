"""应用内一键更新：检查更新纯函数与端点测试（工单 auto-update/03）。

覆盖：版本规范化 / semver 解析与比对（含 v 前缀与非法降级）、GitHub
Release 资产解析（zip + sha256 配套、tag 精确匹配）、sha256 文本解析、
check 主逻辑四态（有新版 / 无新版 / 网络不可达 / 无资产 / sha 缺失 / 非法
版本降级）、webapp 端点（monkeypatch update.http_json / http_text，不碰网络）。
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from contest_generator import update as update_mod
from contest_generator.update import (
    ERROR_NETWORK,
    ERROR_NO_ASSET,
    MSG_BAD_VERSION,
    MSG_NO_SHA,
    check_for_update,
    compare_versions,
    normalize_version,
    parse_sha256_text,
    parse_semver,
    resolve_assets,
)
from contest_generator.webapp import AppContext, create_app


# ---------------------------------------------------------------------------
# 版本比对纯函数
# ---------------------------------------------------------------------------


def test_normalize_version() -> None:
    assert normalize_version("v1.1.0") == "1.1.0"
    assert normalize_version(" 1.0.0 ") == "1.0.0"
    assert normalize_version("V2.0.0") == "2.0.0"


def test_parse_semver() -> None:
    assert parse_semver("1.2.3") == (1, 2, 3)
    assert parse_semver("v10.0.1") == (10, 0, 1)
    assert parse_semver("1.2") is None
    assert parse_semver("abc") is None


def test_compare_versions() -> None:
    assert compare_versions("1.0.0", "1.1.0") == 1
    assert compare_versions("1.1.0", "1.0.0") == -1
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("v1.0.0", "1.1.0") == 1  # 容忍 v 前缀
    assert compare_versions("1.9.0", "1.10.0") == 1  # 数字比较非字符串
    assert compare_versions("1.0", "1.0.0") is None  # 非法 → None


# ---------------------------------------------------------------------------
# 资产解析与 sha256 文本
# ---------------------------------------------------------------------------


def _release(tag: str = "v1.1.0", with_assets: bool = True) -> dict[str, Any]:
    assets = [
        {
            "name": f"firstep-update-{tag}.zip",
            "browser_download_url": f"https://example.com/files/{tag}.zip",
            "size": 123456,
        },
        {
            "name": f"firstep-update-{tag}.sha256.txt",
            "browser_download_url": f"https://example.com/files/{tag}.sha256.txt",
            "size": 100,
        },
        {
            "name": f"firstep-update-{tag}.removed.txt",
            "browser_download_url": f"https://example.com/files/{tag}.removed.txt",
            "size": 50,
        },
    ] if with_assets else []
    return {
        "tag_name": tag,
        "body": "测试更新说明",
        "published_at": "2026-09-01T00:00:00Z",
        "assets": assets,
    }


def test_resolve_assets_matches_zip_and_sha() -> None:
    zip_url, size, sha_url, removed_url = resolve_assets(_release("v1.1.0"))
    assert zip_url == "https://example.com/files/v1.1.0.zip"
    assert size == 123456
    assert sha_url == "https://example.com/files/v1.1.0.sha256.txt"
    assert removed_url == "https://example.com/files/v1.1.0.removed.txt"


def test_resolve_assets_ignores_unrelated_uploads() -> None:
    release = _release("v1.1.0")
    release["assets"].append(
        {"name": "firstep-full.7z.001", "browser_download_url": "https://x/1", "size": 1}
    )
    zip_url, size, sha_url, removed_url = resolve_assets(release)
    assert zip_url == "https://example.com/files/v1.1.0.zip"
    assert size == 123456
    assert sha_url == "https://example.com/files/v1.1.0.sha256.txt"
    assert removed_url == "https://example.com/files/v1.1.0.removed.txt"


def test_resolve_assets_no_assets() -> None:
    assert resolve_assets(_release("v1.1.0", with_assets=False)) == (None, 0, None, None)


def test_parse_sha256_text() -> None:
    text = "1BA4C9F2581A0C33CB266B10298257A30921CB2D9340BE28E98D9BE0B4A1B870  firstep-update-v1.1.0.zip\n"
    assert parse_sha256_text(text) == text.split()[0].lower()
    assert parse_sha256_text("") == ""
    assert parse_sha256_text("无校验文件") == ""


# ---------------------------------------------------------------------------
# check 主逻辑（注入假 fetch）
# ---------------------------------------------------------------------------


def _fake_fetch(
    release: dict[str, Any] | None, sha_text: str = None
) -> tuple[Any, Any]:
    """返回 (fetch_json, fetch_text)：release None = 抛网络异常。"""

    def fetch_json(url: str) -> Any:
        assert url == update_mod.LATEST_RELEASE_URL
        if release is None:
            raise OSError("network down")
        return release

    def fetch_text(url: str) -> str:
        if sha_text is None:
            raise OSError("sha download failed")
        return sha_text

    return fetch_json, fetch_text


def test_check_has_new_version_full_contract() -> None:
    release = _release("v1.1.0")
    sha = "a" * 64
    fetch_json, fetch_text = _fake_fetch(release, sha + "  firstep-update-v1.1.0.zip\n")
    result = check_for_update("1.0.0", fetch_json, fetch_text)
    assert result["current_version"] == "1.0.0"
    assert result["latest_version"] == "1.1.0"
    assert result["update_available"] is True
    assert result["zip_url"] == "https://example.com/files/v1.1.0.zip"
    assert result["size_bytes"] == 123456
    assert result["sha256"] == sha
    assert result["removed_url"] == "https://example.com/files/v1.1.0.removed.txt"
    assert result["release_notes"] == "测试更新说明"
    assert result["published_at"] == "2026-09-01T00:00:00Z"
    assert result["error"] == ""
    assert result["message"] == ""


def test_check_same_version_no_update() -> None:
    release = _release("v1.0.0")
    fetch_json, fetch_text = _fake_fetch(release, "a" * 64 + "  x.zip\n")
    result = check_for_update("1.0.0", fetch_json, fetch_text)
    assert result["update_available"] is False
    assert result["error"] == ""


def test_check_network_error_chinese_200() -> None:
    fetch_json, fetch_text = _fake_fetch(None)
    result = check_for_update("1.0.0", fetch_json, fetch_text)
    assert result["error"] == ERROR_NETWORK
    assert "网络原因" in result["message"]
    assert result["update_available"] is False
    assert result["zip_url"] == ""


def test_check_no_asset_reports_no_asset() -> None:
    release = _release("v1.1.0", with_assets=False)
    fetch_json, fetch_text = _fake_fetch(release)
    result = check_for_update("1.0.0", fetch_json, fetch_text)
    assert result["error"] == ERROR_NO_ASSET
    assert "没有发布更新包" in result["message"]
    assert result["update_available"] is False


def test_check_sha_download_failure_degrades() -> None:
    release = _release("v1.1.0")
    fetch_json, fetch_text = _fake_fetch(release, None)  # sha 下载失败
    result = check_for_update("1.0.0", fetch_json, fetch_text)
    assert result["sha256"] == ""
    assert MSG_NO_SHA in result["message"]
    assert result["update_available"] is True  # 校验值缺失不阻断“有新版”判断


def test_check_bad_versions_compare_as_string() -> None:
    release = _release("1.1")
    fetch_json, fetch_text = _fake_fetch(release, "a" * 64 + "  x.zip\n")
    result = check_for_update("1.0", fetch_json, fetch_text)
    assert MSG_BAD_VERSION in result["message"]
    assert result["latest_version"] == "1.1"


# ---------------------------------------------------------------------------
# webapp 端点（monkeypatch 默认 HTTP 实现）
# ---------------------------------------------------------------------------


def test_check_endpoint_returns_contract(tmp_path, monkeypatch) -> None:
    release = _release("v1.1.0")
    sha = "b" * 64
    monkeypatch.setattr(
        update_mod, "http_json", lambda url, timeout=15.0: release
    )
    monkeypatch.setattr(
        update_mod,
        "http_text",
        lambda url, timeout=15.0: sha + "  firstep-update-v1.1.0.zip\n",
    )
    ctx = AppContext(config_path=tmp_path / "config.json")
    client = TestClient(create_app(ctx))
    resp = client.get("/api/update/check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version"] == "1.0.0"
    assert body["latest_version"] == "1.1.0"
    assert body["update_available"] is True
    assert body["sha256"] == sha
    assert body["error"] == ""


def test_check_endpoint_network_error_is_200(tmp_path, monkeypatch) -> None:
    def boom(url, timeout=15.0):
        raise OSError("no network")

    monkeypatch.setattr(update_mod, "http_json", boom)
    ctx = AppContext(config_path=tmp_path / "config.json")
    client = TestClient(create_app(ctx))
    resp = client.get("/api/update/check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] == ERROR_NETWORK
    assert "网络原因" in body["message"]
