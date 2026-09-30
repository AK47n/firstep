"""浅色调色板轮 · 例外表生成器（01 单）：把「盘上不达标 / 不适用」的颜色对变成守卫里的数据。

**为什么要有生成器**（照描边那轮 `generate-01-register.py` 的先例）：
例外表是**数据的机械产物**（"此刻盘上哪些对不达标、比值多少"），拿手抄必然抄错；
生成器还把"这份表还是不是生成时那张"变成一条可复核的命令（`--check`）。

跑法（仓库根）：
    python .scratch/light-contrast/generate-01-contrast-register.py            # 打印表（不写盘）
    python .scratch/light-contrast/generate-01-contrast-register.py --write    # 写进守卫（替换块）
    python .scratch/light-contrast/generate-01-contrast-register.py --check    # 守卫那张表还是生成时那张吗
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

MARK = "// <<CONTRAST_EXCEPTIONS>>"

#: 谁负责修（写进理由，读表的人一眼知道去向）
OWNER = [
    (re.compile(r"--accent\b|--on-accent\b|#fff|#ffffff"), "02 单（--accent-text / 两处白字）"),
    (re.compile(r"--ok|--warn|--danger|--info|--purple"), "02 单（六族微调）"),
]

DARK_OWNER = "03 单（暗色顺手修）"


def owner_of(fg_raw: str, theme: str) -> str:
    if theme == "dark":
        return DARK_OWNER
    for rx, who in OWNER:
        if rx.search(fg_raw):
            return who
    return "02 单"


def reason(p, theme: str) -> str:
    fg = p.fg_raw.replace("var(", "").replace(")", "")
    bg = p.bg_raw.replace("var(", "").replace(")", "")
    return f"{fg} 压 {bg}：{p.ratio:.2f}，低于 {p.need}——{owner_of(p.fg_raw, theme)}"


def js_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_rows():
    """→ `[(主题, 认人键, 类别, 理由, 冻结比值)]`（机械面 + 族面）。"""
    text = L.read_page()
    tok = L.Tokens(text)
    rows = []
    for p in L.contrast_pairs(text, tok):
        if p.ratio >= p.need - 1e-9:
            continue
        kind = "skip" if "::selection" in p.selector else "debt"
        why = ("选区反白块不是「文字压底」：静态口径不适用（跳过判据，只留登记）"
               if kind == "skip" else reason(p, p.theme))
        rows.append((p.theme, p.selector, kind, why, round(p.ratio, 2)))
    # 族面：每族每主题只登记**最坏格**（细节矩阵在读数里）。
    # ⚠ 例外类别只有 debt / skip 两种：族表的 kind（text / nontext）**只决定阈值档位**，
    #   "非文字"不是"允许不达标"的理由——焦点环低于 3:1 同样是 debt。
    cells = L.contrast_family_cells(text, tok)          # **算一次**给所有族用（评审点过重复计算）
    for label, _pick, _layers, fkind, why in L.CONTRAST_FAMILIES:
        for theme in ("dark", "light"):
            sub = [c for c in cells if c["label"] == label and c["theme"] == theme]
            if not sub:
                raise SystemExit(f"族「{label}」在 {theme} 下一格都没算出来")
            worst = min(sub, key=lambda c: c["ratio"])
            if worst["ratio"] >= worst["need"] - 1e-9:
                continue
            tier = "非文字图形 3:1" if fkind == "nontext" else "文字 4.5:1"
            rows.append((theme, L.contrast_family_key(label), "debt",
                         f"最坏格 {worst['token']} on {worst['layer']}：{worst['ratio']:.2f}"
                         f"，低于 {worst['need']}（{tier}）——{why}",
                         round(worst["ratio"], 2)))

    # **令牌面**（第三面）：无底规则里的文字令牌，同样每主题只登记最坏格
    used = L.unbased_color_tokens(text)
    declared = {lit: (layers, kind, why) for lit, layers, kind, why in L.CONTRAST_TOKEN_BASES}
    tcells = L.contrast_token_cells(text, tok)
    for literal in used:
        layers, kind, why = declared[literal]
        if not layers:
            continue
        for theme in ("dark", "light"):
            sub = [c for c in tcells if c["literal"] == literal and c["theme"] == theme]
            if not sub:
                raise SystemExit(f"令牌 {literal} 在 {theme} 下一格都没算出来")
            worst = min(sub, key=lambda c: c["ratio"])
            if worst["ratio"] >= worst["need"] - 1e-9:
                continue
            tier = "非文字图形 3:1" if kind == "nontext" else "文字 4.5:1"
            rows.append((theme, L.contrast_token_key(literal), "debt",
                         f"最坏格压 {worst['layer']}：{worst['ratio']:.2f}，低于 {worst['need']}"
                         f"（{tier}）——{why}",
                         round(worst["ratio"], 2)))
    # **渐变端点面**（02 单评审补的盲区）：逐端点算，不达标的登记
    for cell in L.contrast_gradient_cells(text, tok):
        if cell["ratio"] >= cell["need"] - 1e-9:
            continue
        rows.append((cell["theme"], L.contrast_gradient_key(cell["fg"], cell["layer"]), "debt",
                     f"{cell['fg']} 压在 {cell['layer']}：{cell['ratio']:.2f}，低于 {cell['need']}"
                     f"——{cell['why']}",
                     round(cell["ratio"], 2)))

    rows.sort(key=lambda r: (r[0] != "dark", r[2] != "skip", r[4]))
    return rows

def render(rows) -> str:
    out = []
    for theme, key, kind, why, ratio in rows:
        out.append(f"  [{js_str(theme)}, {js_str(key)}, {js_str(kind)}, {js_str(why)}, {ratio}],")
    return "\n".join(out)


def current_block() -> str | None:
    js = L.guard_text()
    m = re.search(r"const CONTRAST_EXCEPTIONS = \[(.*?)\n\];", js, re.S)
    return m.group(1) if m else None


def main() -> None:
    args = sys.argv[1:]
    rows = build_rows()
    body = render(rows)
    face = lambda key: sum(1 for r in rows if r[1].startswith(key))  # noqa: E731
    print(f"# 例外表：{len(rows)} 条（机械面 {len(rows) - face('族：') - face('令牌：')} + "
          f"族面 {face('族：')} + 令牌面 {face('令牌：')}）")
    by_kind: dict[str, int] = {}
    by_theme: dict[str, int] = {}
    for theme, _k, kind, _w, _r in rows:
        by_kind[kind] = by_kind.get(kind, 0) + 1
        by_theme[theme] = by_theme.get(theme, 0) + 1
    print(f"# 类别分布：{by_kind}；主题分布：{by_theme}")

    if "--write" in args:
        js = L.guard_text()
        m = re.search(r"const CONTRAST_EXCEPTIONS = \[(.*?)\n\];", js, re.S)
        if not m:
            raise SystemExit(f"守卫里找不到 `const CONTRAST_EXCEPTIONS = [...];`（标记 {MARK}）")
        new = js[:m.start(1)] + "\n" + body + "\n" + js[m.end(1):]
        L.GUARD.write_text(new, encoding="utf-8", newline="")
        print(f"# 已写进 {L.GUARD.relative_to(L.ROOT)}")
    elif "--check" in args:
        cur = current_block()
        if cur is None:
            raise SystemExit("守卫里找不到例外表")
        norm = lambda s: [ln.strip() for ln in s.strip().splitlines() if ln.strip()]  # noqa: E731
        if norm(cur) != norm(body):
            raise SystemExit("守卫里的例外表与生成器算出来的不一致——重跑 --write，并复核差在哪几条")
        print("# --check OK：守卫那张表就是生成器现在算出来的这张")
    else:
        print(body)


if __name__ == "__main__":
    main()
