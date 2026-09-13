# -*- coding: utf-8 -*-
"""真 socket 走廊验收：**接了线的任务**下到一半断流 → 自动重试 → 接上 → 完成（工单 resumable-download/03）。

与工单 01/02 那支探针的区别（别混）：

| | `probe-01-resume.py`（01/02） | 本探针（03） |
|---|---|---|
| 被测对象 | 下载函数本身（`resumable_download` / `download_part`） | **任务层**：`FullDownloadTask` 走缺省下载器 |
| 重试循环住在哪 | 探针自己（所以它带「不续传也会重试」的兜底） | **产品代码里**（任务不再自己重试，重试是下载器的职责） |
| 判的是什么 | 每次尝试的起始偏移 + 最终哈希 | 起始偏移、任务重试计数、边车、最终哈希、进度总量 |

本探针回答四个问题（每条都有明确数据源，见 `_verdict`）：

1. 断流之后**下一次请求是不是从断点起的**（服务器请求台账里的 `Range` 起点）；
2. 任务的 `retry_count` 是否**如实**（= 下载器实际重试次数，不是探针自己数的）；
3. 完成时**边车（`.partial.json`）有没有清干净**（不留孤儿），失败时**半成品与边车都在**；
4. 最终文件 SHA256 == 清单 sha256，且 `parts[].downloaded_bytes` == 卷大小（进度没算丢）。

反证（`--negative-no-resume`）：把 `_download_one` 换回**旧行为**（下载异常就 `unlink`
半成品）——同一个探针必须转红，红的理由必须是「第二次请求又从头下（偏移退回 0）」。
只改这一件事，才说明红的成因就是这一件事。

用法::

    python .scratch/resumable-download/probe-03-corridor.py            # 正证
    python .scratch/resumable-download/probe-03-corridor.py --negative-no-resume
    python .scratch/resumable-download/probe-03-corridor.py --out verify-03-corridor.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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

PAYLOAD_SIZE = 2 * 1024 * 1024        # 2 MiB：与工单 01 探针同一个量级，秒级跑完
CUT_FRACTION = 0.4                    # 每次断在「剩余部分的 40%」
CUT_RUNS = 3                          # 连断 3 次（与 spec 的三档口径一致）


class Sim:
    """模拟服务器子进程把手（照 `probe-01-resume.py` 的 Sim 抄，别各写一套）。"""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.port = 0
        self.size = 0
        self.sha = ""

    def __enter__(self) -> "Sim":
        args = [sys.executable, str(HERE / "sim-server.py"),
                "--port", "0", "--size", str(PAYLOAD_SIZE)]
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
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/reset",
                                    timeout=10) as resp:
            resp.read()


def load_task_class():
    """缺省任务类；反证模式换成「下载异常就删半成品」的旧行为子类。"""
    from contest_generator.full_task import FullDownloadTask
    return FullDownloadTask


def _payload_head(size: int, fraction: float) -> bytes:
    """模拟服务器载荷的前 `fraction` 段（种子半成品用）。

    算法必须与 `sim-server.py` 的 `_build_payload(size, seed)` **逐字节一致**
    （同一个 `random.Random(20260913)` 顺序取字节），否则铺下去的种子与服务器载荷
    对不上，重下完的哈希自然不符——那是判据自己造出来的假红。
    """
    import random

    rng = random.Random(20260913)          # 与 sim-server.py 的 --seed 一致
    return bytes(rng.getrandbits(8) for _ in range(size))[:int(size * fraction)]


def make_negative_class(base):
    """对照：把「下载异常**保留**半成品」改回工单 03 之前的「不留断点」。

    做法 = 缺省下载器外面包一层「每次尝试前先删掉半成品」（这正是旧实现的效果：
    每次重试都从 0 重来，进程重启后也一样）。

    两次反证的留痕都在 `verify-03-negative.txt` 里（别重犯）：

    - 第一版把对照写在 `_download_one` 的异常分支里 → **走廊没转红**。原因：自动重试
      住在**下载器内部**，异常根本到不了任务层（重试用尽才到）。写反证前先确认
      「要否掉的那件事」发生在哪一层。
    - 第二版只判「走廊的起始偏移」→ 仍不转红。原因：走廊每次重试都能续上，
      与「失败后删不删」无关——**真正被这条判据影响的是跨进程续传**（工单 03
      的验收标准：重启后不重下已完成部分）。所以反证要打在那一例上。
    """

    from contest_generator.download_resume import resumable_download

    def deletes_partial(url, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        Path(dest).unlink(missing_ok=True)       # 旧行为：不留断点
        return resumable_download(url, dest, on_progress, **kwargs)

    class DeletesPartialOnFailure(base):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            super().__init__(*args, **kwargs)
            # 实例属性优先于类属性（任务模块的解析顺序），所以注入点在这里
            self._download = deletes_partial

    return DeletesPartialOnFailure


def _pin_retry_delay(seconds: float = 0.2) -> None:
    """把退避拉短（判据不变，只省时间）。

    产品的退避是 2→4→8→16→32→60 秒（spec 定的，不改）。探针跑一遍走廊要三次重试，
    照原值要等 14 秒；这里压到 0.2 秒，判的是「有没有接着下」而不是「等了几秒」。
    真机端到端那一档（工单 06）跑的是产品原值，别混。
    """
    from contest_generator import download_resume

    download_resume.retry_delay = lambda attempt: seconds   # type: ignore[assignment]


def _run_corridor(task_cls, tmp: Path, sim: Sim, *, label: str,
                  mode: str = "cut", cut_runs: int = CUT_RUNS,
                  seed_fraction: float = 0.0) -> dict:
    """跑一遍走廊：断 N 次 → 自动重试 → 接上 → 完成。判定在 `_verdict`。

    `mode="ignore-range"` 时服务器恒回 200 整份：任务应当**丢弃半成品从 0 重下**
    并且最终哈希仍正确（spec 断点契约表那一行）。配合 `seed_fraction` 先铺一份
    带边车的半成品，才真的走到「带了 Range 却被忽略」那条路。
    """
    if mode == "cut":
        url = sim.url("cut", fraction=CUT_FRACTION, cut_runs=cut_runs)
    else:
        url = sim.url(mode)
    # 台账与 `cut_runs` 是**每例一份**的判据卫生（工单 01/02 都踩过）：
    # 不清就会带着上一例已经用掉的「切几次」继续算，后面的用例永远等不到「不切的那次」。
    sim.reset()
    task_dir = tmp / label
    task_dir.mkdir(parents=True, exist_ok=True)
    dest = task_dir / "full" / "firstep-full-v1.1.0.zip"
    if seed_fraction > 0:
        from contest_generator.download_resume import write_partial_marker
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_payload_head(sim.size, seed_fraction))
        write_partial_marker(dest, url, sim.size)
    task = task_cls(
        task_dir=task_dir,
        parts=[{"name": "firstep-full-v1.1.0.zip", "url": url,
                "size": sim.size, "sha256": sim.sha}],
        snapshot_interval=0.0,
    )
    bytes_at_start = dest.stat().st_size if dest.is_file() else 0
    if seed_fraction > 0:
        from contest_generator.download_resume import is_resumable_partial
        print(f"  [种子自检] 落盘 {bytes_at_start} 字节，边车在 "
              f"{Path(str(dest) + '.partial.json').is_file()}，可续="
              f"{is_resumable_partial(dest, url, sim.size)}")
    t0 = time.time()
    task.run()
    seconds = round(time.time() - t0, 2)

    reqs = sim.requests()
    marker = Path(str(dest) + ".partial.json")
    local_sha = hashlib.sha256(dest.read_bytes()).hexdigest() if dest.is_file() else ""
    return {
        "case": label,
        "state": task.state.value,
        "error": task.error,
        "seconds": seconds,
        "bytes_at_start": bytes_at_start,
        "request_starts": [r["start"] for r in reqs],
        "request_ranges": [r["range"] for r in reqs],
        "network_requests": len(reqs),
        "task_retry_count": task.retry_count,
        "last_error_kind": task.last_error_kind,
        "message_at_end": task._message,
        "bytes_on_disk": dest.stat().st_size if dest.is_file() else 0,
        "expected_bytes": sim.size,
        "sha_local": local_sha,
        "sha_expected": sim.sha,
        "part_downloaded_bytes": task.parts[0].downloaded_bytes,
        "part_ok": task.parts[0].ok,
        "marker_left": marker.is_file(),
    }


def _verdict(run: dict, sim: Sim, negative: bool) -> list[str]:
    """判据集中在这里（一行一条问题，空列表 = 通过）。"""
    if negative:
        # 反证模式下走廊**不做判定**，只如实登记数据。理由（两次踩过的留痕）：
        # 「失败就删半成品」这件事影响的是**跨进程续传**（见 `_verify_failure_case`），
        # 而走廊里每一次重试都发生在同一个进程内、且都由下载器自己接上——
        # 在这里判红就会得到「反证居然续传了」这种**假红**（判据与要否掉的事无关）。
        # 判据能不能红，由失败态那一例回答。
        return []
    problems: list[str] = []
    starts = run["request_starts"]
    if not starts:
        return ["一次请求都没发出去（判据本身失效，先查服务器起没起来）"]

    if run["state"] != "done":
        problems.append(f"任务没走到 done：{run['state']}（{run['error']}）")
    if starts[0] != 0:
        problems.append(f"第一次请求就该从头下，实际起始偏移 {starts[0]}")
    resumed = [s for s in starts[1:] if s > 0]
    if len(resumed) < CUT_RUNS:
        problems.append(
            f"断 {CUT_RUNS} 次但只有 {len(resumed)} 次从断点接上（起始偏移 {starts}）"
        )
    if starts[1:] != sorted(starts[1:]):
        problems.append(f"起始偏移不单调递增 = 回退了（{starts}）")
    if run["task_retry_count"] < CUT_RUNS:
        problems.append(
            f"任务重试计数不实：断了 {CUT_RUNS} 次，retry_count={run['task_retry_count']}"
        )
    if run["sha_local"] != sim.sha:
        problems.append("最终文件与载荷逐字节不符（断点拼接出坏文件）")
    if run["part_downloaded_bytes"] != sim.size:
        problems.append(
            f"进度总量不对：{run['part_downloaded_bytes']} / {sim.size}"
            "（续传时把已落盘的那部分算丢了）"
        )
    if run["marker_left"]:
        problems.append("成功之后边车还在（留了孤儿文件）")
    if run["message_at_end"] != "":
        problems.append(f"终态摘要没清空：{run['message_at_end']!r}")
    return problems


def _verdict_ignore_range(run: dict, sim: Sim, negative: bool) -> list[str]:
    """忽略 Range 那一例的判据：**从 0 重下但最终文件正确**，且进度不超算。

    反证模式不判（这一例与「失败后删不删半成品」无关，同走廊那条的理由）。
    """
    if negative:
        return []
    problems: list[str] = []
    if run["state"] != "done":
        problems.append(f"任务没走到 done：{run['state']}（{run['error']}）")
    if run["sha_local"] != sim.sha:
        problems.append("忽略 Range 之后拼出来的文件不对（该从 0 重下却续写了）")
    if run["part_downloaded_bytes"] > sim.size:
        problems.append(
            f"进度超算：{run['part_downloaded_bytes']} > 卷大小 {sim.size}"
            "（把已丢弃的半成品算进了进度）"
        )
    if run["bytes_at_start"] <= 0:
        problems.append("种子半成品没铺上——这一例根本没走到「带了 Range 却被忽略」")
    elif run["request_starts"] and run["request_starts"][0] != run["bytes_at_start"]:
        problems.append(
            f"第一次请求该带 Range（从 {run['bytes_at_start']} 起），"
            f"实际 {run['request_starts']}"
        )
    return problems


def _verify_failure_case(task_cls, tmp: Path, sim: Sim, *, label: str = "failed-case") -> dict:
    """失败态 + 跨进程续传：一轮断在半路就失败 → **换一个新任务实例**接着下完。

    为什么这是工单 03 的要害用例：用户视角的收益（「回来还能接着下」）就发生在这条
    跨进程路径上。半成品如果被删（旧行为），第二个任务只能从 0 重来；留着就接着下。
    判据 = 第二个任务的**第一次请求起始偏移**必须等于第一个任务断掉时的落盘字节。
    """
    from contest_generator.download_resume import is_resumable_partial, resumable_download

    url = sim.url("cut", fraction=CUT_FRACTION, cut_runs=1)
    sim.reset()                     # 每例自己的台账（见 `_run_corridor` 的说明）
    task_dir = tmp / label
    task_dir.mkdir(parents=True, exist_ok=True)
    parts = [{"name": "firstep-full-v1.1.0.zip", "url": url,
              "size": sim.size, "sha256": sim.sha}]

    def capped(url_, dest, on_progress, **kwargs):  # noqa: ANN001, ANN003
        # 产品的重试无上限；这里封顶只是让「失败态」在秒级出现
        return resumable_download(url_, dest, on_progress, max_attempts=1, **kwargs)

    first = task_cls(task_dir=task_dir, parts=parts, snapshot_interval=0.0)
    first._download = capped  # type: ignore[attr-defined]
    first.run()
    dest = task_dir / "full" / "firstep-full-v1.1.0.zip"
    marker = Path(str(dest) + ".partial.json")
    got_before = dest.stat().st_size if dest.is_file() else 0
    # 「失败态留下什么」必须在**第二个任务跑之前**读：它跑完会（正确地）清掉边车
    # ——读晚了就会把「已经清干净」误判成「从来没写过」（本探针第一版就是这么错的）。
    marker_after_failure = marker.is_file()
    resumable_after_failure = is_resumable_partial(dest, url, sim.size)

    # 新实例 = 换一次进程（快照没写过 ok，只能靠盘上的半成品与边车）
    mark = len(sim.requests())
    second = task_cls(task_dir=task_dir, parts=parts, snapshot_interval=0.0)
    t0 = time.time()
    second.run()
    second_starts = [r["start"] for r in sim.requests()[mark:]] or [None]

    return {
        "case": label,
        "state": first.state.value,
        "error": first.error[:200],
        "seconds": round(time.time() - t0, 2),
        "request_starts": [r["start"] for r in sim.requests()][:mark],
        "bytes_before_restart": got_before,
        "resume_start_after_restart": second_starts[0],
        "second_state": second.state.value,
        "second_error": second.error[:200],
        "expected_bytes": sim.size,
        "sha_local": hashlib.sha256(dest.read_bytes()).hexdigest() if dest.is_file() else "",
        "sha_expected": sim.sha,
        "bytes_on_disk": dest.stat().st_size if dest.is_file() else 0,
        "marker_left": marker_after_failure,
        "resumable_next_time": resumable_after_failure,
        "task_retry_count": first.retry_count,
        "message_at_end": first._message,
    }


def _verify_failure_verdict(run: dict) -> list[str]:
    """正证：失败态留半成品 + 边车，且下一个实例**从断点接着下**。"""
    problems: list[str] = []
    if run["state"] != "failed":
        problems.append(f"该失败的没失败：{run['state']}")
    if not (0 < run["bytes_before_restart"] < run["expected_bytes"]):
        problems.append(f"失败态上半成品不见了（{run['bytes_before_restart']} 字节）")
    if not run["marker_left"]:
        problems.append("失败态没写边车——下次进程重启就认不出这份半成品")
    if not run["resumable_next_time"]:
        problems.append("盘上这份半成品下次接不上（边车 / 长度对不上）")
    if run["second_state"] != "done":
        problems.append(f"重启后没下完：{run['second_state']}（{run['second_error']}）")
    if run["resume_start_after_restart"] != run["bytes_before_restart"]:
        problems.append(
            f"重启后没从断点接上：请求起始偏移 {run['resume_start_after_restart']}，"
            f"断在 {run['bytes_before_restart']}"
        )
    if run["sha_local"] != run["sha_expected"]:
        problems.append("最终文件与载荷不符")
    if run["message_at_end"] != "":
        problems.append(f"终态摘要没清空：{run['message_at_end']!r}")
    return problems


def _failure_negative_verdict(run: dict) -> list[str]:
    """反证：对照实现必须**接不上**（否则说明「保留半成品」这件事没被测到）。"""
    problems: list[str] = []
    if run["resume_start_after_restart"] == run["bytes_before_restart"]:
        problems.append(
            "对照实现居然从断点接上了——反证不成立，说明「保留半成品」没被测到"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-no-resume", action="store_true",
                        help="反证：把「下载异常保留半成品」换回 unlink → 探针必须转红")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    base = load_task_class()
    task_cls = make_negative_class(base) if args.negative_no_resume else base
    _pin_retry_delay()
    print(f"实现 = {task_cls.__module__}.{task_cls.__name__}"
          f"{'（反证：下载异常就删半成品）' if args.negative_no_resume else ''}")
    print(f"载荷 = {PAYLOAD_SIZE} 字节；断流点 = 每次剩余部分的 {int(CUT_FRACTION * 100)}%，"
          f"连断 {CUT_RUNS} 次；退避压到 0.2 秒（只省时间，不改判据）\n")

    metrics: dict = {"negative": args.negative_no_resume, "payload_bytes": PAYLOAD_SIZE,
                     "cut_runs": CUT_RUNS, "runs": []}
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="firstep-corridor-probe-") as tmpdir, \
            Sim() as sim:
        tmp = Path(tmpdir)
        corridor = _run_corridor(task_cls, tmp, sim, label="corridor")
        metrics["runs"].append(corridor)
        row = _verdict(corridor, sim, args.negative_no_resume)
        problems += [f"[走廊] {p}" for p in row]
        _print_run(corridor, row, judged=not args.negative_no_resume)

        # 服务器忽略 Range（恒 200 整份）：任务要丢弃半成品从 0 重下，最终哈希仍对
        ignored = _run_corridor(task_cls, tmp, sim, label="ignore-range",
                                mode="ignore-range", cut_runs=0, seed_fraction=0.5)
        metrics["runs"].append(ignored)
        row_ignored = _verdict_ignore_range(ignored, sim, args.negative_no_resume)
        problems += [f"[忽略 Range] {p}" for p in row_ignored]
        _print_run(ignored, row_ignored, judged=not args.negative_no_resume)

        failed = _verify_failure_case(
            task_cls, tmp, sim,
            label="failed-case" if not args.negative_no_resume else "failed-case-negative",
        )
        metrics["runs"].append(failed)
        row2 = (_failure_negative_verdict(failed) if args.negative_no_resume
                else _verify_failure_verdict(failed))
        problems += [f"[失败态] {p}" for p in row2]
        _print_run(failed, row2)

    if args.negative_no_resume:
        # 反证模式：走廊不判（数据已如实登记），只判失败态那一例是否**如期转红**。
        # 「转红」在数据上 = 对照实现重启后从 0 重下（`resume_start_after_restart` 退回 0），
        # 也就是 `_failure_negative_verdict` 恰好没有报「反证不成立」。
        on_target = [
            p for p in problems
            if p.startswith("[失败态]") and "反证不成立" in p
        ]
        turned_red = not on_target
        verdict = ("PASS（反证如期转红）" if turned_red
                   else "FAIL（反证没转红——判据被调软了）")
    else:
        verdict = "FAIL：" + "；".join(problems) if problems else "PASS"
    metrics["verdict"] = verdict
    print(f"\n总判：{verdict}")
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = HERE / out
        out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"证据已写：{out}")
    return 0 if verdict.startswith("PASS") else 1


def _print_run(run: dict, problems: list[str], *, judged: bool = True) -> None:
    mark = "OK " if not problems else "!! "
    if not judged:
        mark = "-- "
    resume_at = run.get("resume_start_after_restart")
    print(f"{mark}{run['case']:<22} state={run['state']}  {run['seconds']}s  "
          f"起始偏移 {run['request_starts']}"
          f"{'（仅登记，反证模式不判它）' if not judged else ''}")
    print(f"      断在 {run.get('bytes_before_restart', run.get('bytes_on_disk'))}"
          f"/{run['expected_bytes']}  "
          f"重启后起始 {resume_at if resume_at is not None else '（正证无需重启）'}  "
          f"重试计数 {run.get('task_retry_count', '-')}  "
          f"边车还在 {run.get('marker_left', '-')}  "
          f"哈希{'一致' if run.get('sha_local') in (None, run.get('sha_expected')) else '不一致'}")
    if run.get("error"):
        print(f"      错误：{run['error']}")
    for line in problems:
        print(f"      · 判红：{line}")


if __name__ == "__main__":
    raise SystemExit(main())
