"""完整包检查更新（工单 full-download/02）。

契约（spec `.scratch/full-download/spec.md`）：
- `GET /api/update/full/check` 返回
  `{current_version, latest_version, update_available, total_bytes,
    parts: [{name, size, sha256, url}], reason, error, message}`；
- 线上取源 = GitHub releases 列表里按**软件 tag**（不以 `materials-` 打头）
  取版本最大者，再取该 Release 上的完整包清单资产
  `firstep-full-<tag>.manifest.json`；
- 本地已装版本 = 用户数据目录 `updates/full-installed.json`（缺失 / 损坏 =
  未知 → `reason=no-installed`，提示可下载完整包，不是报错）；
- 网络不可达 / 无软件 Release / 该 Release 无完整包资产 / 清单解析失败 /
  分卷表为空 / 清单列的分卷在 Release 上找不到 → 一律 200 级 + `error` 类型
  + 中文 `message`（不 500、不抛异常）；
- 「已是最新」也保留分卷表：用户可能主动重下（修损坏 / 换机器）。

HTTP 面与资产定位复用发布通道公共件（工单 release-channel-dedupe/01）：列表端点 / 取资产
地址 / 找最新 release / 版本比较降级都住 `update.py`，本模块只留"完整包"特有的东西——
清单资产名、分卷表解析、载荷形状与中文文案。测试注入假函数，不碰网络。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .update import (
    ERROR_BAD_MANIFEST,
    ERROR_NETWORK,
    ERROR_NO_ASSET,
    ERROR_NO_RELEASE,
    MATERIALS_TAG_PREFIX,
    RELEASES_URL,
    asset_url,
    compare_versions_or_text,
    http_json,
    http_text,
    latest_release,
)

FULL_MANIFEST_SUFFIX = ".manifest.json"
FULL_ASSET_PREFIX = "firstep-full-"

# 已装完整包标记（用户数据目录 updates/ 下，与 full-task.json 同级）
INSTALLED_MARKER_FILENAME = "full-installed.json"

REASON_OUTDATED = "outdated"
REASON_UP_TO_DATE = "up-to-date"
REASON_NO_INSTALLED = "no-installed"

MSG_NETWORK = "检查完整包更新失败（网络原因），请检查网络后重试"
MSG_NO_RELEASE = "还没有发布过完整包，请稍后再试"
MSG_NO_ASSET = "该版本的 Release 上没有完整包资产，请联系发布者"
MSG_BAD_MANIFEST = "完整包清单解析失败，请联系发布者"


# ---------------------------------------------------------------------------
# 缺省 HTTP 面（委托壳）
# ---------------------------------------------------------------------------
# 实现（urllib / 请求头 / 超时 / UA）只在 update.py；这里留两个一行的壳，是**给端点与测试
# 的注入缝**：`check_for_full_update(fetch_json=None)` 走它们，端点的缺省路径与既有端点
# 用例靠 patch 这两个名字替换网络（工单 release-channel-dedupe/01 保缝不改判据）。


def _fetch_releases() -> list[dict[str, Any]]:
    return http_json(RELEASES_URL)


def _fetch_text(url: str) -> str:
    return http_text(url)


# ---------------------------------------------------------------------------
# 资产名与已装标记
# ---------------------------------------------------------------------------


def full_manifest_asset_name(version: str) -> str:
    """完整包清单资产名（与发布侧 `full_pack.full_manifest_filename` 同源）。"""
    return f"{FULL_ASSET_PREFIX}{version}{FULL_MANIFEST_SUFFIX}"


def load_installed_marker(updates_dir: Path) -> str | None:
    """读已装完整包版本；缺失 / 损坏 / 空值 = None（未知，不抛）。"""
    marker = Path(updates_dir) / INSTALLED_MARKER_FILENAME
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    version = str(data.get("version") or "").strip()
    return version or None


# ---------------------------------------------------------------------------
# 线上 release / 资产定位
# ---------------------------------------------------------------------------


def _is_full_release(release: dict[str, Any]) -> bool:
    """软件 Release（非 `materials-` 前缀、非空 tag）。"""
    tag = str(release.get("tag_name") or "").strip()
    return bool(tag) and not tag.startswith(MATERIALS_TAG_PREFIX)


def find_latest_full_release(releases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """releases 列表里版本最大的软件 Release（不依赖 API 顺序）。

    算法与降级兜底都在 `update.latest_release`（发布通道共用件）；本模块只提供谓词。
    """
    return latest_release(releases, _is_full_release)


def _manifest_asset_url(release: dict[str, Any]) -> str:
    tag = str(release.get("tag_name") or "")
    return asset_url(release, full_manifest_asset_name(tag))


def resolve_part_url(release: dict[str, Any], zip_name: str) -> str:
    """分卷名 → 下载地址（Release 资产缺该名 → 空串，调用方按不可下处理）。"""
    return asset_url(release, zip_name)


# ---------------------------------------------------------------------------
# 响应构建
# ---------------------------------------------------------------------------


def _response(
    *,
    current_version: str,
    latest_version: str = "",
    total_bytes: int = 0,
    parts: list[dict[str, Any]] | None = None,
    update_available: bool = False,
    reason: str = "",
    error: str = "",
    message: str = "",
    manifest_url: str = "",
) -> dict[str, Any]:
    return {
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": update_available,
        "total_bytes": total_bytes,
        "parts": parts or [],
        "reason": reason,
        "error": error,
        "message": message,
        # 清单地址给应用编排用（更新器自己读它拿删除清单与资料库基线；
        # 清单含全量文件清单，几 MB 级，不在前端与后端之间搬运）
        "manifest_url": manifest_url,
    }


def _parse_parts(
    manifest: dict[str, Any], release: dict[str, Any]
) -> list[dict[str, Any]]:
    """清单分卷表 → 带下载地址的分卷表；任一缺失资产 = 空表（整体判不可下）。"""
    parts: list[dict[str, Any]] = []
    for item in manifest.get("parts") or []:
        if not isinstance(item, dict):
            return []
        name = str(item.get("zip_name") or "")
        url = resolve_part_url(release, name)
        if not name or not url:
            return []
        parts.append(
            {
                "name": name,
                "size": int(item.get("size") or 0),
                "sha256": str(item.get("sha256") or ""),
                "url": url,
            }
        )
    return parts


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------


def check_for_full_update(
    installed: str | None,
    fetch_json: Callable[[str], Any] | None = None,
    fetch_text: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """检查完整包更新（端点薄调它；fetch 可注入，测试不碰网络）。

    `installed` = 本地已装完整包版本（None = 未知）。任何失败都返回 200 级
    契约 + 中文 message，绝不抛。
    """
    current = installed or ""
    # 缺省 HTTP 面 = 委托壳 → update.py 的公共实现（同一 GitHub 仓库、同一超时策略）。
    # 走壳而非直接调 http_json：端点的缺省路径与既有端点用例靠 patch `_fetch_*` 替换网络。
    if fetch_json is None:
        fetch_json = lambda url: _fetch_releases()  # noqa: E731
    if fetch_text is None:
        fetch_text = _fetch_text

    try:
        releases = fetch_json(RELEASES_URL)
    except Exception:
        return _response(
            current_version=current, error=ERROR_NETWORK, message=MSG_NETWORK
        )
    if not isinstance(releases, list):
        return _response(current_version=current, error=ERROR_NETWORK, message=MSG_NETWORK)

    release = find_latest_full_release(releases)
    if release is None:
        return _response(
            current_version=current, error=ERROR_NO_RELEASE, message=MSG_NO_RELEASE
        )

    tag = str(release.get("tag_name") or "")
    manifest_url = _manifest_asset_url(release)
    if not manifest_url:
        return _response(
            current_version=current,
            latest_version=tag,
            error=ERROR_NO_ASSET,
            message=MSG_NO_ASSET,
        )

    try:
        manifest = json.loads(fetch_text(manifest_url))  # type: ignore[operator]
    except Exception:
        return _response(
            current_version=current,
            latest_version=tag,
            error=ERROR_BAD_MANIFEST,
            message=MSG_BAD_MANIFEST,
        )
    if not isinstance(manifest, dict):
        return _response(
            current_version=current,
            latest_version=tag,
            error=ERROR_BAD_MANIFEST,
            message=MSG_BAD_MANIFEST,
        )

    parts = _parse_parts(manifest, release)
    if not parts:
        return _response(
            current_version=current,
            latest_version=tag,
            error=ERROR_NO_ASSET,
            message=MSG_NO_ASSET,
        )

    total_bytes = int(manifest.get("total_bytes") or 0)
    if total_bytes <= 0:
        total_bytes = sum(int(p["size"]) for p in parts)

    if not current:
        reason = REASON_NO_INSTALLED
        update_available = True
        message = (
            f"本地完整包版本未知（未安装或标记缺失）；最新完整包 {tag}，"
            f"约 {total_bytes / 1024 / 1024:.0f} MB，可一键下载"
        )
    else:
        cmp_val, _fell_back = compare_versions_or_text(current, tag)
        if cmp_val > 0:
            reason = REASON_OUTDATED
            update_available = True
            message = (
                f"发现完整包新版本：{current} → {tag}，"
                f"约 {total_bytes / 1024 / 1024:.0f} MB"
            )
        else:
            reason = REASON_UP_TO_DATE
            update_available = False
            message = (
                f"已是最新完整包（{current}）；如需修复损坏或换机器，"
                f"仍可重新下载完整包（约 {total_bytes / 1024 / 1024:.0f} MB）"
            )

    return _response(
        current_version=current,
        latest_version=tag,
        total_bytes=total_bytes,
        parts=parts,
        update_available=update_available,
        reason=reason,
        message=message,
        manifest_url=manifest_url,
    )
