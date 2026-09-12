"""诊断：正在运行的更新器进程收到了什么参数；以及清单 URL 能否直接拉通。"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request

URL = (
    "https://github.com/AK47n/firstep/releases/download/v1.1.0/"
    "firstep-full-v1.1.0.manifest.json"
)

print("== 1. 正在运行的 update-app 进程命令行 ==")
result = subprocess.run(
    [
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
        "Where-Object { $_.CommandLine -like '*update-app*' } | "
        "Select-Object -ExpandProperty CommandLine",
    ],
    capture_output=True, text=True, encoding="utf-8",
)
for line in (result.stdout or "").splitlines():
    if line.strip():
        print("  ", line.strip())
        for token in line.split():
            if "--full-manifest" in token:
                continue
            if token.startswith("http") or "github" in token:
                print("     └─ 清单参数：", repr(token))

print("== 2. 直接拉清单（同一个 Python / 同一个网络）==")
started = time.time()
try:
    request = urllib.request.Request(URL, headers={"User-Agent": "firstep-updater"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    elapsed = time.time() - started
    data = json.loads(raw.decode("utf-8-sig"))
    print(f"   OK：{len(raw) / 1048576:.2f} MB / {elapsed:.1f}s / version={data['version']}")
except Exception as exc:  # noqa: BLE001 - 诊断脚本，任何异常都直接打印
    print(f"   FAIL（{time.time() - started:.1f}s）：{type(exc).__name__}: {exc}")
