"""复现「全套一条命令跑会卡死」：整支 pytest 反复跑，卡住时让 faulthandler 自己倒栈。

为什么不是「跑某个可疑文件」：本机实测**逐文件跑十几秒就完事**，卡死只在
「多文件同一进程」这一形态出现过（`docs/agents/local-environment.md` 2.5 节记了两次）。
所以回路必须打在这个形态上——单文件循环跑不出来的东西，再跑一百次也跑不出来。

用法：python .scratch/test-speedup/probe-hang.py [轮数] [单轮超时秒]
输出：每轮 stdout/stderr 落 run-<i>.txt（超时被杀也留得住半截），末尾打小结。
卡住判定 = 单轮超过 OUTER_TIMEOUT；此时 `-o faulthandler_timeout=30` 已经把
所有线程的栈写进 run-<i>.txt —— 那才是「钉住」要的证据。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FAULTHANDLER_TIMEOUT = 30


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    outer = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    hung: list[int] = []
    durations: list[float] = []
    for i in range(1, rounds + 1):
        log = OUT / f"run-{i}.txt"
        t0 = time.time()
        with log.open("w", encoding="utf-8", errors="replace") as fh:
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                     "-o", f"faulthandler_timeout={FAULTHANDLER_TIMEOUT}"],
                    cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, timeout=outer,
                )
                rc: int | str = proc.returncode
            except subprocess.TimeoutExpired:
                rc = "卡住被杀"
                hung.append(i)
        dt = time.time() - t0
        durations.append(dt)
        tail = _tail(log)
        print(f"  第 {i} 轮: {dt:7.1f}s  rc={rc}  {tail}", flush=True)

    print(f"\n== 小结（{rounds} 轮，单轮超时 {outer:.0f}s）==", flush=True)
    print(f"  卡住轮次: {hung or '无'}", flush=True)
    if durations:
        print(f"  耗时: 最快 {min(durations):.1f}s / 最慢 {max(durations):.1f}s", flush=True)
    print(f"  逐轮输出: {OUT}\\run-*.txt", flush=True)
    return 1 if hung else 0


def _tail(log: Path) -> str:
    if not log.is_file():
        return "(无输出)"
    lines = [ln for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not lines:
        return "(无输出)"
    # 卡住时最后几行就是 faulthandler 的栈，取最后一行有信息量的
    return lines[-1][:150]


if __name__ == "__main__":
    sys.exit(main())
