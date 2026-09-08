"""门禁实测（只读，不落盘改动）：beep + jq8900 同吃 PA15 的冲突标注。

两种形态都跑：
- 现状（修复后）：真实库数据直接喂既有引脚冲突能力 `auto_assign_bindings`
  （`/api/bindings/auto` 与前端 pinShareClass 的同一数据源）；
- 修复前：把 beep 的 `pins` 声明从内存 manifest 里摘掉（等价于补声明之前的
  清单），同一调用——看 beep 是否从 PA15 组里消失（= 静默放行）。

用法：python .scratch/beep-pin-declaration/probe_gate.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.boards import BOARDS_DIR, load_boards  # noqa: E402
from contest_generator.manifest import ModuleManifest  # noqa: E402
from contest_generator.pin_bindings import auto_assign_bindings  # noqa: E402

MODULES = ROOT / "library" / "modules"
PLATFORM = "stm32"


def _manifests(*, beep_pins_declared: bool) -> list[ModuleManifest]:
    out: list[ModuleManifest] = []
    for d in sorted(MODULES.iterdir()):
        if not d.is_dir():
            continue
        m = ModuleManifest.load(d)
        if m.slug == "beep" and not beep_pins_declared:
            entry = m.platforms[PLATFORM]
            m = replace(
                m,
                platforms={**m.platforms, PLATFORM: replace(entry, pins=())},
            )
        out.append(m)
    return out


def _pa15_group(manifests: list[ModuleManifest]) -> dict[str, object] | None:
    board = next(b for b in load_boards(BOARDS_DIR) if b.platform == PLATFORM)
    result = auto_assign_bindings(manifests, PLATFORM, board, {})
    return next((dict(g) for g in result.shared if g["pin"] == "PA15"), None)


def _report(label: str, manifests: list[ModuleManifest]) -> None:
    group = _pa15_group(manifests)
    print(f"=== {label} ===")
    if group is None:
        print("  PA15 无标注（同脚冲突静默放行）")
        return
    print(f"  roles : {group['roles']}")
    print(f"  kind  : {group['kind']}")
    print(f"  reason: {group['reason']}")
    roles = [str(r) for r in group["roles"]]  # type: ignore[union-attr]
    print(
        f"  beep 可见: {any(r.startswith('beep.') for r in roles)}；"
        f"jq8900 在组内: {'jq8900.JQ8900_TX' in roles}"
    )


def main() -> None:
    full = {True: _manifests(beep_pins_declared=True),
            False: _manifests(beep_pins_declared=False)}
    # 场景 A：全库选中（含 config——config.BUZZER 与 beep 同宏同脚）
    _report("场景 A 修复前（全库选中）", full[False])
    _report("场景 A 修复后（全库选中）", full[True])
    # 场景 B：只选 beep + jq8900（题面：两者同吃 PA15）——修复前无人认领该脚
    for label, declared in (("场景 B 修复前", False), ("场景 B 修复后", True)):
        subset = [m for m in full[declared] if m.slug in ("beep", "jq8900", "delay")]
        _report(f"{label}（仅 beep + jq8900）", subset)


if __name__ == "__main__":
    main()
