"""发布后真机核对：三个检查端点对新发布版本的反应。

分别打两个实例：
  8000 —— 用户正在用的实例（跑的是工作树里的 1.1.1 代码）
  8020 —— 沙箱「模拟用户机」（上一轮已用 v1.1.0 完整包更新过，现在应看到 v1.1.1 可更新）
"""

from __future__ import annotations

import json
import urllib.request

failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + what)
    if not cond:
        failures.append(what)


def get(port: int, path: str, timeout: float = 90) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


for port, label in ((8000, "用户实例"), (8020, "沙箱模拟机")):
    print(f"== {label}（端口 {port}）==")
    try:
        health = get(port, "/api/health", timeout=10)
    except Exception as exc:  # noqa: BLE001
        check(False, f"服务可达（{type(exc).__name__}）")
        continue
    print(f"    运行版本 = {health['version']}")
    full = get(port, "/api/update/full/check")
    print(f"    完整包：latest={full['latest_version']} available={full['update_available']} "
          f"reason={full['reason']} error={full['error']!r}")
    check(full["error"] == "", "完整包检查无错误")
    check(full["latest_version"] == "v1.1.1", "认出最新完整包 v1.1.1")
    small = get(port, "/api/update/check")
    print(f"    小发版：current={small['current_version']} latest={small['latest_version']} "
          f"available={small['update_available']}")
    check(small["current_version"] == "1.1.1", "本地版本 = 1.1.1")
    check(small["latest_version"] == "1.1.1", "线上最新 = 1.1.1")
    check(small["update_available"] is False, "自己就是最新版（不提示更新）")

print()
if failures:
    print(f"核对失败：{len(failures)} 项")
    for item in failures:
        print("  ✗", item)
    raise SystemExit(1)
print("核对通过：两个实例都认出 v1.1.1，且自认最新")
