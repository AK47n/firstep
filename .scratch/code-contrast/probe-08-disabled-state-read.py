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
    python .scratch\\code-contrast\\probe-08-disabled-state-read.py --tag forms --dir .scratch\\disabled-forms

`--tag` 按**前缀**匹配（`--tag forms` 会同时取到 `forms-before` 与 `forms-after` 两张，
正是逐格对照要的那一对）；`--dir` 指到读数所在的目录（默认本目录）。
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
    """两套静态预测（**都报**，工单 `disabled-forms/02` 要求）：

    · **A**（整块连底一起压到祖先底上 = probe-08 的几何）：
      `bg' = op×over(background, behind) + (1-op)×behind`，字同样往 behind 拉；
    · **B**（字往**元素自己声明的底**上拉平、底不动）：`fg' = op×fg + (1-op)×bg_own`，`bg' = bg_own`。

    返回 `(fg_A, bg_A, fg_B, bg_B, op)`。`op = 1` 时两套退化成同一个"字形压在底色上"。
    ⚠ 预测只看**元素自己**的 `opacity`：`opacity` 写在**祖先**上时（`.module-card.off` 那类
    "整块变淡"），子元素的 `getComputedStyle(el).opacity` 是 1 ⇒ 预测按"没变淡"算、
    与实测差出几百——那不是探针坏了，**正是"静态面看不见 opacity 形态"的实证**。
    """
    fg = rgba(shot["color"])
    behind = tuple(shot["behind"])[:3]
    if fg is None:
        return None, None, None, None, 1.0
    own = rgba(shot["background"])
    bg_own = L.over(own, behind) if own is not None else behind
    op = float(shot.get("opacity", 1))
    fg_flat = L.over(fg, bg_own) if fg[3] < 1 else fg[:3]
    if op >= 1:
        return fg_flat, bg_own, fg_flat, bg_own, op
    blend = lambda c: tuple(int(v + 0.5) for v in (op * c[i] + (1 - op) * behind[i] for i in range(3)))
    fg_b = tuple(int(v + 0.5) for v in (op * fg_flat[i] + (1 - op) * bg_own[i] for i in range(3)))
    return blend(fg_flat), blend(bg_own), fg_b, bg_own, op


def main() -> None:
    args = sys.argv[1:]

    def opt(name):
        """取 `--x <值>`；缺值就**大声失败**（别 `index()+1` 抛 IndexError 那种看不懂的错）。"""
        if name not in args:
            return None
        i = args.index(name) + 1
        if i >= len(args) or args[i].startswith("--"):
            raise SystemExit(f"{name} 后面要给一个值")
        return args[i]

    only = opt("--tag")
    where = Path(opt("--dir") or HERE)
    files = sorted(where.glob("probe-08-shots-*.json"))
    if only:
        # **前缀**匹配：`--tag forms` 取到 `forms-before` / `forms-after` 这一对（逐格对照要的）
        files = [f for f in files
                 if (f.stem[len("probe-08-shots-"):] == only
                     or f.stem[len("probe-08-shots-"):].startswith(only + "-"))]
    if not files:
        raise SystemExit(f"一个 probe-08-shots-*.json 都没有（目录 {where}，tag {only}）"
                         "——先跑 probe-08-disabled-state.mjs")

    text = L.read_page()
    tok = L.Tokens(text)
    print("=" * 104)
    print("代码配色族轮 · 禁用态读数（probe-08：真元素截图 + 读像素）")
    print(f"读数目录 = {where}；文件 = {', '.join(f.name for f in files)}")
    print(f"口径单源 = probe_lib / pixel_lib；"
          f"静态参照：`--muted` 压 `--panel-2` = "
          f"浅 {L.contrast(tok.value('--muted', 'light'), tok.value('--panel-2', 'light')):.2f} / "
          f"暗 {L.contrast(tok.value('--muted', 'dark'), tok.value('--panel-2', 'dark')):.2f}"
          f"（族面「--muted × 禁用态底」那两格）")
    print("=" * 104)

    summary = {}      # tag → [(theme, tab, slug, text, key, ratio, opacity)]
    # **认人面三方对账**（评审整改）：JSON 里那份 `forms` 是探针**从守卫正则解析**出来的
    # （第 3 份口径），这里拿 Python 侧的单源 `probe_lib.CONTRAST_DISABLED_FORMS`（`disabled` 档，
    # 由 `tests/test_contrast_mirror.py` 钉住与守卫同源）逐条比——不问的话，守卫那张表改名 /
    # 换行都会让探针静默少认几处。（断言形状与探针的"读不到就大声失败"配套。）
    want_forms = [(s, sel) for s, sel, kind, _why in L.CONTRAST_DISABLED_FORMS if kind == "disabled"]
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        tag = data.get("tag", f.stem)
        got_forms = [(x.get("scope"), x.get("sel")) for x in data.get("forms", [])]
        if got_forms != want_forms:
            print(f"⚠ {f.name} 里的认人面与 probe_lib 的单源不一致："
                  f"JSON {got_forms} / probe_lib {want_forms}——探针那份是正则解析来的，须复核")
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        tag = data.get("tag", f.stem)
        print(f"\n{'#' * 104}\n# tag = {tag}（{f.name}；{len(data['shots'])} 格）\n{'#' * 104}")
        # 这一发是怎么把靶子造出来的 + "没量到"的账（**跟着 JSON 落盘**，不再只活在控制台）
        for p in data.get("prepares", []):
            print(f"  准备[{p['theme']}/{p['tab']}]：{p['note']}")
        for n in data.get("notes", []):
            if n.get("missing"):
                print(f"  没量到[{n['theme']}/{n['tab']}/{n['scope']}]：页签或浮层不存在")
                continue
            sk = " / ".join(f"{k} {v}" for k, v in (n.get("skipped") or {}).items() if v)
            if sk:
                print(f"  没量到[{n['theme']}/{n['tab']}/{n['scope']}]：{sk}")
            for d in n.get("skippedDetail") or []:
                print(f"      · 靶子没量到：{d}")
            for x in n.get("failedShots") or []:
                print(f"      · 截图失败：{x['how']} @ {x['sel']} <{x['tag']}> {x['box']}")
        print(f"{'主题':<7}{'页签':<11}{'形态':<13}{'op':>5}{'实测比值':>9}{'底':<10}{'字形':<10}"
              f"{'预测A':>8}{'差A':>5}{'预测B':>8}{'差B':>5}  文字")
        rows = []
        for s in data["shots"]:
            if not s["text"]:
                # 没有字形像素（空输入框那类）：截图里最"远"的像素会是描边/圆角，
                # 拿它当"字形"算比值是假证据——如实跳过（PNG 仍在盘上可人眼看）。
                print(f"{s['theme']:<7}{s['tab']:<11}{s['how']:<13}{s.get('opacity', 1):>5}"
                      f"{'—':>9}   这一格**没有文字**（无字形像素）——跳过比值，只留截图")
                continue
            cnt = PX.histogram(where / s["file"])
            bg_meas, n_bg = PX.dominant(cnt)
            fg_meas = PX.glyph_core(cnt)
            cover = n_bg / sum(cnt.values())
            r_meas = L.contrast(fg_meas, bg_meas)
            fg_a, bg_a, fg_b, bg_b, op = predicted(s)
            gap_a = PX.dist(fg_meas, fg_a) + PX.dist(bg_meas, bg_a) if fg_a else None
            gap_b = PX.dist(fg_meas, fg_b) + PX.dist(bg_meas, bg_b) if fg_b else None
            mark = "✅" if r_meas >= L.CONTRAST_THRESHOLDS["small"] else "❌"
            rows.append((s["theme"], s["tab"], s["slug"], s["text"], r_meas, op))
            summary.setdefault(tag, []).append(
                (s["theme"], s["tab"], s["slug"], s["text"], s.get("key"),
                 round(r_meas, 2), op))
            print(f"{s['theme']:<7}{s['tab']:<11}{s['how']:<13}{op:>5}"
                  f"{r_meas:>7.2f}{mark}{PX.hx(bg_meas):<10}{PX.hx(fg_meas):<10}"
                  f"{(PX.hx(fg_a) if fg_a else '—'):>8}{(str(gap_a) if gap_a is not None else '—'):>5}"
                  f"{(PX.hx(fg_b) if fg_b else '—'):>8}{(str(gap_b) if gap_b is not None else '—'):>5}"
                  f"  「{s['text']}」"
                  + (f"  底占 {cover:.0%}" if cover < 0.30 else "")
                  + ("  ⚠祖先渐变" if s.get("ancestorGradient") else ""))
        if rows:
            worst = min(rows, key=lambda x: x[4])
            print(f"  —— {tag} 最低：**{worst[4]:.2f}**（{worst[1]} / {worst[3]}）")

    # `before` 永远排在前面（逐格对照的方向 = 改前 → 改后；按字典序排会把方向搞反）。
    # 前缀命名（`forms-before` / `forms-after`）按"以 before 结尾"认——只按字典序会把方向搞反。
    tags = sorted(summary, key=lambda t: (0 if t.endswith("before") else 1, t))
    if len(tags) >= 2:
        print(f"\n{'=' * 104}\n## 逐格对照（{tags[0]} → {tags[1]}）：禁用态改前 / 改后\n")
        # 两张表都按同一把认人键 `(主题, 页签, 元素, 文字, 元素序号)` 索引（**不写两遍查找**）。
        # ⚠ 键里必须带 `key`：同一页签里可以有**两张同路径同文字的卡**（dark generate 的两张 off 卡
        # 都有「详情」「需切换平台」）——不带它就会塌成一格、丢掉一张（评审逮到过）。
        idx = {t: {(th, tab, slug, txt, k): (r, o) for th, tab, slug, txt, k, r, o in summary[t]}
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
        only_b = [k for k in b if k not in a]
        only_a = [k for k in a if k not in b]
        if only_a or only_b:
            print(f"  —— 两边不是一一对应（键 = 主题/页签/元素/文字/序号）："
                  f"只有 {tags[0]} 有 {len(only_a)} 格、只有 {tags[1]} 有 {len(only_b)} 格")
            for k in only_a:
                print(f"       只在 {tags[0]}：{k[2:]} = {a[k][0]:.2f}")
            for k in only_b:
                print(f"       只在 {tags[1]}：{k[2:]} = {b[k][0]:.2f}")

    print("\n" + "=" * 104)
    print("怎么读：`实测比值` = 截图里**字形核心像素 vs 主色底**的 WCAG 比值（`pixel_lib`）；")
    print("       `预测A`（整块连底一起压到祖先底上）/ `预测B`（字往元素自己声明的底上拉平、底不动）")
    print("       = 两套静态模型 + opacity 合成；差 = 曼哈顿距离，**几十以上说明那套模型不适用**，")
    print("       看实测、别看预测（`opacity` 写在祖先上时子元素的 opacity 是 1，两套预测都会偏乐观）。")
    print("       `底占` 低说明取样盒里颜色不单一，那一格只当参考。")
    print("=" * 104)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
