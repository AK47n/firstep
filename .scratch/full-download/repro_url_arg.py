"""最小复现：Windows 上 cmd/Popen 传参时 URL 的正斜杠是否被吃掉。

背景：更新器进程日志里出现 `https:\\github.com\\...`（[Errno 22]），而
pending-update.json 里存的是正常 URL。怀疑是「URL 当命令行参数传」被
Windows 参数解析/转义改坏。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

URL = "https://github.com/AK47n/firstep/releases/download/v1.1.0/firstep-full-v1.1.0.manifest.json"

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    printer = tmp_path / "print_args.py"
    printer.write_text(
        "import sys, json\nprint(json.dumps(sys.argv[1:], ensure_ascii=False))\n",
        encoding="utf-8",
    )

    print("直接 Popen（列表参数，shell=False）：")
    result = subprocess.run(
        [sys.executable, str(printer), "--full-manifest", URL],
        capture_output=True, text=True, encoding="utf-8",
    )
    print("  ", result.stdout.strip())

    print("经 cmd /c（模拟 vbs 里 ws.Run 走的那条路）：")
    command = f'"{sys.executable}" "{printer}" --full-manifest {URL}'
    result = subprocess.run(
        ["cmd", "/c", command], capture_output=True, text=True, encoding="utf-8"
    )
    print("  ", result.stdout.strip())

    print("经 cmd /c 且 URL 加引号：")
    command = f'"{sys.executable}" "{printer}" --full-manifest "{URL}"'
    result = subprocess.run(
        ["cmd", "/c", command], capture_output=True, text=True, encoding="utf-8"
    )
    print("  ", result.stdout.strip())
