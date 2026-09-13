# -*- coding: utf-8 -*-
"""工单 07：**双轴评审发现的五处断言** 的独立复现（真 HTTP，本地线程服务器）。

评审（Spec 轴）报了五条「spec 说要 X、代码做 Y」。评审不是判据——**复现才是**。
本探针逐条把评审的话当假设来验，每条给出「评审说 / 实测」两列，跑完打总判。

五条假设：
1. `resumed_from` 语义与 spec 相反（spec = 「本次真正用 Range 接上的起始偏移」）。
   → **已修**（改由 `_AttemptOutcome.resumed_at` 回填 + 单测
   `test_resumed_from_reports_whether_range_actually_connected`）；复跑应报「不成立」。
2. 服务器 `416` 没被处理（spec 断点契约表要求「删掉从 0 重下」）。
   → **工单 08 已修**（`_attempt` 里就地清掉、去掉 Range 重来）。本探针**保留原用例**
   作为回归：修好后它应当报「不成立」（该 JSON 的状态即「修复后」）；
   专门的判据与红基线在 `probe-08-416.py`。**别把这两支探针的结论混读**——
   工单 07 当时记的是「未修、留决策点」，工单 08 记的是「已修 + 反向验证」。
3. 「本地比远端大」清了半成品却**不重下**（spec 要求「删掉从 0 重下」）。
4. 「已下字节 == 卷大小 → 直接进校验」那条分支成功后会**留孤儿边车**
   （spec：「成功 / 校验失败时一并删除边车与半成品，不留孤儿」）。
5. 对照组：正常整份下载，边车该被清掉（防探针自己假绿）。

用法：`python .scratch/resumable-download/probe-07-review-claims.py`
产出：`verify-07-review-claims.txt` + `.json`
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

PAYLOAD = bytes((i * 37 + 11) % 256 for i in range(300 * 1024))   # 300 KB 确定性载荷
PAYLOAD_SHA = download_resume.file_sha256  # 占位，下面用真实函数
LINES: list[str] = []
RESULTS: dict = {}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def sha_of(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    """按 server.mode 切换行为：
    - `full`         : 正常整份（忽略 Range 也可，看 mode）
    - `ignore-range` : 恒返回 200 整份
    - `range-416`    : 只要带 Range 就回 416
    """

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # noqa: ANN002 —— 静音
        pass

    def do_GET(self):  # noqa: ANN201
        mode = self.server.mode                      # type: ignore[attr-defined]
        ranges = self.server.ranges                   # type: ignore[attr-defined]
        rng = self.headers.get("Range")
        ranges.append(rng or "")
        if mode == "range-416" and rng:
            body = b""
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(PAYLOAD)}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if rng and mode != "ignore-range":
            start = int(rng.split("=", 1)[1].split("-", 1)[0])
            if start >= len(PAYLOAD):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{len(PAYLOAD)}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = PAYLOAD[start:]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            body = PAYLOAD
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server:
    def __init__(self, mode: str) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.mode = mode            # type: ignore[attr-defined]
        self.httpd.ranges = []            # type: ignore[attr-defined]
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def ranges(self) -> list[str]:
        return self.httpd.ranges          # type: ignore[attr-defined]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/payload.bin"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def run_case(name: str, work: Path, mode: str, *, seed: int = 0,
             expected_size: int | None = None,
             expected_sha256: str | None = None,
             seed_from_payload: bool = True) -> dict:
    """跑一个假设。seed = 预铺的字节数（从 PAYLOAD 头部取）。"""
    server = _Server(mode)
    dest = work / f"{name}.bin"
    if seed:
        dest.write_bytes(PAYLOAD[:seed] if seed_from_payload else b"\x00" * seed)
    got_sha = ""
    error = ""
    result = None
    try:
        result = download_resume.resumable_download(
            server.url, dest,
            lambda n: None,
            expected_size=len(PAYLOAD) if expected_size is None else expected_size,
            expected_sha256=sha_of(PAYLOAD) if expected_sha256 is None else expected_sha256,
        )
        got_sha = result.sha256
    except Exception as exc:  # noqa: BLE001 —— 异常也是判据的一部分
        error = f"{type(exc).__name__}: {exc}"
    on_disk = dest.stat().st_size if dest.is_file() else 0
    marker = download_resume.marker_for(dest)
    outcome = {
        "case": name,
        "mode": mode,
        "seed_bytes": seed,
        "range_headers": list(server.ranges),
        "error": error,
        "sha_ok": got_sha == sha_of(PAYLOAD),
        "on_disk": on_disk,
        "sidecar_left": marker.is_file(),
        "resumed_from": getattr(result, "resumed_from", None),
        "attempts": getattr(result, "attempts", None),
        "transferred": getattr(result, "transferred_bytes", None),
    }
    server.close()
    return outcome


def main() -> int:
    log("# 工单 07 探针：双轴评审五条断言的独立复现（真 HTTP，本地线程服务器）")
    log("")
    log(f"仓库：{REPO}")
    log(f"载荷：{len(PAYLOAD)} 字节，sha256={sha_of(PAYLOAD)[:16]}…")
    log("")
    work = Path(tempfile.mkdtemp(prefix="fe07-claims-"))
    cases: list[dict] = []
    try:
        log("## 假设 1：`resumed_from` 语义（spec = 「本次**真正用 Range 接上**的起始偏移」）")
        # 预铺 102400 字节（> MIN_RESUME_BYTES 64 KB，会发 Range）；服务器**忽略** Range
        # 回 200 整份 → 真正的起始偏移是 0（半成品被丢弃），spec 语义下 resumed_from 该是 0。
        c1 = run_case("ignore-range", work, "ignore-range", seed=102400)
        cases.append(c1)
        log(f"  铺 102400 字节 + 服务器忽略 Range（回 200 整份）")
        log(f"  实测 range_headers={c1['range_headers']}（客户端确实带了 Range）")
        log(f"  实测 resumed_from={c1['resumed_from']} / 最终 sha_ok={c1['sha_ok']}")
        log(f"  评审说：应报 0（真正接上的偏移），代码报「进函数时盘上的字节」。")
        log(f"  → 复现{'成立' if c1['resumed_from'] == 102400 else '**不成立**'}"
            f"（实测 resumed_from={c1['resumed_from']}）")
        log("")

        log("## 假设 2：服务器 416（spec 断点契约表：「删掉从 0 重下」）")
        c2 = run_case("range-416", work, "range-416", seed=102400)
        cases.append(c2)
        log(f"  铺 102400 字节 + 服务器对带 Range 的请求恒回 416")
        log(f"  实测 error={c2['error']!r}")
        log(f"  实测 半成品在盘={c2['on_disk'] > 0} / 边车在={c2['sidecar_left']}")
        log(f"  → 「删掉并重下」{'成立' if c2['sha_ok'] else '**不成立**'}"
            f"（最终 sha_ok={c2['sha_ok']}，请求数={len(c2['range_headers'])}）")
        log("")

        log("## 假设 3：本地比远端大（spec：「本地坏，删掉从 0 重下」）")
        c3 = run_case("local-bigger", work, "full", seed=len(PAYLOAD) + 4096)
        cases.append(c3)
        log(f"  铺 {len(PAYLOAD) + 4096} 字节（比清单大 4096）")
        log(f"  实测 error={c3['error']!r}")
        log(f"  实测 半成品在盘={c3['on_disk']} / 请求数={len(c3['range_headers'])}")
        log(f"  → 「删掉并重下」{'成立' if c3['sha_ok'] else '**不成立**'}"
            f"（最终 sha_ok={c3['sha_ok']}）")
        log("")

        log("## 假设 4：完整卷跑完后是否留孤儿边车（spec：「成功…一并删除…不留孤儿」）")
        c4 = run_case("complete-volume", work, "full", seed=len(PAYLOAD))
        cases.append(c4)
        log(f"  铺一整卷（{len(PAYLOAD)} 字节）+ 服务器正常")
        log(f"  实测 请求数={len(c4['range_headers'])}（期望 0 = 不发请求直接进校验）")
        log(f"  实测 最终 sha_ok={c4['sha_ok']} / 边车还在={c4['sidecar_left']}")
        log(f"  → 「不留孤儿」{'成立' if not c4['sidecar_left'] else '**不成立**'}")
        log("")

        log("## 假设 5（对照组）：正常整份下载，边车该被清掉")
        c5 = run_case("clean-full", work, "full", seed=0)
        cases.append(c5)
        log(f"  实测 边车还在={c5['sidecar_left']} / sha_ok={c5['sha_ok']}")
        log("")
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)

    RESULTS["cases"] = cases
    claims = {
        "1_resumed_from_semantics_inverted": cases[0]["resumed_from"] == 102400,
        "2_416_not_cleared_and_restarted": not cases[1]["sha_ok"],
        "3_local_bigger_not_restarted": not cases[2]["sha_ok"],
        "4_orphan_sidecar_after_complete_volume": cases[3]["sidecar_left"],
        "5_control_clean_full_download": not cases[4]["sidecar_left"] and cases[4]["sha_ok"],
    }
    RESULTS["claims"] = claims
    log("## 总判")
    for key, value in claims.items():
        log(f"  {key}：{'**复现成立**' if value else '不成立'}")
    (HERE / "verify-07-review-claims.txt").write_text("\n".join(LINES) + "\n",
                                                      encoding="utf-8")
    (HERE / "verify-07-review-claims.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("证据已写：verify-07-review-claims.txt / .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
