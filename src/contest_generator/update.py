"""应用内一键更新：检查更新纯逻辑与 GitHub Release 解析（工单 auto-update/03）。

契约（spec `.scratch/auto-update/spec.md`）：
- check 端点返回
  `{current_version, latest_version, update_available, zip_url, size_bytes,
    sha256, release_notes, published_at, error, message}`；
- GitHub 不可达 / 非 2xx / 无更新包资产 → 一律 200 级 + `error` 类型 + 中文
  `message`（不 500、不裸异常）；`error` 取值：network / no-asset / 空串（成功）。
- 版本比对纯函数 `compare_versions`：容忍 `v` 前缀；任一侧非合法 semver →
  返回 None（调用方降级为字符串比较并附中文提示）。

HTTP 面（`http_json` / `http_text`）用 urllib（标准库），测试注入假函数。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable

GITHUB_API_BASE = "https://api.github.com"
REPO = "AK47n/firstep"
LATEST_RELEASE_URL = f"{GITHUB_API_BASE}/repos/{REPO}/releases/latest"

UPDATE_ZIP_PREFIX = "firstep-update-"
UPDATE_SHA_SUFFIX = ".sha256.txt"

ERROR_NETWORK = "network"
ERROR_NO_ASSET = "no-asset"

# 中文提示（前端直接展示；语义由 error 类型登记，前端可据此附加文案）
MSG_NETWORK = "检查更新失败（网络原因），请检查网络后重试"
MSG_NO_ASSET = "最新版本没有发布更新包，请等待更新包发布"
MSG_BAD_VERSION = "版本号格式异常，已按字符串比较，结果仅供参考"
MSG_NO_SHA = "无法获取更新包校验值，可尝试直接去 GitHub Releases 下载"

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def normalize_version(version: str) -> str:
    """去空白与 `v` 前缀（`v1.1.0` → `1.1.0`）。"""
    return version.strip().lower().lstrip("v").strip()


def parse_semver(version: str) -> tuple[int, int, int] | None:
    """`1.2.3` → (1,2,3)；非法返回 None（容忍 `v` 前缀与空白）。"""
    match = _SEMVER_RE.match(normalize_version(version))
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def compare_versions(current: str, latest: str) -> int | None:
    """语义化比较：latest 大于 current 返回 1、相等 0、小于 -1。

    任一侧非合法 semver 返回 None——调用方降级为字符串比较（见
    `check_for_update` 的 message 提示）。纯函数，可单测。
    """
    a = parse_semver(current)
    b = parse_semver(latest)
    if a is None or b is None:
        return None
    return (b > a) - (b < a)  # type: ignore[operator]


def is_stale_service(served: str, on_disk: str) -> bool | None:
    """端口上跑着的那个服务是不是「旧进程」：**服务版本 < 盘上版本**。

    为什么需要这条判据（工单 `update-restart-stale-service/01`）：更新做的事是「换盘上的文件」，
    **跑着的进程不会跟着变**。旧进程还占着端口时，启动器探测到的 `/api/health` 一切正常
    （`app` 也对得上），于是判定「本应用已在运行」→ 只开一个浏览器标签就退出，
    用户就永远停在旧版本、且界面说更新成功了。

    三态（不是二态——「判不了」必须与「不是旧进程」分开，调用方要打印不同的结论）：

    - `True` = 是旧进程（服务的版本**小于**盘上版本）→ 该踢掉重起；
    - `False` = 不是旧进程：版本相等（正常复用）或服务比盘上**新**（同一个端口上跑着另一个
      安装的新版）→ 不动它，重启反而会把用户踢回旧代码；
    - `None` = **判不了**（版本读不到 / 任一侧不是合法 semver）→ 宁可少踢一次，
      也不拿解析不了的东西去 kill 用户的服务。
    """
    comparison = compare_versions(served, on_disk)
    if comparison is None:
        return None
    return comparison == 1


def resolve_assets(
    release: dict[str, Any],
) -> tuple[str | None, int, str | None, str | None]:
    """从 GitHub Release JSON 中识别更新包四件套里的 zip / sha256 / removed。

    返回 `(zip_url, size_bytes, sha_url, removed_url)`；zip 按
    `firstep-update-<tag>.zip` 精确匹配 release tag（避免同 release 挂了多个
    更新包时选错），sha 匹配同名 `.sha256.txt`，removed 匹配
    `<zip 名去 .zip>.removed.txt`；找不到对应项为 None。
    """
    tag = str(release.get("tag_name") or "")
    zip_name = f"{UPDATE_ZIP_PREFIX}{tag}.zip"
    sha_name = f"{UPDATE_ZIP_PREFIX}{tag}{UPDATE_SHA_SUFFIX}"
    removed_name = f"{UPDATE_ZIP_PREFIX}{tag}.removed.txt"
    zip_url = None
    sha_url = None
    removed_url = None
    size = 0
    for asset in release.get("assets") or []:
        name = str(asset.get("name") or "")
        if name == zip_name:
            zip_url = asset.get("browser_download_url")
            size = int(asset.get("size") or 0)
        elif name == sha_name:
            sha_url = asset.get("browser_download_url")
        elif name == removed_name:
            removed_url = asset.get("browser_download_url")
    return (zip_url, size, sha_url, removed_url)


def parse_sha256_text(text: str) -> str:
    """从 `sha256.txt` 内容（`<hex>  firstep-update-...zip`）提取小写 hex。"""
    match = re.search(r"[0-9a-fA-F]{64}", text or "")
    return match.group(0).lower() if match else ""


def http_json(url: str, timeout: float = 15.0) -> Any:
    """GET 一个 URL 并解析 JSON（GitHub API 用；标准库，无第三方依赖）。"""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "firstep-update-check",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_text(url: str, timeout: float = 15.0) -> str:
    """GET 一个 URL 返回文本（配套 .sha256.txt 用）。"""
    request = urllib.request.Request(url, headers={"User-Agent": "firstep-update-check"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def check_for_update(
    current_version: str,
    fetch_json: Callable[[str], Any] | None = None,
    fetch_text: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """检查更新主逻辑（端点薄调它；fetch 函数可注入，测试不碰网络）。

    fetch 参数传 None 时用模块级默认实现（`update.http_json` / `http_text`，
    运行时可被 monkeypatch——默认参数不能直接绑定函数对象，否则 patch 失效）。

    成功（有可比的版本）→ `update_available` 按比对结果；任一步失败 →
    200 级契约 + error 类型 + 中文 message，绝不抛（端点侧 _map_errors
    兜底也不该被触发——这里自己登记错误类型）。
    """
    if fetch_json is None:
        fetch_json = http_json
    if fetch_text is None:
        fetch_text = http_text
    try:
        release = fetch_json(LATEST_RELEASE_URL)
    except Exception:
        return {
            "current_version": current_version,
            "latest_version": "",
            "update_available": False,
            "zip_url": "",
            "size_bytes": 0,
            "sha256": "",
            "removed_url": "",
            "release_notes": "",
            "published_at": "",
            "error": ERROR_NETWORK,
            "message": MSG_NETWORK,
        }

    tag = str(release.get("tag_name") or "")
    latest_version = normalize_version(tag)
    zip_url, size_bytes, sha_url, removed_url = resolve_assets(release)

    # 无更新包资产：更新机制还没在该 release 落地，报「无资产」中文提示
    if not zip_url:
        return {
            "current_version": current_version,
            "latest_version": latest_version or tag,
            "update_available": False,
            "zip_url": "",
            "size_bytes": 0,
            "sha256": "",
            "removed_url": "",
            "release_notes": release.get("body") or "",
            "published_at": release.get("published_at") or "",
            "error": ERROR_NO_ASSET,
            "message": MSG_NO_ASSET,
        }

    # sha256 尽力获取：失败不阻断（返回空 + 中文提示，apply 侧须防护）
    sha256 = ""
    sha_message = ""
    if sha_url:
        try:
            sha256 = parse_sha256_text(fetch_text(sha_url))
        except Exception:
            sha256 = ""
    if not sha256:
        sha_message = MSG_NO_SHA

    cmp = compare_versions(current_version, latest_version)
    if cmp is None:
        # 降级：字符串比较 + 明示结果仅供参考
        cmp = (latest_version > current_version) - (latest_version < current_version)
        message = MSG_BAD_VERSION + ("，" + sha_message if sha_message else "")
    else:
        message = sha_message

    return {
        "current_version": current_version,
        "latest_version": latest_version or tag,
        "update_available": cmp > 0,
        "zip_url": zip_url,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "removed_url": removed_url or "",
        "release_notes": release.get("body") or "",
        "published_at": release.get("published_at") or "",
        "error": "",
        "message": message,
    }
