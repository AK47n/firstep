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
#: 选值时的**余量口径**（不是判据）：过线还不够，要留出 0.15 的余地，
#: 免得后续任何一点微调（比如 03 单加深淡底）立刻把它推回线下。
HEADROOM = 0.15
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


def darken(rgb, k):
    return tuple(max(0, round(c * k)) for c in rgb[:3]) + (1.0,)


def main() -> None:
    text = L.read_page()
    tok = L.Tokens(text)
    p2_target = (int(PANEL2_TARGET[1:3], 16), int(PANEL2_TARGET[3:5], 16), int(PANEL2_TARGET[5:7], 16))
    print("=" * 78)
    print("浅色调色板轮 · 选值读数（probe-04：六族改哪一侧）")
    print(f"判据：四种底上 ≥ {AA} 且余量 ≥ {HEADROOM}（= ≥ {AA + HEADROOM:.2f}）；淡底目标 {PANEL2_TARGET}")
    print("=" * 78)

    for label, fg_name, dim_name, dfg_name, ddim_name in FAMILIES:
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
            # 路①：压暗文字令牌（按 5% 步长找第一个达标的）
            k = 1.0
            while k > 0.3:
                cand = darken(fg, k)
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
