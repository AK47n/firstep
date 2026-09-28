r"""工单 05 施工脚本（三）：`settings` 作用域**内层完整描边**的逐条处置。

口径（spec「描边规矩」+ 01/02 单落的规矩 + 04 单补的三类例外）：
**一屏一层完整描边**——一个页面页签 / 一个弹层内，完整矩形描边只有最外层容器那一条。

**这一页的家底（两个口径，别混着读）**：探针"border 声明"口径 = **8** 处（含单边分隔线与
`border: 0`），**整圈完整框** = **4** 处（`scope_lib.full_borders`）。逐条处置：

  · 改 **2** 条（内层盒去框，留淡底）：
      `.recent-wf-summary`（卡片里的 mono 数据块 → 照样板 `pre.result`：数据面不画框）
      `.materials-pick-list`（弹层里的批次勾选清单 → 弹层外壳才是那一层；行间已有单边分隔）
  · 留 **2** 条，逐条写理由：
      `.env-jump`（② 可点控件：缺失项跳转小胶囊）
      `.settings-stickybar`（② 悬浮控件：fixed 的保存胶囊，它自己就是一层）

完整性证明（比 04c 加严两处——04 单评审点名的弱点）：
  · 改前 / 改后对账**连取值一起比**（`(行号, 取值)` 集合，不只是行号集合）；
  · 认人按 `(行号, 选择器片段)`（同一行落两条规则时不会挑错人）；
  · 口径函数用 `scope_lib.full_borders`（单一出处，不再各抄一份正则）；
  · 替换串**不含换行**。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05c-borders.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05c-borders.py --write
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import (PAGE, ROOT, full_borders, load_scopes, read_page,  # noqa: E402
                       rules_of, scope_of, write_page)

SCOPE = "settings"
FLAT = "border: none;"

# 行号（探针口径）→ [(选择器片段, 取值（不含分号，与 scope_lib.full_borders 同口径）, 换成, 理由)]
FIX: dict[int, list[tuple[str, str, str, str]]] = {
    1484: [(".recent-wf-summary", "1px solid var(--border)", FLAT,
            "卡片里的 mono 数据块：照样板 `pre.result`——代码/数据面不画框，留 --code-bg 淡底")],
    1514: [(".materials-pick-list", "1px solid var(--border)", FLAT,
            "弹层里的批次勾选清单：弹层外壳（.ref-files-modal）才是那一层；行间已有单边分隔")],
}

# 行号（探针口径）→ (选择器片段, 取值, 保留理由)
KEEP: dict[int, tuple[str, str, str]] = {
    370: (".env-jump", "1px solid var(--border)", "② 可点控件：缺失项「去设置填」小胶囊按钮"),
    1602: (".settings-stickybar", "1px solid var(--border)",
           "② 悬浮控件：fixed 保存胶囊（自己就是一屏里的那一层）"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()
    problems: list[str] = []

    # ① 改前完整性：**连取值一起对账**（(行号, 取值) 多重集 == FIX ∪ KEEP）
    #    用 Counter 比**重数**（04a 立的口径：集合差集在"同一行两条规则同值"时会静默放行——
    #    05 单评审 Standards 抓到本支第一版正是集合，已按 04a 的标准改回来）
    before = full_borders(text, SCOPE)
    before_counts = Counter((line, value) for line, _, value in before)
    fix_pairs = Counter((line, value) for line, fixes in FIX.items() for _, value, _, _ in fixes)
    keep_pairs = Counter((line, value) for line, (_, value, _) in KEEP.items())
    declared = fix_pairs + keep_pairs
    if before_counts != declared:
        problems.append(f"改前的整圈完整框 (行号, 取值) 重数与申报不符："
                        f"多出 {sorted((before_counts - declared).elements())}、"
                        f"少了 {sorted((declared - before_counts).elements())}")

    # ② 逐条锚点：按 (行号, 选择器片段) 认人，锚点在规则体内恰好命中一次
    #    锚点原文 = `border: {取值};`（取值与 full_borders 同口径，不含分号）
    edits: list[tuple[int, int, str, str]] = []
    hit: dict[tuple[int, str], int] = {}
    for line, sel, b0, b1 in rules_of(text):
        if line not in FIX:
            continue
        body = text[b0:b1]
        for frag, value, new, why in FIX[line]:
            if frag not in sel:
                continue                       # 同一行可能有好几条规则，按选择器片段认人
            anchor = f"border: {value};"
            key = (line, value)
            hit[key] = hit.get(key, 0) + 1
            if body.count(anchor) != 1:
                problems.append(f"L{line} {frag}: 锚点 {anchor!r} 出现 {body.count(anchor)} 次（期望 1）")
                continue
            at = b0 + body.index(anchor)
            edits.append((at, at + len(anchor), new,
                          f"L{line}  {sel.split('*/')[-1].strip()[:40]:<40} → {why}"))
    for line, fixes in sorted(FIX.items()):
        for frag, value, _, _ in fixes:
            if hit.get((line, value), 0) == 0:
                problems.append(f"L{line}（{frag}）的锚点 {value!r} 一次都没命中")
            elif hit[(line, value)] > 1:
                problems.append(f"L{line}（{frag}）的锚点 {value!r} 命中 {hit[(line, value)]} 条规则（期望 1）")

    print(f"== {SCOPE} 描边：改 {len(edits)} 条 / 保留 {len(KEEP)} 条"
          f"（改前整圈完整框 {len(before)} 处）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改  " + note)
    for line in sorted(KEEP):
        print(f"  留  L{line}  {KEEP[line][0]}  {KEEP[line][2]}")

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ③ 改后复扫：整圈完整框只剩 KEEP，且**取值逐字相同**（同样比重数）
    after = full_borders(text, SCOPE)
    after_counts = Counter((line, value) for line, _, value in after)
    if after_counts != keep_pairs:
        print("\n== **停下**：改后剩下的整圈完整框与申报不符（没写盘）==")
        print(f"  多出 {sorted((after_counts - keep_pairs).elements())}")
        print(f"  少了 {sorted((keep_pairs - after_counts).elements())}")
        for line, sel, value in after:
            print(f"  · L{line}  {sel[:70]}  →  {value}")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫 {SCOPE} 整圈完整框 = {len(after)} 处，"
              f"全部在申报的例外里、取值逐字未变 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：改 {len(edits)} 条；"
          f"复扫整圈完整框 = {len(after)} 处（全部在申报的例外里）✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
