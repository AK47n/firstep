"""反向验证（临时）：停用本轮两处新判据 → 对应用例/全库相必须当场红。

两处：
  ① 成对实例谓词（uart/i2c）：停用后全库空种子相应回到 188（mspm0）+ 52（stm32）；
  ② `constraints` 数组（并列谓词）：退回「只发第一条」后默认脚种子相应回到 37（mspm0）。

跑法：python .scratch/mspm0-slot-conflict/reverse_verify_pair_predicate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import test_bindings_matrix as t  # noqa: E402
from contest_generator import pin_bindings as pb  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402

ORIGINAL = pb.build_bindings_matrix


def _measure(platform, seed_kind):
    board = t.BOARDS[platform]
    manifests = list_modules(t.LIBRARY_MODULES)
    seed = (
        {} if seed_kind == "空种子"
        else t._default_pin_seed(manifests, platform, board)
    )
    fg, fr, checked = t._stepwise_false_greens(manifests, platform, board, seed)
    return len(fg), len(fr), checked


def _disabled_pair_only():
    """① 停用成对实例谓词（uart/i2c）：把那些行的谓词抹掉、数组也清掉。"""
    def build(manifests, platform, board, raw):
        model = ORIGINAL(manifests, platform, board, raw)
        for row in model["roles"]:
            if row["type"] in pb._PAIRED_ROLE_KINDS:
                row["constraint"] = None
                row.pop("constraints", None)
        return model
    return build


def _first_only():
    """② 只发第一条谓词（退回 `constraint` 单条口径）。"""
    def build(manifests, platform, board, raw):
        model = ORIGINAL(manifests, platform, board, raw)
        for row in model["roles"]:
            row.pop("constraints", None)
        return model
    return build


def main():
    print("=== 基线（当前实现）===")
    for platform in ("mspm0", "stm32"):
        for kind in ("空种子", "默认脚种子"):
            print(f"  {platform:5s} {kind:6s} 假绿/假红/样本 =", _measure(platform, kind))

    for label, patched in (("① 停用成对实例谓词", _disabled_pair_only()), ("② 只发第一条谓词", _first_only())):
        pb.build_bindings_matrix = patched
        t.build_bindings_matrix = patched
        print(f"\n=== {label}（应回到修前的分歧数）===")
        for platform in ("mspm0", "stm32"):
            for kind in ("空种子", "默认脚种子"):
                print(f"  {platform:5s} {kind:6s} 假绿/假红/样本 =", _measure(platform, kind))

    pb.build_bindings_matrix = ORIGINAL
    t.build_bindings_matrix = ORIGINAL
    print("\n（产品代码未改动：补丁只在本进程内生效）")


if __name__ == "__main__":
    main()
