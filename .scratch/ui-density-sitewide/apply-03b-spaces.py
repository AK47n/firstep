r"""工单 03 施工脚本（二）：`generate` 作用域里**等于令牌却裸写**的 padding / margin / gap。

规矩（spec「间距走令牌」+ 01 单立的纪律）：值等于 `--space-1..6`（4/8/12/16/20/24）的
间距一律写 `var(--space-N)`。这一支是**保值变换**（12px → `var(--space-3)` = 同一像素值），
所以逐条"显式锚点"由**断言**承担，而不是靠人手抄 100 多条相同形状的表：

  · 每条改动的锚点 = **那一条声明的完整原文**（`padding: 8px 12px;`），
    要求它在该规则体内**恰好命中一次**——命中 0 次或 2 次都整支停手；
  · 只动 `padding` / `margin` / `gap`（含 `-top/-right/-bottom/-left`）这几条声明，
    其余一律不碰；含 `calc(` 的值跳过（不猜它想算什么）；
  · 改完**回头复扫**：该作用域里"等于令牌却裸写"的间距必须是 0（漏一条就停手）。
      —— 这条复扫就是本支的覆盖率证明：探针与守卫用的是同一个判据。

替换串里**不含换行**，因此 02 单那条"替换侧把裸 LF 写进 CRLF 文件"的坑在本支不可能发生
（票尾照旧跑一次 fix-crlf.py 复核行尾）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03b-spaces.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03b-spaces.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"
SCOPE = "generate"

SPACE_TOKEN = {4: "--space-1", 8: "--space-2", 12: "--space-3",
               16: "--space-4", 20: "--space-5", 24: "--space-6"}
SPACE_RE = re.compile(r"(?:padding|margin|gap)(?:-top|-right|-bottom|-left)?:\s*([^;]+);")
NUM_RE = re.compile(r"(?<![\w.-])(\d+)px")


def load_scopes() -> list[tuple[str, re.Pattern[str]]]:
    text = GUARD.read_text(encoding="utf-8")
    block = re.search(r"const PAGE_SCOPES = \[(.*?)\n\];", text, re.S)
    if not block:
        raise SystemExit("守卫里找不到 PAGE_SCOPES")
    return [(m.group(1), re.compile(m.group(2)))
            for m in re.finditer(r'\["([\w-]+)", /(.*?)/\]', block.group(1))]


def scope_of(sel: str, scopes: list[tuple[str, re.Pattern[str]]]) -> str:
    clean = re.sub(r"^(?:/\*.*?\*/\s*)+", "", sel, flags=re.S).strip()
    for name, rx in scopes:
        if rx.search(clean):
            return name
    return scopes[-1][0]


def rules_of(text: str) -> list[tuple[int, str, int, int]]:
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text, re.S):
        out.append((text.count("\n", 0, m.start()) + 1,
                    " ".join(m.group(1).split()), m.start(2), m.end(2)))
    return out


def tokenize(decl: str) -> str | None:
    """把一条声明里等于令牌的裸 px 换成 var(--space-N)；没有可换的就返回 None。"""
    value = SPACE_RE.match(decl)
    if not value or "calc(" in value.group(1):
        return None
    body = value.group(1)
    changed = NUM_RE.sub(lambda m: f"var({SPACE_TOKEN[int(m.group(1))]})"
                         if int(m.group(1)) in SPACE_TOKEN else m.group(0), body)
    if changed == body:
        return None
    return decl[:value.start(1)] + changed + decl[value.end(1):]


def bare_spaces(text: str) -> list[tuple[int, str, str]]:
    """该作用域里现算的"等于令牌却裸写"的间距：[(行号, 选择器, 取值px)]。"""
    scopes = load_scopes()
    found: list[tuple[int, str, str]] = []
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        for m in SPACE_RE.finditer(text[b0:b1]):
            for n in NUM_RE.finditer(m.group(1)):
                if int(n.group(1)) in SPACE_TOKEN:
                    found.append((line, sel, n.group(1)))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    before = bare_spaces(text)
    print(f"== generate 间距：盘上现算 {len(before)} 处等于令牌却裸写 ==")

    scopes = load_scopes()
    edits: list[tuple[int, int, str, str]] = []
    problems: list[str] = []
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        body = text[b0:b1]
        for m in SPACE_RE.finditer(body):
            decl = m.group(0)
            new = tokenize(decl)
            if new is None:
                continue
            if body.count(decl) != 1:
                problems.append(f"L{line}: 锚点 {decl!r} 在该规则体内出现 {body.count(decl)} 次（期望 1）")
                continue
            at = b0 + body.index(decl)
            edits.append((at, at + len(decl), new, f"L{line}  {sel}  {decl}  →  {new}"))

    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    left = bare_spaces(text)
    if left:
        print("\n== **停下**：改完仍有裸写的令牌间距（没写盘）==")
        for line, sel, value in left:
            print(f"  ✗ L{line}  {sel} → {value}px")
        return 1

    if not args.write:
        print(f"\n（--dry-run：{len(edits)} 处待改，没有写盘。复扫 {SCOPE} 裸令牌间距 = 0 ✅；"
              f"确认无误后加 --write）")
        return 0
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：{len(edits)} 处；复扫 {SCOPE} 裸令牌间距 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
