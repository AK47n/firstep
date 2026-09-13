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


class DownloadVerifyError(DownloadError):
    """内容与清单不符（**任务层判出来的**校验失败：重下也不会有变化）。

    为什么要在谱系里单列一支、而不是让任务层自己给异常打标记：`error_kind` 是
    「状态面 `error_kind` 字段的单源」，分类必须只有一处。校验失败发生在任务层
    （下载器已经把整卷算过哈希了），但它**语义上属于同一张表**——所以由任务层
    抛这个类型，分类仍归这里（工单 04 的双轴评审整改）。
    """


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


@dataclass
class _AttemptOutcome:
    """单次尝试的产出（**本次**连接的帐，不是整卷的）。"""

    got: int                        # 本次从网络读到的字节
    restarted: bool                 # 服务器忽略了 Range / 起点不符 → 本地半成品已丢弃


class _RestartFlag:
    """「这一轮服务器没让我们接上」的跨层记号（`_attempt` 写、重试循环读）。

    为什么不走返回值：截断是**在 `_attempt` 内部**抛的，返回值那一行根本走不到——
    实测过一次：起始偏移明明是 0（服务器忽略了 Range），重试消息却写「从 21% 接着下」。
    """

    __slots__ = ("seen",)

    def __init__(self) -> None:
        self.seen = False

    def note(self, restarted: bool) -> None:
        self.seen = bool(restarted)


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
    if isinstance(exc, DownloadVerifyError):
        return str(exc)
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
    """错误分类（状态面 `error_kind` 字段的**单源**）："" | "network" | "verify" | "cancelled"。

    任务层只消费、不自己判——校验失败也走这张表（抛 `DownloadVerifyError`）。
    """
    if isinstance(exc, DownloadCancelledError):
        return "cancelled"
    if isinstance(exc, (DownloadSizeMismatchError, DownloadLocalCorruptError,
                        DownloadVerifyError)):
        return "verify"
    return "network"


def retry_reason(exc: BaseException) -> str:
    """重试原因（人话，用在「第 N 次自动重试」那句话里）。

    取 `describe_network_error` 的第一句并去掉「会自动重连接着下」这个尾巴——
    重试次数由调用方拼（消息里不必重复说两遍会重试）。
    """
    text = describe_network_error(exc)
    text = text.split("，会自动重连接着下")[0].rstrip("，。")
    return text or "网络中断"


def retry_message(reason: str) -> str:
    """进行中的摘要（任务 `message` 字段的单源文案）：**只说原因**。

    形态：「连接中断：本次声明 2097152 字节，只收到 838860 字节」。

    **不带「第 N 次」也不带「从 X% 接着下」**：那两件事分别是 `retry_count` 与
    `resume_percent` 两个**字段**的事。文案里再写一遍会与界面自己拼的那句撞车
    （实测读出「正在自动重试（第 1 次）：…，第 1 次自动重试，从 39% 接着下」）；
    而让前端反过来解析这句话取百分比更是把文案当接口
    （工单 05 的双轴评审整改：第一版正是这么写的，两个轴都判了它）。
    """
    return str(reason)


def retry_resume_percent(done_bytes: int, total_bytes: int) -> int:
    """重试时已下载的百分比（状态面 `resume_percent` 字段的单源）。

    `-1` = 不知道（总量未知）：前端据此决定要不要写百分比。
    `0` = 从 0 开始（真相，不是「不知道」）——例如服务器忽略了 Range，半成品已被丢弃。
    """
    total = int(total_bytes or 0)
    if total <= 0:
        return -1
    return int(int(done_bytes or 0) * 100 / total)


def resume_message(done_bytes: int, total_bytes: int) -> str:
    """「这次是从上次断开处接着下」的摘要（任务 `run()` 启动时用）。"""
    if total_bytes > 0:
        return f"接着上次的进度从 {int(done_bytes * 100 / total_bytes)}% 继续下载"
    return f"接着已下载的 {done_bytes} 字节继续下载"


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
    on_start: Callable[[int], None] | None = None,
    before_attempt: Callable[[], None] | None = None,
) -> DownloadResult:
    """把一卷下到 `dest`：断点续传 + 截断判定 + 无上限退避重试。

    - `expected_size` / `expected_sha256`：清单里的卷大小与内容哈希。给了它们才能做
      四件不给就做不了的事——到点即成功（不发多余请求）、本地已完整且**内容相符**则直接复用、
      `Content-Length` 与清单矛盾时直报不可重试、**内容与清单不符时整份重下**。
      只给 size 会有个死局：本地尺寸到点但内容坏，重试每次都收到 0 字节（实测踩过），
      所以任务层应当两个都给。
    - `cancel`：置位后**不再发起下一次尝试**，退避等待中也能立刻返回（抛 `DownloadCancelledError`）。
    - `before_retry(attempt, error, bytes_on_disk, restarted)`：每次重试前回调，其异常不外抛。
      `restarted=True` = 这一轮服务器没让我们接上（忽略 Range / 起点不符），落盘从 0 重新计。
    - `on_start(resume_offset)`：**每次尝试开始时**报一次「本轮实际从盘上第几字节起写」。
      调用方据此把进度基准对齐到**这一次尝试的真实起点**——服务器忽略 Range 时会
      把它从「以为接着下」纠正回落盘真相（不报这一下，进度会把已丢弃的半成品算进去）。异常不外抛。
    - `before_attempt()`：**退避等待结束、马上要真的重连**时报一次。观测面用它关掉
      「正在重试」这个窗口——窗口 = `before_retry`（开）→ 这一次回调（关）。
      为什么不复用 `on_start`：两者在同一轮循环里紧挨着发生（先报重试、再开始下一轮），
      在 `on_start` 里关会把窗口压成 0 宽。异常不外抛。
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
    # 「这一轮服务器没让我们接上」的记号。**不能用返回值带出来**：截断是在 `_attempt`
    # 内部抛的，返回值那一行根本走不到（实测：起始偏移明明是 0，消息却写「从 21% 接着下」）。
    forced_restart = _RestartFlag()
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
            outcome = _attempt(
                url=url, dest=dest, on_progress=on_progress, cancel=cancel,
                expected_size=expected, min_resume_bytes=min_resume_bytes,
                timeout=timeout, opener=opener, on_start=on_start,
                restart_flag=forced_restart,
            )
            transferred += outcome.got
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
            # **失败即写边车**（spec：边车只在取消 / 失败时写）。写在重试循环里而不是
            # 只在「重试用尽」分支：产品的重试是**无上限**的，那条分支真机上永远走不到
            # ——于是「断了之后半成品没人认领」这个洞会一直藏着（工单 03 的探针实测：
            # 只有半成品没有边车，下一个进程会把它当来路不明的东西丢掉，白下一次）。
            write_partial_marker(dest, url, expected)
            if max_attempts is not None and attempts >= int(max_attempts):
                size_now = dest.stat().st_size if dest.is_file() else 0
                raise DownloadTruncatedError(
                    f"重试 {attempts} 次仍未下完（{size_now} / {expected or '?'} 字节）："
                    f"{describe_network_error(exc)}"
                ) from exc
            _notify_retry(before_retry, attempts, exc, dest, bool(forced_restart.seen))
            _wait_or_cancel(cancel, retry_delay(attempts))
            if cancel is not None and cancel.is_set():
                # 退避期间被取消：立刻收手，不再发起下一次尝试（半成品保留）
                write_partial_marker(dest, url, expected)
                raise DownloadCancelledError("已取消下载")
            _notify_attempt(before_attempt)      # 窗口关闭：马上要真的重连了
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
    on_start: Callable[[int], None] | None = None,
    restart_flag: "_RestartFlag | None" = None,
) -> _AttemptOutcome:
    """一次尝试。返回本次的产出；失败抛异常，半成品状态留给外层处置。"""
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
        restarted = bool(resume) and start != offset
        if restart_flag is not None:
            restart_flag.note(restarted)     # 先记账：下面可能抛异常（返回值走不到）
        if restarted:
            # 服务器要么忽略了 Range（整份重发，start=0），要么给的区间起点与请求不符。
            # 两种都不能续写——续写会把「旧字节 + 新字节」拼成一份坏文件。
            clear_partial(dest)
            offset = 0
        # 把**本轮真实起点**报给调用方：它据此校准进度基准。必须赶在第一个
        # chunk 之前报（此时「服务器忽略 Range」这件事已经判完了）。
        _notify_start(on_start, offset)
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
        return _AttemptOutcome(got=got, restarted=restarted)


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


def _notify_start(callback: Callable[[int], None] | None, offset: int) -> None:
    """告知调用方「本轮从盘上第几字节起写」（观测面，异常不外抛）。"""
    if callback is None:
        return
    try:
        callback(int(offset))
    except Exception:  # noqa: BLE001 —— 同上
        pass


def _notify_attempt(callback: Callable[[], None] | None) -> None:
    """告知调用方「退避结束、马上要重连了」（观测面，异常不外抛）。"""
    if callback is None:
        return
    try:
        callback()
    except Exception:  # noqa: BLE001 —— 同上
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


def is_resumable_partial(dest: Path, url: str, expected_size: int) -> bool:
    """盘上这份半成品能不能接着下（任务 `run()` 启动时的判据）。

    三个条件缺一不可，因为「来路不明的不完整文件」比重新下更糟：

    1. 文件在，且长度 **> 0 且 < 期望总长**（0 字节 = 没有可续的东西；长度到点 = 该进校验而不是发 Range）；
    2. 边车在（没有边车 = 不是本项目留下的半成品）；
    3. 边车里的 `url` 与 `expected_size` 都对得上（换版本后同名卷不能拿来续）。

    对不上就当它不存在：清掉半成品与边车，从头下。

    两条接口约定（评审提过，写下来免得被当成 bug）：

    - 本函数是**纯判据**，自己不删任何东西；「对不上就清掉」是**调用点**的动作
      （任务层在判据为假时显式调 `clear_partial`），因为删不删是任务层的策略。
    - `expected_size <= 0`（清单没给大小）时「长度到点」这条无从判起，于是只按
      「有文件 + 边车对得上」算可续。当前唯一调用方（两个任务）永远给得出大小。
    """
    dest = Path(dest)
    if not dest.is_file():
        return False
    size = dest.stat().st_size
    total = int(expected_size or 0)
    if size <= 0 or (total > 0 and size >= total):
        return False
    marker = read_partial_marker(dest)
    if not marker:
        return False
    if str(marker.get("url") or "") != str(url or ""):
        return False
    try:
        if int(marker.get("expected_size") or 0) != total:
            return False
    except (TypeError, ValueError):
        return False
    return True


def _accepts_modern_kwargs(download: Callable[..., Any]) -> bool:
    """这个下载函数吃不吃「新式」关键字（`expected_size` / `cancel` / `before_retry` …

    判据两条：显式声明了 `expected_size`，或声明了 `**kwargs`（测试里的 spy 常这样写）。
    没有签名（内建 / C 实现）按「不吃」处理——宁可退回三参老形态。
    """
    from inspect import Parameter, signature

    try:
        params = signature(download).parameters
    except (TypeError, ValueError):
        return False
    return (
        "expected_size" in params
        or any(p.kind is Parameter.VAR_KEYWORD for p in params.values())
    )


def as_task_downloader(
    download: Callable[..., Any],
    *,
    cancel: threading.Event | None = None,
    before_retry: Callable[..., None] | None = None,
    on_start: Callable[[int], None] | None = None,
    before_attempt: Callable[[], None] | None = None,
    default: bool = False,
) -> Callable[..., Any]:
    """任务层的下载适配层：`(url, dest, on_progress, *, expected_size, expected_sha256)`。

    三件事，缺一不可（工单 03）：

    1. **把清单的 `size` 与 `sha256` 一并传给缺省的 `resumable_download`**。
       只给 size 会掉进工单 02 实测的死局——「尺寸到点但内容坏」时服务器见
       「你要的起点=整卷大小」就不发字节，重试每轮收 0 字节，白转到上限；
    2. **把 `cancel` / `before_retry` / `on_start` 接到缺省实现上**（退避中可取消、
       重试如实计数、进度基准随本轮真实起点校准）；
    3. **保住三参注入缝**：`default=False`（注入的下载器）时按位置传三个参数就完事——
       除非这个下载器自己声明要吃那几个关键字参数（显式写了 `expected_size`
       或 `**kwargs`），那就照传，好让它走完整的注入契约。

    `default=True` 由调用方在「解析出来的是缺省实现」时给出：此时关键字参数是无条件
    传的（不靠签名嗅探——`default` 的判断更结实）。
    """
    accepts_kwargs = True if default else _accepts_modern_kwargs(download)

    def task_download(
        url: str,
        dest: Path,
        on_progress: Callable[[int], None],
        *,
        expected_size: int = 0,
        expected_sha256: str = "",
    ) -> Any:
        if not accepts_kwargs:
            return download(url, dest, on_progress)
        return download(
            url, dest, on_progress,
            cancel=cancel, before_retry=before_retry, on_start=on_start,
            before_attempt=before_attempt,
            expected_size=expected_size, expected_sha256=expected_sha256,
        )

    return task_download

