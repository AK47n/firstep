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

**本模块同时是「发布通道」公共件的单源**（工单 release-channel-dedupe/01）：完整包
（`full_update.py`）与资料库（`materials_update.py`）两条通道的**载荷形状与中文文案各写各的**，
但机制共用这里的四件——`RELEASES_URL`（列表端点）、`asset_url`（按资产名取下载地址）、
`latest_release`（找版本最大的 release）、`compare_versions_or_text`（比较 + 降级兜底）——
以及四个 `error` 码常量（前端 `fx/update.js` / `fx/materials-update.js` 按这些字符串分支，
故它们是**线上契约**，由 `tests/test_release_channel_home.py` 对账）。
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
# releases 列表端点（三条发布通道共用；per_page=30 足够覆盖同仓的软件与资料库两类 tag）
RELEASES_URL = f"{GITHUB_API_BASE}/repos/{REPO}/releases?per_page=30"

UPDATE_ZIP_PREFIX = "firstep-update-"
UPDATE_SHA_SUFFIX = ".sha256.txt"

# 资料库通道的 tag 前缀（区分"软件 Release"与"资料库 Release"的那一个字面量）。
# 住这里而不是各自模块：完整包要按它排除、资料库要按它筛选、比较版本前还要剥它
# （工单 release-channel-dedupe/01 评审整改：此前 full_update 与 materials_update 各定义一份）。
MATERIALS_TAG_PREFIX = "materials-"

# 发布通道的 error 码（**线上契约**：前端按这些字符串分支，改字面量等于改 UI 行为）
ERROR_NETWORK = "network"
ERROR_NO_ASSET = "no-asset"
ERROR_NO_RELEASE = "no-release"
ERROR_BAD_MANIFEST = "bad-manifest"

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


def compare_versions_or_text(current: str, latest: str) -> tuple[int, bool]:
    """比较两个版本号；任一侧非法 semver 时**降级为字符串比较**。

    返回 `(结果, 是否降级)`：`结果` 语义同 `compare_versions`（latest 大 = 1 / 等 = 0 / 小 = -1），
    降级与否供调用方决定要不要附「版本号格式异常…」提示（三条通道都要这条兜底，
    而各家的提示文案不同，故降级标志从这里出去、文案留在各功能模块）。

    降级时**按传入的原样字符串比**（不 normalize）：三条通道历史上就是各自按自己传进来的形态
    比的（`update.py` 传已归一化的 latest、`full_update.py` 传原始 tag、`materials_update.py`
    传剥过 `materials-` 前缀的版本串）。若在这里统一 normalize，非法版本号下的**判定方向会翻**——
    实证 `("1.0-Release", "1.0-beta")`：原样比较是 1（有更新），归一化后是 -1（无更新）。

    这是「`(b > a) - (b < a)` 兜底」的唯一出处（工单 release-channel-dedupe/01）：
    此前同一 idiom 在 5 处重复，改一处忘一处就是三条通道判定不一致。
    """
    comparison = compare_versions(current, latest)
    if comparison is not None:
        return comparison, False
    return (latest > current) - (latest < current), True


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


def asset_url(release: dict[str, Any], asset_name: str) -> str:
    """release 里名为 `asset_name` 的资产下载地址；缺该名 → 空串（调用方据此判不可下）。

    发布通道共用件（此前 `full_update` 与 `materials_update` 各有一份逐字相同的实现）。
    """
    for asset in release.get("assets") or []:
        if str(asset.get("name") or "") == asset_name:
            return str(asset.get("browser_download_url") or "")
    return ""


def latest_release(
    releases: list[dict[str, Any]],
    matches: Callable[[dict[str, Any]], bool],
    version_of: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any] | None:
    """`releases` 里**满足 `matches`** 且版本号最大的那个；一个都没有 → None。

    不依赖 API 返回顺序（GitHub 按创建时间排序，tag 乱序发版时首个匹配未必最新）：
    过滤 → 逐个用 `compare_versions_or_text` 比大小（版本号非法时降级字符串比较），
    `matches` 一个都不满足 → None。

    `version_of` 给出"从 release 取用于比较的版本串"，缺省取 `tag_name`。**必须可注入**：
    资料库通道的 tag 形如 `materials-v1.1.0`，比较前要先剥前缀——不剥就退回字符串比较，
    于是 `v1.10.0` 会被判成小于 `v1.9.0`（发布通道共用件，工单 release-channel-dedupe/01；
    三条通道的差别只有谓词与取版本串的方式）。
    """
    if version_of is None:
        version_of = lambda release: str(release.get("tag_name") or "")  # noqa: E731
    candidates = [release for release in releases if matches(release)]
    if not candidates:
        return None
    latest = candidates[0]
    for release in candidates[1:]:
        comparison, _fell_back = compare_versions_or_text(version_of(latest), version_of(release))
        if comparison > 0:
            latest = release
    return latest


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

    cmp, fell_back = compare_versions_or_text(current_version, latest_version)
    if fell_back:
        # 降级：字符串比较 + 明示结果仅供参考
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
