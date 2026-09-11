"""工单 pin-capacity/01 验收探针：门禁耗时增量 + 生成链路（generate_project）可达性。

只读、零额度、零网络。三件事：

1. 门禁耗时前后对照：同一真机 2026H 组合，分别测「未接诊断」（只做判据 + 抛错）与
   「已接诊断」（判据 + 容量诊断 + 抛错）的单次墙钟，取多轮最小值。
2. 生成链路可达性：真母版 `mspm0` + 真库 2026H 13 模块集（不带 bindings）调
   `generate_project` —— 必须在门禁处 400（`SyscfgPinConflictError`）且**输出目录未产生**，
   错误文案里带容量数字段（钉住「门禁在真机链路上拿得到板定义」这条前提）。
3. 同一组合的「容量诊断单独耗时」。

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-capacity/probe-04-gate-timing.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8")

import tests.test_generator as harness  # noqa: E402
from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.generator import (  # noqa: E402
    GateContext,
    SyscfgPinConflictError,
    _check_syscfg_pin_conflicts,
    generate_project,
)
from contest_generator.patchers import PLATFORM_MSPM0  # noqa: E402
from contest_generator.pin_capacity import diagnose_pin_capacity  # noqa: E402

TMP = REPO / ".scratch/pin-capacity/_tmp"
TMP.mkdir(parents=True, exist_ok=True)


def _best_ms(fn, rounds: int = 7) -> float:
    """多轮取最小墙钟（门禁正常形态就是抛错，异常按正常结果吞掉）。"""
    best = float("inf")
    for _ in range(rounds):
        start = time.perf_counter()
        try:
            fn()
        except SyscfgPinConflictError:
            pass
        best = min(best, (time.perf_counter() - start) * 1000)
    return best


def main() -> int:
    manifests = harness._real_mspm0_manifests(*harness.REAL_2026H_MSPM0_SLUGS)
    board = harness._mspm0_board()
    corpus = harness._real_mspm0_syscfg_corpus(TMP)

    print(f"[组合] 2026H/mspm0：{len(manifests)} 模块（含依赖展开）\n")

    gate_with_board = lambda: _check_syscfg_pin_conflicts(  # noqa: E731
        corpus, manifests, PLATFORM_MSPM0, GateContext(board=board)
    )
    gate_without_board = lambda: _check_syscfg_pin_conflicts(  # noqa: E731
        corpus, manifests, PLATFORM_MSPM0, GateContext()
    )
    diagnosis_only = lambda: diagnose_pin_capacity(  # noqa: E731
        manifests, PLATFORM_MSPM0, board, {}
    )

    for label, fn in (
        ("门禁（未接诊断：无板上下文）", gate_without_board),
        ("门禁（已接诊断：带板上下文）", gate_with_board),
        ("容量诊断单独跑", diagnosis_only),
    ):
        print(f"  {label:<28} 最快 {_best_ms(fn):7.2f} ms")

    # 生成链路可达性：真母版 + 真库 + 无 bindings（与 webapp 缺省路径同形）
    out_dir = TMP / "out-2026h-mspm0"
    if out_dir.exists():
        import shutil

        shutil.rmtree(out_dir)
    verdict = "未抛错"
    segment = False
    try:
        generate_project(
            platform=PLATFORM_MSPM0,
            slugs=[m.slug for m in manifests],
            masters_dir=REPO / "library" / "masters",
            module_library_dir=REPO / "library" / "modules",
            output_dir=out_dir,
            main_c_content="int main(void) { while (1) {} }\n",
        )
    except SyscfgPinConflictError as exc:
        verdict = "SyscfgPinConflictError"
        segment = "【引脚容量】" in str(exc)
    except Exception as exc:  # noqa: BLE001 —— 如实报出别的失败形态
        verdict = f"{type(exc).__name__}: {exc}"
    print(f"\n[生成链路] generate_project → {verdict}")
    print(f"[生成链路] 文案带容量段 = {segment}；输出目录产生 = {out_dir.exists()}")
    print(f"[生成链路] 板上可用 IO（board_for_platform）= "
          f"{sum(1 for p in board_for_platform(PLATFORM_MSPM0).pins if p.capabilities)} 脚")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
