# -*- coding: utf-8 -*-
"""一次性诊断：在沙箱里逐字节复现启动器那段判据，看 `for /f` 到底拿到什么。

做法：从沙箱 `start-app.bat`（GBK）里**原样抽出**两段——
① 头部设置（chcp / cd / PYTHONPATH / PYEXE / LAUNCHER_STALE_PY / 端口）；
② 身份判定 + 问 CLI + 分支那几行；
把两段拼成一个探针 .bat（goto 的目标补成空标签，避免跳飞），配一个「旧版本」桩服务器跑一次，
打印 `GOT=[…] NOTE=[…]`。
"""

from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

SIM = Path(r"C:\Users\luoji\Desktop\firstep-sim")
BAT = SIM / "start-app.bat"
PROBE = SIM / "_probe-stale.bat"
PORT = 8099


def main() -> int:
    raw = BAT.read_bytes().decode("gbk")
    lines = raw.split("\r\n")

    def find(pred) -> int:
        for index, line in enumerate(lines):
            if pred(line):
                return index
        raise SystemExit("找不到锚点")

    head_start = find(lambda s: s.startswith("chcp 936"))
    probe_end = find(lambda s: s.strip() == "goto :already_running")

    # 整段照抄（chcp 起，到 CLI 分支那行为止）——**不能只挑几行**：`set PYEXE` 在中间，
    # 少抄一段就会出现「%PYEXE% 展开成空」这种假象（第一版探针正是这么误报的）。
    probe_lines = lines[head_start:probe_end + 1]
    tail = [
        "",
        ":updating",
        "echo RESULT=updating",
        "exit /b 0",
        ":update_left",
        "echo RESULT=update_left",
        "exit /b 0",
        ":no_python",
        "echo RESULT=no_python",
        "exit /b 0",
        ":old_python",
        "echo RESULT=old_python",
        "exit /b 0",
        ":no_deps",
        "echo RESULT=no_deps",
        "exit /b 0",
        ":already_running",
        'echo RESULT=already_running GOT=[%FIRSTEP_STALE%] NOTE=[%FIRSTEP_STALE_NOTE%]',
        "exit /b 0",
        ":stale_service",
        'echo RESULT=stale GOT=[%FIRSTEP_STALE%] NOTE=[%FIRSTEP_STALE_NOTE%]',
        "exit /b 0",
        ":port_busy",
        "echo RESULT=port_busy",
        "exit /b 0",
        ":start_service",
        "echo RESULT=start_service",
        "exit /b 0",
        ":timeout",
        "echo RESULT=timeout",
        "exit /b 0",
    ]
    probe_lines += tail
    PROBE.write_bytes("\r\n".join(probe_lines).encode("gbk"))
    print(f"探针已写：{PROBE}（{len(probe_lines)} 行）")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"app": "contest-generator", "version": "1.1.1",
                               "ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"桩服务器：127.0.0.1:{PORT} 答 app=contest-generator version=1.1.1")

    env = {**os.environ, "FIRSTEP_LAUNCHER_PORT": str(PORT),
           "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(["cmd", "/c", str(PROBE)], cwd=str(SIM), env=env,
                          capture_output=True, text=True, encoding="gbk",
                          errors="replace", timeout=120)
    print("--- 探针 stdout ---")
    print(proc.stdout.strip())
    print("--- 探针 stderr ---")
    print(proc.stderr.strip())
    print(f"退出码 {proc.returncode}")
    server.shutdown()
    PROBE.unlink(missing_ok=True)
    print(f"（探针已删：{PROBE}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
