"""代码配色族轮 · 禁用态像素读数（probe-08 的第二半）：把元素截图里的**真像素**读出来，
与「静态声明 + opacity 合成」的预测逐格对差，并给出**禁用控件在屏幕上的实测比值**（工单 03）。

## 它为什么存在

`probe-07` 的禁用桶曾经**实测是空的**（被"祖先渐变"整条滤掉），于是"禁用态达标了没有"这件事
在渲染面**没有任何读数**。这一支补上：真元素 + 真像素，一个元素一张 PNG，可人眼复核。

## 口径（不另起一套）

· 颜色数学 / 令牌 → `probe_lib`（与守卫腿⑧ 同源、镜像守卫钉住）；
· 读像素（直方图 / 主色 / 字形核心） → `pixel_lib`（与 probe-02 读数半共用同一份）；
· 预测 = 浏览器怎么合成：
    `bg' = op × over(background-color, behind) + (1-op) × behind`
    `fg' = op × color + (1-op) × behind`（`opacity < 1` 时整块先自己合成再压到 behind 上）
  其中 `behind` = 祖先背景合成（probe-08 的 mjs 记进 JSON）。**opacity = 1 的新态**下
  这两个式子退化成"字形压在底色上"，与静态面的算法一致。

跑法（仓库根；先跑 probe-08-disabled-state.mjs --tag before / --tag after）：

    python .scratch\\code-contrast\\probe-08-disabled-state-read.py
    python .scratch\\code-contrast\\probe-08-disabled-state-read.py --tag after
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                        # pixel_lib（读像素的公共半）
sys.path.insert(0, str(HERE.parent / "light-contrast"))

import pixel_lib as PX  # noqa: E402
import probe_lib as L  # noqa: E402

NUM_RE = re.compile(r"[\d.]+")


def rgba(css: str):
    """`rgb(r, g, b)` / `rgba(r, g, b, a)` → 四元组（解不出 = None）。"""
    if not css:
        return None
    parts = NUM_RE.findall(css)
    if len(parts) < 3:
        return None
    r, g, b = (int(float(p)) for p in parts[:3])
    a = float(parts[3]) if len(parts) > 3 else 1.0
    return (r, g, b, a)


def predicted(shot):
    """浏览器合成出来的「字形 / 底」（不透明 RGB）——静态声明 + opacity。"""
    fg = rgba(shot["color"])
    behind = tuple(shot["behind"])[:3]
    if fg is None:
        return None, None, None
    own = rgba(shot["background"])
    bg_own = L.over(own, behind) if own is not None else behind
    op = float(shot.get("opacity", 1))
    if op >= 1:
        return L.over(fg, bg_own), bg_own, op
    blend = lambda c: tuple(int(v + 0.5) for v in (op * c[i] + (1 - op) * behind[i] for i in range(3)))
    return blend(L.over(fg, bg_own) if fg[3] < 1 else fg[:3]), blend(bg_own), op


def main() -> None:
    args = sys.argv[1:]
    only = args[args.index("--tag") + 1] if "--tag" in args else None
    files = sorted(HERE.glob("probe-08-shots-*.json"))
    if only:
        files = [f for f in files if f.name.endswith(f"-{only}.json")]
    if not files:
        raise SystemExit("一个 probe-08-shots-*.json 都没有——先跑 probe-08-disabled-state.mjs")

    text = L.read_page()
    tok = L.Tokens(text)
    print("=" * 104)
    print("代码配色族轮 · 禁用态读数（probe-08：真元素截图 + 读像素）")
    print(f"口径单源 = probe_lib / pixel_lib；"
          f"静态参照：`--muted` 压 `--panel-2` = "
          f"浅 {L.contrast(tok.value('--muted', 'light'), tok.value('--panel-2', 'light')):.2f} / "
          f"暗 {L.contrast(tok.value('--muted', 'dark'), tok.value('--panel-2', 'dark')):.2f}"
          f"（族面「--muted × 禁用态底」那两格）")
    print("=" * 104)

    summary = {}      # tag → [(theme, tab, slug, text, ratio, opacity)]
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        tag = data.get("tag", f.stem)
        print(f"\n{'#' * 104}\n# tag = {tag}（{f.name}；{len(data['shots'])} 格）\n{'#' * 104}")
        print(f"{'主题':<7}{'页签':<11}{'形态':<13}{'op':>5}{'实测比值':>9}{'底':<10}{'字形':<10}"
              f"{'预测':>7}{'差':>5}  文字")
        rows = []
        for s in data["shots"]:
            if not s["text"]:
                # 没有字形像素（空输入框那类）：截图里最"远"的像素会是描边/圆角，
                # 拿它当"字形"算比值是假证据——如实跳过（PNG 仍在盘上可人眼看）。
                print(f"{s['theme']:<7}{s['tab']:<11}{s['how']:<13}{s.get('opacity', 1):>5}"
                      f"{'—':>9}   这一格**没有文字**（无字形像素）——跳过比值，只留截图")
                continue
            cnt = PX.histogram(HERE / s["file"])
            bg_meas, n_bg = PX.dominant(cnt)
            fg_meas = PX.glyph_core(cnt)
            cover = n_bg / sum(cnt.values())
            r_meas = L.contrast(fg_meas, bg_meas)
            fg_pred, bg_pred, op = predicted(s)
            gap = PX.dist(fg_meas, fg_pred) + PX.dist(bg_meas, bg_pred) if fg_pred else None
            mark = "✅" if r_meas >= L.CONTRAST_THRESHOLDS["small"] else "❌"
            rows.append((s["theme"], s["tab"], s["slug"], s["text"], r_meas, op))
            summary.setdefault(tag, []).append(
                (s["theme"], s["tab"], s["slug"], s["text"], round(r_meas, 2), op))
            print(f"{s['theme']:<7}{s['tab']:<11}{s['how']:<13}{op:>5}"
                  f"{r_meas:>7.2f}{mark}{PX.hx(bg_meas):<10}{PX.hx(fg_meas):<10}"
                  f"{(PX.hx(fg_pred) if fg_pred else '—'):>7}{(str(gap) if gap is not None else '—'):>5}"
                  f"  「{s['text']}」"
                  + (f"  底占 {cover:.0%}" if cover < 0.30 else "")
                  + ("  ⚠祖先渐变" if s.get("ancestorGradient") else ""))
        if rows:
            worst = min(rows, key=lambda x: x[4])
            print(f"  —— {tag} 最低：**{worst[4]:.2f}**（{worst[1]} / {worst[3]}）")

    # `before` 永远排在前面（逐格对照的方向 = 改前 → 改后；按字典序排会把方向搞反）
    tags = sorted(summary, key=lambda t: (t != "before", t))
    if len(tags) >= 2:
        print(f"\n{'=' * 104}\n## 逐格对照（{tags[0]} → {tags[1]}）：禁用态改前 / 改后\n")
        # 两张表都按同一把认人键 `(主题, 页签, 元素, 文字)` 索引（**不写两遍查找**）
        idx = {t: {(th, tab, slug, txt): (r, o) for th, tab, slug, txt, r, o in summary[t]}
               for t in tags[:2]}
        a, b = idx[tags[0]], idx[tags[1]]
        turned_red, unchanged, improved = 0, 0, 0
        for k, (ra, oa) in a.items():
            hit = b.get(k)
            if hit is None:
                print(f"  {str(k):<52}{ra:>6.2f} → ——（改后没拍到这一格）")
                continue
            rb, ob = hit
            if rb > ra:
                verdict, improved = "✅ 变好", improved + 1
            elif rb < ra:
                verdict, turned_red = "❌ **变差**", turned_red + 1
            else:
                verdict, unchanged = "· 没变（本来就达标 / 没被这一单碰到）", unchanged + 1
            print(f"  {str(k):<52}{ra:>6.2f} → {rb:>6.2f}   {verdict}"
                  f"（opacity {oa} → {ob}）")
        print(f"\n  变好 {improved} / 没变 {unchanged} / **变差 {turned_red}**"
              f"（共 {len(a)} 格）")

    print("\n" + "=" * 104)
    print("怎么读：`实测比值` = 截图里**字形核心像素 vs 主色底**的 WCAG 比值（`pixel_lib`）；")
    print("       `预测` = 静态声明 + opacity 合成（差 = 曼哈顿距离，几十以上说明预测的模型不适用，")
    print("       看实测、别看预测）；`底占` 低说明取样盒里颜色不单一，那一格只当参考。")
    print("=" * 104)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
