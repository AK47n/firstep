r"""工单 04 施工脚本（四）：**人眼看图 + 双轴评审**抓到的整改，逐条显式锚点 + 断言。

公共件一律 `from scope_lib import …`（03 单评审的账第 6 条：04 起的新脚本不再各抄一份）。
形状照 `apply-03e-review-fixups.py`：按 `(行号, 选择器片段)` 认人（同一行可能落两条规则）、
锚点在该规则体内**恰好命中一次**、**可重跑**（锚点没了但新形态已在 ⇒ 记为"已应用"）。

  0   **`apply-04a` 写坏的一个字节**（双轴评审两轴都抓到，Standards 硬违规 / Spec (c)1）：
      `index.html` 的 `.code-gutter-line.code-err-line::after` 上是
      `font-size: .62em;m; color: …` —— 多一个 `m`（CSS 非法声明，浏览器丢弃、两道门禁都看不见）。
      根因：`apply-04a` 把同一处**列了两次**（`FONT_BY_LINE[2282]` 的 `8px → .62em` 与
      `DERIVE[3]` 的 `font-size: 8px; → font-size: .62em;`），两条编辑区间**重叠**，后一条按
      旧下标多吃一个字符。本支负责把这一处修回；`apply-04a` 已就地更正（去掉重复项 +
      新增"编辑区间不许重叠"断言 + docstring 记这一笔），账见票尾。

  A1  **`.code-pane-title` 从 `--fs-block`(16) 降到 `--fs-note`(13)**（本单自查，人眼看图抓到）：
      它是**面板内的行首小标签**——240px 的树面板里那一行还同排挤着「新建文件 / 新建文件夹 /
      选择文件夹…」三个按钮，16px 把「文件」挤成两行、白吃一行高度（`04-after-dark-code-*`
      与 `04-before-dark-code-*` 两张图并排看得出：改前 11px 也折行，改后折得更胖）。
      口径 = 03 单 `.res-toolbar-title` 的先例（"面板内的行首小标签，升 16 会把密度拉爆"）。
      **`.code-compile-head strong`（底部五面板的块标题）留在 16**：它独占一行、右侧只有一个
      「收起」按钮，是这一页主流里唯一的 16 落点。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04d-review-fixups.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04d-review-fixups.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import PAGE, ROOT, read_page, rules_of, write_page  # noqa: E402

# 行号（探针/守卫口径 = 规则起点前那一行的行号）→ [(选择器里必须出现的片段, 锚点, 换成, 理由)]
FIX: dict[int, list[tuple[str, str, str, str]]] = {
    2282: [(".code-err-line::after", "font-size: .62em;m; color: var(--danger);",
            "font-size: .62em; color: var(--danger);",
            "0  apply-04a 的编辑区间重叠留下的那个 `m`（非法声明）")],
    2117: [(".code-pane-title", "font-size: var(--fs-block);", "font-size: var(--fs-note);",
            "A1 面板内的行首小标签：16 在 240px 树面板里把「文件」挤成两行（同 03 单 .res-toolbar-title 先例）")],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    edits: list[tuple[int, int, str, str]] = []
    problems: list[str] = []
    hit: dict[tuple[int, str], int] = {}
    done: list[str] = []
    for line, sel, b0, b1 in rules_of(text):
        if line not in FIX:
            continue
        body = text[b0:b1]
        for frag, old, new, why in FIX[line]:
            if frag not in sel:
                continue                      # 同一行可能有好几条规则，按选择器片段认人
            # **可重跑**：锚点没了但新形态已在 ⇒ 这条已经改过了
            if old not in body and new in body:
                hit[(line, old)] = 1
                done.append(f"L{line}  {sel[:60]}  →  已应用（{why}）")
                continue
            hit[(line, old)] = hit.get((line, old), 0) + 1
            if body.count(old) != 1:
                problems.append(f"L{line} {sel[:60]}: 锚点 {old!r} 出现 {body.count(old)} 次（期望 1）")
                continue
            at = b0 + body.index(old)
            edits.append((at, at + len(old), new, f"L{line}  {sel.split('*/')[-1].strip()[:46]}  →  {why}"))

    print(f"== 04 整改：{len(edits)} 处待改 / {len(done)} 处已应用 ==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改    " + note)
    for note in done:
        print("  跳过  " + note)

    for line, fixes in sorted(FIX.items()):
        for frag, old, _, why in fixes:
            if hit.get((line, old), 0) != 1:
                problems.append(f"L{line}（{frag}）的锚点 {old!r} 命中 {hit.get((line, old), 0)} 次（期望 1）")

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # 复扫：这批锚点都不该再原样出现
    for line, sel, b0, b1 in rules_of(text):
        if line not in FIX:
            continue
        body = text[b0:b1]
        for frag, old, new, _ in FIX[line]:
            if frag in sel and old in body and old not in new:
                print(f"\n✗ 复扫：L{line} 的 {old!r} 还在（没写盘）")
                return 1

    if not args.write:
        print("\n（--dry-run：没有写盘；复扫通过 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；{len(edits)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
