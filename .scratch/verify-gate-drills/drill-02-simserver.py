# -*- coding: utf-8 -*-
"""B2 用的本地可控下载服务器（工单 sandbox-drill/02）。

与 `.scratch/resumable-download/sim-server.py` **同族、行为照抄**（stable / ignore-range /
cut / stall / slow / deadline），两处刻意的差异：

1. **载荷可以是一个真文件**（`--file`）——B2 要的不只是「字节流断没断」，还要让下载
   产物**一路走完替换链**（更新器会拿它当 zip 解压）。随机字节不是 zip，
   替换链会在预检处失败，于是「终态 done」这一格就永远看不到。
2. **多两个开关**：`kbps` 对**所有模式**生效（把「断流 + 弱网」叠起来，
   否则 4 MB 在本机是秒级，`retry_count` 根本来不及被 status 轮询看到）；
   `mode=corrupt` 在发送前把载荷里某个字节改坏（造**真·校验失败**：字节不对，长度对）。

载荷与台账口径与 sim-server 一致：启动时打印 `READY port=… size=… sha256=…`，
sha256 是**干净载荷**的哈希（corrupt 模式改的是发出去的字节，不改这个值——
所以客户端拿到的哈希必然对不上，这正是我们造的判据）。

用法::

    python drill-02-simserver.py --port 0 --file <真 zip 路径>
    python drill-02-simserver.py --port 8031 --size 4194304      # 不用文件时照 sim-server 造随机载荷

行为开关（查询串，每个用例一份 URL）::

    /p?mode=stable
    /p?mode=slow&kbps=64
    /p?mode=cut&fraction=0.4&cut_runs=2&kbps=512
    /p?mode=stall&fraction=0.4&cut_runs=1
    /p?mode=corrupt&at=1024
    /p?mode=ignore-range
    /p?mode=deadline&seconds=6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CHUNK = 32 * 1024
# 卡死模式发完首块后还要安静多久（必须长于客户端读超时 30s，理由同 sim-server）
STALL_HOLD_SECONDS = 35.0

ARGS = argparse.Namespace(port=0, size=4 * 1024 * 1024, seed=20260918, file="")
PAYLOAD = b""
PAYLOAD_SHA = ""
REQUESTS: list[dict[str, object]] = []
_LOCK = threading.Lock()


def _build_payload(size: int, seed: int) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


def _request_index() -> int:
    with _LOCK:
        return max(1, len(REQUESTS))


def _record(path: str, mode: str, range_header: str, start: int, status: int) -> None:
    with _LOCK:
        REQUESTS.append(
            {"n": len(REQUESTS) + 1, "path": path, "mode": mode,
             "range": range_header, "start": start, "status": status}
        )


def _parse_range(header: str, total: int) -> tuple[int, int] | None:
    if not header or not header.startswith("bytes="):
        return None
    spec = header[len("bytes="):].strip()
    if "," in spec:
        return None
    first, _, last = spec.partition("-")
    try:
        if first == "":
            n = int(last)
            if n <= 0:
                return None
            return max(0, total - n), total - 1
        start = int(first)
        end = int(last) if last else total - 1
    except ValueError:
        return None
    if start >= total:
        return None
    return start, min(end, total - 1)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "firstep-drill-sim/1.0"

    def log_message(self, *a) -> None:  # 静音：探针自己打印台账
        pass

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/ping":
            self._send_bytes(200, b"ok", "text/plain")
            return
        if parsed.path == "/requests":
            with _LOCK:
                body = json.dumps(REQUESTS).encode("utf-8")
            self._send_bytes(200, body, "application/json")
            return
        if parsed.path == "/reset":
            with _LOCK:
                REQUESTS.clear()
            self._send_bytes(200, b"reset", "text/plain")
            return
        if parsed.path != "/p":
            self._send_bytes(404, b"not found", "text/plain")
            return

        q = parse_qs(parsed.query)
        mode = (q.get("mode") or ["stable"])[0]
        kbps = float((q.get("kbps") or ["0"])[0])
        size = int((q.get("size") or [str(len(PAYLOAD))])[0])
        payload = PAYLOAD[:size] if size <= len(PAYLOAD) else PAYLOAD
        total = len(payload)

        range_header = self.headers.get("Range") or ""

        if mode == "deadline":
            try:
                time.sleep(float((q.get("seconds") or ["6"])[0]))
            except ValueError:
                time.sleep(6.0)

        if mode == "ignore-range":
            requested = _parse_range(range_header, total)
            start = requested[0] if requested else 0
            _record(parsed.path, mode, range_header, start, 200)
            self._send_bytes(200, payload, "application/octet-stream",
                             accept_ranges="none")
            return

        rng = _parse_range(range_header, total)
        if rng is None:
            if range_header and range_header.startswith("bytes="):
                _record(parsed.path, mode, range_header, total, 416)
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            start, end, status = 0, total - 1, 200
        else:
            start, end = rng
            status = 206

        _record(parsed.path, mode, range_header, start, status)
        blob = bytearray(payload[start:end + 1])

        if mode == "corrupt":
            # 真·内容损坏：长度一字不改，只把其中若干字节改坏 →
            # 客户端下满、算出来的 SHA256 与清单对不上 = 产品该报「校验失败」。
            offset = int((q.get("at") or ["1024"])[0])
            count = int((q.get("count") or ["16"])[0])
            for i in range(count):
                idx = offset + i
                if 0 <= idx < len(blob):
                    blob[idx] = (blob[idx] + 1) % 256

        headers = {
            "Content-Type": "application/octet-stream",
            "Accept-Ranges": "bytes",
        }
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"

        if mode == "cut":
            frac = float((q.get("fraction") or ["0.4"])[0])
            cut_runs = int((q.get("cut_runs") or ["2"])[0])
            if _request_index() <= cut_runs:
                keep = max(1, int(len(blob) * frac))
                self._stream(status, bytes(blob[:keep]), headers, declared=len(blob),
                             kbps=kbps)
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.close_connection = True
                return

        if mode == "stall":
            cut_runs = int((q.get("cut_runs") or ["1"])[0])
            if _request_index() <= cut_runs:
                frac = float((q.get("fraction") or ["0.4"])[0])
                keep = max(1, int(len(blob) * frac))
                self._stream(status, bytes(blob[:keep]), headers, declared=len(blob),
                             kbps=kbps)
                self._stall_until_client_gives_up()
                return

        self._stream(status, bytes(blob), headers, declared=len(blob), kbps=kbps)

    # -- 发送原语 ---------------------------------------------------------
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
                declared: int, kbps: float = 0.0) -> None:
        """发响应头 + body；kbps>0 时限速（对每个模式都生效，见模块 docstring 第 2 条）。"""
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(declared))
        self.end_headers()
        per_chunk = CHUNK / (kbps * 1024.0) if kbps > 0 else 0.0
        for i in range(0, len(body), CHUNK):
            if not self._write_chunk(body[i:i + CHUNK]):
                return
            if per_chunk:
                time.sleep(per_chunk)

    def _stall_until_client_gives_up(self) -> None:
        deadline = time.time() + STALL_HOLD_SECONDS
        while time.time() < deadline:
            try:
                self.connection.settimeout(1.0)
                if self.connection.recv(1) == b"":
                    break
            except socket.timeout:
                continue
            except OSError:
                break
        self.close_connection = True


def main() -> int:
    global PAYLOAD, PAYLOAD_SHA
    parser = argparse.ArgumentParser(description="firstep B2 本地可控下载服务器")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--size", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--seed", type=int, default=20260918)
    parser.add_argument("--file", default="", help="用真文件的字节当载荷（必须是可当 zip 用的文件）")
    ns = parser.parse_args()
    ARGS.port, ARGS.size, ARGS.seed, ARGS.file = ns.port, ns.size, ns.seed, ns.file

    if ARGS.file:
        PAYLOAD = Path(ARGS.file).read_bytes()
        ARGS.size = len(PAYLOAD)
    else:
        PAYLOAD = _build_payload(ARGS.size, ARGS.seed)
    PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()

    server = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler)
    server.daemon_threads = True
    actual = server.server_address[1]
    print(f"READY port={actual} size={len(PAYLOAD)} sha256={PAYLOAD_SHA} "
          f"source={ARGS.file or 'seeded-random'}", flush=True)

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
    try:
        sys.stdin.readline()
    except Exception:
        pass
    server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
