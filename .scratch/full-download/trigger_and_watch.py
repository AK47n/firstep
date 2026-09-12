"""触发沙箱实例的「一键下载完整 firstep」，并跟踪到终态（含更新器重启）。

用法：python trigger_and_watch.py
输出：从 apply 到终态的状态变化；终态（done / failed）与总耗时。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8020"


def get(path: str, timeout: float = 30) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post(path: str, payload: dict, timeout: float = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


check = get("/api/update/full/check", timeout=120)
names = [p["name"] for p in check["parts"]]
print(f"check：{check['latest_version']} / {len(names)} 卷 / {check['total_bytes'] / 1048576:.0f} MB")
print(f"apply：{names}")

started = post("/api/update/full/apply", {"parts": names})
print("apply 返回：", started)
if not started.get("started"):
    raise SystemExit(f"apply 未启动：{started}")

deadline = time.time() + 45 * 60
last_line = ""
restart_seen = False
while time.time() < deadline:
    try:
        status = get("/api/update/full/status", timeout=15)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        restart_seen = True
        print(f"[{time.strftime('%H:%M:%S')}] 服务暂不可达（更新器正在替换/重启）：{type(exc).__name__}")
        time.sleep(4)
        continue
    state = status.get("state")
    done_mb = status.get("total_downloaded_bytes", 0) / 1048576
    total_mb = status.get("total_bytes", 0) / 1048576
    speed = status.get("speed_bps", 0) / 1048576
    line = (
        f"[{time.strftime('%H:%M:%S')}] {state:11} {done_mb:7.1f}/{total_mb:.0f} MB "
        f"{speed:5.1f} MB/s 当前卷={status.get('current_part_name') or '-'}"
    )
    if line[11:] != last_line[11:]:
        print(line)
        last_line = line
    if state in ("done", "failed", "cancelled"):
        print("\n终态：", json.dumps(status, ensure_ascii=False)[:600])
        print("重启期间出现过服务不可达：", restart_seen)
        raise SystemExit(0 if state == "done" else 1)
    time.sleep(3)

print("等待超时（45 分钟）")
raise SystemExit(2)
