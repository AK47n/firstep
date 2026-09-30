"""浅色调色板轮 · 侦察探针（01）：对比度清单 + 候选值扫描。

**它回答三问，全是数**：
  ① 现在到底有多少处「文字色 × 底色」配对的对比度低于 WCAG AA？（两主题各算一遍）
  ② `--accent` 当**文字色**用在哪几处？（`--accent-text` 要替换的消费方清单）
  ③ `--panel-2` 加深到哪儿才够（浅色 ×1.065 → 目标），以及加深之后压在上面那些文字还过不过 AA
     —— **两个决定互相咬**：底越深，深字越难过线（§10 的格网就是为此画的）。

口径**不再自己抄一份**：颜色数学、令牌解析、规则切分、取色对全部走 `probe_lib`
（与守卫腿⑧ 同源，`tests/test_contrast_mirror.py` 钉住两侧一致）。

跑法（仓库根）：
    python .scratch/light-contrast/probe-01-inventory.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

AA = L.CONTRAST_THRESHOLDS["small"]


def main() -> None:
    text = L.read_page()
    tok = L.Tokens(text)
    print("=" * 78)
    print("浅色调色板轮 · 侦察读数（probe-01：对比度清单 + 候选值扫描）")
    print(f"页面：{L.PAGE.relative_to(L.ROOT)}")
    print(f"口径（单源 = probe_lib）：小字 ≥ {AA}:1；大字（≥{L.LARGE_TEXT['px']}px 或 "
          f"≥{L.LARGE_TEXT['bold_px']}px 加粗）≥ {L.CONTRAST_THRESHOLDS['large']}:1；"
          f"底 = 元素自己那层背景合成到 {L.CONTRAST_BASE_TOKEN} 上")
    print("=" * 78)

    # --- 1. 取色相关令牌现值 -------------------------------------------------
    print("\n## 1. 令牌现值（只列取色相关的；`—` = 该主题未覆盖、沿用 :root）\n")
    names = [n for n in tok.names()
             if not n.startswith(("--fs-", "--space-", "--radius-", "--dur-", "--ease-", "--shadow"))]
    print(f"{'令牌':<22}{'暗色':<34}{'亮色':<34}")
    for n in names:
        print(f"{n:<22}{(tok.raw['dark'].get(n, '')):<34}{tok.raw['light'].get(n, '—'):<34}")

    # --- 2. 机械配对清单 -----------------------------------------------------
    pairs = L.contrast_pairs(text, tok)
    print("\n## 2. 机械配对清单（同一条规则里既有 `color:` 又有 `background:`）\n")
    print(f"总配对数：{len(pairs)}（两主题各算一遍）")
    for theme in ("dark", "light"):
        sub = [p for p in pairs if p.theme == theme]
        bad = [p for p in sub if p.ratio < p.need - 1e-9]
        near = [p for p in sub if p.need - 1e-9 <= p.ratio < p.need + 0.6]
        print(f"\n### {theme}：{len(sub)} 对，不达标 **{len(bad)}**，贴线（+0.6 内）{len(near)}\n")
        if bad:
            print(f"{'比值':>6}  {'需':>4}  选择器 / 色对")
            for p in sorted(bad, key=lambda x: x.ratio):
                print(f"{p.ratio:>6.2f}  {p.need:>4.1f}  {p.selector[:62]}  [{p.fg_hex} on {p.bg_hex}]")
        if near:
            print("  —— 贴线：")
            for p in sorted(near, key=lambda x: x.ratio):
                print(f"  {p.ratio:>6.2f}  {p.need:>4.1f}  {p.selector[:62]}  [{p.fg_hex} on {p.bg_hex}]")

    # --- 3. accent 当文字色 -------------------------------------------------
    sites = [p for p in pairs if p.fg_raw == "var(--accent)"]
    print("\n## 3. `--accent` 当**文字色**用的地方（同规则里带 own 底的配对）\n")
    print(f"共 **{len(sites)}** 处带自己那层底；另有 `color: var(--accent)` 但底在祖先的规则"
          f"（要迁移时要逐条看）——总数见守卫那条腿的读数。\n")
    for p in sites:
        print(f"  {p.theme:<6}{p.ratio:>6.2f}  {p.selector[:60]:<60} {p.fg_hex} on {p.bg_hex}")

    # --- 4. --panel-2 当底 --------------------------------------------------
    p2 = [p for p in pairs if "--panel-2" in (p.bg_raw or "")]
    print("\n## 4. `--panel-2` 当底的地方\n")
    print(f"共 **{len(p2)}** 条（两主题各算一遍；亮色那半边有 {len([p for p in p2 if p.theme == 'light'])} 条）")

    # --- 5/6/7. 候选值 ------------------------------------------------------
    bg_light = tok.value("--bg", "light")[:3]
    panel_light = tok.value("--panel", "light")[:3]
    accent_light = tok.value("--accent", "light")
    dim_light = tok.value("--accent-dim", "light")
    text_light = tok.value("--text", "light")[:3]
    muted_light = tok.value("--muted", "light")[:3]

    print("\n## 5. 候选：`--accent-text`（浅色压暗一档；暗色 = 与 `--accent` 同值）\n")
    at_cands = ["#0096c7", "#0089b6", "#007ea8", "#00759c", "#006d92", "#00668a",
                "#005f80", "#005877", "#00526e", "#004c66", "#00465e", "#004056"]
    p2_grid = ["#eef1f4", "#e7ebef", "#e4e9ee", "#e1e6ec", "#dee4ea", "#dbe1e8"]
    print(f"现值 `--accent` = {L.hexs(accent_light)}（暗色 = {L.hexs(tok.value('--accent', 'dark'))}）\n")
    print(f"{'候选':<12}{'页面底':>9}{'卡片':>9}{'淡底':>9}{'dim@卡片':>11}{'dim@淡底':>11}")
    for c in at_cands:
        rgb = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        dim_card = L.over((accent_light[0], accent_light[1], accent_light[2], dim_light[3]), panel_light)
        dim_p2 = L.over((accent_light[0], accent_light[1], accent_light[2], dim_light[3]),
                        tok.value("--panel-2", "light")[:3])
        cells = [L.contrast(rgb, x) for x in (bg_light, panel_light, tok.value("--panel-2", "light")[:3],
                                              dim_card, dim_p2)]
        mark = " ✅" if min(cells) >= AA else ""
        print(f"{c:<12}" + "".join(f"{v:>9.2f}" for v in cells[:3])
              + "".join(f"{v:>11.2f}" for v in cells[3:]) + mark)

    print("\n## 6. 候选：`--panel-2`（浅色加深；目标 = 与页面底分得开）\n")
    print(f"现值 `--panel-2` = {L.hexs(tok.value('--panel-2', 'light'))}，"
          f"与页面底 {L.hexs(bg_light)} 比值 ×{L.contrast(tok.value('--panel-2', 'light')[:3], bg_light):.3f}\n")
    print(f"{'候选':<12}{'vs 页面底':>10}{'vs 卡片':>9}{'--text':>9}{'--muted':>9}")
    for c in p2_grid:
        rgb = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        print(f"{c:<12}{L.contrast(rgb, bg_light):>10.3f}{L.contrast(rgb, panel_light):>9.3f}"
              f"{L.contrast(text_light, rgb):>9.2f}{L.contrast(muted_light, rgb):>9.2f}")

    # --- 8. 代码配色族（只量不修） -------------------------------------------
    print("\n## 8. 代码配色族 `--tok-*` × 代码底（本轮**只量不修**，数字进登记表）\n")
    matrix = L.tok_family_matrix(tok)
    for theme in ("dark", "light"):
        print(f"\n### {theme}\n")
        layers = [n for n, _ in L.CODE_LAYERS]
        print(f"{'令牌':<14}" + "".join(f"{n:>20}" for n in layers))
        for tname in [n for n in tok.names() if n.startswith("--tok-")]:
            cells = [matrix.get((theme, ly, tname)) for ly in layers]
            if any(c is None for c in cells):
                continue
            worst = min(cells)
            print(f"{tname:<14}" + "".join(f"{c:>20.2f}" for c in cells)
                  + ("  ❌" if worst < AA else "  ✅"))

    # --- 10. 选型格网 -------------------------------------------------------
    print("\n## 10. 选型格网：`--accent-text` × `--panel-2`"
          "（单元格 = 最坏比值：accent-text 压在 dim 合成底上）\n")
    print(f"{'accent-text':<14}" + "".join(f"{c:>12}" for c in p2_grid))
    print(f"{'':<14}" + "".join(f"{'×' + format(L.contrast((int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)), bg_light), '.3f'):>12}"
                                for c in p2_grid))
    for at_c in at_cands:
        at = (int(at_c[1:3], 16), int(at_c[3:5], 16), int(at_c[5:7], 16))
        cells = ""
        for c in p2_grid:
            p2 = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
            dim_p2 = L.over((accent_light[0], accent_light[1], accent_light[2], dim_light[3]), p2)
            worst = min(L.contrast(at, p2), L.contrast(at, dim_p2),
                        L.contrast(at, bg_light), L.contrast(at, panel_light))
            mark = "✅" if worst >= AA + 0.15 else ("⚠" if worst >= AA else "❌")
            cells += f"{worst:>10.2f}{mark}"
        print(f"{at_c:<14}" + cells)
    print("\n（✅ = 最坏格 ≥ 4.65（留 0.15 余量）；⚠ = 过线但余量 < 0.15；❌ = 掉线。"
          "\n  四类底都算进去了：页面底 / 卡片 / 加深后的淡底 / dim 合成底——"
          "**最后一格最咬人**，它决定 `--panel-2` 能深到哪。）")


if __name__ == "__main__":
    main()
