# -*- coding: utf-8 -*-
"""引脚配色 02 / 03 单的验收：**两发真像素逐格对照**。

## 两种模式（`--expect`）

  · `same`（02 单）：取色来源换了、颜色**一个字节没换** ⇒ 静态取值与真像素都必须**逐格相同**。
  · `improve`（03 单）：色值收口 ⇒ 允许变好、**不许变差**；每格按阈值判一次（文字 4.5 / 非文字 3.0），
    并统计 变好 / 没变 / 变差。

## 认人（跨两发配对）

`(theme, scope, face, 文本/备注)` —— **不取行号、不取坐标**（DOM 结构变过：内联属性换成了
`data-pin-family`）。同一键出现多次（15 个类型标里同族重复）时按**多重集**配对，键内顺序无关。

跑法：

    python .scratch\\pin-type-contrast\\probe-02-compare.py --before before --after after
    python .scratch\\pin-type-contrast\\probe-02-compare.py --before before --after tokens --expect improve
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STYLE_KEYS = ("color", "background", "fill", "stroke", "border", "behind", "pcbFill")
TEXT_FACES = {"badge", "status", "board-label", "menu-badge"}


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
    mode = opt("--expect", "same")
    out: list[str] = []
    out.append("=" * 100)
    out.append(f"引脚配色验收（--expect {mode}）：{'颜色逐格相同？' if mode == 'same' else '改后不许变差、每格过阈值？'}")
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
    # ⚠ **配方漂移**：自动绑定的落点会变一格（同一个角色这一发绑上了、那一发是"默认"），
    #   于是某一格只在改前/改后一侧出现。`improve` 模式下如实记账、**不计入判据**
    #   （判据看的是"同键的那些格有没有变差"）；`same` 模式下它仍是硬差异（那一单要求逐格可配）。
    drift_note = (mode == "improve")
    if only_before:
        out.append(f"{'⚠ 配方漂移' if drift_note else '⚠'} 只在改前出现的键 {len(only_before)} 个"
                   + ("（不计入判据）" if drift_note else "（改后没量到同一格）") + "：")
        for k in only_before[:12]:
            out.append(f"    {k}")
    if only_after:
        out.append(f"{'⚠ 配方漂移' if drift_note else '⚠'} 只在改后出现的键 {len(only_after)} 个"
                   + ("（不计入判据）" if drift_note else "") + "：")
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
    out.append(f"配到 {pairs} 对格；静态取值不同的字段：{len(diffs)} 处"
               + ("（`--expect same`：应为 0）" if mode == "same" else "（`--expect improve`：色值本来就要变）"))
    for k, field, b, a, bb, ab in diffs[:40]:
        out.append(f"  {k} · {field}: 改前 {b} → 改后 {a}")

    # 真像素那一层：两发的**机器可读**读数逐格比（`probe-01-readings-<tag>.json`）
    # ⚠ 不许去解析 `.txt` 的中文表格：列宽与文本里的空格会把键解析错（实测过一次"格数对不上"的假账）。
    read_b = HERE / f"probe-01-readings-{opt('--before', 'before')}.json"
    read_a = HERE / f"probe-01-readings-{opt('--after', 'after')}.json"
    if read_b.is_file() and read_a.is_file():
        def ratios(path):
            data = json.loads(path.read_text(encoding="utf-8"))
            got = defaultdict(list)
            for r in data["rows"]:
                # ⚠ 键里**必须带主题**：不带的话浅色格与暗色格会撞成同一把键，
                #    排序配对就会把浅色的那一行配给暗色（实测踩过：报了个不存在的"变差 6.92→6.79"）。
                got[(r["theme"], r["face"], r["family"], r["text"])].append(
                    (r["static"], r["measured"], r["need"]))
            return got

        rb, ra = ratios(read_b), ratios(read_a)
        keys = sorted(set(rb) | set(ra))
        worst = []
        drift = []          # 只在改前/改后一侧出现的键：**配方漂移**（自动绑定的落点会变一格），不计入判据
        stats = {"变好": 0, "没变": 0, "变差": 0, "未达阈值": 0}
        for k in keys:
            vb = sorted(rb.get(k, []))
            va = sorted(ra.get(k, []))
            if not vb or not va:
                drift.append(k)
                continue
            if len(vb) != len(va):
                worst.append((k, f"格数不同（改前 {len(vb)} / 改后 {len(va)}）"))
                continue
            for (sb, mb, _nb), (sa, ma, na) in zip(vb, va):
                d = ma - mb
                stats["变好" if d > 0.05 else ("变差" if d < -0.05 else "没变")] += 1
                need = na
                if ma < need - 1e-9:
                    stats["未达阈值"] += 1
                if mode == "same":
                    if abs(sb - sa) > 0.005 or abs(mb - ma) > 0.05:
                        worst.append((k, f"静态 {sb:.2f}→{sa:.2f} / 实测 {mb:.2f}→{ma:.2f}"))
                else:
                    if d < -0.05:
                        worst.append((k, f"**变差**：实测 {mb:.2f}→{ma:.2f}"))
                    if ma < need - 1e-9:
                        worst.append((k, f"**仍不达标**：实测 {ma:.2f} < {need}"))
        out.append("")
        stats_txt = f"变好 {stats['变好']}、没变 {stats['没变']}、变差 {stats['变差']}"
        if mode == "improve":
            stats_txt += f"、未达阈值 {stats['未达阈值']}"
        out.append(f"真像素读数逐格对照（{len(keys)} 个键）：{stats_txt}")
        if drift:
            out.append(f"⚠ 配方漂移（只在改前/改后一侧出现的键，**不计入判据**）：{len(drift)} 处")
            for k in drift[:10]:
                side = "改前" if k in rb else "改后"
                out.append(f"  {k}：只在{side}那一发量到（自动绑定的落点变了）")
        if mode == "improve" and stats["变差"] == 0 and stats["未达阈值"] == 0 and not drift:
            out.append("✅ 没有一格变差、没有一格未达阈值，且两发量到的是同一批格")
        elif mode == "improve" and stats["变差"] == 0 and stats["未达阈值"] == 0:
            out.append("✅ **已量到的格**没有一格变差、没有一格未达阈值"
                       "（上列配方漂移的那些格这一发没量到——不拿它当通过）")
        for k, why in worst[:40]:
            out.append(f"  {k}：{why}")
    else:
        out.append("")
        out.append("（读数表还没生成——先跑 probe-01-read.py --tag before/<after>，再重跑本脚本）")

    body = "\n".join(out)
    dest = HERE / f"probe-02-compare-{mode}.txt"
    dest.write_text(body + "\n", encoding="utf-8")
    print(body.encode("utf-8", "replace").decode("utf-8", "replace"))
    print(f"\n[落盘] {dest}")
    ok = not only_before and not only_after and not diffs and not worst if mode == "same" \
        else not worst
    print(f"判定：{'✅ 通过' if ok else '⚠ 有差异，见上'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
