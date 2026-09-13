"""单测用的本机字节服务器（工单 resumable-download/03 起）。

**为什么单测里也要真 socket**：工单 03 判的是「任务层 + 缺省下载器」联手的端到端
行为——失败后半成品留没留、边车写没写、下次从哪个偏移接着下。注入假下载器的用例
证明不了这些：假下载器不会自己写边车，也不会真发 `Range`。

与探针那边的 `sim-server.py` 不是一个东西，别混：

| | 本文件（`tests/_byte_server.py`） | `.scratch/resumable-download/sim-server.py` |
|---|---|---|
| 跑在哪 | 单测进程内的线程 | 独立子进程（探针起它） |
| 剧本 | 只切流（`cut_runs` 次） | 六种：stable/ignore-range/cut/stall/deadline/slow |
| 判据强度 | 够判任务层接线（偏移序列 + 哈希） | 真机探针那一档 |

强度取舍的理由写在 spec「测试决策」：真 socket + sleep 会让 CI 变脆，
所以探针不进 `tests/`；这里只补「任务层接线」那一小段真网络，不重做探针的六种剧本。
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    payload = b""
    cut_after = 0
    cut_runs = 0
    ignore_range = False
    seen: list[int] = []

    def do_GET(self) -> None:            # noqa: N802 —— BaseHTTPRequestHandler 接口
        start = 0
        header = self.headers.get("Range") or ""
        if header.startswith("bytes=") and header.endswith("-"):
            start = int(header[len("bytes="):-1] or 0)
        type(self).seen.append(start)
        total = len(self.payload)
        if type(self).ignore_range:
            # 忽略 Range：恒 200 发整份（模拟代理 / 镜像剥掉断点能力）。
            # 台账仍如实记下「客户端要的是哪一段」——判据看的是这个。
            # 若同时带 cut 剧本，就先断一次（客户端于是重试，而重试仍被整份重发）。
            body = self.payload
            cutting = type(self).cut_runs > 0
            if cutting:
                type(self).cut_runs -= 1
                body = body[: type(self).cut_after]
            self.send_response(200)
            self.send_header("Content-Length", str(total))
            self.send_header("Accept-Ranges", "none")
            if cutting:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return
        if start >= total:                   # 本地已完整还来要：如实回 416
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{total}")
            self.end_headers()
            return
        body = self.payload[start:]
        cutting = type(self).cut_runs > 0
        if cutting:                          # 按剧本切：只切前 N 次（「坏一阵就好」）
            type(self).cut_runs -= 1
            body = body[: type(self).cut_after]
        self.send_response(206 if start else 200)
        # 声明的是**这一份资源该有的长度**，不是「我实际打算发多少」——真实服务器
        # 中途断流时头部早就发出去了，客户端只能靠「少收了」自己判出来。
        # 反过来（声明短长度）是另一码事：那是「发布信息不一致」，属不可重试。
        self.send_header("Content-Length", str(len(self.payload) - start))
        self.send_header("Accept-Ranges", "bytes")
        if start:
            self.send_header("Content-Range", f"bytes {start}-{total - 1}/{total}")
        if cutting:
            self.send_header("Connection", "close")   # 发完就断，别让客户端干等
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: ANN002 —— 别把测试输出弄脏
        return


class ByteServer:
    """字节服务器的外部把手：`url` / `starts`（每次请求的起始偏移）。"""

    def __init__(self, payload: bytes, *, cut_after: int = 0,
                 cut_runs: int = 0, ignore_range: bool = False) -> None:
        self.payload = payload
        self.cut_after = cut_after
        self.cut_runs = cut_runs
        self.ignore_range = ignore_range
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._seen: list[int] = []

    def __enter__(self) -> "ByteServer":
        seen: list[int] = []
        handler = type("_BoundHandler", (_Handler,), {
            "payload": self.payload, "cut_after": self.cut_after,
            "cut_runs": self.cut_runs, "ignore_range": self.ignore_range,
            "seen": seen,
        })
        self._seen = seen
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    @property
    def url(self) -> str:
        assert self.httpd is not None
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/part"

    @property
    def starts(self) -> list[int]:
        """每次请求的起始偏移（工单 01 探针在真机上用的同一条判据）。"""
        return self._seen
