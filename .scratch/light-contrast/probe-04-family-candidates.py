"""浅色调色板轮 · 选值探针（04）：六族各自的"改哪一侧、改成多少"。

**为什么需要它**：02 单要把它读成"每族最坏格 ≥ 4.5 且留 ≥ 0.15 余量"，而每族有两条路——
① 压暗**文字令牌**；② 调**淡底 alpha**。两条路对观感的影响不同（① 动语义色本身、
② 动"淡底有多淡"），所以得先把两条路的数都算出来再挑，**不许凭手感调**。

判据（与守卫腿⑧ 同一套口径，走 `probe_lib`）：
  每族的「文字色 × 自己的淡底」在**四种底**上（页面底 / 卡片 / 加深后的淡底 / dim 合成底）
  全部 ≥ 4.5；暗色侧同样算一遍（**不许退化**）。
跑法（仓库根）：
    python .scratch/light-contrast/probe-04-family-candidates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

AA = L.CONTRAST_THRESHOLDS["small"]
#: 选值时的**余量口径**（不是判据）：过线还不够，要留出 0.30 的余地，
#: 免得后续任何一点微调（比如 03 单加深淡底）立刻把它推回线下。
#: ⚠ **口径要与落盘值一致**（02 单双轴评审点名：曾出现"脚本按 0.15 算、值按 0.30 落"，
#: 于是树里没有任何读数能复现那六个值）——改这里就要重跑并核对落盘值。
HEADROOM = 0.30
PANEL2_TARGET = "#e1e6ec"          # 03 单要落的值（spec 拍的）

#: 六族：`(族名, 浅色文字令牌, 浅色淡底令牌, 暗色文字令牌, 暗色淡底令牌)`
FAMILIES = [
    ("ok", "--ok-bright", "--ok-dim", "--ok-bright", "--ok-dim"),
    ("ok(深)", "--ok", "--ok-dim", "--ok", "--ok-dim"),
    ("warn", "--warn", "--warn-dim", "--warn", "--warn-dim"),
    ("danger", "--danger", "--danger-dim", "--danger", "--danger-dim"),
    ("info", "--info", "--info-dim", "--info", "--info-dim"),
    ("purple", "--purple-grad", "--purple-dim", "--purple-grad", "--purple-dim"),
    ("accent", "--accent", "--accent-dim", "--accent", "--accent-dim"),
]


def worst_ratio(fg, dim, theme, tok, p2_override=None):
    """把 dim 叠到三类底上，返回与 fg 的最小比值（底 = 页面底 / 卡片 / 淡底）。"""
    bgs = []
    for name in ("--bg", "--panel"):
        v = tok.value(name, theme)
        bgs.append(v[:3])
    if p2_override is not None and theme == "light":
        bgs.append(p2_override)
    else:
        bgs.append(tok.value("--panel-2", theme)[:3])
    dim_rgba = (fg[0], fg[1], fg[2], dim[3])
    ratios = []
    for base in bgs:
        eff = L.over(dim_rgba, base)          # dim 的色相就取自该族文字色（实际令牌是独立 rgba）
        ratios.append(L.contrast(fg, eff))
        ratios.append(L.contrast(fg, base))
    return min(ratios)


def worst_with_real_dim(fg, dim_token, theme, tok, p2_override=None):
    """**严格口径**：dim 用**真实令牌值**（不是拿 fg 的色相当 dim），三类底各算一遍。

    落定 `-text` 令牌的值要用这个——`worst_ratio` 是侦察期的近似（把 dim 当同色相），
    它会把"别的色相的淡底"漏掉（例如 `--purple-dim` 是紫底、`--warn-dim` 是琥珀底）。
    """
    dim = tok.value(dim_token, theme)
    if dim is None:
        return None
    bases = [tok.value("--bg", theme)[:3], tok.value("--panel", theme)[:3],
             (p2_override if (p2_override is not None and theme == "light")
              else tok.value("--panel-2", theme)[:3])]
    vals = []
    for base in bases:
        vals.append(L.contrast(fg, L.over(dim, base)))   # 压在淡底上
        vals.append(L.contrast(fg, base))                # 压在纯底上
    return min(vals)


#: 六族：`(族名, 浅色文字令牌, 淡底令牌, 暗色文字令牌, 暗色淡底令牌, 目标 -text 令牌名)`
FAMILIES = [
    ("accent", "--accent", "--accent-dim", "--accent", "--accent-dim", "--accent-text"),
    ("ok", "--ok", "--ok-dim", "--ok", "--ok-dim", "--ok-text"),
    ("ok-bright", "--ok-bright", "--ok-dim", "--ok-bright", "--ok-dim", "--ok-text"),
    ("warn", "--warn", "--warn-dim", "--warn", "--warn-dim", "--warn-text"),
    ("danger", "--danger", "--danger-dim", "--danger", "--danger-dim", "--danger-text"),
    ("info", "--info", "--info-dim", "--info", "--info-dim", "--info-text"),
    ("purple", "--purple-grad", "--purple-dim", "--purple-grad", "--purple-dim", "--purple-text"),
]


def main() -> None:
    text = L.read_page()
    tok = L.Tokens(text)
    p2_target = (int(PANEL2_TARGET[1:3], 16), int(PANEL2_TARGET[3:5], 16), int(PANEL2_TARGET[5:7], 16))
    print("=" * 78)
    print("浅色调色板轮 · 选值读数（probe-04：六族改哪一侧）")
    print(f"判据：四种底上 ≥ {AA} 且余量 ≥ {HEADROOM}（= ≥ {AA + HEADROOM:.2f}）；淡底目标 {PANEL2_TARGET}")
    print("=" * 78)

    print("\n## 落定候选：每族解一个 `-text` 令牌值（严格口径：真实 dim × 三类底）\n")
    print("做法：沿「把文字色按比例压暗/提亮」这条线扫，取**第一个**满足最坏格 ≥ "
          f"{AA + HEADROOM:.2f} 的值；暗色侧若现值已达标，`-text` 就取**现值**（暗色零变化）。\n")
    print(f"{'族':<11}{'主题':<7}{'现值':<10}{'现值最坏':>9}{'-text 候选':<12}{'候选最坏':>9}  说明")
    solved: dict[tuple[str, str], tuple] = {}
    for label, fg_name, dim_name, dfg_name, ddim_name, text_name in FAMILIES:
        for theme, fgn, dmn in (("light", fg_name, dim_name), ("dark", dfg_name, ddim_name)):
            fg = tok.value(fgn, theme)
            if fg is None:
                continue
            p2 = p2_target if theme == "light" else None
            cur = worst_with_real_dim(fg, dmn, theme, tok, p2)
            best, best_r = None, cur
            if cur < AA + HEADROOM - 1e-9:
                step = 0.01
                k = 1.0
                while k > 0.25:
                    k -= step
                    cand = tuple(max(0, min(255, round(c * k))) for c in fg[:3]) + (1.0,)
                    r = worst_with_real_dim(cand, dmn, theme, tok, p2)
                    if r is not None and r >= AA + HEADROOM:
                        best, best_r = cand, r
                        break
                if best is None:   # 压暗不够 → 试**提亮**（暗色主题的路子）
                    k = 1.0
                    while k < 1.9:
                        k += step
                        cand = tuple(max(0, min(255, round(c * k))) for c in fg[:3]) + (1.0,)
                        r = worst_with_real_dim(cand, dmn, theme, tok, p2)
                        if r is not None and r >= AA + HEADROOM:
                            best, best_r = cand, r
                            break
            else:
                best, best_r = fg, cur
            note = "现值已达标 → -text 取现值" if best is fg else (
                "压暗" if (best and best[0] <= fg[0]) else "提亮")
            print(f"{label:<11}{theme:<7}{L.hexs(fg):<10}{cur:>9.2f}  "
                  f"{(L.hexs(best) if best else '（扫不出来）'):<12}{best_r:>9.2f}  {note}")
            if best is not None:
                solved[(label, theme)] = (text_name, best, best_r)

    print("\n## 落定值（可以直接抄进 :root / light 两块）\n")
    print("⚠ 同一个 `-text` 可能被**多族共用**（`--ok-text` 同时服务 `--ok` 与 `--ok-bright`）——"
          "落定取**最保守**的那一档（两主题都取**更暗**的那个：在浅底上更暗 = 更保守，"
          "在深底上更暗 = 对比更低 = 也更保守），否则严的那一族仍会掉线。\n")
    for text_name in sorted({v[0] for v in solved.values()}):
        rows = [(k[1], v[1], v[2]) for k, v in solved.items() if v[0] == text_name]
        light_rows = [r for r in rows if r[0] == "light"]
        dark_rows = [r for r in rows if r[0] == "dark"]
        light = min(light_rows, key=lambda r: sum(r[1][:3])) if light_rows else None
        dark = min(dark_rows, key=lambda r: sum(r[1][:3])) if dark_rows else None
        shared = "（多族共用，取最保守）" if len(rows) > 2 else ""
        print(f"  {text_name:<16} 暗色 = {L.hexs(dark[1]) if dark else '—':<10}"
              f"亮色 = {L.hexs(light[1]) if light else '—':<10}"
              f"（最坏 {light[2]:.2f} / {dark[2]:.2f}）{shared}")

    print("\n## 近似口径的老表（侦察期用；落定值以上面的严格口径为准）\n")
    for label, fg_name, dim_name, dfg_name, ddim_name, _text_name in FAMILIES:
        print(f"\n## 族「{label}」：文字 {fg_name} × 淡底 {dim_name}\n")
        for theme, fgn, dmn in (("light", fg_name, dim_name), ("dark", dfg_name, ddim_name)):
            fg = tok.value(fgn, theme)
            dim = tok.value(dmn, theme)
            if fg is None or dim is None:
                print(f"  {theme}: 令牌解不出（{fgn} / {dmn}）——跳过")
                continue
            p2 = p2_target if theme == "light" else None
            cur = worst_ratio(fg, dim, theme, tok, p2)
            print(f"  {theme:<6} 现值：{L.hexs(fg)} × dim α={dim[3]:.2f}"
                  f"（dim={L.hexs(L.over((fg[0], fg[1], fg[2], dim[3]), tok.value('--panel', theme)[:3]))}）"
                  f"→ 最坏 **{cur:.2f}** {'✅' if cur >= AA else '❌'}")
            # 路①：压暗文字令牌（按 2% 步长找第一个达标的）
            k = 1.0
            while k > 0.25:
                cand = tuple(max(0, round(c * k)) for c in fg[:3]) + (1.0,)
                r = worst_ratio(cand, dim, theme, tok, p2)
                if r >= AA + HEADROOM:
                    print(f"        路① 文字压暗 ×{k:.2f} → {L.hexs(cand)}：最坏 {r:.2f} ✅")
                    break
                k -= 0.02
            else:
                print("        路① 压暗到 ×0.30 仍不达标——该族只能走淡底/换色")
            # 路②：调淡底 alpha（往小调，10% 相对步长）
            a = dim[3]
            while a > 0.02:
                cand_dim = (dim[0], dim[1], dim[2], a)
                r = worst_ratio(fg, cand_dim, theme, tok, p2)
                if r >= AA + HEADROOM:
                    print(f"        路② 淡底 α {dim[3]:.2f} → {a:.2f}：最坏 {r:.2f} ✅")
                    break
                a = round(a - 0.01, 3)
            else:
                print("        路② 淡底降到 α0.02 仍不达标——该族得换文字色")

    print("\n" + "=" * 78)
    print("怎么读：两条路都列出来，**选改动小的那一侧**（票尾要写清每族选了哪条、为什么）。")
    print("⚠ 淡底 alpha 调小会让「淡底」更淡——与 03 单「去框留淡底要分得开」的方向相反，")
    print("   所以对那几处**纯淡底**的块要留神：它们靠的是 `--panel-2`，不是语义 dim。")
    print("=" * 78)


if __name__ == "__main__":
    main()
