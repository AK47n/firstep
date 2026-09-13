# -*- coding: utf-8 -*-
"""断点续传真 socket 判据（工单 resumable-download/01）。

问的问题只有一个：**断了之后，下一次尝试是从断点接上，还是从 0 重来？**
以及由此派生的三件事：重试次数是否如实、最终文件是否与载荷逐字节一致、服务器不支持
断点时（忽略 Range 返回 200）会不会正确地整份重下而不是拼出一份坏文件。

判据强度说明（重要，别误读）：
- **重试循环住在探针里**，所以本探针自带「不续传也会重试」的兜底——它判的不是「有没有重试」，
  而是**每一次尝试从哪个偏移开始**（取自服务器请求台账的 Range 头），以及最终哈希对不对。
- 因此「红」的形态是：**偏移退回到 0** + 最终哈希不符（因为已落盘的半成品被当成了完整文件）。

用法::

    python probe-01-resume.py                      # 自动选实现
    python probe-01-resume.py --impl plain         # 强制用 download_part（红基线复现）
    python probe-01-resume.py --negative-no-resume # 反证：每次尝试前丢掉半成品 → 必须转红
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PAYLOAD_SIZE = 2 * 1024 * 1024          # 2 MiB：快到能在秒级跑完，又足够被切成几段
SLICE_FRACTION = 0.4                    # cut / stall 模式发到 40% 就出事
MAX_ATTEMPTS_PER_CASE = 8               # 探针自己的兜底重试上限
RETRY_PAUSE = 0.4


# ---------------------------------------------------------------------------
# 实现选择
# ---------------------------------------------------------------------------

def load_impl(name: str):
    """返回 (下载函数, 实现名)。`resumable_download` 未实现时 auto 退到 download_part。"""
    from contest_generator import materials_task

    if name == "plain":
        return materials_task.download_part, "download_part"

    def _try_resumable():
        try:
            from contest_generator import download_resume
        except ImportError:
            return None
        return getattr(download_resume, "resumable_download", None)

    if name == "resumable":
        fn = _try_resumable()
        if fn is None:
            raise SystemExit(
                "download_resume.resumable_download 不存在（工单 02 尚未落地）——"
                "本探针的红基线就该是这样：先红，再由 02 判绿。"
            )
        return fn, "resumable_download"

    fn = _try_resumable()
    if fn is not None:
        return fn, "resumable_download"
    return materials_task.download_part, "download_part"


# ---------------------------------------------------------------------------
# 模拟服务器
# ---------------------------------------------------------------------------

class Sim:
    def __init__(self, port: int = 0, size: int = PAYLOAD_SIZE):
        self.size = size
        self.proc: subprocess.Popen | None = None
        self.port = port
        self.sha = ""

    def __enter__(self) -> "Sim":
        args = [sys.executable, str(HERE / "sim-server.py"),
                "--port", str(self.port or 0), "--size", str(self.size)]
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        self.proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE, text=True, encoding="utf-8", env=env,
        )
        ready = self.proc.stdout.readline().strip()
        if not ready.startswith("READY"):
            raise RuntimeError(f"模拟服务器未就绪：{ready!r}")
        fields = dict(kv.split("=", 1) for kv in ready.split()[1:])
        self.port = int(fields["port"])
        self.size = int(fields["size"])
        self.sha = fields["sha256"]
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

    def requests(self) -> list[dict]:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/requests",
                                    timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def reset(self) -> None:
        """清台账：让 `cut_runs` 的「第几次请求」从 1 重新算（每例开始前调）。"""
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/reset",
                                    timeout=10) as resp:
            resp.read()


# ---------------------------------------------------------------------------
# 单个用例
# ---------------------------------------------------------------------------

class Case:
    """一个用例：只带名字与「要回答的问题」，判定逻辑全在 `_run_one` / `_overall`。"""

    def __init__(self, name: str, question: str):
        self.name = name
        self.question = question


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", default="auto",
                        choices=["auto", "plain", "resumable"])
    parser.add_argument("--negative-no-resume", action="store_true",
                        help="反证：每次尝试前丢弃半成品（探针必须转红）")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    download, impl_name = load_impl(args.impl)
    print(f"实现 = {impl_name}"
          f"{'（反证模式：每次尝试前丢弃半成品）' if args.negative_no_resume else ''}")
    print(f"载荷 = {PAYLOAD_SIZE} 字节；断流点 = {int(SLICE_FRACTION * 100)}%\n")

    cases = [
        Case("stable", "不断的情况下能不能下完"),
        Case("cut", "连断 3 次，能不能从断点接上"),
        Case("stall", "对端卡死不动，能不能判出来并接上"),
        Case("ignore-range", "服务器不支持断点（恒 200），会不会拼出坏文件"),
        Case("slow", "弱网但连接正常，能不能下完"),
    ]
    metrics = {"impl": impl_name, "negative": args.negative_no_resume,
               "payload_bytes": PAYLOAD_SIZE, "cases": []}

    with tempfile.TemporaryDirectory(prefix="firstep-resume-probe-") as tmpdir, \
            Sim(size=PAYLOAD_SIZE) as sim:
        tmp = Path(tmpdir)
        urls = {
            "stable": sim.url("stable"),
            # 断流 3 次后恢复：验「连断之后能不能接上」
            "cut": sim.url("cut", fraction=SLICE_FRACTION, cut_runs=3),
            # 卡死只卡 1 次：这一次要静默超过客户端的读超时（服务器侧 STALL_HOLD_SECONDS），
            # 才验得到「零字节卡死被超时判出来」
            "stall": sim.url("stall", fraction=SLICE_FRACTION, cut_runs=1),
            "ignore-range": sim.url("ignore-range"),
            "slow": sim.url("slow", kbps=384),
        }
        for case in cases:
            # 判据卫生：每次跑之前把这一例的落盘点清干净。
            # 不清会怎样：上一次留下的**完整文件**会被实现直接复用（它还带 sha 校验），
            # 于是「断了能不能接上」根本不会发生——实测 stall 用例 0.05 秒就"通过"了。
            for leftover in [tmp / f"{case.name}.bin",
                             Path(str(tmp / f"{case.name}.bin") + ".partial.json")]:
                leftover.unlink(missing_ok=True)
            # 台账只用来对「本用例第几次请求从哪开始」：先清台账再取基线
            sim.reset()
            before = len(sim.requests())
            t0 = time.time()
            outcome = _run_one(case, sim, urls[case.name], download, tmp,
                               args.negative_no_resume)
            outcome["seconds"] = round(time.time() - t0, 2)
            all_reqs = sim.requests()
            outcome["request_starts"] = [r["start"] for r in all_reqs[before:]]
            outcome["ranges_seen"] = [r["range"] for r in all_reqs[before:]]
            outcome["resumed_observed"] = any(s > 0 for s in outcome["request_starts"][1:])
            metrics["cases"].append(outcome)
            _print_case(outcome)

    verdict = _overall(metrics)
    metrics["verdict"] = verdict
    text = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(f"\n总判：{verdict}")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"证据已写：{args.out}")
    return 0 if verdict == "PASS" else 1


def _run_one(case: Case, sim: Sim, url: str, download, tmp: Path,
             negative: bool) -> dict:
    """跑一个用例。

    两个计数要分开看，别混：
    - `probe_attempts`：**探针**的兜底重试次数（本探针自带的循环）；
    - `network_requests`：服务器真的被请求了几次 —— 下载器**内部**的重试也会计入这里。
      「自动重试」是产品行为，所以判据看的是 network_requests，而不是探针那层。
    """
    dest = tmp / f"{case.name}.bin"
    for leftover in [dest, Path(str(dest) + ".partial.json")]:
        leftover.unlink(missing_ok=True)
    before_requests = len(sim.requests())
    attempts_log: list[dict] = []
    digest = ""
    got_total = 0
    claimed_ok = False
    for attempt in range(1, MAX_ATTEMPTS_PER_CASE + 1):
        if negative:
            dest.unlink(missing_ok=True)
        offset_before = dest.stat().st_size if dest.is_file() else 0
        got = 0

        def on_progress(n: int) -> None:
            nonlocal got
            got += n

        t0 = time.time()
        try:
            returned = download(url, dest, on_progress)
            digest = returned if isinstance(returned, str) else str(
                getattr(returned, "sha256", ""))
            attempts_log.append({"attempt": attempt, "offset_before": offset_before,
                                 "bytes_this_try": got,
                                 "seconds": round(time.time() - t0, 2), "outcome": "ok"})
            got_total += got
            claimed_ok = True
            break
        except Exception as exc:  # noqa: BLE001
            attempts_log.append({"attempt": attempt, "offset_before": offset_before,
                                 "bytes_this_try": got,
                                 "seconds": round(time.time() - t0, 2),
                                 "outcome": f"{type(exc).__name__}: {exc}"[:160]})
            got_total += got
            time.sleep(RETRY_PAUSE)

    on_disk = dest.stat().st_size if dest.is_file() else 0
    local_sha = hashlib.sha256(dest.read_bytes()).hexdigest() if dest.is_file() else ""
    return {
        "case": case.name,
        "question": case.question,
        "probe_attempts": len(attempts_log),
        "network_requests": len(sim.requests()) - before_requests,
        "attempts": len(attempts_log),          # 兼容旧字段名
        "attempts_log": attempts_log,
        "claimed_ok": claimed_ok,
        "bytes_on_disk": on_disk,
        "expected_bytes": sim.size,
        "sha_local": local_sha,
        "sha_expected": sim.sha,
        "sha_returned_matches": digest == sim.sha,
        "hashes_match": local_sha == sim.sha and digest == sim.sha,
    }


def _print_case(o: dict) -> None:
    mark = "OK " if o["hashes_match"] else "!! "
    claim = "自称成功" if o["claimed_ok"] else "如实报错"
    print(f"{mark}{o['case']:<13} 探针重试 {o['probe_attempts']} 次 / 网络请求 {o['network_requests']} 次"
          f" / {o['seconds']}s  落盘 {o['bytes_on_disk']}/{o['expected_bytes']}  "
          f"请求起始偏移 {o['request_starts']}  {claim}  "
          f"哈希{'一致' if o['hashes_match'] else '不一致'}")
    for a in o["attempts_log"]:
        print(f"      · 第 {a['attempt']} 次：起始偏移 {a['offset_before']}，"
              f"本次收到 {a['bytes_this_try']} 字节，{a['seconds']}s → {a['outcome']}")


def _overall(metrics: dict) -> str:
    """总判（正向）：五例都要求最终文件与载荷逐字节一致；
    cut / stall 还额外要求**观察到续传**（非首次请求的起始偏移 > 0）。

    两条容易读错的判据，写在这里免得下次又绕：
    - **「自称成功」是缺陷，不是「没有续传能力」的合理表现**：断流/截断时下载器若回一句
      「下好了」，任务层只会在校验那一步才发现，用户看到的是「100% → 校验失败 → 重下」。
      故本探针把 `claimed_ok && !hashes_match` 单列为一项失败。
    - 反向模式（--negative-no-resume）判的是**反证是否如期转红**，不是功能是否可用。
    """
    by_name = {c["case"]: c for c in metrics["cases"]}
    if metrics["negative"]:
        red = [n for n in ("cut", "stall") if not by_name[n]["hashes_match"]]
        return "PASS（反证如期转红）" if len(red) == 2 else f"FAIL（反证未如期转红：{red}）"
    problems = []
    for name in ("stable", "ignore-range", "slow"):
        c = by_name[name]
        if not c["hashes_match"]:
            problems.append(f"{name} 最终文件与载荷不符")
    for name in ("cut", "stall"):
        c = by_name[name]
        if c["claimed_ok"] and not c["hashes_match"]:
            problems.append(
                f"{name} **被截断却自称成功**（落盘 {c['bytes_on_disk']}/{c['expected_bytes']}）"
                "——截断必须是失败，否则用户看到的是「100% → 校验失败」")
        elif not c["resumed_observed"]:
            problems.append(
                f"{name} 没有从断点接上（请求起始偏移一直是 0 = 整卷重下），"
                f"当前落盘 {c['bytes_on_disk']}/{c['expected_bytes']}")
        elif not c["hashes_match"]:
            problems.append(f"{name} 接上了但最终文件与载荷不符")
    return "PASS" if not problems else "FAIL：" + "；".join(problems)


if __name__ == "__main__":
    raise SystemExit(main())
