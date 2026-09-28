r"""工单 05 施工脚本（二）：`settings` 作用域里**等于令牌却裸写**的 padding / margin / gap。

做法与 04b 同（**保值变换**：`8px` → `var(--space-2)` 像素值不变），断言由"整条声明当锚点 +
规则体内恰好命中一次"承担；改完回头复扫"等于令牌却裸写"必须是 0（判据与守卫/探针同一处：
`scope_lib.bare_token_spaces`）。**含 `calc(` 的值默认跳过**并在输出里列出来——本作用域这一趟
一条 calc 都没有（脚本会打印"跳过 0 条"）。

替换串**不含换行**（02 单那条"替换侧写进裸 LF"的坑在本支不可能发生）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05b-spaces.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05b-spaces.py --write
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

SCOPE = "settings"
NUM_RE = re.compile(r"(?<![\w.-])(\d+)px")


def tokenize(decl: str) -> str | None:
    """把一条声明里等于令牌的裸 px 换成 var(--space-N)；没有可换的就返回 None。

    ⚠ `calc(` 的值**一律不碰**——本支没有 calc 例外（04b 那条
    `padding-left: calc(3.4em + 12px)` 是代码页的）；真出现就停手让人看，
    **不留"恒空的点名表"那种死参数**（05 单评审点名的 Speculative Generality）。
    """
    m = SPACE_RE.match(decl)
    if not m:
        return None
    if "calc(" in m.group(1):
        return None
    body = m.group(1)
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
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        body = text[b0:b1]
        for m in SPACE_RE.finditer(body):
            decl = m.group(0)
            if "calc(" in decl:
                problems.append(f"L{line}  {sel[:50]}: 这条声明里有 calc(——本支没有登记例外，"
                                f"停手让人看一眼：{decl!r}")
                continue
            new = tokenize(decl)
            if new is None:
                continue
            if body.count(decl) != 1:
                problems.append(f"L{line}: 锚点 {decl!r} 在该规则体内出现 {body.count(decl)} 次（期望 1）")
                continue
            at = b0 + body.index(decl)
            edits.append((at, at + len(decl), new, f"L{line}  {sel.split('*/')[-1].strip()[:42]:<42} "
                                                   f"{decl}  →  {new}"))

    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)

    # 编辑区间不许重叠（04 单的账第 9 条）
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1!r} 与 [{s2},…)")

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
        print(f"\n（--dry-run：{len(edits)} 条声明待改（{len(before)} 处取值），没有写盘。"
              f"复扫 {SCOPE} 裸令牌间距 = 0 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：{len(edits)} 条声明；"
          f"复扫 {SCOPE} 裸令牌间距 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
