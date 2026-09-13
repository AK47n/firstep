"""工单 11 的**证据落盘器**：跑探针并把输出与补充记录写成 UTF-8 文件。

为什么单独一支：`Tee-Object` 在 Windows PowerShell 5.1 下写的是 **UTF-16**，
而 `.scratch/resumable-download/verify-*.txt` 的既有口径是 **UTF-8**
（本单第一版落的三个证据文件都是 UTF-16，已改；改的**中转过程**又把一段补充记录弄坏过一次——
所以现在补充记录**写在脚本里**，由脚本落盘，不再走 shell 追加）。
落盘一律用 `Path.write_text(..., encoding="utf-8")`，不走 shell 重定向。

用法：python .scratch/resumable-download/run-11-evidence.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# 逐文件隔离跑 `always_default` 那格的原始输出（见下方补充记录）
ISOLATION = """
== 补充：always_default 那格为什么按「探针失效」记（逐文件隔离的结果）==

把用例文件拆开单跑（同一错版插件，逐文件 90s 上限）：
  tests/test_full_task.py                 11.8s rc=1  19 failed, 14 passed   <- 判据有效
  tests/test_full_apply.py                 1.7s rc=1   2 failed,  5 passed   <- 判据有效
  tests/test_materials_task.py            90.0s TIMEOUT（真下载器取不到真 url，卡在重试退避里）
  tests/test_download_status_surface.py   90.0s TIMEOUT（同上，尾部已出现 FF）

结论：这一格的「红」是**真的**（两个文件红），只是有文件会卡死，故整支探针按超时记为
探针失效，不拿它当判据；真正要判的那件事（错版会不会被抓到）已由前面三格答清楚。
"""


def run_probe(name: str, extra: str = "") -> str:
    out = subprocess.run(
        [sys.executable, str(HERE / name)], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return (out.stdout or "") + (out.stderr or "") + extra


def main() -> int:
    jobs = [
        ("verify-11-resolve-seam.txt", "probe-11-resolve-seam.py", ""),
        ("verify-11-guard-strength.txt", "probe-11-guard-strength.py", ISOLATION),
        ("verify-11-suite.txt", "run-11-suite.py", ""),
    ]
    for target, script, extra in jobs:
        text = run_probe(script, extra)
        path = HERE / target
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"  写入 {target}（{len(text)} 字符，UTF-8）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
