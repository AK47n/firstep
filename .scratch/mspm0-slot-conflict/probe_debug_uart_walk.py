"""诊断（临时，第四轮）：把「pair 谓词」的后果落到一条**真模块真脚**的走查上。

对象：mspm0 `debug_uart`（TX 默认 PA23 = UART2，RX 默认 PA22 = UART2；两者不同脚同实例）。
逐步走查三件事：
 ① 用户把 TX 搬到 UART0 的脚（PA28）——后端收吗？现模型怎么判？
 ② 用户把 TX 和 RX 一起搬到 UART0（PA28/PA29 之类）——后端收吗？
 ③ 「先 TX 后 RX」这条用户在界面上唯一走得通的路，中间态到底合不合法
    （口径 A/B 的分歧就落在这一步）。

跑法：python .scratch/mspm0-slot-conflict/probe_debug_uart_walk.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
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

SLUGS = ["debug_uart"]


def _inst(board, pin_name, role_type):
    pin = board.pin_index.get(pin_name)
    return sorted(pin.capabilities) if pin else []


def main():
    board = t.MSPM0_BOARD
    manifests = resolve_selection(t.LIBRARY_MODULES, "mspm0", SLUGS).manifests

    # UART 实例 → 脚（只列前几只）
    by_inst = defaultdict(list)
    for pin in board.pins:
        if pin.kind != "io":
            continue
        for token in pin.capabilities:
            if token.startswith("uart_tx:") or token.startswith("uart_rx:"):
                by_inst[token].append(pin.name)
    print("mspm0 UART 实例 → 脚（前 3）：")
    for token in sorted(by_inst)[:8]:
        print(f"   {token:16s} {by_inst[token][:3]}")

    print("\ndebug_uart 默认脚能力：")
    for role in ("debug_uart.DEBUG_UART_TX", "debug_uart.DEBUG_UART_RX"):
        decl = next(
            d
            for m in manifests
            for d in m.platforms["mspm0"].pins
            if f"{m.slug}.{d.id}" == role
        )
        print(f"   {role} 默认 {decl.default}：{_inst(board, decl.default, decl.type)}")

    def verdict(bindings, label):
        try:
            resolve_bindings(manifests, "mspm0", board, bindings)
            print(f"   {label:52s} → 后端收")
            return True
        except PinBindingError as exc:
            print(f"   {label:52s} → 后端拒：{str(exc)[:100]}")
            return False

    print("\n① 只搬 TX（RX 未绑、走默认 UART2）：")
    verdict({"debug_uart.DEBUG_UART_TX": "PA28"}, "TX→PA28（UART0）")
    print("   ↑ 后端拒 = 界面上「先搬一脚」这条路本来就走不通（不是模型造出来的）")

    print("\n② TX/RX 一起搬到 UART0（PA28 = UART0_TX，PA1 = UART0_RX）：")
    ok_joint = verdict(
        {"debug_uart.DEBUG_UART_TX": "PA28", "debug_uart.DEBUG_UART_RX": "PA1"},
        "TX→PA28 + RX→PA1（同实例 UART0）",
    )

    print("\n③ 现模型（无 pair 谓词）怎么判这两步：")
    for seed in ({}, {"debug_uart.DEBUG_UART_TX": "PA28"}):
        rows = {r["role"]: r for r in build_bindings_matrix(
            manifests, "mspm0", board, seed or None
        )["roles"]}
        row = rows["debug_uart.DEBUG_UART_RX"]
        print(
            f"   seed={seed or '{}'}：RX←PA1 判定 {t._selectable(row, 'PA1', board)}"
            f"（constraint={row['constraint']}）"
        )
    print(f"\n② 结论：整对一起搬 = {'可行' if ok_joint else '不可行'}")


if __name__ == "__main__":
    main()
