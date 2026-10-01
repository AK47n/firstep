# -*- coding: utf-8 -*-
"""引脚配色 02 单的验收：**改前 / 改后真像素逐格相同**（取色来源换了，颜色一个字节没换）。

## 为什么这是硬判据

02 单做的事是"把取色从内联模板串搬进样式块"——**只换取色来源**。所以
① 静态那一层（computed `color` / `background` / SVG `fill`·`stroke`）必须**逐字相同**；
② 真像素那一层（读 PNG 的比值）必须**逐格相同**（留 0.05 的量化余量）。
任何一格不同都要解释——它要么是搬错了，要么是搬的时候顺手改了颜色（那是 03 单的事）。

## 认人（跨两发配对）

`(theme, scope, face, 文本/备注)` —— **不取行号、不取坐标**（DOM 结构变过：内联属性换成了
`data-pin-family`）。同一键出现多次（15 个类型标里同族重复）时按**多重集**配对，键内顺序无关。

跑法：

    python .scratch\\pin-type-contrast\\probe-02-compare.py --before before --after after
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STYLE_KEYS = ("color", "background", "fill", "stroke", "border", "behind", "pcbFill")


def key_of(row):
    return (row["theme"], row["scope"], row["face"], row.get("note") or row.get("text") or "")


def load(tag):
    path = HERE / f"probe-01-shots-{tag}.json"
    if not path.is_file():
        raise SystemExit(f"找不到 {path}——先跑 probe-01-pin-family-pixels.mjs --tag {tag}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = sys.argv[1:]

    def opt(name, dflt):
        i = args.index(name) + 1 if name in args else None
        return args[i] if i else dflt

    before = load(opt("--before", "before"))
    after = load(opt("--after", "after"))
    out: list[str] = []
    out.append("=" * 100)
    out.append("引脚配色 02 单验收：取色来源换了，颜色逐格相同？")
    out.append(f"改前 = probe-01-shots-{opt('--before', 'before')}.json（{len(before['rows'])} 格）"
               f"；改后 = probe-01-shots-{opt('--after', 'after')}.json（{len(after['rows'])} 格）")
    out.append("=" * 100)

    bmap, amap = defaultdict(list), defaultdict(list)
    for r in before["rows"]:
        bmap[key_of(r)].append(r)
    for r in after["rows"]:
        amap[key_of(r)].append(r)

    only_before = sorted(set(bmap) - set(amap))
    only_after = sorted(set(amap) - set(bmap))
    if only_before:
        out.append(f"⚠ 只在改前出现的键 {len(only_before)} 个（改后没量到同一格）：")
        for k in only_before[:12]:
            out.append(f"    {k}")
    if only_after:
        out.append(f"⚠ 只在改后出现的键 {len(only_after)} 个：")
        for k in only_after[:12]:
            out.append(f"    {k}")

    diffs = []
    pairs = 0
    for k in sorted(set(bmap) & set(amap)):
        bl, al = bmap[k], amap[k]
        # 多重集配对：键内先按静态取值排序，再逐位比（同键的格子外观应当一致）
        bl = sorted(bl, key=lambda r: json.dumps({x: r.get(x) for x in STYLE_KEYS}, sort_keys=True))
        al = sorted(al, key=lambda r: json.dumps({x: r.get(x) for x in STYLE_KEYS}, sort_keys=True))
        for rb, ra in zip(bl, al):
            pairs += 1
            for field in STYLE_KEYS:
                if rb.get(field) != ra.get(field):
                    diffs.append((k, field, rb.get(field), ra.get(field), rb.get("box"), ra.get("box")))
        if len(bl) != len(al):
            out.append(f"⚠ 同键格数不同（改前 {len(bl)} / 改后 {len(al)}）：{k}")

    out.append("")
    out.append(f"配到 {pairs} 对格；静态取值不同的字段：{len(diffs)} 处")
    for k, field, b, a, bb, ab in diffs[:40]:
        out.append(f"  {k} · {field}: 改前 {b} → 改后 {a}")

    # 真像素那一层：两发的读数表逐格比（读数值由 probe-01-read.py 落盘）
    read_b = HERE / f"probe-01-readings-{opt('--before', 'before')}.txt"
    read_a = HERE / f"probe-01-readings-{opt('--after', 'after')}.txt"
    if read_b.is_file() and read_a.is_file():
        def ratios(path):
            got = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("  ") or line.lstrip().startswith(("面", "【", "准备", "没量到")):
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                face, fam, text = parts[0], parts[1], parts[2]
                try:
                    static, measured = float(parts[3]), float(parts[4])
                except ValueError:
                    continue
                got.setdefault((face, fam, text), []).append((static, measured))
            return got

        rb, ra = ratios(read_b), ratios(read_a)
        keys = sorted(set(rb) | set(ra))
        worst = []
        for k in keys:
            vb = sorted(rb.get(k, []))
            va = sorted(ra.get(k, []))
            if len(vb) != len(va):
                worst.append((k, f"格数不同（改前 {len(vb)} / 改后 {len(va)}）"))
                continue
            for (sb, mb), (sa, ma) in zip(vb, va):
                if abs(sb - sa) > 0.005 or abs(mb - ma) > 0.05:
                    worst.append((k, f"静态 {sb:.2f}→{sa:.2f} / 实测 {mb:.2f}→{ma:.2f}"))
        out.append("")
        out.append(f"真像素读数逐格对照（{len(keys)} 个键）：不一致 {len(worst)} 处")
        for k, why in worst[:40]:
            out.append(f"  {k}：{why}")
    else:
        out.append("")
        out.append("（读数表还没生成——先跑 probe-01-read.py --tag before/after，再重跑本脚本）")

    body = "\n".join(out)
    dest = HERE / "probe-02-compare.txt"
    dest.write_text(body + "\n", encoding="utf-8")
    print(body.encode("utf-8", "replace").decode("utf-8", "replace"))
    print(f"\n[落盘] {dest}")
    verdict = "✅ 逐格相同" if not diffs and not only_before and not only_after else "⚠ 有差异，见上"
    print(f"判定：{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
