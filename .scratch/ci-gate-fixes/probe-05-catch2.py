# probe-05-catch2.py — 工单 ci-gate-fixes/05：逮红并**留全档**（不筛日志）。
#
# 为什么不用上一版（probe-05-catch.py）：它把服务端日志筛成"只看 /api/tabs/*"，结果红的
# 那两轮里最要紧的 `GET /`（新文档的 HTML 有没有被服务完）与顺序信息全丢了——留档的
# round-09/10.log 只剩 register/bye 交替，看不出真因。**取证时不要提前筛**。
#
# 本版跑的是 richest 的那支探针（probe-05-diag3.mjs：Node 时间轴 + 独立 health/TCP 通道 +
# 页面侧 resource timing），红的那些套件把**未筛**的服务端日志整份留档。
#
# 跑法：python .scratch/ci-gate-fixes/probe-05-catch2.py [--suites=10] [--rounds=8]
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".txt")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=8)
    args = ap.parse_args()

    log_dir = OUT.with_name(OUT.stem + "-logs")
    log_dir.mkdir(exist_ok=True)
    rows = []
    reds = 0
    for i in range(1, args.suites + 1):
        log = log_dir / f"suite-{i:02d}.log"
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                   FIRSTEP_BROWSER_SERVER_LOG=str(log))
        t0 = time.time()
        proc = subprocess.run(
            ["node", str(Path(__file__).with_name("probe-05-diag3.mjs")),
             f"--rounds={args.rounds}", "--suite=1"],
            cwd=str(REPO), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        out = (proc.stdout or "") + (proc.stderr or "")
        red = "**红**" in out
        elapsed = int(time.time() - t0)
        rows.append(f"套件 {i:2d}: {'红  ' if red else '全绿'} 用时={elapsed}s")
        print(rows[-1])
        if red:
            reds += 1
            keep = log_dir / f"suite-{i:02d}-red.txt"
            keep.write_text(out, encoding="utf-8")
            print(f"    现场留档：{keep.name}（探针全文）+ {log.name}（未筛服务端日志）")
        elif log.exists():
            log.unlink()
    OUT.write_text("\n".join(rows), encoding="utf-8")
    print(f"\n=== 小结：{reds}/{args.suites} 套件红（记账 {OUT.name}）===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
