r"""工单 06 施工脚本（二）：五个素材/库页作用域里**等于令牌却裸写**的 padding / margin / gap。

做法与 05b 同（**保值变换**：`8px` → `var(--space-2)` 像素值不变），但这一趟加了 05 单评审
点名缺的那条：**覆盖率断言**——每个作用域的取值数必须与申报一致（多一处少一处都停手），
不是"只打印现算了几处"。

  · 锚点 = 那条声明的**完整原文**（`padding: 8px 12px;`），要求在该规则体内恰好命中一次；
  · 编辑区间不许重叠（04 账第 9 条）；
  · **含 `calc(` 的声明一律停手**（本五页没有 calc 例外；不留恒空的点名表——05 单的账第 7 条）；
  · 改完复扫：五页"等于令牌却裸写"必须是 0（判据与守卫/探针同一处 `scope_lib.bare_token_spaces`）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06b-spaces.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06b-spaces.py --write
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import (PAGE, ROOT, SPACE_RE, bare_token_spaces, load_scopes,  # noqa: E402
                       read_page, rules_of, scope_of, tokenize_space_decl, write_page)

# 申报的取值数（= 开工前 probe-01 现算），用作覆盖率断言
EXPECT_VALUES = {"library": 24, "reference": 8, "pdf": 1, "md": 3, "topic": 15}
SCOPES = list(EXPECT_VALUES)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    problems: list[str] = []
    edits: list[tuple[int, int, str, str]] = []

    before = {sc: bare_token_spaces(text, sc) for sc in SCOPES}
    for sc in SCOPES:
        if len(before[sc]) != EXPECT_VALUES[sc]:
            problems.append(f"{sc}: 盘上现算 {len(before[sc])} 处取值，申报 {EXPECT_VALUES[sc]} 处"
                            f"（多/少都要先弄清为什么）")

    scopes = load_scopes()
    for line, sel, b0, b1 in rules_of(text):
        sc = scope_of(sel, scopes)
        if sc not in EXPECT_VALUES:
            continue
        body = text[b0:b1]
        for m in SPACE_RE.finditer(body):
            decl = m.group(0)
            if "calc(" in decl:
                problems.append(f"{sc} L{line}: 这条声明里有 calc(——本五页没有登记例外，"
                                f"停手让人看一眼：{decl!r}")
                continue
            new = tokenize_space_decl(decl)
            if new is None:
                continue
            if body.count(decl) != 1:
                problems.append(f"{sc} L{line}: 锚点 {decl!r} 在该规则体内出现 {body.count(decl)} 次（期望 1）")
                continue
            at = b0 + body.index(decl)
            edits.append((at, at + len(decl), new,
                          f"{sc:<9} L{line}  {sel.split('*/')[-1].strip()[:36]:<36} {decl}  →  {new}"))

    # 编辑区间不许重叠（04 账第 9 条）
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== 五页间距：{len(edits)} 条声明待改"
          f"（{' / '.join(f'{sc} {len(before[sc])}' for sc in SCOPES)} 处取值）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    left = {sc: bare_token_spaces(text, sc) for sc in SCOPES}
    bad = [(sc, *row) for sc in SCOPES for row in left[sc]]
    if bad:
        print("\n== **停下**：改完仍有裸写的令牌间距（没写盘）==")
        for sc, line, sel, value in bad:
            print(f"  ✗ {sc} L{line}  {sel[:60]} → {value}px")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫五页裸令牌间距 = 0 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：{len(edits)} 条声明；复扫五页裸令牌间距 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
