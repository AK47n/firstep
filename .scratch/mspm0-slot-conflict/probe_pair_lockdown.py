"""诊断（临时，第六轮）：口径 A（严格镜像后端）到底把 uart 对锁到什么程度。

问题：严格谓词下，每个 uart 对在**真默认态**里
  · 两只脚各自还剩多少可绑脚（只算与对脚有效实例同实例的脚）？
  · 存不存在「同一实例里两只脚都另有一个可用位」的实例（= 整对能搬过去）？
  · 单脚迁移（TX 先走）在后端本来是否可行（= 死结是后端语义带来的、不是模型造的）？

跑法：python .scratch/mspm0-slot-conflict/probe_pair_lockdown.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import test_bindings_matrix as t  # noqa: E402
from contest_generator.boards import BOARDS_DIR, load_boards  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.pin_bindings import (  # noqa: E402
    PinBindingError,
    pin_capability_instances,
    resolve_bindings,
)

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
PAIR_TYPES = ("uart_tx", "uart_rx", "i2c_scl", "i2c_sda")


def main():
    for platform in ("mspm0", "stm32"):
        board = BOARDS[platform]
        manifests = list_modules(t.LIBRARY_MODULES)
        decls = {
            f"{m.slug}.{d.id}": d
            for m in manifests
            if m.platforms.get(platform)
            for d in m.platforms[platform].pins
        }
        pairs: dict[str, dict[str, str]] = {}
        for key, decl in decls.items():
            if decl.type in PAIR_TYPES:
                pairs.setdefault(key.rsplit("_", 1)[0], {})[decl.type] = key
        pairs = {k: v for k, v in pairs.items() if len(v) == 2 and len(set(
            decls[x].type[:3] for x in v.values())) == 1}

        # 实例 → 该类型的脚
        pins_by_inst = defaultdict(list)
        for pin in board.pins:
            if pin.kind != "io":
                continue
            for token in pin.capabilities:
                typ, _, inst = token.partition(":")
                if typ in PAIR_TYPES and inst:
                    pins_by_inst[(typ, inst)].append(pin.name)

        print(f"\n===== {platform}：{len(pairs)} 个 uart/i2c 对 =====")
        one_option, movable_pairs = [], []
        for stem, feet in sorted(pairs.items()):
            (ka, kb) = sorted(feet.values())
            da, db = decls[ka], decls[kb]
            ia = set(pin_capability_instances(board.pin_index[da.default], da.type))
            ib = set(pin_capability_instances(board.pin_index[db.default], db.type))
            shared = ia & ib
            if not shared:
                continue
            inst = sorted(shared)[0]
            pool_a = pins_by_inst[(da.type, inst)]
            pool_b = pins_by_inst[(db.type, inst)]
            # 严格谓词下 A 的可绑脚 = 与「对脚有效实例」同实例的脚 = 该实例的池
            if len(pool_a) < 2 and len(pool_b) < 2:
                one_option.append((ka, da.default, pool_a, kb, db.default, pool_b))
            else:
                movable_pairs.append((inst, ka, pool_a, kb, pool_b))

        print(f"  两只脚在默认实例里都没有第二个位（严格谓词下 = 原地不动）：{len(one_option)} 对")
        for row in one_option[:6]:
            print("    ", row)
        print(f"  默认实例里至少有第二个位（整对可能搬，但两脚必须同时搬）：{len(movable_pairs)} 对")
        for row in movable_pairs[:6]:
            print("    ", row)

        # 单脚迁移在后端是否可行（真默认态下，把 TX 搬到同实例另一只脚 —— 若能搬动）
        for inst, ka, pool_a, kb, pool_b in movable_pairs[:3]:
            alt_a = [p for p in pool_a if p != decls[ka].default]
            alt_b = [p for p in pool_b if p != decls[kb].default]
            print(f"   {ka}（{decls[ka].default}）同实例候选 {alt_a} / {kb}（{decls[kb].default}）同实例候选 {alt_b}")
            if alt_a and alt_b:
                single = {ka: alt_a[0]}
                try:
                    resolve_bindings(manifests, platform, board, single)
                    print(f"      单脚 {ka}→{alt_a[0]}：后端收（→ 严格谓词按对脚默认实例也只放行同实例脚）")
                except PinBindingError as exc:
                    print(f"      单脚 {ka}→{alt_a[0]}：后端拒（{str(exc)[:60]}）")
                joint = {ka: alt_a[0], kb: alt_b[0]}
                try:
                    resolve_bindings(manifests, platform, board, joint)
                    print(f"      双脚同时搬 {joint}：后端收")
                except PinBindingError as exc:
                    print(f"      双脚同时搬：后端拒（{str(exc)[:60]}）")


if __name__ == "__main__":
    main()
