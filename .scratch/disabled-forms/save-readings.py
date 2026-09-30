"""disabled-forms 轮 · 读数落盘小工具（照 `.scratch/hwcheck-hygiene/readings.py` 的用途，够用即止）。

Windows 上 `python x.py > out.txt` 走的是系统 ANSI（GBK），中文会变味；PowerShell 的 `>` 又写
UTF-16LE。这里让子进程以 UTF-8 输出、按字节落盘，并在文件头写上命令与时间。

跑法（仓库根）：`python .scratch\\disabled-forms\\save-readings.py <读数名> -- <命令...>`
例：`python .scratch\\disabled-forms\\save-readings.py probe-00-inventory -- python .scratch\\disabled-forms\\probe-00-inventory.py`
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv: list[str]) -> int:
    if "--" not in argv or len(argv) < 3:
        print(__doc__)
        return 2
    cut = argv.index("--")
    name, cmd = argv[0], argv[cut + 1:]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.run(cmd, capture_output=True, env=env)
    head = (f"# 读数：{name}\n"
            f"# 命令：{' '.join(cmd)}\n"
            f"# 时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"# 退出码：{proc.returncode}\n"
            f"{'-' * 78}\n").encode("utf-8")
    out = HERE / f"{name}.txt"
    out.write_bytes(head + proc.stdout + (b"\n[stderr]\n" + proc.stderr if proc.stderr else b""))
    print(f"→ {out.relative_to(HERE.parents[1])}（{len(proc.stdout)} 字节 stdout，退出码 {proc.returncode}）")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
