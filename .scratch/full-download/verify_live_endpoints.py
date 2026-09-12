"""真机验证：打本机端点的完整包/资料库检查接口，断言发布后可被工具发现。"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8011"
failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + what)
    if not cond:
        failures.append(what)


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


print("== /api/health ==")
health = get("/api/health")
check(health.get("app") == "contest-generator", "服务是本应用")
check(health.get("version") == "1.1.0", f"运行版本 = 1.1.0（实际 {health.get('version')}）")

print("== /api/update/full/check（真实 GitHub）==")
full = get("/api/update/full/check")
print(f"    latest={full['latest_version']} parts={len(full['parts'])} "
      f"total={full['total_bytes'] / 1048576:.1f} MB reason={full['reason']}")
check(full["error"] == "", "无错误（error 为空）")
check(full["latest_version"] == "v1.1.0", "认出最新完整包 v1.1.0")
check(full["update_available"] is True, "判定为「可下载」")
check(len(full["parts"]) == 1, "分卷表 1 卷")
check(
    full["parts"][0]["name"] == "firstep-full-v1.1.0.zip"
    and full["parts"][0]["sha256"].startswith("8c919e3c"),
    "分卷名与 SHA256 来自线上清单",
)
check(
    full["manifest_url"].endswith("firstep-full-v1.1.0.manifest.json"),
    "清单地址就绪（更新器据此拉删除清单与资料库基线）",
)
check(full["reason"] == "no-installed", "本机无已装标记 → reason=no-installed")
check("完整包" in full["message"], "中文提示含版本与体积说明")

print("== /api/update/check（小发版）==")
try:
    small = get("/api/update/check")
    print(f"    current={small.get('current_version')} latest={small.get('latest_version')} "
          f"available={small.get('update_available')}")
    check(small.get("current_version") == "1.1.0", "本地小发版版本 = 1.1.0")
    check(small.get("latest_version") == "1.1.0", "线上最新 = 1.1.0（刚发布的这一版）")
    check(small.get("update_available") is False, "自己就是最新版 → 不提示更新")
except Exception as exc:  # noqa: BLE001 - 网络类异常都按失败记录
    check(False, f"小发版检查请求失败：{exc}")

print("== /api/update/materials/check（资料库增量）==")
materials = get("/api/update/materials/check")
print(f"    error={materials.get('error')} current={materials.get('current_version')!r} "
      f"latest={materials.get('latest_version')!r}")
check(
    materials.get("error") == "baseline-missing",
    "本机无基线 → 明确回 baseline-missing（前端据此显示「一键下载完整 firstep」）",
)

print()
if failures:
    print(f"真机验证失败：{len(failures)} 项")
    for item in failures:
        print("  ✗", item)
    raise SystemExit(1)
print("真机验证通过：发布后的完整包可被工具发现，小发版与资料库检查均正常")
