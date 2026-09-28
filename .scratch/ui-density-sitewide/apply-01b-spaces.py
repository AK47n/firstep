r"""工单 01 施工脚本（二）：shell 作用域的**间距令牌化**。

把「数值明明等于 `--space-*` 却裸写」的 padding / margin / gap 就地换成令牌
（渲染零变化——只是把同一个数说成令牌的名字）。

**分区表从守卫解析**（`tests/js/css-tokens.test.mjs` 的 `PAGE_SCOPES`，单一出处）：
作用域口径与守卫、与读数探针三处一致。

只动「整条声明里出现的、且等于 4/8/12/16/20/24 的 px 值」——其余 px（3/5/9/10/14 这类
细内边距、`border-radius`、`box-shadow` 偏移）一个字不碰。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-01b-spaces.py --scope shell --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-01b-spaces.py --scope shell --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"

SPACE_TOKEN = {4: 1, 8: 2, 12: 3, 16: 4, 20: 5, 24: 6}
DECL_RE = re.compile(r"\b(padding|margin|gap)(-top|-right|-bottom|-left)?:\s*([^;]+);")
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def load_scopes() -> list[tuple[str, re.Pattern[str]]]:
    block = re.search(r"const PAGE_SCOPES = \[(.*?)\n\];", GUARD.read_text(encoding="utf-8"), re.S)
    if not block:
        raise SystemExit("守卫里找不到 PAGE_SCOPES —— 解析失败，别拿空表当尺子")
    return [(m.group(1), re.compile(m.group(2)))
            for m in re.finditer(r'\["([\w-]+)", /(.*?)/\]', block.group(1))]


def scope_of(sel: str, scopes: list[tuple[str, re.Pattern[str]]]) -> str:
    for name, rx in scopes:
        if rx.search(sel):
            return name
    return scopes[-1][0]


def rewrite(body: str) -> tuple[str, list[str]]:
    """把声明块里等于令牌的间距值换成 `var(--space-N)`；返回 (新声明块, 改动说明)。"""
    notes: list[str] = []

    def one(m: re.Match[str]) -> str:
        prop, side, value = m.group(1), m.group(2) or "", m.group(3)

        def num(nm: re.Match[str]) -> str:
            v = int(nm.group(1))
            if v in SPACE_TOKEN:
                notes.append(f"{prop}{side}: {v}px → var(--space-{SPACE_TOKEN[v]})")
                return f"var(--space-{SPACE_TOKEN[v]})"
            return nm.group(0)

        return f"{prop}{side}: {re.sub(r'(\d+)px', num, value)};"

    return DECL_RE.sub(one, body), notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    scopes = load_scopes()
    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    edits: list[tuple[int, int, str, str]] = []
    for m in RULE_RE.finditer(text):
        sel = " ".join(m.group(1).split())
        if scope_of(sel, scopes) != args.scope:
            continue
        new_body, notes = rewrite(m.group(2))
        if not notes:
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        edits.append((m.start(2), m.end(2), new_body, f"L{line_no}  {sel[:70]}  |  {'; '.join(notes)}"))

    for start, end, new, note in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    print(f"== {args.scope} 作用域：{len(edits)} 条规则、{sum(n.count('→') for *_, n in edits)} 处取值 ==")
    for *_, note in sorted(edits, key=lambda e: int(e[3].split()[0][1:])):
        print("  " + note)

    if not edits:
        print("  （没有可改的——要么已经令牌化了，要么作用域名写错了）")
        return 0
    if not args.write:
        print("\n（--dry-run：没有写盘。确认无误后加 --write）")
        return 0
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
