# -*- coding: utf-8 -*-
"""本地可控 HTTP 服务器：给「断点续传」造真 socket 判据（工单 resumable-download/01）。

用途：让「断了能不能接上」这句话可以在**真 socket 上重复复现**，而不是靠拔网线或撞运气。
载荷是确定性伪随机字节，启动时打印 SHA256 与字节数，供探针对账。

用法::

    python sim-server.py [--port 8031] [--size 4194304] [--seed 20260913]

行为开关走查询串（每个用例一份 URL，不必换端口）::

    /p?mode=stable         正常发完（支持 Range）
    /p?mode=ignore-range   忽略 Range，恒 200 发整份（模拟代理/镜像剥掉断点能力）
    /p?mode=cut&fraction=0.4&cut_runs=3   发到 40% 直接关连接（只切前 3 次，之后正常发完）
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
# 卡死模式发完首块后还要安静多久。
# 必须**长于客户端的读超时**（download_resume.SOCKET_TIMEOUT_SECONDS = 30），
# 否则先关连接的是服务器，客户端走的是「读干净了但没读满」那条路，
# 验不到「零字节卡死被超时判出来」——这正是本模式存在的理由。
STALL_HOLD_SECONDS = 35.0

ARGS = argparse.Namespace(port=8031, size=4 * 1024 * 1024, seed=20260913)
PAYLOAD = b""
PAYLOAD_SHA = ""

# 请求台账：探针据此断言「第 N 次请求带没带 Range、从哪开始」
REQUESTS: list[dict[str, object]] = []
_LOCK = threading.Lock()


def _build_payload(size: int, seed: int) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


def _request_index() -> int:
    """**当前这次**请求是第几次（1 起）。`_record` 已把本次记进台账，故取长度即可。

    台账被 `/reset` 清过之后重新从 1 起——`cut_runs` / `stall.cut_runs` 的语义
    就是「每个用例内的前几次请求」，所以探针每例开始前会调一次 `/reset`。
    """
    with _LOCK:
        return max(1, len(REQUESTS))


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
        if parsed.path == "/reset":
            # 清台账：`cut_runs` / `stall.cut_runs` 按「第几次请求」生效，
            # 跨用例累加会让它们永远不满足（探针实测踩过：stall 用例 0.02 秒就"通过"了）。
            # 探针每例开始前调一次，用例之间才互不干扰。
            with _LOCK:
                REQUESTS.clear()
            self._send_bytes(200, b"reset", "text/plain")
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
            # 忽略 Range：恒 200 发整份（模拟代理 / 镜像剥掉断点能力）。
            # **台账记的是「客户端要的是哪一段」**（`_parse_range` 从 Range 头解析出的起点），
            # 不是「服务器实际从哪发」——本模式的判据正是「客户端带了 Range，服务器没理会」，
            # 记成 0 会让这条判据永远看不到「带了却没被理会」这件事（工单 03 实测踩到：
            # 任务层已经正确地从断点重下，台账却显示起始偏移一直是 0）。
            requested = _parse_range(range_header, total)
            start = requested[0] if requested else 0
            _record(parsed.path, range_header, start, 200)
            self._send_bytes(200, payload, "application/octet-stream",
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
            # 只切前 cut_runs 次请求，之后正常发完。
            # 为什么要这样：每次都切掉「剩余部分的 40%」在数学上会收敛（0.6^n → 0），
            # 但工程上要几十轮才凑满，探针会跑到天荒地老。真实的坏网络也是「坏一阵就好」，
            # 所以默认切 3 次——既够验「断了能接上」，又能在秒级跑完。
            frac = float((q.get("fraction") or ["0.4"])[0])
            cut_runs = int((q.get("cut_runs") or ["3"])[0])
            if _request_index() <= cut_runs:
                keep = max(1, int(len(blob) * frac))
                self._stream(status, blob[:keep], headers, declared=len(blob))
                try:  # 模拟断流：不发完就关，客户端会拿到 IncompleteRead / 连接重置
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.close_connection = True
                return

        if mode == "stall":
            # 与 cut 同理：卡死只卡前几次，之后正常发完（否则探针要一轮轮等 35 秒兜底）。
            # 默认只卡 1 次——这一次就够验「零字节卡死被读超时判出来，然后重连接着下」。
            cut_runs = int((q.get("cut_runs") or ["1"])[0])
            if _request_index() <= cut_runs:
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
