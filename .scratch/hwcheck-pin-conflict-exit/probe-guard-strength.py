# -*- coding: utf-8 -*-
"""判据强度探针（反向验证）：本单三处新判据各停一次，看现象会不会回来。

为什么要有它：新增的三处判据都可能"写了但没生效"——用例照样绿，真机照样炸。
逐条把判据停掉、看**坏现象是否重现**，才知道判据真的在起作用（本仓库的既有
惯例：`.scratch/module-hwcheck/probe-09-guard-strength.py`）。

三条：
① `pin_bindings._role_resource_keys` 的 adc 分支（薄封装共读同槽判 share）
   → 停掉后 `auto_assign_bindings` 把 us016 的模拟输入脚搬走；
② `syscfg_model` 的孤儿槽位让位（prune 的 adc_plan）
   → 停掉后落盘冲突报告重现「角色未登记」的 PA22/ADC12_0.adcPin7；
③ `syscfg_pin_conflict_report` 的 `diagnosis_bindings` 基准
   → 拿"已经搬过一遍"的增量当基准，容量诊断读成「可解开 0 组」（与事实相反）。

全程进程内 monkeypatch，**不写任何文件**、跑完自动还原。
用法：python .scratch/hwcheck-pin-conflict-exit/probe-guard-strength.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator import pin_bindings  # noqa: E402
from contest_generator.selection import resolve_dependencies  # noqa: E402
from contest_generator.syscfg_model import (  # noqa: E402
    MSPM0_SYSCFG_FILENAME,
    parse_syscfg,
)
from contest_generator.syscfg_prune import (  # noqa: E402
    adc_slot_plan,
    syscfg_pin_conflict_report,
)

MASTER = (
    REPO / "library" / "masters" / "mspm0" / MSPM0_SYSCFG_FILENAME
).read_text(encoding="utf-8", newline="")
BOARD = board_for_platform("mspm0")
BY_SLUG = {m.slug: m for m in list_modules(REPO / "library" / "modules")}
OUT = Path(__file__).resolve().parent / "probe-guard-strength.txt"


def _manifests(slugs):
    return list(resolve_dependencies(list(slugs), BY_SLUG))


def check_adc_share_branch() -> tuple[bool, str]:
    """① 停掉 adc 分支 → 共读同槽的件被当成冲突搬走。"""
    manifests = _manifests(["adc", "us016"])
    original = pin_bindings._role_resource_keys

    def without_adc_branch(slug, decl, bound):
        if decl.type == "adc":
            return set()
        return original(slug, decl, bound)

    pin_bindings._role_resource_keys = without_adc_branch  # type: ignore[assignment]
    try:
        broken = pin_bindings.auto_assign_bindings(
            manifests, "mspm0", BOARD, {}, resolve_default_conflicts=True
        )
    finally:
        pin_bindings._role_resource_keys = original  # type: ignore[assignment]
    healed = pin_bindings.auto_assign_bindings(
        manifests, "mspm0", BOARD, {}, resolve_default_conflicts=True
    )
    ok = bool(broken.bindings) and not healed.bindings
    return ok, (
        f"停用后：{broken.bindings or '（没搬）'}；还原后：{healed.bindings or '（没搬）'}"
    )


def check_slot_relocation() -> tuple[bool, str]:
    """② 停掉槽位级让位（不给 adc_plan）→ 「角色未登记」的冲突重现。"""
    slugs = ["led", "delay", "debug_uart", "adc"]
    manifests = _manifests(slugs)
    plan = adc_slot_plan(manifests, "mspm0", {})

    healed = parse_syscfg(MASTER).prune(slugs, adc_plan=plan)
    broken = parse_syscfg(MASTER).prune(slugs)
    healed_text, broken_text = healed.to_text(), broken.to_text()
    # 让位后的落盘文本里 PA22 只剩 UART 一家；旧口径下 ADC12_0 的孤儿落点也在那儿
    # （那就是检测页 400 里「角色未登记」的那一条）。
    healed_conflicts = _conflict_text(healed_text)
    broken_conflicts = _conflict_text(broken_text)
    ok = (
        "ADC12_0.peripheral.adcPin7.$assign" not in healed_text
        and "ADC12_0.peripheral.adcPin7.$assign" in broken_text
        and "PA22" not in healed_conflicts
        and "PA22" in broken_conflicts
    )
    return ok, (
        "停用后 PA22 冲突：" + (broken_conflicts.replace("\n", " / ") or "（无）")
        + f"；还原后 PA22 冲突：{healed_conflicts or '（无）'}"
    )


def _conflict_text(pruned_text: str) -> str:
    """把一段裁剪后的 syscfg 当「已落盘」送判据（不算选中集）→ 逐脚冲突文本。"""
    by_pin: dict[str, list[str]] = {}
    for assign in parse_syscfg(pruned_text).assigns:
        by_pin.setdefault(assign.pin, []).append(assign.path)
    return "\n".join(
        f"  · {pin}：" + " × ".join(paths)
        for pin, paths in sorted(by_pin.items())
        if len({path.split(".", 1)[0] for path in paths}) > 1
    )


def check_diagnosis_baseline() -> tuple[bool, str]:
    """③ 拿"已经搬过"的增量当诊断基准 → 读成「可解开 0 组」（与事实相反）。"""
    slugs = ["led", "oled", "debug_uart", "key", "beep", "sr04", "jy61p",
             "xunji", "ml_mpu6050"]
    manifests = _manifests(slugs)
    solved = pin_bindings.auto_assign_bindings(
        manifests, "mspm0", BOARD, {}, resolve_default_conflicts=True
    )
    good = syscfg_pin_conflict_report(
        master_syscfg=MASTER, manifests=manifests, platform="mspm0",
        board=BOARD, bindings=solved.bindings, diagnosis_bindings={},
    )
    bad = syscfg_pin_conflict_report(
        master_syscfg=MASTER, manifests=manifests, platform="mspm0",
        board=BOARD, bindings=solved.bindings,
    )
    ok = "可解开 2 组" in good.capacity and "可解开 0 组" in bad.capacity
    return ok, (
        "原始选择基准：" + _capacity_line(good.capacity)
        + " ｜ 解过一遍当基准：" + _capacity_line(bad.capacity)
    )


def _capacity_line(capacity: str) -> str:
    for line in capacity.splitlines():
        if "自动配置" in line:
            return line.strip()
    return "（无诊断）"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    checks = (
        ("① adc 共读同槽判 share（pin_bindings._role_resource_keys）",
         check_adc_share_branch),
        ("② 孤儿 ADC 槽位让位（syscfg_model.prune 的 adc_plan）",
         check_slot_relocation),
        ("③ 容量诊断基准（syscfg_pin_conflict_report.diagnosis_bindings）",
         check_diagnosis_baseline),
    )
    lines = [
        "# 判据强度探针：停掉本单三处判据，坏现象是否重现（工单 hwcheck-pin-conflict-exit/01）",
        "",
    ]
    failed = 0
    for title, fn in checks:
        ok, reading = fn()
        failed += 0 if ok else 1
        lines.append(("PASS  " if ok else "FAIL  ") + title)
        lines.append("      " + reading)
    lines.append("")
    lines.append(
        f"结论：{len(checks)} 处判据里 {len(checks) - failed} 处「停掉即坏现象重现」"
        + ("。" if not failed else "；**有判据是摆设。**")
    )
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
