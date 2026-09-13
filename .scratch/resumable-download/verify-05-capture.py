# -*- coding: utf-8 -*-
"""工单 05 目视证据第一步：**真任务跑出真载荷**（工单 resumable-download/05）。

界面上「慢 / 在重试 / 真失败」三种样子，判据得是真状态面的载荷——不是手写的假 JSON
（手写的会把「字段名对不对」这件事一起放过）。所以这里跑真任务，把载荷原样存下来，
交给 `verify-05-render.mjs` 用**真前端纯函数**渲染并截图。

产出：`verify-05-payloads.json`（每个状态一份 status 载荷 + 一份说明）。
用法：`python .scratch/resumable-download/verify-05-capture.py`
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PAYLOAD_SIZE = 2 * 1024 * 1024
OUT = HERE / "verify-05-payloads.json"


class Sim:
    """与 probe-01/03 同一台模拟服务器（别再另写一台）。"""

    def __init__(self, size: int = PAYLOAD_SIZE) -> None:
        self.proc: subprocess.Popen | None = None
        self.port = 0
        self.size = size
        self.sha = ""

    def __enter__(self) -> "Sim":
        args = [sys.executable, str(HERE / "sim-server.py"),
                "--port", "0", "--size", str(self.size)]
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        self.proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE, text=True, encoding="utf-8", env=env,
        )
        ready = self.proc.stdout.readline().strip()
        fields = dict(kv.split("=", 1) for kv in ready.split()[1:])
        self.port, self.size, self.sha = (int(fields["port"]), int(fields["size"]),
                                          fields["sha256"])
        return self

    def __exit__(self, *exc) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.write("stop\n")
                self.proc.stdin.flush()
                self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None

    def url(self, mode: str, **kw) -> str:
        query = [f"mode={mode}"] + [f"{k}={v}" for k, v in kw.items()]
        return f"http://127.0.0.1:{self.port}/p?" + "&".join(query)

    def reset(self) -> None:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/reset", timeout=10) as r:
            r.read()


def collect_full_cases(tmp: Path, sim: "Sim") -> list[dict]:
    """完整包链路的四个状态（真任务跑出来）。"""
    from contest_generator import download_resume as dr
    from contest_generator.full_task import FullDownloadTask, full_task_status

    dr.retry_delay = lambda attempt: 0.4        # 让退避窗口长到能采样
    cases: list[dict] = []

    # ① 慢：**速度字段人工指定**（其余字段全部来自真任务）。
    #
    # 为什么这条不采真速度：`speed_bps` 是「上次 status 调用至今」的瞬时估算，
    # 而限速 32 KB/s 的下载在 2 MB 上要跑一分钟——采样窗口里客户端可能一个块都
    # 还没拿到（实测 `total_downloaded_bytes` 仍是 0，速度就是 0）。为了让这条
    # 证据**确定性可复现**，只把 speed_bps 写成「弱网该有的值」，其余照真任务。
    slow = FullDownloadTask(
        task_dir=tmp / "slow",
        parts=[{"name": "firstep-full-v1.1.0.zip", "url": sim.url("stable"),
                "size": sim.size, "sha256": sim.sha}],
        snapshot_interval=0.0,
    )
    base_status = full_task_status(slow)
    base_status.update({
        "state": "downloading",
        "total_downloaded_bytes": 512 * 1024,
        "speed_bps": 32 * 1024,
        "parts": [{"name": "firstep-full-v1.1.0.zip",
                   "downloaded_bytes": 512 * 1024,
                   "total_bytes": sim.size, "ok": False}],
    })
    cases.append({
        "id": "slow",
        "note": "弱网但连接正常（32 KB/s，速度字段人工指定，其余来自真任务）："
                "应出现「网络较慢」且不出现失败/重试话术",
        "status": base_status,
    })

    # ② 在重试：连断多次，退避窗口里采样
    retrying = FullDownloadTask(
        task_dir=tmp / "retry",
        parts=[{"name": "firstep-full-v1.1.0.zip",
                "url": sim.url("cut", fraction=0.4, cut_runs=5),
                "size": sim.size, "sha256": sim.sha}],
        snapshot_interval=0.0,
    )
    sampled: dict | None = None
    worker = threading.Thread(target=retrying.run, daemon=True)
    worker.start()
    deadline = time.time() + 20
    while worker.is_alive() and time.time() < deadline and sampled is None:
        status = full_task_status(retrying)
        if status["retrying"]:
            sampled = status
        time.sleep(0.01)
    retrying.cancel()
    worker.join(timeout=20)
    cases.append({"id": "retrying",
                  "note": "断流后自动重试（退避等待中）：应出现「正在自动重试（第 N 次）…从 X% 接着下」",
                  "status": sampled or full_task_status(retrying)})

    # ③ 网络失败终态（重试封顶）
    netfail = FullDownloadTask(
        task_dir=tmp / "netfail",
        parts=[{"name": "firstep-full-v1.1.0.zip",
                "url": sim.url("cut", fraction=0.4, cut_runs=999),
                "size": sim.size, "sha256": sim.sha}],
        snapshot_interval=0.0,
    )

    def capped(url, dest, on_progress, **kw):     # noqa: ANN001, ANN003
        return dr.resumable_download(url, dest, on_progress, max_attempts=1, **kw)

    netfail._download = capped
    netfail.run()
    cases.append({"id": "failed-network",
                  "note": "断流且重试用尽：error_kind=network → 「网络中断（已下载 N%）…接着下」",
                  "status": full_task_status(netfail)})

    # ④ 校验失败终态（下载器所报 sha 与清单不符）
    verifyfail = FullDownloadTask(
        task_dir=tmp / "verifyfail",
        parts=[{"name": "firstep-full-v1.1.0.zip", "url": "https://example.com/x.zip",
                "size": 300 * 1024, "sha256": "0" * 64}],
        snapshot_interval=0.0,
    )

    def wrong_content(url, dest, on_progress):     # noqa: ANN001
        data = b"x" * (300 * 1024)
        dest.write_bytes(data)
        on_progress(len(data))
        return "f" * 64                            # 自称的 sha 与清单不符

    verifyfail._download = wrong_content
    verifyfail.run()
    cases.append({"id": "failed-verify",
                  "note": "内容与清单不符：error_kind=verify → 「重新下载也不会有变化」",
                  "status": full_task_status(verifyfail)})
    return cases


def collect_materials_cases(tmp: Path, sim: "Sim") -> list[dict]:
    """资料库链路的两个状态（**真 ApplyTask**，字段与完整包同形）。"""
    from contest_generator import download_resume as dr
    from contest_generator.materials_task import ApplyTask, task_status

    dr.retry_delay = lambda attempt: 0.4
    batches = [{"slug": "k230", "name": "k230资料",
                "parts": [{"zip_url": sim.url("cut", fraction=0.4, cut_runs=5),
                           "zip_name": "k230.zip", "size_bytes": sim.size,
                           "sha256": sim.sha}]}]
    cases: list[dict] = []

    # 在重试（退避窗口里采样）
    retrying = ApplyTask(task_dir=tmp / "m-retry", batches=batches, snapshot_interval=0.0)
    sampled: dict | None = None
    worker = threading.Thread(target=retrying.run, daemon=True)
    worker.start()
    deadline = time.time() + 20
    while worker.is_alive() and time.time() < deadline and sampled is None:
        status = task_status(retrying)
        if status["retrying"]:
            sampled = status
        time.sleep(0.01)
    retrying.cancel()
    worker.join(timeout=20)
    cases.append({"id": "materials-retrying",
                  "note": "资料库链路断流重试（真 ApplyTask）：话术应与完整包同源",
                  "status": sampled or task_status(retrying)})

    # 网络失败终态
    fail_batches = [{"slug": "k230", "name": "k230资料",
                     "parts": [{"zip_url": sim.url("cut", fraction=0.4, cut_runs=999),
                                "zip_name": "k230.zip", "size_bytes": sim.size,
                                "sha256": sim.sha}]}]
    netfail = ApplyTask(task_dir=tmp / "m-netfail", batches=fail_batches,
                        snapshot_interval=0.0)

    def capped(url, dest, on_progress, **kw):     # noqa: ANN001, ANN003
        return dr.resumable_download(url, dest, on_progress, max_attempts=1, **kw)

    netfail._download = capped
    netfail.run()
    cases.append({"id": "materials-failed-network",
                  "note": "资料库链路网络失败终态（真 ApplyTask）",
                  "status": task_status(netfail)})

    # 校验失败终态
    bad_batches = [{"slug": "k230", "name": "k230资料",
                    "parts": [{"zip_url": "https://example.com/k230.zip",
                               "zip_name": "k230.zip", "size_bytes": 300 * 1024,
                               "sha256": "0" * 64}]}]
    verifyfail = ApplyTask(task_dir=tmp / "m-verifyfail", batches=bad_batches,
                           snapshot_interval=0.0)
    verifyfail._download = lambda url, dest, on_progress: (   # noqa: ANN001
        dest.write_bytes(b"x" * (300 * 1024)), on_progress(300 * 1024), "f" * 64
    )[2]
    verifyfail.run()
    cases.append({"id": "materials-failed-verify",
                  "note": "资料库链路校验失败终态（真 ApplyTask）",
                  "status": task_status(verifyfail)})
    return cases


def main() -> int:
    cases: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="firstep-05-") as tmpdir, Sim() as sim:
        tmp = Path(tmpdir)
        cases += collect_full_cases(tmp, sim)
        sim.reset()
        cases += collect_materials_cases(tmp, sim)

    OUT.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"载荷已写：{OUT}")
    for case in cases:
        s = case["status"]
        print(f"  · {case['id']:<24} state={s['state']:<12} retry={s['retry_count']} "
              f"retrying={s['retrying']} kind={s['error_kind']!r} "
              f"resume={s.get('resume_percent')} msg={s['message'][:34]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

