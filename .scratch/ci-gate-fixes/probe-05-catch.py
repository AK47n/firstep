# probe-05-catch.py — 工单 ci-gate-fixes/05：**逮住红那一轮**并留全档。
#
# 设计（为什么要这样）：
#   · 红的不是"某一次 reload"，是**整条 spec 跑起来**才偶发（读数：10 轮里红 2 轮）；
#     所以用**真的 spec 命令**（`node --test … launcher-reload.spec.mjs`）而不是自演一遍。
#   · 每一轮起一个**带时间戳的服务端日志**（夹具的 `FIRSTEP_BROWSER_SERVER_LOG` 边跑边写），
#     红的那些轮把日志原样留档；绿的轮删掉（只留计数）。
#   · 逐轮记账落盘（UTF-8），最后打一张表——**红了就有现场，绿了就是持续绿读数**。
#
# 跑法：python .scratch/ci-gate-fixes/probe-05-catch.py [--rounds=12]
import argparse
import os
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
    args = ap.parse_args()

    log_dir = OUT.with_name(OUT.stem + "-logs")
    log_dir.mkdir(exist_ok=True)
    rows = []
    for i in range(1, args.rounds + 1):
        log = log_dir / f"round-{i:02d}.log"
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                   FIRSTEP_BROWSER_SERVER_LOG=str(log))
        t0 = time.time()
        proc = subprocess.run(
            ["node", "--test", "--test-concurrency=1",
             "tests/browser/launcher-reload.spec.mjs"],
            cwd=str(REPO), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        out = (proc.stdout or "") + (proc.stderr or "")
        passed = _count(out, "pass")
        failed = _count(out, "fail")
        elapsed = int(time.time() - t0)
        first_fail = ""
        for ln in out.splitlines():
            if ln.strip().startswith("✖ ") and "failing tests" not in ln:
                first_fail = ln.strip()
                break
        line = f"轮 {i:2d}: pass={passed} fail={failed} 用时={elapsed}s {first_fail}"
        rows.append(line)
        print(line)
        # 红的留档；绿的删掉（只留计数）
        if failed == 0 and log.exists():
            log.unlink()
        else:
            # 只留 P5 / tabs / 退出行（access log 太长）
            keep = [ln.rstrip() for ln in
                    log.read_text(encoding="utf-8", errors="replace").splitlines()
                    if "[P5]" in ln or "/api/tabs/" in ln or "fixture" in ln]
            log.write_text("\n".join(keep), encoding="utf-8")
            print(f"    现场留档：{log.name}（{len(keep)} 行）")
    OUT.write_text("\n".join(rows), encoding="utf-8")
    red = sum(1 for r in rows if "fail=0" not in r)
    print(f"\n=== 小结：{red}/{len(rows)} 轮红（记账 {OUT.name}）===")
    return 0


def _count(text: str, key: str) -> str:
    import re
    m = re.search(rf"^ℹ {key} (\d+)", text, re.M)
    return m.group(1) if m else "?"


if __name__ == "__main__":
    sys.exit(main())
