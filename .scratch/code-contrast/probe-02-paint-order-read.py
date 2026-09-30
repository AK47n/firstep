"""代码配色族轮 · 像素读数（probe-02 的第二半）：把截图里的颜色分布读出来，
与「高亮层压在字上（over）」/「垫在字下（behind）」两个模型的预测逐条对比；
多个 `--tag` 的读数还会**逐格对照**（工单 01 的"观感零变化"取证）。

**口径不另起一套**：颜色数学 / 令牌 / 层配方 / alpha 全部走 `probe_lib`
（与守卫腿⑧ 同源）——本文件只做"读 PNG + 拼预测 + 对差"。

跑法（仓库根；先跑 probe-02-paint-order.mjs --tag before / --tag after）：
    python .scratch\\code-contrast\\probe-02-paint-order-read.py            # 读全部 tag
    python .scratch\\code-contrast\\probe-02-paint-order-read.py --tag after
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                        # 读像素的公共半（pixel_lib）与本文件同级
sys.path.insert(0, str(HERE.parent / "light-contrast"))

import pixel_lib as PX  # noqa: E402  （读像素的口径：直方图 / 主色 / 字形核心）
import probe_lib as L  # noqa: E402  （颜色数学与令牌的口径单源）

WORD_LAYER = "--code-bg+hl.词命中"
SEL_LAYER = "--code-bg+hl.选区"

hx, dist, histogram, dominant, glyph_core = (
    PX.hx, PX.dist, PX.histogram, PX.dominant, PX.glyph_core)


def predictions(tok, theme, shot, base):
    """两个模型的预测（**走 probe_lib 的层配方与 alpha**，不在这里另抄一份数字）。"""
    if shot["name"] == "brace":
        layer = "--code-bg+--bracket-rainbow-0"
        fg = tok.value("--code-text", theme)
    else:
        layer = SEL_LAYER
        fg = base
    _b, bg, tint, geom = L.layer_colors(layer, theme, tok)
    if geom == "behind":
        over_pred = tuple(fg[:3])                      # 垫在字下：字形不变
    else:
        over_pred = L.over(tint, fg)                   # 压在字上：字形被染一遍
    return {
        "over（压在字上）": over_pred,
        "behind（垫在字下）": tuple(fg[:3]),
        "两层都压（词命中 + 选区）": L.over(L.layer_tint(SEL_LAYER, theme, tok),
                                       L.over(L.layer_tint(WORD_LAYER, theme, tok), fg)),
    }


def main() -> None:
    args = sys.argv[1:]
    only = args[args.index("--tag") + 1] if "--tag" in args else None
    files = sorted(HERE.glob("probe-02-shots-*.json"))
    if only:
        files = [f for f in files if f.name.endswith(f"-{only}.json")]
    if not files:
        raise SystemExit("一个 probe-02-shots-*.json 都没有——先跑 probe-02-paint-order.mjs")

    text = L.read_page()
    tok = L.Tokens(text)
    print("=" * 100)
    print("代码配色族轮 · 像素读数（probe-02：高亮层压在字上还是垫在字下）")
    print(f"口径单源 = probe_lib；页面上 --code-hl-rgb = "
          f"{L.hexs(tok.value(L.CONTRAST_CODE_HL_TOKEN, 'dark'))}（暗）/ "
          f"{L.hexs(tok.value(L.CONTRAST_CODE_HL_TOKEN, 'light'))}（浅）")
    print("=" * 100)

    summary = {}      # tag → {(theme, name, state): glyph 色}
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        tag = data.get("tag", f.stem)
        print(f"\n{'#' * 100}\n# tag = {tag}（{f.name}）\n{'#' * 100}")
        for s in data["shots"]:
            theme = s["theme"]
            print(f"\n### [{tag}] {theme} / {s['name']}（{s['info'].get('text', '')}）\n")
            cols, cnts, tops = {}, {}, {}
            for key, fn in s["files"].items():
                cnt = histogram(HERE / fn)
                cnts[key] = cnt
                tops[key] = cnt.most_common(4)
                cols[key] = glyph_core(cnt)
                summary[(tag, theme, s["name"], key)] = cols[key]
                total = sum(cnt.values())
                print(f"  {key:<9}{total:>6} px  主色 {hx(cnt.most_common(1)[0][0])}  字形 {hx(cols[key])}"
                      f"  （前 4 高频：" + " ".join(hx(c) for c, _n in tops[key]) + "）")
            base = cols["before"]
            preds = predictions(tok, theme, s, base)
            # **单层底预测**（这一发本该只有它）：选区态 = `over(选区 tint, 代码底)`；
            # 括号那一发 = `over(彩虹, 代码底)`。实测主色与它不符 ⇒ 掺了别的层/混色，不当证据。
            want_layer = ("--code-bg+--bracket-rainbow-0" if s["name"] == "brace" else SEL_LAYER)
            _b, want_bg, _t, _g = L.layer_colors(want_layer, theme, tok)
            for label, p in preds.items():
                print(f"    预测 {label:<26}{hx(p)}")
            for key in s["files"]:
                if key == "before":
                    continue
                obs = cols[key]
                gap = {label: dist(obs, p) for label, p in preds.items()}
                best = min(gap, key=gap.get)
                print(f"    实测 {key:<9}= {hx(obs)} → 最贴近：**{best}**（曼哈顿距离 {gap[best]}）")
            # **屏幕上量出来的比值**（02 单的验收：过线要有真像素那一份）。
            # 只有当取样盒里**主色占绝对多数**（单一底）时才算——掺了别的层（相邻行 / 叠加态）
            # 就不当"过线证据"，如实标出来（评审点名：底不单一时的数不能混着读）。
            print("    实测比值（字形 vs 该画面的主色底）：")
            for key in s["files"]:
                cnt = cnts[key]
                bg, n_bg = dominant(cnt)
                cover = n_bg / sum(cnt.values())
                r = L.contrast(cols[key], bg)
                tier = "（**叠加态 = 口径边界**）" if key == "dblclick" else ""
                if key != "before" and s.get("info", {}).get("lineActive"):
                    print(f"      {key:<9}该行同时是当前行（掺了 `.07`）——**跳过比值**{tier}")
                    continue
                if key != "before" and dist(bg, want_bg) > 12:
                    print(f"      {key:<9}底与单层预测不符（实测 {hx(bg)} / 预测 {hx(want_bg)}）"
                          f"——**掺层或混色，跳过比值**"
                          + "（⚠ 若这一发来自**旧 tag**，对不上是**预期**的：像素是当时的强度拍的、"
                            "预测按现行口径算）" + f"{tier}")
                    continue
                if cover < 0.30:
                    print(f"      {key:<9}底不单一（主色只占 {cover:.0%}）——**跳过比值**，只留像素{tier}")
                    continue
                mark = "✅" if r >= L.CONTRAST_THRESHOLDS["small"] else (
                    "·边界" if key == "dblclick" else "❌")
                print(f"      {key:<9}{hx(cols[key])} on {hx(bg)}  **{r:.2f}**  "
                      f"（底占 {cover:.0%}）  {mark}{tier}")

    # --- 多 tag 逐格对照（观感零变化取证） ----------------------------------
    tags = sorted({k[0] for k in summary})
    if len(tags) >= 2:
        print(f"\n{'=' * 100}\n## 逐格对照（{tags[0]} vs {tags[1]}）——工单 01 的「观感零变化」取证\n")
        keys = sorted({k[1:] for k in summary if k[0] == tags[0]})
        bad = 0
        for k in keys:
            a = summary.get((tags[0],) + k)
            b = summary.get((tags[1],) + k)
            if a is None or b is None:
                print(f"  {k}  只在一侧有（跳过）")
                continue
            same = a == b
            bad += 0 if same else 1
            print(f"  {str(k):<44}{hx(a):<10}{hx(b):<10}{'✅ 相同' if same else '❌ 有差异'}")
        print(f"\n  合计 **{len(keys) - bad}/{len(keys)}** 格逐字节相同"
              + ("——**观感零变化成立**" if bad == 0 else "——**有差异，别当零变化**"))

    print("\n" + "=" * 100)
    print("怎么读：实测字形像素贴近哪条预测，就是哪种叠法；多 tag 那一节是「改前/改后」的真像素对照。")
    print("=" * 100)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
