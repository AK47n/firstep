"""浅色调色板轮 · 读数探针（03）：守卫那张例外表 ↔ 盘上现算的双向对账。

**单源**：例外表、族表、阈值全部**从守卫源码解析**（不另抄一份）——
格式变化就大声失败，别拿空表当读数（描边那轮 `probe-03` 的先例）。

它报四栏：
  ① 机械配对：总数、两主题不达标数、逐条清单（比值 / 需 / 选择器 / 色对）；
  ② 例外表：条数、类别分布、主题分布、逐条（含冻结值）；
  ③ **双向差**：盘上不达标但表里没有（漏登记）/ 表里有但盘上认不到（死条）；
  ④ 族面：每族每主题的最坏格与冻结值对照（`--tok-*` 那笔账的现成清单）。

跑法（仓库根）：
    python .scratch/light-contrast/probe-03-contrast.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402


def rows_as_dicts() -> list[dict]:
    """守卫里的例外表 → dict（`[主题, 认人键, 类别, 理由, 冻结比值]`）。"""
    out = []
    for row in L.load_exceptions():
        if len(row) < 5:
            raise SystemExit(f"例外表某行形状不对（应 5 格）：{row}")
        out.append(dict(theme=row[0], key=row[1], kind=row[2], why=row[3], frozen=float(row[4])))
    return out


def main() -> None:
    text = L.read_page()
    tok = L.Tokens(text)
    pairs = L.contrast_pairs(text, tok)
    exceptions = rows_as_dicts()
    reg = {(e["theme"], e["key"]): e for e in exceptions}

    print("=" * 78)
    print("浅色调色板轮 · 读数（probe-03：例外表 ↔ 盘上双向对账）")
    print(f"页面：{L.PAGE.relative_to(L.ROOT)}；守卫：{L.GUARD.relative_to(L.ROOT)}")
    print("=" * 78)

    print("\n## ① 机械配对（同规则 `color:` × `background:`，两主题各算一遍）\n")
    print(f"总数 **{len(pairs)}**")
    for theme in ("dark", "light"):
        sub = [p for p in pairs if p.theme == theme]
        bad = [p for p in sub if p.ratio < p.need - 1e-9]
        print(f"  {theme:<6}{len(sub):>4} 对，不达标 **{len(bad)}**")
    bad = [p for p in pairs if p.ratio < p.need - 1e-9]
    if bad:
        print(f"\n{'主题':<7}{'比值':>6}{'需':>5}  选择器 / 色对")
        for p in sorted(bad, key=lambda x: (x.theme, x.ratio)):
            print(f"{p.theme:<7}{p.ratio:>6.2f}{p.need:>5.1f}  {p.selector[:58]}  [{p.fg_hex} on {p.bg_hex}]")

    print("\n## ② 例外表（守卫源码解析；单源）\n")
    print(f"条数 **{len(exceptions)}**；类别分布 {dict(Counter(e['kind'] for e in exceptions))}；"
          f"主题分布 {dict(Counter(e['theme'] for e in exceptions))}")
    mech = [e for e in exceptions if not e["key"].startswith(("族：", "令牌："))]
    fam = [e for e in exceptions if e["key"].startswith("族：")]
    tok_rows = [e for e in exceptions if e["key"].startswith("令牌：")]
    print(f"机械面 {len(mech)} 条 / 族面 {len(fam)} 条 / 令牌面 {len(tok_rows)} 条")
    print(f"\n{'主题':<7}{'类别':<7}{'冻结':>6}  认人键")
    for e in sorted(exceptions, key=lambda x: (x["theme"], x["kind"], x["frozen"])):
        print(f"{e['theme']:<7}{e['kind']:<7}{e['frozen']:>6.2f}  {e['key'][:66]}")

    print("\n## ③ 双向差（本探针的核心读数）\n")
    missing = []
    for p in pairs:
        if p.ratio >= p.need - 1e-9:
            continue
        hit = reg.get((p.theme, p.selector))
        if hit is None:
            missing.append(p)
        elif abs(hit["frozen"] - p.ratio) > 0.01:
            missing.append(p)
    print(f"盘上不达标 / 冻结值对不上的：**{len(missing)}** 条")
    for p in missing:
        print(f"  {p.theme} {p.selector[:56]} 现算 {p.ratio:.2f}")
    seen = {(p.theme, p.selector) for p in pairs}
    dead = [e for e in mech if (e["theme"], e["key"]) not in seen]
    # 族面 / 令牌面各有自己的"认得到人"判据（与守卫里那两条反向对账同口径）
    fam_labels = {L.contrast_family_key(f[0]) for f in L.load_families()}
    tok_literals = {L.contrast_token_key(r[0]) for r in L.load_token_bases()}
    dead += [e for e in fam if e["key"] not in fam_labels]
    dead += [e for e in tok_rows if e["key"] not in tok_literals]
    print(f"\n表里有、盘上认不到的（死条）：**{len(dead)}** 条")
    for e in dead:
        print(f"  {e['theme']} {e['key'][:60]}")    # 反过来：过线了却还挂着债（02/03 单修完之后最该看的一栏）
    stale = [e for e in mech if (e["theme"], e["key"]) in seen
             and next(p for p in pairs if (p.theme, p.selector) == (e["theme"], e["key"])).ratio >=
             next(p for p in pairs if (p.theme, p.selector) == (e["theme"], e["key"])).need - 1e-9]
    print(f"\n已经过线却还挂着登记的（该摘掉）：**{len(stale)}** 条")
    for e in stale:
        print(f"  {e['theme']} {e['key'][:60]}")

    print("\n## ④ 族面：每族每主题的最坏格 ↔ 冻结值\n")
    print("（族表**从守卫源码解析**；逐格矩阵看 `probe-01-inventory.txt` §8——这里只报最坏格，"
          "免得同一张 100 行矩阵在两张读数里各抄一份）\n")
    cells = L.contrast_family_cells(text, tok)
    families = L.load_families()
    print(f"{'族':<40}{'主题':<7}{'最坏格':<34}{'比值':>7}{'需':>5}{'冻结':>7}")
    for label, _pick, _layers, _kind, _why in families:
        for theme in ("dark", "light"):
            sub = [c for c in cells if c["label"] == label and c["theme"] == theme]
            if not sub:
                print(f"{label[:38]:<40}{theme:<7}{'（一格都没算出来）':<34}")
                continue
            worst = min(sub, key=lambda c: c["ratio"])
            e = reg.get((theme, L.contrast_family_key(label)))
            frozen = f"{e['frozen']:.2f}" if e else "—（过线，未登记）"
            print(f"{label[:38]:<40}{theme:<7}{worst['token'] + ' on ' + worst['layer']:<34}"
                  f"{worst['ratio']:>7.2f}{worst['need']:>5.1f}{frozen:>7}")

    print("\n## ⑤ 令牌面（第三面）：无底规则里的文字令牌 ↔ 冻结值\n")
    print("（令牌表同样从守卫源码解析；这一面是 01 单双轴评审点名的覆盖缺口——")
    print(" 584 条含 `color:` 的规则里 390 条底在基类/祖先，机械面看不见它们）\n")
    table = L.load_token_bases()
    tcells = L.contrast_token_cells(text, tok, table=[(lit, layers, kind, why)
                                                      for lit, layers, kind, why in table])
    used = L.unbased_color_tokens(text)
    print(f"无底规则里当文字色用的令牌：**{len(used)}** 个；令牌表 **{len(table)}** 行"
          f"（其中空底的 skip 行 {sum(1 for r in table if not r[1])} 行）\n")
    print(f"{'令牌字面':<26}{'主题':<7}{'最坏格压':<18}{'比值':>7}{'需':>5}{'冻结':>7}")
    for literal, layers, kind, _why in table:
        if not layers or literal not in used:
            continue
        for theme in ("dark", "light"):
            sub = [c for c in tcells if c["literal"] == literal and c["theme"] == theme]
            if not sub:
                continue
            worst = min(sub, key=lambda c: c["ratio"])
            e = reg.get((theme, L.contrast_token_key(literal)))
            frozen = f"{e['frozen']:.2f}" if e else "—（过线，未登记）"
            print(f"{literal:<26}{theme:<7}{worst['layer']:<18}{worst['ratio']:>7.2f}"
                  f"{worst['need']:>5.1f}{frozen:>7}")

    print("\n## ⑥ 覆盖审计：机械面会不会漏掉「同选择器、跨规则」的配对？\n")
    print("机械面按「**同一条规则**里既有 `color:` 又有 `background:`」配对。样式块里还存在另一种写法——")
    print("同一个选择器拆成两条规则，一条给字色、一条给底。这一栏把那种写法也配一遍，与机械面对差集：\n")
    from collections import defaultdict
    by = defaultdict(lambda: {"color": [], "bg": []})
    for sel, body in L.css_rules(L.contrast_style_text(text)):
        d = L.decls(body)
        if "color" in d:
            by[sel]["color"].append(d["color"])
        b = L.bg_of_rule(d)
        if b:
            by[sel]["bg"].append(b)
    split = set()
    combos = 0
    for sel, v in by.items():
        if not (v["color"] and v["bg"]):
            continue
        for theme in ("dark", "light"):
            fg = tok.parse(v["color"][0], theme)
            bg = tok.parse(v["bg"][0], theme)
            if fg is None or bg is None:
                continue
            combos += 1
            base = L.base_of(tok, theme)
            be = L.over(bg, base)
            if L.contrast(L.over(fg, be), be) < L.CONTRAST_THRESHOLDS["small"] - 1e-9:
                split.add((theme, sel))
    mech_bad = {(p.theme, p.selector) for p in pairs if p.ratio < p.need - 1e-9}
    print(f"跨规则组合数 **{combos}**；其中不达标 **{len(split)}**")
    print(f"机械面不达标 **{len(mech_bad)}**")
    print(f"**只在跨规则面**（机械面漏掉）：{len(split - mech_bad)} 条")
    for x in sorted(split - mech_bad):
        print(f"  {x[0]} {x[1]}")
    print(f"**只在机械面**：{len(mech_bad - split)} 条")
    for x in sorted(mech_bad - split):
        print(f"  {x[0]} {x[1]}")
    print("\n（两向差集都为 0 = 在这个文件上，两种口径**逐条相同**——"
          "机械面没有漏掉跨规则那种写法；哪天真漏了，这一栏会先红。）")

    print("\n## ⑦ 底部口径（别混着读）\n")
    print("  · 底 = **元素自己那层背景合成到 `--panel` 上**——上一轮那三个乐观数"
          "（6.11 / 5.19 / 3.39）量的是祖先底，本轮口径已更正；")
    print("  · 阈值两档：小字 4.5 / 大字（≥24px 或 ≥18.66px+bold）3.0；族面 `nontext` 用 3.0；")
    print("  · **三面各管一段**：机械面 = 同规则带底的配对；族面 = 底在代码页那几层的族；")
    print("    令牌面 = 无底规则里的文字令牌（票面口径：底在基类/祖先，选择器级判不了）。")
    print("  · 三面都**只登记不达标与不适用**（达标的现算即可）——这与描边那轮"
          "『115 条全登记』不是同一把尺。")


if __name__ == "__main__":
    main()
