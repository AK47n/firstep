"""诊断（临时）：槽位互斥在「跨模块同默认脚」下的模型漏判（huidu.R3 / pid.GRAY_D7 同默认 PB6）。

2026-08-15 起本次会话已修的门禁不含槽位互斥（工单 03 记为「本轮不进」）。
判据：单绑定口径 vs 累积态口径结论是否相反——相反 = 板图点得下去，点完那一组必 400。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import test_bindings_matrix as t  # noqa: E402
from contest_generator.pin_bindings import (  # noqa: E402
    PinBindingError,
    build_bindings_matrix,
    resolve_bindings,
)
from contest_generator.selection import resolve_selection  # noqa: E402

SLUGS = ["huidu", "pid"]


def _verdict(manifests, board, bindings, label):
    try:
        resolve_bindings(manifests, "mspm0", board, bindings or None)
        print(f"  {label} → 后端收")
        return True
    except PinBindingError as exc:
        print(f"  {label} → 后端拒：{str(exc)[:120]}")
        return False


def test_slot_gap():
    board = t.MSPM0_BOARD
    manifests = resolve_selection(t.LIBRARY_MODULES, "mspm0", SLUGS).manifests
    model = build_bindings_matrix(manifests, "mspm0", board, None)
    rows = {r["role"]: r for r in model["roles"]}
    print("\nhuidu/pid 同默认脚：R3/GRAY_D7 → PB6；R4/GRAY_D8 → PB7\n")

    print("① 单绑定口径（parity 用例现在用的）：")
    _verdict(manifests, board, {"huidu.R3": "PA0"}, "huidu.R3=PA0")

    print("② 累积态口径（界面点下去之后真实发出去的那份）：")
    _verdict(
        manifests, board,
        {"huidu.R3": "PA0", "pid.GRAY_D7": "PB6"},
        "huidu.R3=PA0 + pid.GRAY_D7=PB6（未动的那脚走默认）",
    )

    print("③ 模型怎么看 huidu.R3 能不能绑 PA0：")
    row = rows["huidu.R3"]
    print("   selectable 含 PA0 =", "PA0" in row["selectable"],
          "| constraint =", row["constraint"],
          "| 判定 =", t._selectable(row, "PA0", board))

    print("④ 点下去之后的模型（其余角色有效脚不变）：")
    m2 = build_bindings_matrix(
        manifests, "mspm0", board, {"huidu.R3": "PA0", "pid.GRAY_D7": "PB6"}
    )
    r2 = {r["role"]: r for r in m2["roles"]}
    print("   pid.GRAY_D7 约束 =", r2["pid.GRAY_D7"]["constraint"])
    print("   huidu.R3 约束 =", r2["huidu.R3"]["constraint"])

    print("\n⑤ 判据口径修正后（工单 mspm0-slot-conflict/02-03）：")
    # 板图此刻观测到的那一份 = 界面当前已配（collectBindings 同源）
    submitted = {"pid.GRAY_D7": "PB6"}
    row3 = {r["role"]: r for r in build_bindings_matrix(
        manifests, "mspm0", board, submitted
    )["roles"]}["huidu.R3"]
    print("   观测 =", submitted)
    print("   huidu.R3 绑 PA0 的判定 =", t._selectable(row3, "PA0", board),
          "| constraint =", row3["constraint"])
    assert not t._selectable(row3, "PA0", board), "槽位谓词没挡住（假绿仍在）"
    assert t._selectable(row3, "PB6", board), "同槽位同脚被误挡（假红）"
    print("   后端逐字原因 →", (row3["constraint"] or {}).get("reason"))
