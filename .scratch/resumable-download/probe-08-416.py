# -*- coding: utf-8 -*-
"""工单 08：服务器 `416` 与本地坏半成品——**先证明现状是红的**。

要修的两个死胡同（工单 07 双轴评审翻出来、当时留作显式决策点）：

1. **服务器回 `416`**（Range 起点超出资源总长）：现状是 HTTPError 直接冒泡，
   任务 `failed`、半成品留在盘上；用户点重试 → 仍带同样的 Range → 仍 416。
   **同一个坏半成品会一直卡住这一卷**，只能手工删文件才能恢复。
   spec 断点契约表要求：「删掉从 0 重下」。
2. **本地半成品比远端还大**：现状抛 `DownloadLocalCorruptError`，它在
   `_NOT_RETRYABLE` 里 → 不重试、直接失败。spec 同一行要求「删掉从 0 重下」。

本探针在**实现之前**跑，两条都必须红；实现之后再跑必须绿。
判据用真 HTTP 本地线程服务器（照 `probe-07-review-claims.py` 的做法），
因为要判的正是「客户端与服务器之间的 Range 协议来回」。

用法：`python .scratch/resumable-download/probe-08-416.py`
产出：`verify-08-416-baseline.txt`（实现前）/ `verify-08-416.txt`（实现后）
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
for _name in [n for n in list(sys.modules)
              if n == "contest_generator" or n.startswith("contest_generator.")]:
    del sys.modules[_name]

from contest_generator import download_resume  # noqa: E402

PAYLOAD = bytes((i * 53 + 7) % 256 for i in range(300 * 1024))
LINES: list[str] = []
RESULTS: dict = {}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def sha_of(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    """按 server.mode：
    - `416-always`  : 带 Range 就 416，不带 Range 正常发（= 本地半成品坏死）
    - `416-once`    : 第一次带 Range 416，之后正常（= 服务器上文件变小过）
    """

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # noqa: ANN002 —— 静音
        pass

    def do_GET(self):  # noqa: ANN201
        mode = self.server.mode                        # type: ignore[attr-defined]
        ranges = self.server.ranges                     # type: ignore[attr-defined]
        rng = self.headers.get("Range")
        ranges.append(rng or "")
        with_range = bool(rng)
        index = sum(1 for r in ranges if r)             # 第几次带 Range 的请求（1 起）

        if with_range and (mode == "416-always" or (mode == "416-once" and index == 1)):
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(PAYLOAD)}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if with_range:
            start = int(rng.split("=", 1)[1].split("-", 1)[0])
            if start >= len(PAYLOAD):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{len(PAYLOAD)}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = PAYLOAD[start:]
            self.send_response(206)
            self.send_header("Content-Range",
                             f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            body = PAYLOAD
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server:
    def __init__(self, mode: str) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.mode = mode        # type: ignore[attr-defined]
        self.httpd.ranges = []        # type: ignore[attr-defined]
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def ranges(self) -> list[str]:
        return self.httpd.ranges      # type: ignore[attr-defined]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/payload.bin"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def run_case(name: str, work: Path, mode: str, *, seed: int,
             expected_size: int | None = None,
             timeout: float = 5.0) -> dict:
    server = _Server(mode)
    dest = work / f"{name}.bin"
    if seed:
        # ⚠️ 别写 `PAYLOAD[:seed]`：seed > len(PAYLOAD) 时切片会**静默截到载荷长度**，
        # 于是「本地比远端还大」这个用例其实铺的是「正好一整卷」，走的是
        # 「已下完直接进校验」那条早返回——探针会在**修与不修两种实现下都报 ✓**
        # （工单 08 自己踩到的假绿：基线里这一格本该红却是绿的）。
        # 超过载荷长度就补零字节，才真的造出「比远端大」。
        if seed <= len(PAYLOAD):
            dest.write_bytes(PAYLOAD[:seed])
        else:
            dest.write_bytes(PAYLOAD + b"\x00" * (seed - len(PAYLOAD)))
    sha = ""
    error = ""
    try:
        result = download_resume.resumable_download(
            server.url, dest, lambda n: None,
            expected_size=len(PAYLOAD) if expected_size is None else expected_size,
            expected_sha256=sha_of(PAYLOAD),
            timeout=timeout,
        )
        sha = result.sha256
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    on_disk = dest.stat().st_size if dest.is_file() else 0
    outcome = {
        "case": name,
        "mode": mode,
        "seed_bytes": seed,
        "range_headers": list(server.ranges),
        "error": error,
        "sha_ok": sha == sha_of(PAYLOAD),
        "on_disk": on_disk,
        "sidecar_left": download_resume.marker_for(dest).is_file(),
    }
    server.close()
    return outcome


def main() -> int:
    log("# 工单 08 探针：服务器 416 / 本地坏半成品 —— 现状（实现前应为红）")
    log("")
    log(f"仓库：{REPO}")
    log(f"载荷：{len(PAYLOAD)} 字节")
    log("")
    work = Path(tempfile.mkdtemp(prefix="fe08-416-"))
    cases: list[dict] = []
    try:
        log("## 用例一：服务器**恒**回 416（本地半成品坏死在这一卷上）")
        log("   铺 102400 字节半成品；带 Range 的请求恒 416，不带 Range 正常")
        c1 = run_case("relentless-416", work, "416-always", seed=102400, timeout=3.0)
        cases.append(c1)
        log(f"   实测 error={c1['error']!r}")
        log(f"   实测 请求数={len(c1['range_headers'])} / 最终 sha_ok={c1['sha_ok']}"
            f" / 半成品在盘={c1['on_disk']} / 边车在={c1['sidecar_left']}")
        log(f"   → 「删掉半成品、从 0 重下并成功」"
            f"{'成立' if c1['sha_ok'] else '**不成立（现状：卡死）**'}")
        log("")

        log("## 用例二：服务器**第一次**带 Range 回 416，之后正常")
        log("   （= 服务器上的文件曾经变小过；客户端半成品偏大）")
        c2 = run_case("transient-416", work, "416-once", seed=102400, timeout=3.0)
        cases.append(c2)
        log(f"   实测 error={c2['error']!r}")
        log(f"   实测 请求数={len(c2['range_headers'])} / 最终 sha_ok={c2['sha_ok']}")
        log(f"   → 「清掉重来一次就好」"
            f"{'成立' if c2['sha_ok'] else '**不成立（现状：一次 416 就判死）**'}")
        log("")

        log("## 用例三：本地半成品比清单还大（不经过网络就能判）")
        c3 = run_case("local-bigger", work, "416-once",
                      seed=len(PAYLOAD) + 4096, timeout=3.0)
        cases.append(c3)
        log(f"   实测 error={c3['error']!r}")
        log(f"   实测 请求数={len(c3['range_headers'])} / 最终 sha_ok={c3['sha_ok']}")
        log(f"   → 「删掉坏的、从 0 重下并成功」"
            f"{'成立' if c3['sha_ok'] else '**不成立（现状：判死）**'}")
        log("")

        log("## 用例四：分类函数对 416 的判定")
        err416 = urllib.error.HTTPError("https://x/p.zip", 416, "range not satisfiable",
                                        {}, None)  # type: ignore[arg-type]
        retryable = download_resume.is_retryable(err416)
        log(f"   is_retryable(416) = {retryable}")
        log(f"   describe_network_error(416) = {download_resume.describe_network_error(err416)!r}")
        log("   → 「416 不当可重试的网络错误」"
            f"{'成立' if not retryable else '**不成立（现状：会被无上限重试）**'}")
        log("   （口径：416 的本地补救在 _attempt 里只做一次；再做还是 416，"
            "当可重试就变成每 60 秒撞一次墙的安静死循环）")
        log("")
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)

    RESULTS["cases"] = cases
    err416 = urllib.error.HTTPError("https://x/p.zip", 416, "x", {}, None)  # type: ignore[arg-type]
    verdict = {
        "relentless_416_recovers": cases[0]["sha_ok"],
        "transient_416_recovers": cases[1]["sha_ok"],
        "local_bigger_recovers": cases[2]["sha_ok"],
        # 口径是**否定式**：416 不该被当成可重试的网络错误（否则无上限重试
        # 会变成每 60 秒撞一次墙）。工单 08 修完的正是这个「不重试的失败」，
        # 而不是「重试没有上限」——后者是 spec 明确要的产品行为。
        "416_is_not_a_retryable_network_error": not download_resume.is_retryable(err416),
    }
    RESULTS["verdict"] = verdict
    log("## 总判")
    all_green = all(verdict.values())
    for key, value in verdict.items():
        log(f"  {key}：{'✓' if value else '✗（红）'}")
    log(f"  → 总判：{'PASS（实现后应有的样子）' if all_green else 'FAIL（实现前的红基线）'}")
    (HERE / "verify-08-416.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    target = "verify-08-416.txt" if all_green else "verify-08-416-baseline.txt"
    (HERE / target).write_text("\n".join(LINES) + "\n", encoding="utf-8")
    print(f"证据已写：{target} / verify-08-416.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
