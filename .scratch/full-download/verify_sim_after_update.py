"""更新后行为验证（沙箱 8020）：工具自认最新 + 资料库已能算增量 + 数据完整。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8020"
TOOL = Path(r"C:\Users\luoji\Desktop\firstep-sim")
failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + what)
    if not cond:
        failures.append(what)


def get(path: str, timeout: float = 90) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


print("== 更新后的工具自检 ==")
health = get("/api/health")
check(health["version"] == "1.1.0", f"版本 = 1.1.0（{health['version']}）")

full = get("/api/update/full/check")
print(f"    完整包检查：latest={full['latest_version']} reason={full['reason']} error={full['error']!r}")
check(full["error"] == "", "完整包检查无错误")

print("== 资料库：无基线 → 已能算增量（全量的核心收益）==")
materials = get("/api/update/materials/check")
print(f"    资料库检查：error={materials.get('error')!r} current={materials.get('current_version')!r} "
      f"latest={materials.get('latest_version')!r} available={materials.get('update_available')}")
# 更新前：基线缺失 → error=baseline-missing（无从算增量）
# 更新后：基线已随包写回，检查读到了本地版本 → error 不再是 baseline-missing；
#         线上当前还没有 materials- 前缀的发布，故为 no-release（符合预期）
check(
    materials.get("error") != "baseline-missing",
    f"不再是 baseline-missing（实际 {materials.get('error')!r}）",
)
check(
    materials.get("current_version") == "v1.1.0",
    f"检查读到了本地资料库基线版本（{materials.get('current_version')!r}）",
)

print("== 落位完整性 ==")
materials_root = TOOL / "sources" / "materials"
count = sum(1 for p in materials_root.rglob("*") if p.is_file())
check(count > 5000, f"资料库文件 {count} 个（全量落位）")
baseline = materials_root / ".materials-manifest.json"
check(baseline.is_file(), "资料库基线文件在场")
if baseline.is_file():
    data = json.loads(baseline.read_text(encoding="utf-8-sig"))
    check(len(data["batches"]) == 12, f"基线 {len(data['batches'])} 个批次")
installer = materials_root / "2026_04_地猛星电赛控制题配套资料" / "01_CCS_20.5.0.00028_win.zip"
check(installer.is_file(), "第三方安装包未被误删（更新不动本机已有的那批文件）")
check((TOOL / "sim-run.py").is_file(), "包外文件保留（沙箱入口仍在）")

print("== 工具本体可用 ==")
check((TOOL / "src" / "contest_generator" / "full_pack.py").is_file(), "新模块已落位")
check((TOOL / "src" / "contest_generator" / "static" / "js" / "ui" / "full-update.js").is_file(),
      "前端完整包下载窗口模块已落位")
check((TOOL / "tools" / "pack-full.ps1").is_file(), "发布侧脚本已落位")

print()
if failures:
    print(f"更新后验证失败：{len(failures)} 项")
    for item in failures:
        print("  ✗", item)
    raise SystemExit(1)
print("更新后验证通过：工具自认最新、资料库已能算增量、内容完整、包外文件保留")
