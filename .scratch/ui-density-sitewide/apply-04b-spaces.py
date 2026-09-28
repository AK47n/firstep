r"""工单 04 施工脚本（二）：`code` 作用域里**等于令牌却裸写**的 padding / margin / gap。

规矩与 03b 同：这一支是**保值变换**（`12px` → `var(--space-3)` = 同一像素值），所以逐条
"显式锚点"由断言承担，而不是靠人手抄 84 条同形状的表：

  · 每条改动的锚点 = **那一条声明的完整原文**（`padding: 8px 12px;`），要求它在该规则体内
    **恰好命中一次**——命中 0 次或 2 次都整支停手；
  · 只动 `padding` / `margin` / `gap`（含 `-top/-right/-bottom/-left`）这几条声明，其余不碰；
  · **含 `calc(` 的值默认跳过**（不猜它想算什么）——唯一例外是本作用域里那一条
    `padding-left: calc(3.4em + 12px)`（`.code-wrap textarea`：12px 是行号列右侧的内边距，
    与 `.hl-layer` 的 `right: 12px` / `scrollbar-gutter` 预留同源；换成 `var(--space-3)`
    值不变）。例外写在 `CALC_ALLOW` 里**逐条点名**，没点名的 calc 一律跳过并在输出里列出来
    ——"跳过了几条"必须是看得见的，不能是静默的。
  · 改完**回头复扫**：该作用域里"等于令牌却裸写"的间距必须是 0（漏一条就停手）——
    复扫用的判据与守卫/探针**同一处**（`scope_lib.bare_token_spaces`）。

替换串里**不含换行**，因此 02 单那条"替换侧把裸 LF 写进 CRLF 文件"的坑在本支不可能发生
（票尾照旧跑一次 fix-crlf.py 复核行尾）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04b-spaces.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04b-spaces.py --write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import (PAGE, ROOT, SPACE_RE, SPACE_TOKEN, bare_token_spaces,  # noqa: E402
                       load_scopes, read_page, rules_of, scope_of, write_page)

SCOPE = "code"
NUM_RE = re.compile(r"(?<![\w.-])(\d+)px")

# 逐条点名的 calc 例外（完整声明原文 → 理由）。没点名的 calc 一律跳过。
CALC_ALLOW: dict[str, str] = {
    "padding-left: calc(3.4em + 12px);":
        "行号列右侧内边距（与 .hl-layer right:12px / scrollbar-gutter 同源），值不变",
}


def tokenize(decl: str) -> str | None:
    """把一条声明里等于令牌的裸 px 换成 var(--space-N)；没有可换的就返回 None。"""
    m = SPACE_RE.match(decl)
    if not m:
        return None
    body = m.group(1)
    if "calc(" in body and decl not in CALC_ALLOW:
        return None
    changed = NUM_RE.sub(lambda mm: f"var({SPACE_TOKEN[int(mm.group(1))]})"
                         if int(mm.group(1)) in SPACE_TOKEN else mm.group(0), body)
    if changed == body:
        return None
    return decl[:m.start(1)] + changed + decl[m.end(1):]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    before = bare_token_spaces(text, SCOPE)
    print(f"== {SCOPE} 间距：盘上现算 {len(before)} 处等于令牌却裸写 ==")

    scopes = load_scopes()
    edits: list[tuple[int, int, str, str]] = []
    problems: list[str] = []
    skipped_calc: list[str] = []
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        body = text[b0:b1]
        for m in SPACE_RE.finditer(body):
            decl = m.group(0)
            if "calc(" in decl and decl not in CALC_ALLOW:
                skipped_calc.append(f"L{line}  {sel[:60]}  {decl}")
            new = tokenize(decl)
            if new is None:
                continue
            if body.count(decl) != 1:
                problems.append(f"L{line}: 锚点 {decl!r} 在该规则体内出现 {body.count(decl)} 次（期望 1）")
                continue
            at = b0 + body.index(decl)
            edits.append((at, at + len(decl), new, f"L{line}  {sel.split('*/')[-1].strip()[:44]:<44} "
                                                   f"{decl}  →  {new}"))

    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if skipped_calc:
        print(f"\n  （跳过含 calc( 的声明 {len(skipped_calc)} 条——未逐条点名的不动）")
        for s in skipped_calc:
            print("     · " + s)
        print("  ）")

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    left = bare_token_spaces(text, SCOPE)
    if left:
        print("\n== **停下**：改完仍有裸写的令牌间距（没写盘）==")
        for line, sel, value in left:
            print(f"  ✗ L{line}  {sel[:70]} → {value}px")
        return 1

    if not args.write:
        print(f"\n（--dry-run：{len(edits)} 处待改、{len(before)} 处取值，没有写盘。"
              f"复扫 {SCOPE} 裸令牌间距 = 0 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：{len(edits)} 条声明；"
          f"复扫 {SCOPE} 裸令牌间距 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
