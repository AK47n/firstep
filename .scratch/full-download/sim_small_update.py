"""让沙箱走一次真实的「一键更新」（1.1.0 → 1.1.1），验证小发版路径。

覆盖：检查更新（线上真 Release）→ apply（真下载 296 MB + SHA256 校验）
→ 写待更新标记 → 独立进程更新器替换 → 版本号落位。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8020"
SIM = Path(r"C:\Users\luoji\Desktop\firstep-sim")
failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + what)
    if not cond:
        failures.append(what)


def get(path: str, timeout: float = 60) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path: str, payload: dict, timeout: float = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


before = (SIM / "src" / "contest_generator" / "__init__.py").read_text(encoding="utf-8")
print("更新前包内版本：", [l for l in before.splitlines() if "__version__" in l][0].strip()[:60])

print("== 检查更新（真实线上 Release）==")
check_result = get("/api/update/check", timeout=90)
print(f"    current={check_result['current_version']} latest={check_result['latest_version']} "
      f"available={check_result['update_available']} size={check_result['size_bytes'] / 1048576:.0f} MB")
check(check_result["current_version"] == "1.1.0", "本机版本 1.1.0")
check(check_result["latest_version"] == "1.1.1", "线上最新 1.1.1")
check(check_result["update_available"] is True, "提示可更新")
check(check_result["error"] == "", "无错误")

print("== 一键更新（真下载 + 独立进程替换）==")
started = post(
    "/api/update/apply",
    {
        "zip_url": check_result["zip_url"],
        "sha256": check_result["sha256"],
        "version": check_result["latest_version"],
        "removed_url": check_result.get("removed_url") or "",
    },
)
print("    apply 返回：", json.dumps(started, ensure_ascii=False)[:200])

deadline = time.time() + 20 * 60
last = ""
while time.time() < deadline:
    try:
        status = get("/api/update/status", timeout=15)
    except (urllib.error.URLError, TimeoutError, OSError):
        print(f"[{time.strftime('%H:%M:%S')}] 服务暂不可达（更新器正在替换/重启）")
        time.sleep(4)
        continue
    line = f"    state={status.get('state')} error={status.get('error')!r}"
    if line != last:
        print(f"[{time.strftime('%H:%M:%S')}]{line}")
        last = line
    if status.get("state") in ("done", "failed", "idle"):
        break
    time.sleep(3)

time.sleep(12)  # 等更新器把文件落完 / 重启尝试结束

print("== 更新后核对 ==")
after = (SIM / "src" / "contest_generator" / "__init__.py").read_text(encoding="utf-8")
version_line = [l for l in after.splitlines() if "__version__" in l][0].strip()
print("    更新后包内版本：", version_line[:60])
check('__version__ = "1.1.1"' in after, "沙箱工具文件已替换为 1.1.1")
check((SIM / "tools" / "update-app.py").is_file(), "更新器脚本仍在（未被破坏）")
check(
    "find_tool_root" in (SIM / "src" / "contest_generator" / "materials_update.py").read_text(encoding="utf-8"),
    "修复后的资料库路径代码已随更新落位",
)
pending = Path.home() / ".contest_generator_sim" / "updates" / "pending-update.json"
check(not pending.is_file(), "待更新标记已被清除（= 替换成功）")
result_file = Path.home() / ".contest_generator_sim" / "updates" / "last-update.json"
result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.is_file() else {}
print("    结果记录：", json.dumps(result, ensure_ascii=False)[:160])
check(result.get("status") == "ok", "更新器结果 status=ok")
check(result.get("mode") == "single", "模式 = single（小发版）")
check(result.get("version") == "1.1.1", "记录版本 = 1.1.1")
check(
    (SIM / "sim-run.py").is_file(),
    "包外文件保留（沙箱入口未被更新删除）",
)

print()
if failures:
    print(f"小发版更新演练失败：{len(failures)} 项")
    for item in failures:
        print("  ✗", item)
    raise SystemExit(1)
print("小发版更新演练通过：真下载 → 真替换 → 版本号落位")
