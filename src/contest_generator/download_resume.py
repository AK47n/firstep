"""可续下载：卷内断点续传 + 截断判定 + 无上限退避重试（工单 resumable-download/02）。

为什么单独立一个模块：完整包（`full_task`）与资料库（`materials_task`）两条链路都要用它，
塞进任一侧都会让两个同层任务模块互相 import。判据与工单：`.scratch/resumable-download/spec.md`。

契约（用户视角，写在这里免得被实现细节淹没）：

- **断了能接上**：非首次尝试从已落盘字节发 `Range` 续下（小卷 ≤ `min_resume_bytes` 除外）；
- **截断算失败**：对端声明了长度却没给够 → `DownloadTruncatedError` 且**保留半成品**走重试。
  这是工单 01 实测到的既有缺陷：旧实现以「读到空为止」收工，把 40% 的截断读成「正常读完」
  并返回自称成功的 SHA256，用户侧看到的是「100% → 校验失败 → 从头再来」；
- **瞬时失败自动重试**：次数无上限，退避 2→4→8→16→32→60 秒封顶；每次重试经 `before_retry`
  如实上报；`cancel` 置位后**不再发起下一次尝试**，退避等待期间也能立刻中断；
- **不可重试的只有三种**：清单与服务器总长互相矛盾（发布物不一致）、本地文件比远端大（本地坏）、
  服务器明确说没有/不给（HTTP 4xx）。这三种直报中文错误，不进重试循环——否则就是死循环。

`resumable_download` 的前三个参数与 `materials_task.download_part` **位置与语义完全一致**，
新参数一律关键字可选：既有注入点（`(url, dest, on_progress)` 三参假下载器）零改动。

异常谱系（任务层据此分类，不用解析文案）：

    层级        下载错误
    ├─ DownloadTruncatedError    传输被截断 / 本地长度不足 —— 可重试，半成品保留
    ├─ DownloadSizeMismatchError 发布物与清单不一致 —— 不可重试
    ├─ DownloadLocalCorruptError 本地文件比远端还大 —— 不可重试（删掉重来即可，但重试同一份没意义）
    └─ DownloadCancelledError    用户取消 —— 不算失败，任务转 cancelled
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.client import IncompleteRead
from pathlib import Path
from typing import Any, Callable

# 单次尝试的 socket 超时：300 秒是「等多久才叫卡死」，对宿舍网/热点太长——
# 断了要尽快让位给重试。30 秒足够，代价只是慢启动的大文件会多试一次。
SOCKET_TIMEOUT_SECONDS = 30.0
# 每次读取的块大小（与 download_part 一致，别改出两套口径）
CHUNK_BYTES = 256 * 1024
# 小于这个的卷直接整卷重下：发 Range 的边界与收益都不划算。
# 定 64 KB 而不是 1 MB：门槛就是「一次断流最多白下多少」——1 MB 意味着断在 1 MB 以内
# 都要重来一遍，而这个量级在弱网下并不罕见（探针实测：断在 800 KB 时整卷重下）。
MIN_RESUME_BYTES = 64 * 1024
# 退避上限（秒）
MAX_RETRY_DELAY_SECONDS = 60.0
# 用户代理（与既有实现同一个，服务端侧看到的是同一个客户端）
USER_AGENT = "firstep-materials"
# 边车后缀：只在取消 / 失败时写，用来让「换一次进程」也知道本地这半份是谁的
PARTIAL_SUFFIX = ".partial.json"

_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", re.IGNORECASE)


class DownloadError(OSError):
    """下载相关错误基类（继承 OSError：与既有 urllib/OSError 抛出点同族）。"""


class DownloadTruncatedError(DownloadError):
    """传输被截断或本地长度不足（**可重试**，半成品保留）。"""


class DownloadSizeMismatchError(DownloadError):
    """清单与服务器的总长互相矛盾（**不可重试**：重试必然同样结果）。"""


class DownloadLocalCorruptError(DownloadError):
    """本地落盘文件比远端还大（**不可重试**：删掉重新下即可，原地重试没意义）。"""


class DownloadCancelledError(DownloadError):
    """用户取消（不是失败：任务层应转 cancelled，且半成品保留）。"""


# 本类错误重试必然同样结果，故不进重试循环（HTTPError 单独判，因为它要分状态码）
_NOT_RETRYABLE = (
    DownloadSizeMismatchError,
    DownloadLocalCorruptError,
)


@dataclass
class DownloadResult:
    """一次完整下载（含内部重试）的结果。"""

    sha256: str
    transferred_bytes: int          # 本次调用从网络真正读到的字节（续传只算新增部分）
    attempts: int                   # 实际尝试次数（1 = 一次成功）
    resumed_from: int               # 首次尝试时本地已有的字节（0 = 从头下）
    retried: bool                   # 是否发生过重试（前端据此在完成行留痕）


# ---------------------------------------------------------------------------
# 单源策略与文案
# ---------------------------------------------------------------------------


def retry_delay(attempt: int) -> float:
    """第 attempt 次失败后等多久再试（attempt 从 1 起）：2、4、8、16、32、60、60…"""
    exponent = max(0, min(int(attempt) - 1, 8))
    return min(2.0 * (2 ** exponent), MAX_RETRY_DELAY_SECONDS)


def is_retryable(exc: BaseException) -> bool:
    """这个错误值不值得再试一次。

    不可重试 = 重试必然同样结果：清单与服务器总长矛盾、本地比远端大、服务器明确拒绝。
    **HTTP 5xx 可重试**（服务端临时故障），404/403 不可重试（文件不在 / 不给）。
    """
    if isinstance(exc, _NOT_RETRYABLE):
        return False
    if isinstance(exc, urllib.error.HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        return 500 <= code < 600 or code in (408, 429)
    return True


def describe_network_error(exc: BaseException) -> str:
    """底层异常 → 中文可行动句子（状态面的错误文案单源）。"""
    if isinstance(exc, DownloadCancelledError):
        return "已取消下载"
    if isinstance(exc, DownloadSizeMismatchError):
        return str(exc)
    if isinstance(exc, DownloadLocalCorruptError):
        return str(exc)
    if isinstance(exc, DownloadTruncatedError):
        return f"{exc}，会自动重连接着下"
    if isinstance(exc, urllib.error.HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        if code == 404:
            return f"服务器上找不到这个文件（HTTP 404）：{getattr(exc, 'url', '')}"
        if code in (401, 403):
            return f"服务器拒绝访问（HTTP {code}），可能是限流或链接失效"
        if code == 416:
            return "服务器说请求的字节范围不合法（本地记录与远端对不上）"
        if code == 429:
            return "服务器限流（HTTP 429），稍后会自动重试"
        if 500 <= code < 600:
            return f"服务器临时出错（HTTP {code}），稍后会自动重试"
        return f"服务器返回 HTTP {code}"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            return f"连接超时（{int(SOCKET_TIMEOUT_SECONDS)} 秒没有数据），会自动重连接着下"
        return f"网络连接失败（{reason}），会自动重连接着下"
    if isinstance(exc, IncompleteRead):
        return "数据没传完就断了，会自动重连接着下"
    if isinstance(exc, TimeoutError):
        return f"读取超时（{int(SOCKET_TIMEOUT_SECONDS)} 秒没有数据），会自动重连接着下"
    if isinstance(exc, ConnectionError):
        return f"连接被中断（{exc}），会自动重连接着下"
    if isinstance(exc, OSError):
        return f"网络读写出错（{exc}），会自动重连接着下"
    return f"下载失败（{type(exc).__name__}: {exc}）"


def error_kind(exc: BaseException) -> str:
    """错误分类（状态面 `error_kind` 字段的单源）："" | "network" | "verify" | "cancelled"。"""
    if isinstance(exc, DownloadCancelledError):
        return "cancelled"
    if isinstance(exc, (DownloadSizeMismatchError, DownloadLocalCorruptError)):
        return "verify"
    return "network"


def parse_content_range(value: str) -> tuple[int, int] | None:
    """`Content-Range: bytes 100-199/2000` → (起始, 总长)；解析不出返回 None。"""
    match = _CONTENT_RANGE_RE.search(value or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(3))


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def resumable_download(
    url: str,
    dest: Path,
    on_progress: Callable[[int], None],
    *,
    cancel: threading.Event | None = None,
    before_retry: Callable[..., None] | None = None,
    expected_size: int = 0,
    expected_sha256: str = "",
    min_resume_bytes: int = MIN_RESUME_BYTES,
    timeout: float = SOCKET_TIMEOUT_SECONDS,
    max_attempts: int | None = None,
    opener: Callable[[Any, float], Any] | None = None,
) -> DownloadResult:
    """把一卷下到 `dest`：断点续传 + 截断判定 + 无上限退避重试。

    - `expected_size` / `expected_sha256`：清单里的卷大小与内容哈希。给了它们才能做
      四件不给就做不了的事——到点即成功（不发多余请求）、本地已完整且**内容相符**则直接复用、
      `Content-Length` 与清单矛盾时直报不可重试、**内容与清单不符时整份重下**。
      只给 size 会有个死局：本地尺寸到点但内容坏，重试每次都收到 0 字节（实测踩过），
      所以任务层应当两个都给。
    - `cancel`：置位后**不再发起下一次尝试**，退避等待中也能立刻返回（抛 `DownloadCancelledError`）。
    - `before_retry(attempt, error, bytes_on_disk, restarted)`：每次重试前回调，其异常不外抛。
    - `max_attempts`：**缺省 None = 无上限**（产品口径：网络故障要自己扛到成功）。
      只有给测试用的假服务器写「永远截断」的剧本时才需要它，真机上不必设。
    - `opener`：注入用（测试）；缺省走 `urllib.request.urlopen`。
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = int(expected_size or 0)
    want_sha = str(expected_sha256 or "").strip().lower()
    opener = opener or _urlopen

    # 本地已是完整卷：先按内容判「能不能直接用」，而不是直接相信尺寸。
    if expected > 0 and dest.is_file() and dest.stat().st_size == expected:
        if not want_sha:
            # 没给期望哈希：只能相信尺寸（无法判内容）。调用方仍会在更高层再验一次。
            return DownloadResult(file_sha256(dest), 0, 1, expected, False)
        if file_sha256(dest) == want_sha:
            clear_marker(dest)
            return DownloadResult(want_sha, 0, 1, expected, False)
        clear_partial(dest)      # 尺寸对、内容不对：整份重下
    elif want_sha and dest.is_file():
        pass                     # 长度不足：照常续传，内容由本轮下载完后再验

    resumed_from = dest.stat().st_size if dest.is_file() else 0
    transferred = 0
    attempts = 0
    need_clean_slate = False
    while True:
        if cancel is not None and cancel.is_set():
            write_partial_marker(dest, url, expected)
            raise DownloadCancelledError("已取消下载")
        if need_clean_slate:
            # 上一轮「内容不对」（外层拿清单 sha256 验出来的）：清掉重下。
            # 不清就会死循环——服务器见「你要的起点=整卷大小」于是不发字节，
            # 每次尝试收到 0 字节，重试白转（实测过，报「重试 N 次仍未下完（307200/307200）」）。
            clear_partial(dest)
            need_clean_slate = False
        attempts += 1
        try:
            transferred += _attempt(
                url=url, dest=dest, on_progress=on_progress, cancel=cancel,
                expected_size=expected, min_resume_bytes=min_resume_bytes,
                timeout=timeout, opener=opener,
            )
            size = dest.stat().st_size if dest.is_file() else 0
            if expected > 0 and size != expected:
                # 这一轮「读完了」但长度不对（对端先声明后少发）：当失败处理，
                # 走下面的重试——**判定必须在循环内**，否则第一次就跳出、重试形同虚设。
                raise DownloadTruncatedError(f"下载未完成（{size} / {expected} 字节）")
            if want_sha and file_sha256(dest) != want_sha:
                # 长度对了但内容不是清单上那一份：**不重试**，删掉整份重下再验。
                clear_partial(dest)
                need_clean_slate = True
                raise DownloadLocalCorruptError(
                    f"下载内容与清单不符（{size} 字节），已丢弃整份重新下载"
                )
        except DownloadCancelledError:
            write_partial_marker(dest, url, expected)
            raise
        except BaseException as exc:  # noqa: BLE001 —— 分类交给 is_retryable，绝不吞掉
            if not is_retryable(exc):
                # 不可重试：不调 before_retry（它语义是「即将重试」），
                # 但它自称的处置要落地——见 _attempt 里 clear_partial 的调用点。
                raise
            if max_attempts is not None and attempts >= int(max_attempts):
                write_partial_marker(dest, url, expected)
                size_now = dest.stat().st_size if dest.is_file() else 0
                raise DownloadTruncatedError(
                    f"重试 {attempts} 次仍未下完（{size_now} / {expected or '?'} 字节）："
                    f"{describe_network_error(exc)}"
                ) from exc
            _notify_retry(before_retry, attempts, exc, dest, False)
            _wait_or_cancel(cancel, retry_delay(attempts))
            if cancel is not None and cancel.is_set():
                # 退避期间被取消：立刻收手，不再发起下一次尝试（半成品保留）
                write_partial_marker(dest, url, expected)
                raise DownloadCancelledError("已取消下载")
            continue
        break

    clear_marker(dest)
    return DownloadResult(file_sha256(dest), transferred, attempts, resumed_from, attempts > 1)


def _attempt(
    *,
    url: str,
    dest: Path,
    on_progress: Callable[[int], None],
    cancel: threading.Event | None,
    expected_size: int,
    min_resume_bytes: int,
    timeout: float,
    opener: Callable[[Any, float], Any],
) -> int:
    """一次尝试。返回本次从网络读到的字节数；失败抛异常，半成品状态留给外层处置。"""
    offset = dest.stat().st_size if dest.is_file() else 0
    if expected_size > 0 and offset > expected_size:
        # 本地坏：先按「不可重试」如实处置（清掉半成品），再报错
        clear_partial(dest)
        raise DownloadLocalCorruptError(
            f"本地文件比远端还大（本地 {offset} / 清单 {expected_size} 字节）"
        )
    resume = offset >= max(1, int(min_resume_bytes))
    if offset > 0 and not resume:
        clear_partial(dest)          # 小卷：重下比发 Range 更省事，也少一堆边界
        offset = 0

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if resume:
        request.add_header("Range", f"bytes={offset}-")

    with opener(request, timeout) as response:
        status, start, declared_total = _decode_response(response)
        if resume and start != offset:
            # 服务器要么忽略了 Range（整份重发，start=0），要么给的区间起点与请求不符。
            # 两种都不能续写——续写会把「旧字节 + 新字节」拼成一份坏文件。
            clear_partial(dest)
            offset = 0
        mode = "ab" if offset > 0 else "wb"
        got = _stream_to_file(response, dest, mode, on_progress, cancel)
        # 完整性判据：**已落盘 + 本次收到** 与响应声明的总长比。
        # 不能拿「本次收到」直接比总长——`Content-Range` 的第三段是**资源总长**，
        # 而本次响应只发剩余部分：一次正常的续传（本地 102400 + 本次 204800 = 307200）
        # 会被误判成「连接中断」（这个错我自己踩过，且它会把好端端的续传打断）。
        # 先判这条，再判「总长与清单矛盾」：断流时不该扣「发布信息不一致」这顶不可重试的帽子。
        received_total = offset + got
        if declared_total > 0 and received_total < declared_total:
            raise DownloadTruncatedError(
                f"连接中断：本次声明 {declared_total} 字节，只收到 {received_total} 字节"
            )
        if expected_size > 0 and declared_total > 0 and expected_size != declared_total:
            raise DownloadSizeMismatchError(
                f"发布信息不一致：清单说 {expected_size} 字节，服务器说 {declared_total} 字节"
            )
        return got


def _decode_response(response: Any) -> tuple[int, int, int]:
    """响应 → (HTTP 状态, 本次响应的起始偏移, 资源总长；未知 = 0)。

    总长的取法有讲究（踩过一次）：**206 必须优先用 `Content-Range` 的第三段**，
    它才是「资源总长」；`Content-Length` 是**本次响应体**的长度，续传时只有剩余部分
    （甚至有服务器先声明后不发，等于 0）。用 `起始 + Content-Length` 猜总长会在
    「续传 + 响应体为空」时算出 `起始`，被误判成「发布信息不一致」而拒绝重试。
    """
    status = int(getattr(response, "status", 0) or getattr(response, "code", 0) or 0)
    headers = getattr(response, "headers", None) or {}
    start, total = 0, 0
    if status == 206:
        parsed = parse_content_range(headers.get("Content-Range") or "")
        if parsed is not None:
            start, total = parsed
        if total <= 0:
            # Content-Range 缺失/是 */N 形态：退回 Content-Length，但只当作
            # 「本次响应体长度」，不当总长（宁可 total 未知，也不要算错）
            return status, start, 0
    if total <= 0 and status != 206:
        length = headers.get("Content-Length")
        if length:
            try:
                total = int(length)      # 200 整份：Content-Length 就是总长
            except ValueError:
                total = 0
    return status, start, total


def _stream_to_file(
    response: Any,
    dest: Path,
    mode: str,
    on_progress: Callable[[int], None],
    cancel: threading.Event | None,
) -> int:
    """按块写盘；取消置位立刻停（抛 DownloadCancelledError，半成品保留）。"""
    got = 0
    with open(dest, mode) as handle:
        while True:
            if cancel is not None and cancel.is_set():
                raise DownloadCancelledError("已取消下载")
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                break
            handle.write(chunk)
            got += len(chunk)
            on_progress(len(chunk))
    return got


def file_sha256(path: Path) -> str:
    """整文件 SHA256（续传后要对整卷求值，不是对本次新增部分）。"""
    digest = hashlib.sha256()
    with open(Path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _urlopen(request: Any, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)


def _notify_retry(
    callback: Callable[..., None] | None,
    attempt: int,
    exc: BaseException,
    dest: Path,
    restarted: bool,
) -> None:
    if callback is None:
        return
    on_disk = dest.stat().st_size if dest.is_file() else 0
    try:
        callback(attempt, exc, on_disk, restarted)
    except Exception:  # noqa: BLE001 —— 回调是观测面，不许把下载带崩
        pass


def _wait_or_cancel(cancel: threading.Event | None, delay: float) -> None:
    if cancel is None:
        time.sleep(delay)
        return
    cancel.wait(delay)   # 取消时立刻醒，不等退避走完


# ---------------------------------------------------------------------------
# 半成品边车（跨进程：换一次进程也知道本地这半份是谁的）
# ---------------------------------------------------------------------------


def marker_for(dest: Path) -> Path:
    return Path(str(dest) + PARTIAL_SUFFIX)


def write_partial_marker(dest: Path, url: str, expected_size: int) -> Path:
    """写边车（取消 / 失败时）。只记 URL 与期望总长——够判「这份还能不能接着用」。"""
    marker = marker_for(dest)
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            json.dumps({"url": url, "expected_size": int(expected_size or 0)},
                       ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass
    return marker


def read_partial_marker(dest: Path) -> dict[str, Any]:
    """读边车；没有 / 坏了都返回空 dict（调用方按「不认识这份半成品」处理）。"""
    marker = marker_for(dest)
    if not marker.is_file():
        return {}
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def clear_marker(dest: Path) -> None:
    """只删边车（成功时：文件本身要留）。"""
    marker_for(dest).unlink(missing_ok=True)


def clear_partial(dest: Path) -> None:
    """删半成品 + 边车（校验失败、服务器忽略 Range、本地坏 时用）。"""
    Path(dest).unlink(missing_ok=True)
    clear_marker(dest)
