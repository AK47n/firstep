"""资料库检查更新：本地基线 + 线上清单对比（工单 materials-update/03）。

契约（spec `.scratch/materials-update/spec.md`）：
- `GET /api/update/materials/check` 返回
  `{current_version, latest_version, update_available, total_size_bytes,
    batches: [{slug, name, add_count, modify_count, del_count, size_bytes,
               parts: [{zip_url, size_bytes, sha256}]}],
    deleted_batches: [{slug, name, file_count}], error, message}`；
- GitHub 不可达 / 无 `materials-` 前缀 release / 清单解析失败 / 本地缺失
  基线 → 一律 200 级 + `error` 类型 + 中文 `message`（不 500、不裸异常）；
  error 取值：network / no-release / bad-manifest / baseline-missing / 空串。
- 版本基准：线上清单顶层 version 为资料库版本（如 `v1.1.0`）；比较容忍
  `v` 前缀，任一侧非法 → 字符串比较 + 中文提示。

HTTP 面与资产定位复用发布通道公共件（工单 release-channel-dedupe/01）：列表端点 / 取资产
地址 / 找最新 release / 版本比较降级都住 `update.py`，本模块只留"资料库"特有的东西——
`materials-` 前缀语义、批次差异载荷、基线缺失（`baseline-missing`）与中文文案。
测试注入假函数，不碰网络。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .materials_pack import MANIFEST_FILENAME
from .tool_root import find_tool_root
from .update import (
    ERROR_BAD_MANIFEST,
    ERROR_NETWORK,
    ERROR_NO_RELEASE,
    MATERIALS_TAG_PREFIX,
    RELEASES_URL,
    asset_url,
    compare_versions_or_text,
    http_json,
    http_text,
    latest_release,
)

MANIFEST_ASSET_SUFFIX = ".manifest.json"

# 资料库通道专有：本地缺基线（其余错误码与三条通道共用，住 update.py）
ERROR_BASELINE_MISSING = "baseline-missing"

MSG_NETWORK = "检查资料库更新失败（网络原因），请检查网络后重试"
MSG_NO_RELEASE = "还没有发布资料库更新包，请稍后再试"
MSG_BAD_MANIFEST = "资料库清单解析失败，请联系发布者"
MSG_BASELINE_MISSING = (
    "本地资料库版本未知（缺少基线清单），无法增量更新；请下载完整包，"
    "或联系发布者提供初始基线"
)
MSG_BAD_VERSION = "资料库版本号格式异常，已按字符串比较，结果仅供参考"


# ---------------------------------------------------------------------------
# 缺省 HTTP 面（委托壳）
# ---------------------------------------------------------------------------
# 实现（urllib / 请求头 / 超时 / UA）只在 update.py；这里留两个一行的壳，是**给端点与测试
# 的注入缝**：`check_for_materials_update(fetch_json=None)` 走它们，端点的缺省路径与既有
# 端点用例靠 patch 这两个名字替换网络（工单 release-channel-dedupe/01 保缝不改判据）。


def _fetch_releases() -> list[dict[str, Any]]:
    return http_json(RELEASES_URL)


def _fetch_text(url: str) -> str:
    return http_text(url)


def materials_library_dir() -> Path:
    """资料库根目录（工具根下 sources/materials；随工具走）。

    工具根判定单源 = `tool_root.find_tool_root`（工单 full-download/09）：此前
    按「本文件上级的上级」推，源码直跑时算成 `<根>/src/sources/materials`，
    于是**本地已有基线也会被判 `baseline-missing`**（真机演练实测）。不依赖
    webapp（同一个单源模块，避免循环导入）。
    """
    return find_tool_root(__file__) / "sources" / "materials"


# ---------------------------------------------------------------------------
# 纯逻辑
# ---------------------------------------------------------------------------


def load_local_manifest(materials_dir: Path) -> dict[str, Any] | None:
    """读取本地基线清单；缺失 / 损坏 = None（调用方按 baseline-missing 处理）。

    损坏不抛——本地清单是展示与 diff 基线，损坏时前端给指引而非崩溃。
    """
    manifest_path = materials_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    if not isinstance(data, dict) or "batches" not in data:
        return None
    return data


def find_latest_materials_release(
    releases: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """从 GitHub releases 列表找版本号最大的 `materials-` 前缀 release。

    算法与降级兜底都在 `update.latest_release`（发布通道共用件）；本模块只提供
    谓词（前缀）与**取版本串的方式**——资料库 tag 要先剥 `materials-` 前缀再比，
    否则 `materials-v1.10.0` 会被字符串比较判成小于 `materials-v1.9.0`。
    """
    return latest_release(
        releases,
        lambda r: str(r.get("tag_name") or "").startswith(MATERIALS_TAG_PREFIX),
        version_of=lambda r: _version_from_tag(str(r.get("tag_name") or "")),
    )


def _manifest_asset_url(release: dict[str, Any]) -> str:
    tag = str(release.get("tag_name") or "")
    version = tag[len(MATERIALS_TAG_PREFIX):]
    return asset_url(release, f"firstep-materials-{version}{MANIFEST_ASSET_SUFFIX}")


def _version_from_tag(tag: str) -> str:
    return tag[len(MATERIALS_TAG_PREFIX):] if tag.startswith(MATERIALS_TAG_PREFIX) else tag


def _batch_by_slug(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b.get("slug", ""): b for b in manifest.get("batches", [])}


def check_for_materials_update(
    local: dict[str, Any] | None,
    fetch_json: Callable[[str], Any] | None = None,
    fetch_text: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """检查资料库更新主逻辑（端点薄调它；fetch 可注入，测试不碰网络）。

    `local` 为本地清单（None = 基线缺失）；fetch 传 None 用模块级默认。
    任一步失败 → 200 级契约 + error 类型 + 中文 message，绝不抛。
    """
    if local is None:
        return {
            "current_version": "",
            "latest_version": "",
            "update_available": False,
            "total_size_bytes": 0,
            "batches": [],
            "deleted_batches": [],
            "error": ERROR_BASELINE_MISSING,
            "message": MSG_BASELINE_MISSING,
        }

    if fetch_json is None:
        fetch_json = lambda url: _fetch_releases()  # noqa: E731
    if fetch_text is None:
        fetch_text = _fetch_text

    try:
        releases = fetch_json(RELEASES_URL)  # type: ignore[operator]
    except Exception:
        return _response(local, error=ERROR_NETWORK, message=MSG_NETWORK)

    release = find_latest_materials_release(releases)
    if release is None:
        return _response(local, error=ERROR_NO_RELEASE, message=MSG_NO_RELEASE)

    manifest_url = _manifest_asset_url(release)
    if not manifest_url:
        return _response(local, error=ERROR_NO_RELEASE, message=MSG_NO_RELEASE)

    try:
        online = json.loads(fetch_text(manifest_url))  # type: ignore[operator]
    except Exception:
        return _response(local, error=ERROR_BAD_MANIFEST, message=MSG_BAD_MANIFEST)
    if not isinstance(online, dict) or "batches" not in online:
        return _response(local, error=ERROR_BAD_MANIFEST, message=MSG_BAD_MANIFEST)

    latest_version = _version_from_tag(str(release.get("tag_name") or ""))
    current_version = str(local.get("version") or "")
    cmp, fell_back = compare_versions_or_text(current_version, latest_version)
    message = MSG_BAD_VERSION if fell_back else ""

    local_batches = _batch_by_slug(local)
    online_batches = _batch_by_slug(online)

    # 线上有增量 parts 的批次 = 用户需更新的批次；差异计数 = 全量文件集对比
    update_batches: list[dict[str, Any]] = []
    total_size = 0
    for slug, online_batch in online_batches.items():
        parts = online_batch.get("parts") or []
        if not parts:
            continue
        local_files = {
            f.get("path", ""): f for f in (local_batches.get(slug, {}).get("files") or [])
        }
        online_files = {
            f.get("path", ""): f for f in (online_batch.get("files") or [])
        }
        add_count = sum(1 for p in online_files if p not in local_files)
        modify_count = sum(
            1 for p in online_files
            if p in local_files and online_files[p].get("sha256") != local_files[p].get("sha256")
        )
        del_count = sum(1 for p in local_files if p not in online_files)
        size_bytes = sum(int(p.get("size") or 0) for p in parts)
        total_size += size_bytes
        parts_out = []
        for part in parts:
            zip_name = str(part.get("zip_name") or "")
            parts_out.append({
                "zip_url": asset_url(release, zip_name),
                "size_bytes": int(part.get("size") or 0),
                "sha256": str(part.get("sha256") or ""),
            })
        update_batches.append({
            "slug": slug,
            "name": str(online_batch.get("name") or slug),
            "add_count": add_count,
            "modify_count": modify_count,
            "del_count": del_count,
            "size_bytes": size_bytes,
            "parts": parts_out,
            # 应用期重建新基线清单所需（工单 05；仅 apply 消费，前端忽略）：
            # 线上全量文件集 + 本批次 removed + 卷名（zip_name 从线上清单 parts）
            "files": [f for f in online_files.values()],
            "removed": list(online_batch.get("removed") or []),
            "zip_names": [str(p.get("zip_name") or "") for p in parts],
        })

    # 本地有、线上无的整批删除（旧批次被整体移除）
    deleted_batches = [
        {
            "slug": slug,
            "name": str(batch.get("name") or slug),
            "file_count": len(batch.get("files") or []),
        }
        for slug, batch in local_batches.items()
        if slug not in online_batches
    ]

    return _response(
        local,
        latest_version=latest_version,
        update_available=bool(update_batches) or bool(deleted_batches),
        total_size_bytes=total_size,
        batches=update_batches,
        deleted_batches=deleted_batches,
        message=message,
    )


def _response(
    local: dict[str, Any],
    latest_version: str = "",
    update_available: bool = False,
    total_size_bytes: int = 0,
    batches: list[dict[str, Any]] | None = None,
    deleted_batches: list[dict[str, Any]] | None = None,
    error: str = "",
    message: str = "",
) -> dict[str, Any]:
    return {
        "current_version": str(local.get("version") or ""),
        "latest_version": latest_version,
        "update_available": update_available,
        "total_size_bytes": total_size_bytes,
        "batches": batches or [],
        "deleted_batches": deleted_batches or [],
        "error": error,
        "message": message,
    }
