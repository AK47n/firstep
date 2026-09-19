# -*- coding: utf-8 -*-
"""诊断：更新器重启那一次，启动器为什么走 `:timeout`（服务没被带起来）。

真机演练现象：`launcher.log` 记 `reason=timeout port=8020`，重定向 profile 里**没有**
`webapp.log`（说明 `:start_service` 那行 `start "" /b python -m contest_generator.webapp`
既没起进程、也没建重定向文件），而单独把那一行拿出来跑又完全正常。

这个探针把「启动器真跑一遍」的条件搬齐：**另起一个进程**当假旧服务（答 1.1.1、端口由内核分配），
`USERPROFILE` 重定向，端口变量指到那个假服务，然后真跑 `start-app.bat`、**捕获它的控制台输出**
（真机上是隐藏窗口，看不到）。另起清扫线程按窗口标题收掉可能弹出的模态框宿主。

⚠️ 假旧服务**必须在独立进程里**：启动器会 `taskkill` 掉监听该端口的进程——第一版把桩放在探针
自己进程里，于是探针被启动器杀了、连输出都没留下（这一次就踩到了）。

用法::

    python .scratch/update-restart-stale-service/probe-02-launcher-timeout.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SIM = Path(r"C:\Users\luoji\Desktop\firstep-sim")
WORK = Path(os.environ["TEMP"]) / f"fe-diag-{time.strftime('%Y%m%d-%H%M%S')}"

STUB = r'''
import http.server, json, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"app": "contest-generator", "version": "1.1.1", "ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        return
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
print(srv.server_address[1], flush=True)
srv.serve_forever()
'''


def main() -> int:
    profile = WORK / "profile"
    (profile / ".contest_generator").mkdir(parents=True, exist_ok=True)
    print(f"演练目录：{WORK}")

    stub = subprocess.Popen([sys.executable, "-c", STUB], stdout=subprocess.PIPE,
                            text=True, encoding="utf-8")
    port = int(stub.stdout.readline().strip())
    print(f"假旧服务（独立进程 PID {stub.pid}）：127.0.0.1:{port} 答 version=1.1.1")

    stop = threading.Event()

    def reaper() -> None:
        """清扫可能弹出的模态框宿主（标题带 firstep 的那类），否则它会挂在桌面上。"""
        while not stop.is_set():
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-Process powershell -ErrorAction SilentlyContinue | "
                     "Where-Object { $_.MainWindowTitle -like '*firstep*' } | "
                     "ForEach-Object { $_.Id }"],
                    capture_output=True, text=True, timeout=20).stdout
                for pid in out.split():
                    print(f"  [清扫] 收掉弹窗宿主 PID {pid}")
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True, text=True)
            except Exception:  # noqa: BLE001 —— 清扫失败不影响诊断
                pass
            time.sleep(1.0)

    threading.Thread(target=reaper, daemon=True).start()

    env = {**os.environ, "USERPROFILE": str(profile), "HOME": str(profile),
           "FIRSTEP_LAUNCHER_PORT": str(port), "PYTHONPATH": str(SIM / "src"),
           "PYTHONIOENCODING": "utf-8"}
    began = time.time()
    print(f"真跑启动器：{SIM / 'start-app.bat'}（端口 {port}，USERPROFILE 重定向）")
    proc = subprocess.run(["cmd", "/c", str(SIM / "start-app.bat")], cwd=str(SIM),
                          env=env, capture_output=True, text=True, encoding="gbk",
                          errors="replace", timeout=300)
    elapsed = time.time() - began
    print(f"--- 启动器 stdout（{elapsed:.1f}s，退出码 {proc.returncode}）---")
    print(proc.stdout.strip()[-4000:])
    if proc.stderr.strip():
        print("--- stderr ---")
        print(proc.stderr.strip()[:2000])

    log = profile / ".contest_generator" / "launcher.log"
    print(f"--- launcher.log ---\n{log.read_text(encoding='utf-8').strip() if log.is_file() else '（无）'}")
    webapp_log = profile / ".contest_generator" / "webapp.log"
    if webapp_log.is_file():
        text = webapp_log.read_text(encoding="utf-8", errors="replace")
        print(f"--- webapp.log（{webapp_log.stat().st_size} 字节，末尾 25 行）---")
        print("\n".join(text.splitlines()[-25:]))
    else:
        print("--- webapp.log：**没有这个文件**（说明 start 那行没起进程）---")

    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as resp:
            print(f"--- {port} /api/health = {resp.read().decode()} ---")
    except Exception as exc:  # noqa: BLE001
        print(f"--- {port} /api/health 连不上：{type(exc).__name__}: {exc} ---")

    stop.set()
    stub.kill()
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[-2] == "LISTENING" and f":{port}" in parts[1]:
            subprocess.run(["taskkill", "/F", "/PID", parts[-1]],
                           capture_output=True, text=True)
            print(f"收尾：收掉 {port} 上的监听 PID {parts[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
