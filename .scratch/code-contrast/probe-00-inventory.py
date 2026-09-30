"""代码配色族轮 · 侦察探针（00）：代码页上的层清单 + **叠放几何** + 选值预算。

## 这个文件与口径的关系（工单 code-contrast/01 起）

**颜色数学、令牌解析、层配方、几何一律走 `.scratch/light-contrast/probe_lib.py`**（口径单源，
与守卫腿⑧ 同源、镜像守卫钉住）。本文件只做三件 probe_lib 不做的事：

1. **层表 vs 盘上**：每层给出处（选择器 + 那一句原文），并**从盘上把 alpha 抠出来与表对账**
   ——层表不再只是"我们以为的"，它是被盘上验过的；
2. **矩阵与决策网格**：把比值排成表，回答"改哪一边、改到多少"；
3. **叠加态**：真实使用里高亮会互叠（同一 tint 的多个 over 层按 `1-∏(1-α)` 合成），
   这是**已知边界**，量出来记账用。

## 几何（本轮更正的口径，实测见 probe-02）

`.code-ta::selection`（z-index 1）与 `.code-marks`（z-index 0）都画在 `.code-hl` 文字**之上**，
半透明色把**字形本身**也染了 ⇒ `over` 层的判据是 `contrast(over(tint,fg), over(tint,base))`；
只有行元素自己那两层（`.active` / `.flash`）垫在字下。

跑法（仓库根）：
    python .scratch\\code-contrast\\probe-00-inventory.py
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "light-contrast"))

import probe_lib as L  # noqa: E402

AA = L.CONTRAST_THRESHOLDS["small"]
HEADROOM = 0.15
NEED = AA + HEADROOM

TOKENS = ["--tok-com", "--tok-str", "--tok-pre", "--tok-kw", "--tok-num",
          "--tok-tag", "--tok-attr", "--tok-val", "--tok-fn", "--tok-const"]

#: 每层的**出处**：`选择器 + 那一句` 的正则（能从盘上把 alpha 抠出来的就抠出来）。
#: 正则**不含 alpha 的字面值**：alpha 由括号捕获，再与 `probe_lib.CODE_LAYERS` 对账——
#: 这样"表里写 .20、盘上还是 .32"这类漂移当场现形。
LAYER_SRC = {
    "--code-bg": (r"background: var\(--code-bg\); position: relative;", "底本身"),
    "--code-bg+hl.当前行": (r"\.code-pre-line\.active \{ background: rgba\(var\(--code-hl-rgb\), \.(\d+)\); \}",
                        "当前行（垫在字下）"),
    "--code-bg+hl.词命中": (r"\.code-mark-word \{ background: rgba\(var\(--code-hl-rgb\), \.(\d+)\); \}",
                        "词命中（压在字上）"),
    "--code-bg+hl.搜索命中": (r"\.code-mark-hit \{ background: rgba\(var\(--code-hl-rgb\), \.(\d+)\); \}",
                         "搜索命中（压在字上）"),
    "--code-bg+hl.选区": (r"\.code-ta::selection \{ background: rgba\(var\(--code-hl-rgb\), \.(\d+)\);",
                       "选区（压在字上；textarea 的 ::selection）"),
    "--code-bg+hl.当前命中": (r"\.code-mark-current \{ background: rgba\(var\(--code-hl-rgb\), \.(\d+)\);",
                         "当前搜索命中（压在字上）"),
    "--code-bg+--danger-dim": (r"\.code-mark-error \{ background: var\(--danger-dim\);",
                               "编译错误行（压在字上）"),
}


def layers_with(overrides=None):
    """层表（可覆盖 alpha）——**表本体是 `probe_lib.CODE_LAYERS`**，这里只是换个档位来算账。"""
    ov = overrides or {}
    return [(n, ov.get(n, a), g) for n, a, g in L.CODE_LAYERS]


def tok_with_hl(tok, theme, spec):
    """换一支青：把 `--code-hl-rgb` 在某一主题下替换成候选值（其余令牌不动）。"""
    t = copy.deepcopy(tok)
    t.raw[theme][L.CONTRAST_CODE_HL_TOKEN] = spec
    return t


def scaled(fg, k):
    return tuple(max(0, min(255, int(c * k + 0.5))) for c in fg[:3]) + (1.0,)


def worst(fg, names, theme, tok, layers=None):
    return min(L.contrast_on_layer(fg, n, theme, tok, layers) for n in names)


def ratio_of(fg, layer, theme, tok, layers=None):
    return L.contrast_on_layer(fg, layer, theme, tok, layers)


def ratio_old_model(fg, layer, theme, tok):
    """**上一轮（00 轮之前）的算法**：把高亮当"垫在字下"，`ratio = contrast(fg, bg)`。

    留着它是为了"旧算 3.10 / 真渲染 2.69"这类对照能一条命令复算（两轴评审点名：
    口径更正的那句话不能只活在散文里）。
    """
    base, bg, tint, _geom = L.layer_colors(layer, theme, tok)
    if bg is None or fg is None:
        return None
    return L.contrast(L.over(fg, base[:3]) if base is not None else tuple(fg[:3]), bg)


def stack_ratio(fg, alphas, theme, tok, layers=None):
    """叠加态：多个 over 层合成一层（同 tint 时 `α = 1-∏(1-α_i)`），底由 behind 层垫。"""
    e = 1.0
    for a in alphas:
        e *= (1 - a)
    e = 1 - e
    base, _bg, _t, _g = L.layer_colors("--code-bg", theme, tok, layers)
    hl = tok.value(L.CONTRAST_CODE_HL_TOKEN, theme)
    bg = L.over((hl[0], hl[1], hl[2], e), base[:3])
    return L.contrast(L.over((hl[0], hl[1], hl[2], e), fg), bg)


def solve(fg, names, theme, tok, layers=None, need=NEED):
    """最小改动解：浅色找**最浅**、暗色找**最暗**的达标值（扫"按比例压暗/提亮"这条线）。"""
    cur = worst(fg, names, theme, tok, layers)
    if cur >= need - 1e-9:
        return 1.0, fg, cur
    lo, hi = (0.02, 1.0) if theme == "light" else (1.0, 3.2)
    k0 = None
    for i in range(int(round((hi - lo) / 0.005)) + 1):
        k = (hi - i * 0.005) if theme == "light" else (lo + i * 0.005)
        if worst(scaled(fg, k), names, theme, tok, layers) >= need:
            k0 = k
            break
    if k0 is None:
        return None, None, None
    best = (k0, scaled(fg, k0), worst(scaled(fg, k0), names, theme, tok, layers))
    for j in range(-5, 6):
        k = k0 + j / 1000
        if k <= 0:
            continue
        c = scaled(fg, k)
        r = worst(c, names, theme, tok, layers)
        if r >= need and (k > best[0] if theme == "light" else k < best[0]):
            best = (k, c, r)
    return best


def main() -> None:
    text = L.read_page()
    tok = L.Tokens(text)
    names = [n for n, _a, _g in L.CODE_LAYERS]
    print("=" * 108)
    print("代码配色族轮 · 侦察读数（probe-00：层清单 + 叠放几何 + 选值预算）")
    print(f"页面：{L.PAGE.relative_to(L.ROOT)}；口径单源 = .scratch/light-contrast/probe_lib.py")
    print(f"小字 ≥ {AA}:1（选值留余量 {HEADROOM} → ≥ {NEED:.2f}）；"
          f"**压在字上的层**：字形 = over(tint, fg)、底 = over(tint, base)")
    print("=" * 108)

    # --- 1. 层表 ↔ 盘上（含 alpha 对账） ------------------------------------
    print("\n## 1. 层表 ↔ 盘上：出处认得到吗？alpha 与表一致吗？\n")
    print(f"{'层':<24}{'几何':<8}{'出处':<34}{'表 α':>7}{'盘上 α':>8}  说明")
    bad = 0
    for name, alpha, geom in L.CODE_LAYERS:
        pat, why = LAYER_SRC[name]
        m = re.search(pat, text)
        if not m:
            print(f"{name:<24}{geom:<8}{pat[:32]:<34}{'':>7}{'':>8}  ❌ 盘上认不到这句")
            bad += 1
            continue
        on_disk = float("0." + m.group(1)) if m.groups() else None
        same = (alpha is None and on_disk is None) or (
            isinstance(alpha, float) and on_disk is not None and abs(alpha - on_disk) < 1e-9)
        if not same:
            bad += 1
        print(f"{name:<24}{geom:<8}{why:<34}"
              f"{(f'{alpha:.2f}' if isinstance(alpha, float) else '—'):>7}"
              f"{(f'{on_disk:.2f}' if on_disk is not None else '—'):>8}  "
              f"{'✅' if same else '❌ 表与盘上不一致'}")
    if bad:
        raise SystemExit(f"层表与盘上有 {bad} 处对不上——先修口径再读别的（探针拒绝在漂移的表上出数）")

    print("\n## 2. 层清单（合成底 / 两主题 / 该层能达到的比值区间）\n")
    print(f"{'层':<24}{'主题':<7}{'合成底':<10}{'亮度':>8}{'C=黑':>8}{'C=白':>8}")
    for name in names:
        for theme in ("dark", "light"):
            bg = L.layer_colors(name, theme, tok)[1]
            rb = ratio_of((0, 0, 0, 1.0), name, theme, tok)
            rw = ratio_of((255, 255, 255, 1.0), name, theme, tok)
            print(f"{name:<24}{theme:<7}{L.hexs(bg):<10}{L.luminance(bg):>8.4f}"
                  f"{rb:>8.2f}{rw:>8.2f}")

    print("\n### 括号彩虹（压在**括号字形**上；括号没有 token 类，字色 = `--code-text`）\n")
    for i in range(8):
        nm = f"--code-bg+--bracket-rainbow-{i}"
        row = []
        for theme in ("dark", "light"):
            bg = L.layer_colors(nm, theme, tok)[1]
            fg = L.over(tok.value(f"--bracket-rainbow-{i}", theme), tok.value("--code-text", theme))
            row.append(f"{theme} 底 {L.hexs(bg)} 字形 {L.hexs(fg)} "
                       f"比值 {L.contrast_on_layer(tok.value('--code-text', theme), nm, theme, tok):.2f}"
                       f"（旧算 {ratio_old_model(tok.value('--code-text', theme), nm, theme, tok):.2f}）")
        print(f"  rainbow-{i}: " + " ｜ ".join(row))

    # --- 3. 矩阵（新旧算法各一张） ------------------------------------------
    print("\n## 3. 矩阵：代码页上的字色 × 每一层\n")
    print("**新算法（判据）**：压在字上的层 = `contrast(over(tint,fg), over(tint,base))`；"
          "**旧算法（上一轮的账，只作对照）**：一律 `contrast(fg, bg)`。\n")
    for theme in ("dark", "light"):
        print(f"\n### {theme}（新算法）\n")
        print(f"{'字色':<12}" + "".join(f"{n.replace('--code-bg', 'bg').replace('+hl.', '+'):>16}"
                                        for n in names))
        for t in TOKENS + ["--code-text"]:
            fg = tok.value(t, theme)
            cells = ""
            for n in names:
                r = ratio_of(fg, n, theme, tok)
                mark = "❌" if r < AA else ("·" if r < NEED else " ")
                cells += f"{r:>14.2f}{mark} "
            print(f"{t:<12}{cells}")
        print(f"\n### {theme}（旧算法 —— **不是判据**，用来复算「更正了多少」）\n")
        print(f"{'字色':<12}" + "".join(f"{n.replace('--code-bg', 'bg').replace('+hl.', '+'):>16}"
                                        for n in names))
        for t in TOKENS:
            fg = tok.value(t, theme)
            print(f"{t:<12}" + "".join(f"{ratio_old_model(fg, n, theme, tok):>16.2f}" for n in names))

    # --- 4. 层侧扫描 -------------------------------------------------------
    print("\n## 4. 层侧：最狠两层（选区 / 当前命中）一起降档——每档下十个令牌几个不达标\n")
    print(f"{'α(两层)':<11}{'浅色选区底':<11}{'浅色要改':>9}{'暗色选区底':<11}{'暗色要改':>9}")
    for a in (0.38, 0.32, 0.28, 0.24, 0.20, 0.16, 0.12):
        ov = {"--code-bg+hl.选区": a, "--code-bg+hl.当前命中": a}
        tab = layers_with(ov)
        row = {}
        for theme in ("light", "dark"):
            bg = L.layer_colors("--code-bg+hl.选区", theme, tok, tab)[1]
            changed = sum(1 for t in TOKENS
                          if worst(tok.value(t, theme), names, theme, tok, tab) < NEED - 1e-9)
            row[theme] = (L.hexs(bg), changed)
        print(f"{a:<11}{row['light'][0]:<11}{row['light'][1]:>9}{row['dark'][0]:<11}"
              f"{row['dark'][1]:>9}")

    print("\n## 5. 层侧：换一支青（`--code-hl-rgb`，α 全不动）\n")
    grid = {
        "light": ["0,150,199", "60,175,205", "90,180,210", "120,195,220", "140,205,230"],
        "dark": ["0,212,255", "0,190,230", "0,170,205", "0,150,185", "0,120,150", "0,90,115"],
    }
    for theme in ("light", "dark"):
        print(f"\n### {theme}\n")
        print(f"{'候选':<16}{'选区底':<10}{'当前命中底':<12}{'可见度':>8}{'要改/10':>9}  解（kw / pre / com）")
        for spec in grid[theme]:
            t2 = tok_with_hl(tok, theme, spec)
            bg32 = L.layer_colors("--code-bg+hl.选区", theme, t2)[1]
            bg38 = L.layer_colors("--code-bg+hl.当前命中", theme, t2)[1]
            code = L.layer_colors("--code-bg", theme, t2)[1]
            changed, ex = 0, []
            for t in TOKENS:
                fg = t2.value(t, theme)
                if worst(fg, names, theme, t2) < NEED - 1e-9:
                    changed += 1
                if t in ("--tok-kw", "--tok-pre", "--tok-com"):
                    _k, cand, _r = solve(fg, names, theme, t2)
                    ex.append(f"{t.replace('--tok-', '')}:{L.hexs(cand) if cand else '—'}")
            print(f"{spec:<16}{L.hexs(bg32):<10}{L.hexs(bg38):<12}"
                  f"{L.contrast(bg38, code):>8.2f}{changed:>9}  " + " ".join(ex))

    # --- 6. 叠加态（边界） --------------------------------------------------
    print("\n## 6. 叠加态（**口径边界**：真实会发生，但不进口径——同一 tint 的 over 层按 "
          "1-∏(1-α) 合成）\n")
    print(f"{'方案':<34}{'主题':<7}{'单层最坏':>9}{'叠词命中':>9}{'叠搜索命中':>11}{'叠当前命中':>11}")
    plans = [
        ("现状（选区 .32 / 当前 .38）", {}),
        ("选区 .20 / 当前 .24（落定）", {"--code-bg+hl.选区": 0.20, "--code-bg+hl.当前命中": 0.24}),
    ]
    for label, ov in plans:
        tab = layers_with(ov)
        a_sel = ov.get("--code-bg+hl.选区", 0.32)
        a12 = L.layer_alpha_of("--code-bg+hl.词命中", tab)
        a18 = L.layer_alpha_of("--code-bg+hl.搜索命中", tab)
        a38 = L.layer_alpha_of("--code-bg+hl.当前命中", tab)
        for theme in ("light", "dark"):
            solved = {t: solve(tok.value(t, theme), names, theme, tok, tab)[1] for t in TOKENS}
            singles = min(worst(c, names, theme, tok, tab) for c in solved.values())
            stacks = [min(stack_ratio(c, [a_sel, a_m], theme, tok, tab) for c in solved.values())
                      for a_m in (a12, a18, a38)]
            print(f"{label if theme == 'light' else '':<34}{theme:<7}{singles:>9.2f}"
                  f"{stacks[0]:>9.2f}{stacks[1]:>11.2f}{stacks[2]:>11.2f}")

    # --- 7. 落定读数 --------------------------------------------------------
    print("\n## 7. 落定读数：选区 .20 / 当前命中 .24 + 暗色 `--code-hl-rgb` 候选\n")
    for label, ov, hl in (
        ("① 层全不动（只压令牌）", {}, None),
        ("② 选区 .20 / 当前命中 .24（落定）", {"--code-bg+hl.选区": 0.20, "--code-bg+hl.当前命中": 0.24}, None),
    ):
        tab = layers_with(ov)
        print(f"\n### {label}\n")
        print(f"{'令牌':<12}{'主题':<7}{'现值':<10}{'现值最坏':>9}{'解':<10}{'改动':>8}{'解最坏':>8}"
              f"{'最狠层':>22}  说明")
        floor_of = {"dark": (9.9, ""), "light": (9.9, "")}
        for t in TOKENS:
            for theme in ("light", "dark"):
                fg = tok.value(t, theme)
                cur = worst(fg, names, theme, tok, tab)
                k, cand, r = solve(fg, names, theme, tok, tab)
                if cand is None:
                    print(f"{t:<12}{theme:<7}{L.hexs(fg):<10}{cur:>9.2f}   扫不出来 ❌")
                    continue
                note = "现值已达标" if k == 1.0 else ("压暗" if theme == "light" else "提亮")
                wl = min(names, key=lambda n: ratio_of(cand, n, theme, tok, tab))
                print(f"{t:<12}{theme:<7}{L.hexs(fg):<10}{cur:>9.2f}{L.hexs(cand):<10}"
                      f"{('×' + format(k, '.3f')):>8}{r:>8.2f}{wl.replace('--code-bg', 'bg'):>22}  {note}")
                if r < floor_of[theme][0]:
                    floor_of[theme] = (r, f"{t} on {wl}")
        print(f"  —— 全域最坏格：浅色 {floor_of['light'][0]:.2f}（{floor_of['light'][1]}）／"
              f"暗色 {floor_of['dark'][0]:.2f}（{floor_of['dark'][1]}）")

    print("\n### ⑦b 落定方案下，暗色 `--code-hl-rgb` 取哪一支（可见度 = 当前命中层相对代码底的比值）\n")
    print(f"{'dark --code-hl-rgb':<20}{'.20 合成':<10}{'.24 合成':<10}{'可见度':>8}{'要改/10':>9}  解（要改的）")
    tab = layers_with({"--code-bg+hl.选区": 0.20, "--code-bg+hl.当前命中": 0.24})
    for spec in ("0,212,255", "0,190,230", "0,170,205", "0,150,185", "0,120,150"):
        t2 = tok_with_hl(tok, "dark", spec)
        bg20 = L.layer_colors("--code-bg+hl.选区", "dark", t2, tab)[1]
        bg24 = L.layer_colors("--code-bg+hl.当前命中", "dark", t2, tab)[1]
        code = L.layer_colors("--code-bg", "dark", t2, tab)[1]
        solved, changed = [], 0
        for t in TOKENS:
            k, cand, _r = solve(t2.value(t, "dark"), names, "dark", t2, tab)
            if k != 1.0 and cand is not None:
                changed += 1
                solved.append(f"{t.replace('--tok-', '')}→{L.hexs(cand)}")
        print(f"{spec:<20}{L.hexs(bg20):<10}{L.hexs(bg24):<10}{L.contrast(bg24, code):>8.2f}"
              f"{changed:>9}  " + " ".join(solved))

    print("\n" + "=" * 108)
    print("怎么读：压在字上的层**既染底也染字** ⇒ 比上一版（把高亮当垫底）更严；")
    print("       §6 是**边界**不是达标项；§7 是要落的值。")
    print("=" * 108)

    # --- 8. 族面格数（守卫里那条冻结值的复算口） ----------------------------
    cells = L.contrast_family_cells(text, tok)
    per = {}
    for c in cells:
        per[c["label"]] = per.get(c["label"], 0) + 1
    print(f"\n## 8. 族面格数（守卫 `CONTRAST_FAMILY_CELL_COUNT` 的复算口）\n")
    print(f"  合计 **{len(cells)}**")
    for label, n in per.items():
        print(f"    {n:>4}  {label}")
    print("  —— 守卫里那个常量必须等于上面这一行的合计；"
          "`tests/test_contrast_mirror.py` 每次跑都会现算复核。")


if __name__ == "__main__":
    main()
