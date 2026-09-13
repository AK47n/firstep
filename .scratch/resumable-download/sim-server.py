# -*- coding: utf-8 -*-
"""本地可控 HTTP 服务器：给「断点续传」造真 socket 判据（工单 resumable-download/01）。

用途：让「断了能不能接上」这句话可以在**真 socket 上重复复现**，而不是靠拔网线或撞运气。
载荷是确定性伪随机字节，启动时打印 SHA256 与字节数，供探针对账。

用法::

    python sim-server.py [--port 8031] [--size 4194304] [--seed 20260913]

行为开关走查询串（每个用例一份 URL，不必换端口）::

    /p?mode=stable         正常发完（支持 Range）
    /p?mode=ignore-range   忽略 Range，恒 200 发整份（模拟代理/镜像剥掉断点能力）
    /p?mode=cut&fraction=0.4   发到 40% 直接关连接（模拟断流）
    /p?mode=stall&fraction=0.4 发到 40% 后不再发、也不关连接（模拟卡死）
    /p?mode=deadline&seconds=6 先睡 6 秒再发整份（模拟「长时间零字节」）
    /p?mode=slow&kbps=64       限速（模拟弱网，但连接是好的）

`size` 可用查询串覆盖单次请求（用于小卷/到点用例）。

退出：Ctrl+C，或向 stdin 写一行（父进程据此收摊）；两处都会关闭监听并退出。
"""

from __future__ import annotations

import argparse
import hashlib
import random
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CHUNK = 32 * 1024
STALL_HOLD_SECONDS = 8.0  # 卡死模式的兜底等待：够判「对端零字节」，又不拖慢探针

ARGS = argparse.Namespace(port=8031, size=4 * 1024 * 1024, seed=20260913)
PAYLOAD = b""
PAYLOAD_SHA = ""

# 请求台账：探针据此断言「第 N 次请求带没带 Range、从哪开始」
REQUESTS: list[dict[str, object]] = []
_LOCK = threading.Lock()


def _build_payload(size: int, seed: int) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


def _record(path: str, range_header: str, start: int, status: int) -> None:
    with _LOCK:
        REQUESTS.append(
            {"n": len(REQUESTS) + 1, "path": path, "range": range_header,
             "start": start, "status": status}
        )


def _parse_range(header: str, total: int) -> tuple[int, int] | None:
    """返回 (start, end) 闭区间；None = 语法不认识（按整份发，HTTP 允许忽略 Range）。"""
    if not header or not header.startswith("bytes="):
        return None
    spec = header[len("bytes="):].strip()
    if "," in spec:  # 多段不实现：当不认识
        return None
    first, _, last = spec.partition("-")
    try:
        if first == "":  # bytes=-N 后缀式
            n = int(last)
            if n <= 0:
                return None
            return max(0, total - n), total - 1
        start = int(first)
        end = int(last) if last else total - 1
    except ValueError:
        return None
    if start >= total:
        return None  # 交给调用方发 416
    return start, min(end, total - 1)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "firstep-sim/1.0"

    def log_message(self, *a) -> None:  # 静音：探针自己打印台账
        pass

    # -- GET ---------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/ping":
            self._send_bytes(200, b"ok", "text/plain")
            return
        if parsed.path == "/requests":
            import json
            body = json.dumps(REQUESTS).encode("utf-8")
            self._send_bytes(200, body, "application/json")
            return
        if parsed.path != "/p":
            self._send_bytes(404, b"not found", "text/plain")
            return

        q = parse_qs(parsed.query)
        mode = (q.get("mode") or ["stable"])[0]
        size = int((q.get("size") or [str(ARGS.size)])[0])
        payload = PAYLOAD[:size] if size <= len(PAYLOAD) else PAYLOAD

        range_header = self.headers.get("Range") or ""
        total = len(payload)

        # mode=deadline：先睡够，再决定发不发（模拟对端长时间零字节）
        if mode == "deadline":
            try:
                time.sleep(float((q.get("seconds") or ["6"])[0]))
            except ValueError:
                time.sleep(6.0)

        if mode == "ignore-range":
            start, end, status = 0, total - 1, 200
            _record(parsed.path, range_header, 0, status)
            self._send_bytes(status, payload, "application/octet-stream",
                             accept_ranges="none")
            return

        rng = _parse_range(range_header, total)
        if rng is None:
            if range_header and range_header.startswith("bytes="):
                # 语法认识但越界 → 416（探针的「本地比远端大」用例）
                _record(parsed.path, range_header, total, 416)
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            start, end, status = 0, total - 1, 200
        else:
            start, end = rng
            status = 206

        _record(parsed.path, range_header, start, status)
        blob = payload[start:end + 1]

        headers = {
            "Content-Type": "application/octet-stream",
            "Accept-Ranges": "bytes" if mode != "ignore-range" else "none",
        }
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"

        if mode == "cut":
            frac = float((q.get("fraction") or ["0.4"])[0])
            keep = max(1, int(len(blob) * frac))
            self._stream(status, blob[:keep], headers, declared=len(blob))
            try:  # 模拟断流：不发完就关，客户端会拿到 IncompleteRead / 连接重置
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True
            return

        if mode == "stall":
            frac = float((q.get("fraction") or ["0.4"])[0])
            keep = max(1, int(len(blob) * frac))
            self._stream(status, blob[:keep], headers, declared=len(blob))
            self._stall_until_client_gives_up()
            return

        if mode == "slow":
            kbps = float((q.get("kbps") or ["64"])[0])
            self._stream_slow(status, blob, headers, kbps)
            return

        self._stream(status, blob, headers, declared=len(blob))

    # -- 发送原语 -----------------------------------------------------------
    def _send_bytes(self, status: int, body: bytes, ctype: str,
                    accept_ranges: str = "bytes") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", accept_ranges)
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            self.close_connection = True

    def _write_chunk(self, data: bytes) -> bool:
        try:
            self.wfile.write(data)
            self.wfile.flush()
            return True
        except OSError:
            self.close_connection = True
            return False

    def _stream(self, status: int, body: bytes, headers: dict[str, str],
                declared: int) -> None:
        """发响应头 + body；declared 可 > len(body)（模拟断流：声明得多、发得少）。"""
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(declared))
        self.end_headers()
        for i in range(0, len(body), CHUNK):
            if not self._write_chunk(body[i:i + CHUNK]):
                return

    def _stream_slow(self, status: int, body: bytes, headers: dict[str, str],
                     kbps: float) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        per_chunk = CHUNK / max(1.0, kbps * 1024.0)
        for i in range(0, len(body), CHUNK):
            if not self._write_chunk(body[i:i + CHUNK]):
                return
            time.sleep(per_chunk)

    def _stall_until_client_gives_up(self) -> None:
        """不再发任何字节、也不关连接——直到客户端自己断开（或 STALL_HOLD_SECONDS 兜底）。

        兜底值故意短：卡死用例要的是「对端零字节」，探针不需要真的等两分钟。
        """
        deadline = time.time() + STALL_HOLD_SECONDS
        while time.time() < deadline:
            try:
                self.connection.settimeout(1.0)
                if self.connection.recv(1) == b"":
                    break  # 对端关了
            except socket.timeout:
                continue
            except OSError:
                break
        self.close_connection = True


def main() -> int:
    global PAYLOAD, PAYLOAD_SHA
    parser = argparse.ArgumentParser(description="firstep 断点续传模拟服务器")
    parser.add_argument("--port", type=int, default=8031)
    parser.add_argument("--size", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--seed", type=int, default=20260913)
    ns = parser.parse_args()
    ARGS.port, ARGS.size, ARGS.seed = ns.port, ns.size, ns.seed

    PAYLOAD = _build_payload(ARGS.size, ARGS.seed)
    PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()

    server = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler)
    server.daemon_threads = True
    actual = server.server_address[1]
    print(f"READY port={actual} size={len(PAYLOAD)} sha256={PAYLOAD_SHA}", flush=True)

    stopper = threading.Thread(target=_wait_for_exit, args=(server,), daemon=True)
    stopper.start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _wait_for_exit(server: ThreadingHTTPServer) -> None:
    """父进程关掉 stdin 或写一行 → 收摊。"""
    try:
        sys.stdin.readline()
    except Exception:
        pass
    server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
