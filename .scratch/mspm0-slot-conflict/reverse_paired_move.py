"""反向验证（工单 mspm0-slot-conflict/05）：停用前端「对脚跟随」→ 新用例必须当场红。

口径：把 `tests/test_bindings_matrix.py` 里的前端镜像 `_frontend_pair_follow` 换成
「恒 None」（= 工单 05 之前的行为：单角色绑一脚，成对角色搬不动），再跑本单新增的
四条用例。三条与「成对搬」直接相关的必须红——它们是本单的守卫；红了才证明它们
不是空转（假绿守卫的价值就在「停掉修复就抓得住」）。

用法：python .scratch/mspm0-slot-conflict/reverse_paired_move.py
证据：`.scratch/mspm0-slot-conflict/reverse-verify-paired-move.txt`
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

import test_bindings_matrix as T  # noqa: E402

CASES = (
    "test_paired_move_frontend_matches_backend",
    "test_paired_move_is_the_only_way_out_of_default_instance",
    "test_paired_move_round_trip_from_default_seed",
    "test_full_library_paired_move_has_no_divergence",
)


def main() -> int:
    print("=== 反向验证：停用前端「对脚跟随」（`_frontend_pair_follow` 恒 None）===")
    T._frontend_pair_follow = lambda *a, **k: None      # 退回工单 05 之前
    failed = 0
    for name in CASES:
        try:
            getattr(T, name)()
        except AssertionError as exc:
            first = (str(exc).splitlines() or [""])[0][:160]
            print(f"{name}: 红 [OK] {first}")
            failed += 1
        except Exception as exc:                        # noqa: BLE001（探针：如实报）
            print(f"{name}: 红 [OK] {type(exc).__name__} {(str(exc).splitlines() or [''])[0][:160]}")
            failed += 1
        else:
            print(f"{name}: 绿（不该绿——守卫空转！）")
    print(f"\n结论：{failed}/{len(CASES)} 条在停用对脚跟随后当场红（守卫有效）")
    return 0 if failed == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
