# -*- coding: utf-8 -*-
"""recon 3：按**引脚角色 type** 反查模块库，挑出「八个色族全覆盖」的最小模块集。

口径：mspm0 平台条目里的 `pins[].type`（角色类型 → 色族的映射单源 = 前端那张
`PIN_TYPE_STYLE` 表；这里只按类型的**前缀族**归并：gpio/pwm/enc/uart/i2c/spi/adc/exti）。

输出：类型 → 模块清单（按"该模块里这个类型的角色数"降序）+ 一个贪心选出的最小覆盖集。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULES = REPO / "library" / "modules"

FAMILIES = ["gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"]


def family_of(t: str) -> str:
    for f in FAMILIES:
        if t.startswith(f):
            return f
    return "其它"


def main() -> int:
    import sys as _sys
    platform = "mspm0"
    if "--platform" in _sys.argv:
        platform = _sys.argv[_sys.argv.index("--platform") + 1]
    by_type: dict[str, list[tuple[str, int]]] = defaultdict(list)
    by_family: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for man in sorted(MODULES.glob("*/manifest.json")):
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠ 读不动 {man}: {e}")
            continue
        slug = data.get("slug") or man.parent.name
        entry = (data.get("platforms") or {}).get(platform) or {}
        counts: dict[str, int] = defaultdict(int)
        for p in entry.get("pins") or []:
            t = p.get("type") or "?"
            counts[t] += 1
        for t, n in counts.items():
            by_type[t].append((slug, n))
            if n:
                by_family[family_of(t)][slug] += n

    out = []
    out.append(f"平台 = {platform}")
    out.append("=" * 96)
    for t in sorted(by_type):
        rows = sorted(by_type[t], key=lambda x: (-x[1], x[0]))[:6]
        out.append(f"  {t:<10}（{family_of(t)}）  " + "、".join(f"{s}×{n}" for s, n in rows))
    out.append("")
    out.append("=" * 96)
    out.append("§2 色族覆盖：每个族有哪些模块（角色数合计）")
    out.append("=" * 96)
    for fam in FAMILIES:
        rows = sorted(by_family[fam].items(), key=lambda x: (-x[1], x[0]))
        out.append(f"  {fam:<6} {len(rows):>3} 个模块：" + "、".join(f"{s}×{n}" for s, n in rows[:8])
                   + (" …" if len(rows) > 8 else ""))
    out.append("")
    out.append("=" * 96)
    out.append("§3 贪心最小覆盖集（每次挑「补得最多」的那个模块；并列取字典序小者）")
    out.append("=" * 96)
    need = set(FAMILIES)
    chosen: list[str] = []
    while need:
        gains = []
        for slug in {s for f in need for s in by_family[f]}:
            gain = {f for f in need if by_family[f].get(slug)}
            if gain:
                gains.append((-len(gain), slug, gain))
        if not gains:
            break
        gains.sort()
        _neg, best, best_gain = gains[0]
        chosen.append(best)
        need -= best_gain
    out.append(f"  选中 {len(chosen)} 个：{'、'.join(chosen)}")
    out.append(f"  仍未覆盖：{sorted(need) or '（无）'}")
    out.append("")
    out.append("  逐个受选模块覆盖的族：")
    for slug in chosen:
        fams = sorted(f for f in FAMILIES if by_family[f].get(slug))
        out.append(f"    {slug:<22} {fams}")
    out.append("")
    out.append("=" * 96)
    out.append("§4 候选大集合（一次选进来，覆盖最稳，但要小心引脚冲突报警）")
    out.append("=" * 96)
    cover_all = [slug for slug in {s for f in FAMILIES for s in by_family[f]}
                 if all(by_family[f].get(slug) for f in FAMILIES)]
    out.append(f"  单模块就覆盖八族的：{sorted(cover_all) or '（无）'}")

    body = "\n".join(out)
    dest = Path(__file__).with_suffix(".txt")
    dest.write_text(body + "\n", encoding="utf-8")
    print(body.encode("utf-8", "replace").decode("utf-8", "replace"))
    print(f"\n[落盘] {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
