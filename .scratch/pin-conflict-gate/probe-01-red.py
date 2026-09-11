"""只读探针（生成期引脚冲突门禁 · 红证 + 口径核实）。

三件事，全只读、零网络、零额度：

1. **红证**：拿真机炸过的那个组合——`.scratch/real-run/out_2026H_mspm0/.contest_context.json`
   的 slugs（2026H / mspm0，真机 SysConfig exit=2、7 条 Resource conflict，日志
   `.scratch/real-run/verify-16-A8-mspm0-2026H-buildlog.txt`）——跑「生成时到底写了什么
   样的 syscfg」：母版 `library/masters/mspm0/mspm0.syscfg` → parse → prune(选中集)，
   按 `$assign` 的引脚分组，列出同脚多实例（判据 = SysConfig 的 Resource conflict）。
   现状**没有任何生成门禁**覆盖它（GENERATION_GATES 里没有 syscfg 引脚判据）——这就是红。

2. **对照**：单元级最小复现（母版全量 + 只选 motor+servo）应只剩 PA7 一条冲突，
   证明判据不是「把所有重叠都算上」的假阳性。

3. **口径核实**：`pin_bindings.auto_assign_bindings(..., 空 bindings)` 对这类
   **默认×默认**冲突到底报什么——「一键自动配置」按钮能不能解，决定工单的指路文案
   与范围（若不能解，要么把默认脚纳入求解，要么指路改成「手动绑脚 / 去模块」）。

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-conflict-gate/probe-01-red.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.boards import load_board  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.pin_bindings import (  # noqa: E402
    PinBindingError,
    auto_assign_bindings,
)
from contest_generator.syscfg_model import parse_syscfg  # noqa: E402

MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
CONTEXT = REPO / ".scratch" / "real-run" / "out_2026H_mspm0" / ".contest_context.json"


def conflicts_by_pin(text: str, slugs) -> dict[str, list[tuple[str, str]]]:
    """prune 后同脚多实例清单：{pin: [(实例路径, $assign 路径), …]}。"""
    model = parse_syscfg(text).prune(slugs)
    by_pin: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for assign in model.assigns:
        # 实例名 = path 的第一段（DC_MOTOR.associatedPins[3].pin → DC_MOTOR）
        instance = assign.path.split(".", 1)[0]
        by_pin[assign.pin].append((instance, assign.path))
    return {
        pin: sites
        for pin, sites in by_pin.items()
        if len({instance for instance, _ in sites}) > 1
    }


def report(title: str, slugs) -> dict[str, list[tuple[str, str]]]:
    found = conflicts_by_pin(MASTER.read_text(encoding="utf-8"), slugs)
    print(f"\n=== {title} ===")
    print(f"选中模块 {len(list(slugs))} 个：{', '.join(slugs)}")
    print(f"prune 后同脚多实例：{len(found)} 条")
    for pin, sites in sorted(found.items()):
        who = " × ".join(f"{inst}({path})" for inst, path in sites)
        print(f"  · {pin}：{who}")
    return found


def main() -> int:
    ctx = json.loads(CONTEXT.read_text(encoding="utf-8"))
    slugs = list(ctx["slugs"])
    real = report("① 真机炸过的组合（2026H / mspm0，现状无门禁拦）", slugs)
    print("  真机日志里的 7 条冲突：DC_MOTOR/SERVO_PWM 抢 PA7、HUIDU/L298N 抢 PA27/31 …")

    report("② 对照：只选 motor + servo（应只剩 PA7）", ["motor", "servo"])

    print("\n=== ③ 口径核实：一键自动配置对「默认×默认」冲突报什么 ===")
    manifests = [m for m in list_modules(REPO / "library" / "modules") if m.slug in slugs]
    board = load_board(
        REPO / "src" / "contest_generator" / "boards" / "mspm0-dimx.json"
    )
    try:
        result = auto_assign_bindings(manifests, "mspm0", board, {})
        print(f"  auto_assign_bindings(空 bindings) → 增量 {result.bindings or '（空）'}")
        print(f"    fixed={result.fixed or '（空）'}")
        conflict_pins = sorted(real)
        print(f"    shared 标注 {len(result.shared)} 条（kind 分布）：")
        for group in sorted(result.shared, key=lambda g: str(g.get("pin"))):
            marker = " ← 真机炸过的脚" if group.get("pin") in conflict_pins else ""
            print(f"      {group.get('pin')} kind={group.get('kind')} "
                  f"roles={group.get('roles')}{marker}")
    except PinBindingError as exc:
        print(f"  auto_assign_bindings 抛错：{exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
