"""可续下载域模块测试（工单 resumable-download/02）。

覆盖：退避序列、错误分类与中文文案、以及 `resumable_download` 的**偏移判定**
（续传起始偏移 / 截断必须失败 / 服务器忽略 Range 时从 0 重下 / 本地坏 / 取消在退避中生效）。

不碰真网络：响应由 `_FakeServer` + 注入的 `opener` 提供（spec 里定的注入缝）。
真 socket 行为由 `.scratch/resumable-download/probe-01-resume.py` 那一档回答。
"""

from __future__ import annotations

import hashlib
import threading
import urllib.error
from http.client import IncompleteRead
from pathlib import Path

import pytest

from contest_generator.download_resume import (
    DownloadCancelledError,
    DownloadLocalCorruptError,
    DownloadResult,
    DownloadSizeMismatchError,
    DownloadTruncatedError,
    describe_network_error,
    error_kind,
    file_sha256,
    is_retryable,
    marker_for,
    parse_content_range,
    read_partial_marker,
    resumable_download,
    retry_delay,
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


def test_retryable_classification() -> None:
    assert is_retryable(OSError("socket"))
    assert is_retryable(TimeoutError("slow"))
    assert is_retryable(IncompleteRead(b"partial", 100))
    assert is_retryable(_http_error(500))
    assert is_retryable(_http_error(429))
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

def test_local_larger_than_remote_clears_and_reports(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\x00" * (len(PAYLOAD) + 10))
    server = _FakeServer()
    with pytest.raises(DownloadLocalCorruptError):
        resumable_download("https://x/p.zip", dest, lambda n: None, opener=server,
                           expected_size=len(PAYLOAD))
    assert not dest.is_file()            # 本地坏的那份要清掉
    assert server.n_requests == 0        # 不可重试，且不必发请求


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
