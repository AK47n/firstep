"""可续下载域模块测试（工单 resumable-download/02）。

覆盖：退避序列、错误分类与中文文案、以及 `resumable_download` 的**偏移判定**
（续传起始偏移 / 截断必须失败 / 服务器忽略 Range 时从 0 重下 / 本地坏 / 取消在退避中生效）。

不碰真网络：响应由 `_FakeServer` + 注入的 `opener` 提供（spec 里定的注入缝）。
真 socket 行为由 `.scratch/resumable-download/probe-01-resume.py` 那一档回答。
"""

from __future__ import annotations

import hashlib
import io
import threading
import urllib.error
from http.client import IncompleteRead
from pathlib import Path

import pytest

from contest_generator import download_resume as _dr
from contest_generator.download_resume import (
    DownloadCancelledError,
    DownloadContentMismatchPersistentError,
    DownloadLocalCorruptError,
    DownloadRangeNotSatisfiableError,
    DownloadResult,
    DownloadSizeMismatchError,
    DownloadTruncatedError,
    as_task_downloader,
    describe_network_error,
    error_kind,
    file_sha256,
    is_resumable_partial,
    is_retryable,
    marker_for,
    parse_content_range,
    read_partial_marker,
    resumable_download,
    retry_delay,
    write_partial_marker,
)

# 工单 08 新增的类型：**按名字取，缺失时让相关用例 skip 而不是整文件 ImportError**。
# 为什么要这样：导入期报错会让「把实现回退一版」的**反向验证**（以及任何在旧版实现上
# 跑测试套件的场景）直接炸在收集阶段——那是 ERROR 不是 FAILED，看起来像测试坏了而不是
# 判据发现了回归，反而掩盖问题。缺类型 = 这些判据在这份实现上「无从谈起」，skip 才如实。
DownloadContentMismatchError = getattr(
    _dr, "DownloadContentMismatchError", None)
_NEEDS_08 = pytest.mark.skipif(
    DownloadContentMismatchError is None,
    reason="本份实现没有 DownloadContentMismatchError（工单 08 之前）：该判据无从谈起",
)

PAYLOAD = bytes((i * 7 + 11) % 251 for i in range(300 * 1024))
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


# ---------------------------------------------------------------------------
# 假服务器：只做「按 Range 回字节 + 按剧本出错」两件事
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self._body = body
        self._pos = 0

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            chunk = self._body[self._pos:]
            self._pos = len(self._body)
            return chunk
        chunk = self._body[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _FakeServer:
    """剧本化服务器：`cut_keep` 截断、`ignore_range` 整份重发、`raise_on` 抛指定异常。

    参数都按「读代码时的直觉」设计：

    - `raise_on` 的序号是 **1 起**（第 1 次请求 = 1）；
    - `cut_keep` 是**逐请求**的「本次响应发到第几成就断」（0~1 的比例，下标 = 第几次请求 - 1，
      超出的不断）：**声明长度仍是整段**，只是提前收尾 —— 这是 TCP 断流的真实形态。
      用比例而不是绝对字节数，是为了让重试**收敛**：绝对字节数会让「越下越多、
      每次都被切掉同样多」永远差最后一点，测试就挂死了（本项目真踩过）。
    - `declared_short` 则相反：**声明得就比实际短**（模拟「发布物与清单不一致」这类坏响应）。
      两者混在一起会分不清「下载被截断」与「发布信息矛盾」，所以分开表达。
    """

    def __init__(self, payload: bytes = PAYLOAD) -> None:
        self.payload = payload
        self.requests: list[dict[str, object]] = []
        self.cut_keep: list[float] = []      # 逐请求：本响应发到该比例即断
        self.declared_short = False          # 响应头里声明的总长比实际短
        self.ignore_range = False            # 恒 200 整份
        self.raise_on: list[tuple[int, BaseException]] = []   # (第几次请求, 抛什么)

    # -- 供测试读取 --------------------------------------------------------
    @property
    def n_requests(self) -> int:
        return len(self.requests)

    def starts(self) -> list[int]:
        return [int(r["start"]) for r in self.requests]

    def cut_at(self, index: int, body_len: int) -> int:
        """第 index 次响应（1 起）本次最多发多少字节；0 = 不切。"""
        if index > len(self.cut_keep):
            return 0
        return int(body_len * float(self.cut_keep[index - 1]))

    # -- opener -----------------------------------------------------------
    def __call__(self, request, timeout: float):  # noqa: ANN001
        header = request.get_header("Range") or ""
        start = 0
        if header.startswith("bytes=") and header.endswith("-"):
            start = int(header[len("bytes="):-1])
        self.requests.append({"range": header, "start": start})
        index = self.n_requests                        # 1 起

        for at, exc in self.raise_on:
            if at == index:
                raise exc

        full = len(self.payload)
        body = self.payload[start:] if start and not self.ignore_range else self.payload
        status = 206 if (start and not self.ignore_range) else 200
        declared = full - start if status == 206 else full
        headers = {"Content-Length": str(declared), "Accept-Ranges": "bytes"}
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{full - 1}/{full}"
        if self.declared_short:
            declared = max(0, len(body) // 2)           # 声明得就比实际短
            headers["Content-Length"] = str(declared)
        keep = self.cut_at(index, len(body))
        if keep:
            body = body[:keep]                          # 提前收尾，但声明仍是 declared
        return _FakeResponse(status, headers, body)


@pytest.fixture()
def dest(tmp_path: Path) -> Path:
    return tmp_path / "parts" / "v1.1.1.zip"


class _Server416:
    """对**带 Range 的请求**回 416 的假服务器（工单 08）。

    为什么单起一个类而不给 `_FakeServer` 加开关：416 是**在 opener 里抛**的
    （`urlopen` 对 4xx/5xx 抛 HTTPError，把响应体封在异常对象上），
    与「返回一个响应对象」是两条不同的路——混在一个类里会让两边的剧本互相干扰。

    剧本 = 「带 Range 一律 416，不带 Range 正常发」。它同时覆盖两种真实现象：
    本地那份坏死在盘上（每次都 416）、服务器上那份变小过一次（第一次 416）。
    """

    def __init__(self, payload: bytes = PAYLOAD) -> None:
        self.payload = payload
        self.ranges: list[str] = []

    @property
    def n_requests(self) -> int:
        return len(self.ranges)

    def starts(self) -> list[int]:
        return [int(h[len("bytes="):-1]) if h else 0 for h in self.ranges]

    def __call__(self, request, timeout: float):  # noqa: ANN001
        header = request.get_header("Range") or ""
        self.ranges.append(header)
        full = len(self.payload)
        if header:
            raise _http_error_with_body(
                416, f"range not satisfiable: bytes */{full}".encode())
        body = self.payload
        return _FakeResponse(200, {"Content-Length": str(len(body)),
                                   "Accept-Ranges": "bytes"}, body)


# ---------------------------------------------------------------------------
# 策略与文案（纯函数）
# ---------------------------------------------------------------------------


def test_retry_delay_doubles_then_caps() -> None:
    assert [retry_delay(n) for n in range(1, 8)] == [2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]


@pytest.mark.parametrize("value,expected", [
    ("bytes 100-199/2000", (100, 2000)),
    ("bytes 0-0/1", (0, 1)),
    ("Bytes=1-2/3", None),
    ("", None),
    ("bytes */2000", None),
])
def test_parse_content_range(value: str, expected: tuple[int, int] | None) -> None:
    assert parse_content_range(value) == expected


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x/p.zip", code, "boom", {}, None)  # type: ignore[arg-type]


def _http_error_with_body(code: int, body: bytes) -> urllib.error.HTTPError:
    """带响应体的 HTTPError：`urlopen` 实际上**总是**这样抛（真实服务器 416 会带
    `Content-Range: bytes */N` 与一段说明体）。用 None 当 body 测不出这条路上
    任何读体的代码（工单 08 的 416 分支要在异常对象上接着重发请求）。"""
    return urllib.error.HTTPError(  # type: ignore[arg-type]
        "https://x/p.zip", code, "boom", {}, io.BytesIO(body))


def test_retryable_classification() -> None:
    assert is_retryable(OSError("socket"))
    assert is_retryable(TimeoutError("slow"))
    assert is_retryable(IncompleteRead(b"partial", 100))
    assert is_retryable(_http_error(500))
    assert is_retryable(_http_error(429))
    # 416 = 「本地那份与远端对不上」：本地补救在 _attempt 里做过一次，重试还是 416
    assert not is_retryable(_http_error(416))
    assert not is_retryable(DownloadRangeNotSatisfiableError("416"))
    assert not is_retryable(_http_error(404))
    assert not is_retryable(_http_error(403))
    assert not is_retryable(DownloadSizeMismatchError("x"))
    assert not is_retryable(DownloadLocalCorruptError("x"))


def test_describe_network_error_is_chinese_and_actionable() -> None:
    timeout = urllib.error.URLError(TimeoutError("timed out"))
    assert "连接超时" in describe_network_error(timeout)
    assert "自动重连" in describe_network_error(timeout)
    assert "找不到这个文件" in describe_network_error(_http_error(404))
    assert "限流" in describe_network_error(_http_error(429))
    assert "临时出错" in describe_network_error(_http_error(503))
    truncated = DownloadTruncatedError("下载未完成（1 / 2 字节）")
    assert "下载未完成" in describe_network_error(truncated)
    mismatch = DownloadSizeMismatchError("发布信息不一致：清单说 2 字节，服务器说 3 字节")
    assert "发布信息不一致" in describe_network_error(mismatch)
    assert describe_network_error(ConnectionResetError("reset"))
    assert describe_network_error(RuntimeError("weird"))


def test_error_kind_single_source() -> None:
    assert error_kind(DownloadCancelledError("stop")) == "cancelled"
    assert error_kind(DownloadSizeMismatchError("x")) == "verify"
    assert error_kind(DownloadLocalCorruptError("x")) == "verify"
    assert error_kind(DownloadTruncatedError("x")) == "network"
    assert error_kind(OSError("x")) == "network"


# ---------------------------------------------------------------------------
# 主流程：偏移判定
# ---------------------------------------------------------------------------


def test_fresh_download_writes_payload(dest: Path) -> None:
    server = _FakeServer()
    progress: list[int] = []
    result = resumable_download("https://x/p.zip", dest, progress.append, opener=server)

    assert isinstance(result, DownloadResult)
    assert result.sha256 == PAYLOAD_SHA
    assert result.attempts == 1
    assert result.resumed_from == 0
    assert result.transferred_bytes == len(PAYLOAD)
    assert dest.read_bytes() == PAYLOAD
    assert server.starts() == [0]
    assert sum(progress) == len(PAYLOAD)
    assert not marker_for(dest).is_file()


def test_truncation_is_a_failure_not_a_success(dest: Path, monkeypatch) -> None:
    """工单 01 实测到的缺陷口径：声明整长却只发一半 → 必须抛错，不许自称成功。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    server = _FakeServer()
    server.cut_keep = [0.5] * 20          # 每次响应都只发一半（声明仍是整段）

    with pytest.raises(DownloadTruncatedError) as err:
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                           expected_size=len(PAYLOAD), max_attempts=2)
    message = str(err.value)
    assert "仍未下完" in message
    assert "连接中断" in message          # 归因是断流，而不是「发布信息不一致」
    assert "发布信息不一致" not in message
    # 半成品保留（它就是断点本身），边车在场供下次识别。
    # 落盘量 = 第 1 次切到 50%（153600）+ 第 2 次对剩余部分再切 50%（+76800）= 230400，
    # 不是「载荷的一半」——每次响应都被切半，所以断言按剧本推，别按直觉写。
    assert dest.stat().st_size == int(len(PAYLOAD) * 0.5) + int(len(PAYLOAD) * 0.5 * 0.5)
    assert read_partial_marker(dest)["expected_size"] == len(PAYLOAD)


def test_declared_total_shorter_than_manifest_is_not_retried(dest: Path) -> None:
    """响应声明得就比清单短 = 发布物与清单不一致：不可重试，直报中文。"""
    server = _FakeServer()
    server.declared_short = True
    with pytest.raises(DownloadSizeMismatchError) as err:
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                           expected_size=len(PAYLOAD))
    assert "发布信息不一致" in str(err.value)
    assert server.n_requests == 1


def test_resume_continues_from_offset_after_cut(dest: Path, monkeypatch) -> None:
    """第一次被截断 → 第二次必须带 Range 且从已落盘字节接着下，最终哈希正确。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(PAYLOAD[:100 * 1024])          # 模拟「上次下到 100 KB 就断了」

    server = _FakeServer()
    retries: list[tuple] = []
    result = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=server,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
        max_attempts=4,                  # 防挂：剧本走偏时立刻报错而不是死循环
        # 测试载荷只有 300 KB < 产品阈值 1 MB；要验续传就得显式把阈值降下来
        # （阈值本身的行为由 test_small_part_is_redownloaded_not_resumed 钉住）
        min_resume_bytes=64 * 1024,
        before_retry=lambda attempt, exc, on_disk, restarted: retries.append(
            (attempt, type(exc).__name__, on_disk, restarted)),
    )

    assert result.sha256 == PAYLOAD_SHA
    assert result.resumed_from == 100 * 1024
    assert result.attempts == 1
    assert result.retried is False
    assert server.starts() == [100 * 1024]
    assert dest.read_bytes() == PAYLOAD
    assert retries == []


def test_resume_after_connection_error_reports_retry(dest: Path, monkeypatch) -> None:
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    server = _FakeServer()
    server.cut_keep = [0.8]                      # 只切第 1 次响应；第 2 次起整段发
    server.raise_on = [(2, OSError("connection reset"))]

    retries: list[tuple] = []
    result = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=server,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
        max_attempts=4,                  # 防挂：剧本走偏时立刻报错而不是死循环
        min_resume_bytes=64 * 1024,      # 见上：测试载荷小于产品阈值
        before_retry=lambda attempt, exc, on_disk, restarted: retries.append(
            (attempt, type(exc).__name__, on_disk)),
    )

    assert result.sha256 == PAYLOAD_SHA
    assert result.retried is True
    assert result.attempts == 3
    first_cut = int(len(PAYLOAD) * 0.8)          # 第一次被切在 80%
    assert server.starts() == [0, first_cut, first_cut]
    assert retries == [
        (1, "DownloadTruncatedError", first_cut),   # 第一次：被截断
        (2, "OSError", first_cut),                  # 第二次：连接重置（没写进任何字节）
    ]


def test_server_ignoring_range_restarts_from_zero(dest: Path) -> None:
    """服务器忽略 Range 返回 200：本地半成品必须作废，否则会拼出坏文件。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\x00" * 50_000)               # 垃圾半成品
    server = _FakeServer()
    server.ignore_range = True

    result = resumable_download("https://x/p.zip", dest, lambda n: None, opener=server)

    assert result.sha256 == PAYLOAD_SHA
    assert dest.read_bytes() == PAYLOAD
    assert server.n_requests == 1                    # 一次就成，不必重试


def test_resumed_from_reports_whether_range_actually_connected(dest: Path) -> None:
    """`resumed_from` 的口径 = 「本次**真正用 Range 接上**的起始偏移」（spec 明写）。

    盘上有 N 字节**不等于**接上了：服务器忽略 Range 回 200 时，半成品被丢弃、
    实际是从 0 下的——此时必须报 0，否则这个字段会把「被重启的下载」说成「续传」。

    （工单 07 探针实测：改之前这里返回 102400，与 spec 语义相反。两条分支都钉。）
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(PAYLOAD[:100 * 1024])

    # 分支一：服务器**忽略** Range → 回 200 整份 → 没接上，报 0
    ignoring = _FakeServer()
    ignoring.ignore_range = True
    result = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=ignoring,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
        min_resume_bytes=64 * 1024,
    )
    assert result.sha256 == PAYLOAD_SHA
    assert ignoring.starts() == [100 * 1024]     # 客户端确实带了 Range（被忽略）
    assert result.resumed_from == 0              # 但**没接上**

    # 分支二：服务器认 Range → 真的从 100 KB 接上
    dest.write_bytes(PAYLOAD[:100 * 1024])       # 复原半成品
    honoring = _FakeServer()
    result2 = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=honoring,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
        min_resume_bytes=64 * 1024,
    )
    assert honoring.starts() == [100 * 1024]
    assert result2.resumed_from == 100 * 1024


def test_http_416_clears_stale_partial_and_redownloads(dest: Path) -> None:
    """服务器对带 Range 的请求回 416 → **清掉本地那份、从 0 重下**（工单 08）。

    spec 断点契约表：「服务器返回 `416` | — | 本地比远端大 = 本地坏，删掉从 0 重下」。
    改之前的现状：416 直接冒泡 → 任务 failed、坏半成品留在盘上 → 用户点重试仍带
    同样的 Range、仍 416——**同一个坏半成品把这一卷永久卡住**。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(PAYLOAD[:100 * 1024])          # 与远端对不上的半成品
    server = _Server416()

    result = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=server,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
        min_resume_bytes=64 * 1024,                 # 载荷 300 KB < 产品阈值 1 MB
    )

    assert result.sha256 == PAYLOAD_SHA
    assert dest.read_bytes() == PAYLOAD
    # 两次请求：第一次带 Range（被 416 拒），第二次**不带 Range** 从 0 重下
    assert server.starts() == [100 * 1024, 0]
    assert result.attempts == 1                     # 就地重来，没走外层的退避重试
    assert not marker_for(dest).is_file()           # 成功不留边车


def test_http_416_without_range_is_not_retried_forever(dest: Path) -> None:
    """**本地补救用尽后仍然 416** → 如实抛，**不进无上限重试**（工单 08）。

    `_attempt` 里只允许「带 Range 被拒 → 清掉本地那份、**去掉 Range 再试一次**」
    这一次让步；若连不带 Range 的请求都被 416 拒，本地的补救手段就用尽了——
    再重试还是同一个结果。**关键判据**：不传 `max_attempts`（产品默认无上限），
    异常仍然立刻抛出、且总共只发两次请求。若把 416 当成可重试的网络错误，
    这里就会变成「每 60 秒撞一次墙」的安静死循环（退避 2→60 秒封顶，只有用户取消
    才停）——那正是本单要消灭的东西，不是要引入的。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(PAYLOAD[:100 * 1024])

    class _HostileServer:
        """恒 416，**连不带 Range 的请求也 416**。"""

        def __init__(self) -> None:
            self.ranges: list[str] = []

        def __call__(self, request, timeout):  # noqa: ANN001
            header = request.get_header("Range") or ""
            self.ranges.append(header)
            raise _http_error_with_body(416, b"range not satisfiable")

    server = _HostileServer()
    with pytest.raises(DownloadRangeNotSatisfiableError) as err:
        resumable_download(
            "https://x/p.zip", dest, lambda n: None, opener=server,
            expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
            min_resume_bytes=64 * 1024,
        )
    # 异常 message 与映射文案都不许出现底层英文原文，也不许承诺自动重连
    assert "HTTP Error" not in str(err.value)
    spoken = describe_network_error(err.value)
    assert "重新点一次下载" in spoken
    assert "自动重连" not in spoken
    assert "对不上" in spoken
    assert error_kind(err.value) == "verify"
    assert server.ranges == ["bytes=102400-", ""]   # 让步一次就收手，没有第三次
    assert not dest.is_file()                       # 坏的那份已清掉，不留半成品


def test_local_bigger_than_manifest_recovers_from_zero(dest: Path) -> None:
    """本地比**清单**还大 = 本地坏：清掉、从 0 重下，最终成功（工单 08）。

    改之前：抛 `DownloadLocalCorruptError`（在 `_NOT_RETRYABLE` 里）直接判死——
    而 spec 同一行的处置是「删掉从 0 重下」。本用例判「结果对」：
    坏的那份被清、请求数 0（不必先问一次服务器）、最终哈希正确。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(PAYLOAD + b"\x00" * 4096)      # 比清单大 4096 字节
    server = _FakeServer()

    result = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=server,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
    )

    assert result.sha256 == PAYLOAD_SHA
    assert dest.read_bytes() == PAYLOAD
    assert server.n_requests == 1                   # 坏的那份被就地清掉，直接重下
    assert not marker_for(dest).is_file()


@_NEEDS_08
def test_content_mismatch_is_retried_from_zero(dest: Path, monkeypatch) -> None:
    """「长度对了但内容不是清单那一份」→ **真的删掉重下**，不是判死（工单 08）。

    改之前：抛 `DownloadLocalCorruptError`（在 `_NOT_RETRYABLE` 里）→ 直接失败，
    而它的文案还写着「已丢弃整份重新下载」——能力只有「清掉」，重下从来没发生。
    这里判三件事：最终内容对得上、确实重试过、重试用的是**整卷重下**（起点 0）。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    dest.parent.mkdir(parents=True, exist_ok=True)

    class _ServerSwappedContent:
        """第 1 次发**另一份内容**（同长度），之后发正确的那份。"""

        def __init__(self) -> None:
            self.starts: list[int] = []

        def __call__(self, request, timeout):  # noqa: ANN001
            header = request.get_header("Range") or ""
            start = int(header[len("bytes="):-1]) if header else 0
            self.starts.append(start)
            body = (b"\xaa" * len(PAYLOAD)) if len(self.starts) == 1 else PAYLOAD[start:]
            status = 206 if header else 200
            headers = {"Content-Length": str(len(body)), "Accept-Ranges": "bytes"}
            if status == 206:
                headers["Content-Range"] = f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"
            return _FakeResponse(status, headers, body)

    server = _ServerSwappedContent()
    retries: list[tuple] = []
    result = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=server,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
        max_attempts=3, min_resume_bytes=64 * 1024,
        before_retry=lambda attempt, exc, on_disk, restarted: retries.append(
            (attempt, type(exc).__name__)),
    )

    assert result.sha256 == PAYLOAD_SHA
    assert dest.read_bytes() == PAYLOAD
    assert server.starts == [0, 0]          # 第二轮从 0 整卷重下（不是接着那份坏字节）
    assert result.attempts == 2
    # 归因是**内容**不是网络：单列一支异常，状态面据此说「会重新下载整卷」
    assert retries == [(1, "DownloadContentMismatchError")]
    assert error_kind(DownloadContentMismatchError("x")) == "verify"
    assert "重新下载整卷" in describe_network_error(DownloadContentMismatchError("内容不对"))
    assert not marker_for(dest).is_file()

class _ScriptedServer:
    """按剧本逐次回应的假服务器（每次都是 200 整份，够本单用）。

    剧本取值：`corrupt` = 长度对、内容被改坏；`truncate` = 声明整段却只发一半；
    `ok` = 正确载荷。**不做 Range**：与本单的调用点一起把 `min_resume_bytes` 提到
    比载荷还大，任何一轮都从 0 重写，剧本因此与「第几次请求」一一对应。
    """

    def __init__(self, script: list[str]) -> None:
        self.script = script
        self.n_requests = 0

    def __call__(self, request, timeout):  # noqa: ANN001
        index = min(self.n_requests, len(self.script) - 1)
        self.n_requests += 1
        kind = self.script[index]
        if kind == "corrupt":
            body = b"\xaa" * len(PAYLOAD)
        elif kind == "truncate":
            body = PAYLOAD[: len(PAYLOAD) // 2]
        else:
            body = PAYLOAD
        return _FakeResponse(
            200,
            {"Content-Length": str(len(PAYLOAD)), "Accept-Ranges": "bytes"},
            body,
        )


HUGE_RESUME_BYTES = 10 ** 9      # 比载荷大 → 每一轮都从 0 整卷重写（剧本可数）


def test_persistent_content_mismatch_turns_terminal_after_the_cap(
    dest: Path, monkeypatch
) -> None:
    """每一轮都坏 → **连续 5 次之后转终态**（工单 `update-content-mismatch-retry-cap/02`）。

    改之前：`DownloadContentMismatchError` 可重试且没有上限，真机 150 秒观察窗内 6 次重试、
    每轮整卷重下、**永远进不了失败态**（线上完整包 765 MB/卷 ⇒ 约 45 GB/小时量级），
    spec 第 177 行那句「重下不会有变化」的终态话术一次都不会出现。

    `max_attempts=8` 是给**反向注入**留的收场：判据强度探针会把封顶去掉，那时这条用例
    若没有别的上限就会无限重试（探针实测卡死）。8 > 5，所以封顶在时仍然先由封顶收场。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    dest.parent.mkdir(parents=True, exist_ok=True)
    server = _ScriptedServer(["corrupt"])

    with pytest.raises(DownloadContentMismatchPersistentError) as err:
        resumable_download(
            "https://x/p.zip", dest, lambda n: None, opener=server,
            expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
            min_resume_bytes=HUGE_RESUME_BYTES, max_attempts=8,
        )

    assert server.n_requests == 5, "连续到上限就该收手（不再每 60 秒重下一整卷）"
    assert "重下不会有变化" in str(err.value), "终态话术要接上 spec 第 177 行那句承诺"
    assert "稍后再试" in str(err.value), "还得给一条可行动作"
    assert error_kind(err.value) == "verify", "归因仍是内容，不是网络"
    assert not is_retryable(err.value), "终态 = 重试必然同样结果"
    assert not marker_for(dest).is_file(), "终态不该留下边车"
    assert not dest.is_file(), "终态不该留下半成品"


def test_content_mismatch_cap_counts_consecutive_not_cumulative(
    dest: Path, monkeypatch
) -> None:
    """连续 ≠ 累计：中途来一次**别的**错误就把计数清零，坏两次也不该被判死。

    判据是「同一卷连续 N 次内容不符」——累计口径会把「偶发坏一次、中间断一次线、
    又偶发坏一次」的服务器判死，那是过度修正。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    dest.parent.mkdir(parents=True, exist_ok=True)
    server = _ScriptedServer(["corrupt", "truncate", "corrupt", "ok"])

    result = resumable_download(
        "https://x/p.zip", dest, lambda n: None, opener=server,
        expected_size=len(PAYLOAD), expected_sha256=PAYLOAD_SHA,
        min_resume_bytes=HUGE_RESUME_BYTES, max_content_mismatch=2,
    )

    assert result.sha256 == PAYLOAD_SHA
    assert dest.read_bytes() == PAYLOAD
    assert server.n_requests == 4, "第 4 轮就该成功（第 3 轮的坏不该被算成「连续第 2 次」）"


def test_manifest_size_mismatch_is_not_retried(dest: Path) -> None:
    """清单说 A、服务器说 B = 发布物与清单不一致：直报，不进重试循环。

    用「清单刻意写错」来造（`expected_size` 比真实载荷多 7 字节），
    与 `declared_short`（服务器侧声明得短）互为镜像。
    """
    server = _FakeServer()
    with pytest.raises(DownloadSizeMismatchError) as err:
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                           expected_size=len(PAYLOAD) + 7)
    assert "发布信息不一致" in str(err.value)
    assert server.n_requests == 1


def test_http_404_is_not_retried(dest: Path) -> None:
    server = _FakeServer()
    server.raise_on = [(1, _http_error(404))]
    with pytest.raises(urllib.error.HTTPError):
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server)
    assert server.n_requests == 1


def test_http_500_is_retried(dest: Path, monkeypatch) -> None:
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    server = _FakeServer()
    server.raise_on = [(1, _http_error(500))]
    result = resumable_download("https://x/p.zip", dest, lambda n: None, opener=server)
    assert result.sha256 == PAYLOAD_SHA
    assert server.n_requests == 2

def test_local_larger_than_remote_recovers_instead_of_dying(dest: Path) -> None:
    """本地比远端大：**清掉接着下**，不再抛 `DownloadLocalCorruptError`（工单 08）。

    这条此前断言的是「抛错 + 请求数 0」（旧行为 = 直接判死）。工单 08 按 spec
    断点契约表把处置改成「删掉从 0 重下」，所以旧断言与 spec 相反、必须改：
    现在判「坏的那份被清掉、从 0 重下、最终哈希正确」。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\x00" * (len(PAYLOAD) + 10))
    server = _FakeServer()

    result = resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                                expected_size=len(PAYLOAD),
                                expected_sha256=PAYLOAD_SHA)

    assert result.sha256 == PAYLOAD_SHA
    assert dest.read_bytes() == PAYLOAD
    assert server.starts() == [0]        # 坏半成品已清，第一次请求就是从头下


def test_complete_local_file_needs_no_request(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(PAYLOAD)
    server = _FakeServer()
    result = resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                                expected_size=len(PAYLOAD))
    assert result.attempts == 1
    assert result.transferred_bytes == 0
    assert result.sha256 == PAYLOAD_SHA
    assert server.n_requests == 0


def test_small_part_is_redownloaded_not_resumed(dest: Path) -> None:
    """小卷不折腾：已落盘 3 KB 但 min_resume_bytes = 64 KB → 整卷重下，请求不带 Range。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\x00" * 3_000)
    server = _FakeServer()
    result = resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                                min_resume_bytes=64 * 1024)
    assert result.sha256 == PAYLOAD_SHA
    assert server.starts() == [0]
    assert dest.read_bytes() == PAYLOAD


def test_cancel_during_backoff_stops_immediately(dest: Path) -> None:
    """取消要在退避等待中生效：只跑一次尝试，不发起第二次；半成品与边车都在。"""
    cancel = threading.Event()
    server = _FakeServer()
    server.cut_keep = [0.02]                  # 第一次响应只发 2%（约 6 KB）就断

    def before_retry(attempt, exc, on_disk, restarted):  # noqa: ANN001
        cancel.set()          # 模拟「界面点了取消」发生在第一次失败之后

    with pytest.raises(DownloadCancelledError):
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                           cancel=cancel, expected_size=len(PAYLOAD),
                           before_retry=before_retry)
    assert server.n_requests == 1                 # 没再发起第二次
    assert dest.is_file() and dest.stat().st_size == int(len(PAYLOAD) * 0.02)
    assert marker_for(dest).is_file()


def test_cancel_before_start_does_not_touch_network(dest: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    server = _FakeServer()
    with pytest.raises(DownloadCancelledError):
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                           cancel=cancel)
    assert server.n_requests == 0


def test_download_start_writes_sidecar_so_a_killed_process_can_resume(
    dest: Path, monkeypatch
) -> None:
    """**开跑就写边车**：硬杀进程（任务管理器结束 / 崩溃 / 断电）留下的半成品也要有人认领。

    这条是工单 06 档③ 真机实测出来的（不是推演）：原来只在「取消 / 失败」两处写边车，
    于是把进程硬杀掉之后，盘上是「210 MB 半成品 + **没有边车**」→ 重启后点重试，
    那份半成品被当来路不明的东西清掉，**白下 210 MB**。

    判据：下载**还没结束**的任意时刻，边车都必须在场（且 URL / 期望大小对得上）。
    """
    server = _FakeServer()
    server.cut_keep = [0.1] * 8              # 每轮只发 10%：保证「下载进行中」有窗口可看
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 1.0)
    seen: list[bool] = []
    cancel = threading.Event()

    def on_progress(nbytes: int) -> None:
        seen.append(marker_for(dest).is_file())      # 下载进行中：边车在不在？
        if len(seen) >= 1:
            cancel.set()                             # 看第一眼就取消（模拟进程被杀）

    with pytest.raises(DownloadCancelledError):
        resumable_download("https://x/p.zip", dest, on_progress, opener=server,
                           cancel=cancel, expected_size=len(PAYLOAD))

    assert seen and all(seen), f"下载进行中边车就不在场：{seen}"
    marker = read_partial_marker(dest)
    assert marker.get("url") == "https://x/p.zip"
    assert marker.get("expected_size") == len(PAYLOAD)
    assert is_resumable_partial(dest, "https://x/p.zip", len(PAYLOAD)), (
        "硬杀后留下的半成品必须能被下一个进程认出来（否则就是白下）"
    )


def test_success_clears_the_early_sidecar(dest: Path) -> None:
    """开跑就写，那成功时必须清干净（不留孤儿）——两条一起才成立。"""
    server = _FakeServer()
    result = resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                                expected_size=len(PAYLOAD),
                                expected_sha256=PAYLOAD_SHA)
    assert result.sha256 == PAYLOAD_SHA
    assert not marker_for(dest).is_file(), "成功后边车必须被清掉"


def test_failure_writes_sidecar_for_the_next_process(dest: Path, monkeypatch) -> None:
    """失败（不是取消）也要写边车——否则下一个进程当它是来路不明的文件，白下一次。

    这条是工单 03 的探针实测出来的洞：边车原来只在「取消」与「重试用尽」两处写，
    而产品的重试**无上限**，「重试用尽」真机上永远走不到 → 断流失败后盘上只有
    半成品、没有边车 → 下一个进程认不出它。
    """
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    server = _FakeServer()
    server.cut_keep = [0.02] * 8                   # 每次都只发 2% 就断（收敛不了）
    with pytest.raises(DownloadTruncatedError):
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                           expected_size=len(PAYLOAD), max_attempts=2)
    assert dest.is_file() and dest.stat().st_size > 0
    marker = read_partial_marker(dest)
    assert marker, "失败后必须有边车，否则这份半成品没人认领"
    assert marker["url"] == "https://x/p.zip"
    assert marker["expected_size"] == len(PAYLOAD)


def test_broken_callback_does_not_break_download(dest: Path, monkeypatch) -> None:
    """before_retry 是观测面：它抛异常不许把下载带崩。"""
    monkeypatch.setattr("contest_generator.download_resume.retry_delay", lambda n: 0.0)
    server = _FakeServer()
    server.cut_keep = [0.1]

    def bad_callback(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("回调自己炸了")

    result = resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                                expected_size=len(PAYLOAD),
                                min_resume_bytes=64 * 1024, before_retry=bad_callback)
    assert result.sha256 == PAYLOAD_SHA
    assert result.attempts == 2


def test_file_sha256_matches_payload(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(PAYLOAD)
    assert file_sha256(dest) == PAYLOAD_SHA


# ---------------------------------------------------------------------------
# 与任务层的共同口径（工单 03：两条链路同源接线）
# ---------------------------------------------------------------------------


def _part_dest(tmp_path: Path) -> Path:
    dest = tmp_path / "k230.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def test_partial_is_resumable_only_with_a_sidecar(tmp_path: Path) -> None:
    """半成品能不能接着用：边车（URL + 期望总长）都对上才算数。

    没有边车 = 来路不明（可能是别的版本、也可能是垃圾字节）→ **不续**，从头下。
    这条判据就是工单 03 备注里那句「别让用户看到一堆来路不明的文件」。
    """
    dest = _part_dest(tmp_path)
    dest.write_bytes(b"x" * 600)
    assert not is_resumable_partial(dest, "https://x/k230.zip", 1200)

    write_partial_marker(dest, "https://x/k230.zip", 1200)
    assert is_resumable_partial(dest, "https://x/k230.zip", 1200)
    # 换了 URL（另一个版本的同名卷）或清单大小变了 → 这份半成品不再能用
    assert not is_resumable_partial(dest, "https://x/k230-v2.zip", 1200)
    assert not is_resumable_partial(dest, "https://x/k230.zip", 900)
    # 已经完整（长度到点）→ 不走「续」，直接进校验
    dest.write_bytes(b"x" * 1200)
    assert not is_resumable_partial(dest, "https://x/k230.zip", 1200)


def test_partial_is_never_resumable_without_a_file(tmp_path: Path) -> None:
    dest = _part_dest(tmp_path)
    write_partial_marker(dest, "https://x/k230.zip", 1200)
    assert not is_resumable_partial(dest, "https://x/k230.zip", 1200)


def test_task_downloader_adds_expected_size_and_sha256(tmp_path: Path) -> None:
    """接线契约：任务层用 `(url, dest, on_progress)` 调默认下载器，
    适配层负责把**清单的 size 与 sha256 一并**传下去。

    两条都传是硬要求（工单 02 踩坑 2）：只给 size 时「尺寸到点但内容坏」是死局，
    重试每轮收 0 字节，白转到上限。
    """
    calls: list[dict] = []

    def fake(url: str, dest: Path, on_progress, **kwargs) -> DownloadResult:  # noqa: ANN003
        calls.append({"url": url, "dest": dest, "kwargs": kwargs})
        return DownloadResult("a" * 64, 10, 1, 0, False)

    cancel = threading.Event()
    seen: list[tuple] = []
    download = as_task_downloader(
        fake, cancel=cancel,
        before_retry=lambda *a: seen.append(a),
    )
    result = download("https://x/k230.zip", tmp_path / "k230.zip", lambda n: None,
                      expected_size=1200, expected_sha256="b" * 64)

    assert result.sha256 == "a" * 64
    assert calls[0]["kwargs"]["expected_size"] == 1200
    assert calls[0]["kwargs"]["expected_sha256"] == "b" * 64
    assert calls[0]["kwargs"]["cancel"] is cancel, "取消要在下载器内部生效（退避中也能停）"
    assert calls[0]["kwargs"]["before_retry"] is not None


def test_task_downloader_falls_back_for_legacy_injected_downloader(tmp_path: Path) -> None:
    """兼容契约：既有的三参假下载器（不吃关键字参数）照旧可用，零改动。"""
    def legacy(url: str, dest: Path, on_progress) -> str:
        dest.write_bytes(url.encode("utf-8"))
        on_progress(len(url))
        return "c" * 64

    download = as_task_downloader(legacy, cancel=threading.Event(), before_retry=None)
    assert download("https://x/k230.zip", tmp_path / "k230.zip", lambda n: None,
                    expected_size=1, expected_sha256="c" * 64) == "c" * 64
