"""工单 11 的**全套回归跑法**：逐文件跑 + 每文件超时，避免被单文件卡死拖垮整轮。

为什么不用一条 `python -m pytest`：本机间歇性会出现「整支命令卡住十分钟以上」
（工单 11 实测两次：一次整支探针无输出、一次全套后台跑 40 分钟没完，CPU 只烧了 120s）。
逐文件跑能把「卡住」与「红」分开——**卡住不算判据**，但要指名道姓记下来。

用法：python .scratch/resumable-download/run-11-suite.py [超时秒数]
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMEOUT = 120

# 已知会真打网络的那几个文件（更新检查 / 下载 e2e）：本机离线时它们自己会走失败分支，
# 不额外处理，只保证卡住时能被超时切断。
SLOW_HINT = {
    "test_full_update.py", "test_update_apply.py", "test_materials_update.py",
    "test_full_apply.py", "test_update_app.py",
}


def main() -> int:
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TIMEOUT
    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("test_*.py"))
    passed = failed = timed_out = 0
    failures: list[str] = []
    timeouts: list[str] = []
    started = time.time()
    for rel in files:
        t0 = time.time()
        try:
            out = subprocess.run(
                [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", rel],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            timed_out += 1
            timeouts.append(rel)
            print(f"  [卡住>{timeout}s] {rel}", flush=True)
            continue
        lines = [ln for ln in (out.stdout or "").strip().splitlines() if ln.strip()]
        summary = lines[-1] if lines else "(无输出)"
        if out.returncode == 0:
            passed += 1
        else:
            failed += 1
            failures.append(f"{rel}: {summary}")
        mark = "OK " if out.returncode == 0 else "红 "
        print(f"  [{mark}]{rel:52s} {time.time() - t0:6.1f}s  {summary}", flush=True)

    print(f"\n== 小结（逐文件，超时 {timeout}s）==", flush=True)
    print(f"  文件数 {len(files)}：绿 {passed} / 红 {failed} / 卡住 {timed_out}", flush=True)
    print(f"  总耗时 {time.time() - started:.1f}s", flush=True)
    for item in failures:
        print(f"  红: {item}", flush=True)
    for item in timeouts:
        print(f"  卡住（不作判据，需单独复跑）: {item}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
