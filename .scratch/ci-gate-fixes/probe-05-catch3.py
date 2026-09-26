# probe-05-catch3.py — 工单 ci-gate-fixes/05：跑**真 spec 命令**逮红，红的轮留**未筛**服务端日志。
#
# 与 probe-05-catch.py 的区别：不筛日志（上一版筛掉 `GET /` 等行，红的现场读不出真因，
# 这个教训已经吃过一次）；与 catch2 的区别：跑的是 spec 本身（含新增的 B2 用例），
# 而不是自演的探针——**要验的是闸门里那条命令**。
#
# 跑法：python .scratch/ci-gate-fixes/probe-05-catch3.py [--rounds=12]
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
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--spec", default="tests/browser/launcher-reload.spec.mjs")
    args = ap.parse_args()

    log_dir = OUT.with_name(OUT.stem + "-logs")
    log_dir.mkdir(exist_ok=True)
    rows, reds = [], 0
    for i in range(1, args.rounds + 1):
        log = log_dir / f"round-{i:02d}.log"
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                   FIRSTEP_BROWSER_SERVER_LOG=str(log))
        t0 = time.time()
        proc = subprocess.run(
            ["node", "--test", "--test-concurrency=1", args.spec],
            cwd=str(REPO), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        out = (proc.stdout or "") + (proc.stderr or "")
        passed = _count(out, "pass")
        failed = _count(out, "fail")
        red = failed not in ("0", "?")
        rows.append(f"轮 {i:2d}: pass={passed} fail={failed} 用时={int(time.time() - t0)}s")
        print(rows[-1])
        if red:
            reds += 1
            (log_dir / f"round-{i:02d}-out.txt").write_text(out, encoding="utf-8")
            first = ""
            for ln in out.splitlines():
                if ln.strip().startswith("✖ ") and "failing tests" not in ln:
                    first = ln.strip()
                    break
            print(f"    红：{first}")
            print(f"    现场留档：round-{i:02d}-out.txt（node 输出）+ {log.name}（未筛服务端日志）")
        elif log.exists():
            log.unlink()
    OUT.write_text("\n".join(rows), encoding="utf-8")
    print(f"\n=== 小结：{reds}/{args.rounds} 轮红（记账 {OUT.name}）===")
    return 0


def _count(text: str, key: str) -> str:
    m = re.search(rf"^ℹ {key} (\d+)", text, re.M)
    return m.group(1) if m else "?"


if __name__ == "__main__":
    sys.exit(main())
