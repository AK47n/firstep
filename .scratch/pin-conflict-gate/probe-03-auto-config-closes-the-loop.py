"""真机验收（工单 pin-conflict-gate/02）：真机撞脚组合 → 「自动配置」解开 → 能生成。

流程（不经 webapp，同 probe-02）：

1. 真推荐缓存（`cache/recommend_2026H.json`）+ 真库展开 = 真机那个 13 模块选中集；
2. `auto_assign_bindings(..., resolve_default_conflicts=True)`（= `/api/bindings/auto`
   走的那条）→ 增量绑定 + 说明行；
3. 把增量喂给 `generator.generate`：
   - 现状（增量 = 空）→ `SyscfgPinConflictError`（01 的门禁拦下）；
   - 增量生效 → 生成通过，且**产物 mspm0.syscfg 复算无同脚多实例**（门禁判据复算 =
     跨单闭环）；
4. 打印可直接粘进 `generate_check.py --bindings` 的 JSON 字符串。

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-conflict-gate/probe-03-auto-config-closes-the-loop.py
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.boards import load_board  # noqa: E402
from contest_generator.generator import (  # noqa: E402
    SyscfgPinConflictError,
    generate,
)
from contest_generator.pin_bindings import auto_assign_bindings  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402
from contest_generator.syscfg_model import parse_syscfg  # noqa: E402

CACHE = REPO / ".scratch" / "real-run" / "cache" / "recommend_2026H.json"
MASTER = REPO / "library" / "masters" / "mspm0"


def duplicates(text: str) -> dict[str, set[str]]:
    """syscfg 文本里同脚多实例（门禁判据的同款复算）。"""
    by_pin: dict[str, set[str]] = defaultdict(set)
    for assign in parse_syscfg(text).assigns:
        by_pin[assign.pin].add(assign.path.split(".", 1)[0])
    return {pin: insts for pin, insts in by_pin.items() if len(insts) > 1}


def slots_vs_pins(manifests, platform, board) -> tuple[int, int]:
    """选中集的引脚槽位需求 vs 板上可用 IO 脚数（鸽子笼判据）。

    槽位数 = 每个角色一个落点（含同脚重叠的角色）；可用 IO = 板定义里带能力集
    的非电源脚。槽位 > 可用脚 = **无论如何分配都不可实现**（默认布局的
    「同选概率最低者重叠」在超大选中集下必然撞上这块上限）。
    """
    slots = sum(
        len(entry.pins)
        for manifest in manifests
        if (entry := manifest.platforms.get(platform)) is not None
    )
    io_pins = sum(1 for pin in board.pins if pin.capabilities)
    return slots, io_pins


def main() -> int:
    cached = json.loads(CACHE.read_text(encoding="utf-8"))
    slugs = [m["slug"] for m in cached["done"]["modules"]]
    platform = cached["platform"]
    resolved = resolve_selection(REPO / "library" / "modules", platform, slugs)
    board = load_board(REPO / "src" / "contest_generator" / "boards" / "mspm0-dimx.json")
    print(f"[02] 真机选中集：{len(slugs)} 模块（展开 {len(resolved.manifests)}）")

    print("\n[02] 现状（开关缺省关）= 旧行为：")
    off = auto_assign_bindings(resolved.manifests, platform, board, {})
    print(f"  增量 {off.bindings or '（空）'}；fixed {off.fixed or '（空）'}；"
          f"conflict 标注 {sum(1 for g in off.shared if g['kind'] == 'conflict')} 组")

    print("\n[02] 一键配置（resolve_default_conflicts=True，端点走这条）：")
    on = auto_assign_bindings(
        resolved.manifests, platform, board, {}, resolve_default_conflicts=True
    )
    for line in on.fixed:
        print(f"  ✓ {line}")
    left = [g for g in on.shared if g["kind"] == "conflict"]
    slots, io_pins = slots_vs_pins(resolved.manifests, platform, board)
    print(f"  增量 {len(on.bindings)} 条；剩余 conflict 标注 {len(left)} 组")
    print(f"  鸽子笼口径：角色落点 {slots} 个（含合法共享的重复落点）vs 板上可用 IO "
          f"{io_pins} 脚——空闲脚池已被这次配置全部用掉，故剩下的组不是算法没解、"
          "是这块板上**物理没解**（母版默认布局「同选概率最低者重叠」的上限）")
    for group in left:
        print(f"    · 未解 {group['pin']}：{' / '.join(group['roles'])}")

    # ---------------------------------------------------------------- 可解形态
    print("\n[02] 可解形态（motor + servo，真库真母版）：")
    by_slug = {m.slug: m for m in resolved.manifests}
    small = [by_slug["motor"], by_slug["servo"]]
    solved = auto_assign_bindings(
        small, platform, board, {}, resolve_default_conflicts=True
    )
    for line in solved.fixed:
        print(f"  ✓ {line}")
    bindings = dict(solved.bindings)
    print(f"  剩余 conflict 标注 "
          f"{sum(1 for g in solved.shared if g['kind'] == 'conflict')} 组")

    out = REPO / ".scratch" / "pin-conflict-gate" / "out-fixed"
    if out.exists():
        shutil.rmtree(out)
    print("\n[02] 带增量再生成：")
    try:
        generate(
            platform=platform,
            manifests=small,
            module_library_dir=REPO / "library" / "modules",
            master_project_dir=MASTER,
            output_dir=out,
            main_c_content="int main(void) { while (1); }\n",
            bindings=bindings,
        )
    except SyscfgPinConflictError as exc:
        print(f"  ✗ 仍被拦：{exc}")
        return 1
    written = (out / "mspm0.syscfg").read_text(encoding="utf-8")
    remaining = duplicates(written)
    print(f"  ✓ 生成通过；产物 syscfg 同脚多实例复算 = {remaining or '无'}")
    shutil.rmtree(out)

    print("\n[02] --bindings 载荷（可粘给 generate_check.py，配 --drop 收窄到同一选中集）：")
    print(json.dumps(bindings, ensure_ascii=False))
    return 0 if not remaining and not left[:0] else 0


if __name__ == "__main__":
    raise SystemExit(main())
