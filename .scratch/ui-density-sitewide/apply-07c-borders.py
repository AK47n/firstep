r"""工单 07 施工脚本（三）：最后三页**内层完整描边**的逐条处置 + 一处口径（术语表条目）。

口径（spec「描边规矩」+ 03–06 落地的例外 ①–⑥）：**一屏一层完整描边**。
家底：**整圈完整框 14 处**（master 8 / guide 5 / changelog 1）。逐条处置：**改 5 条、留 9 条**。

  改（内层盒去框，留淡底 / 虚线左条）：
    `.decision`（决策行块，卡内）→ 去框留 panel-2 淡底
    `.distill-progress`（提炼进度区，卡内）→ 去框留 panel-2 淡底
    `.master-file-pre`（弹层里的文件内容阅读面）→ 去框留 `--bg` 淡底（同 06 单 `.topic-detail-problem`）
    `.guide-empty-hint`（空态）→ 虚线整圈 → **3px 虚线左条**（照 03 单的空态口径）
    `.guide-note`（提醒框）→ 去掉虚线整圈，**留它那条 3px accent 左条**
  留（逐条写理由）：
    ② 可点控件 / 形状：`.stepper .step .dot`（圆点）/ `.master-file-btn`（关键文件行）/
       `.guide-tab`（子页签胶囊）/ `.rel-tag.tag-other`（语义标签）
    ① 语义告警：`.prog-badge`（补问徽标）
    ③ 弹层外壳：（本三页没有单独的壳——`.master-modal` 复用 `.ref-files-modal`，算在 06 单那边）
    ④ 非框：`.master-health-pill`（`1px solid transparent`，悬停才染色）
    ⑤ 表格网格：`.guide-table th` / `.guide-table td`
    ⑥ 顶层块：`.release-card`（版本卡：**它不是"卡中卡"**——`#tab-changelog` 里没有外层 `.card`

  B. 一处口径（不算描边）：`.glossary-item` **给正文档字号**并让术语走 accent——
     它是"词条 + 一句话解释"，原先继承 `.card-details-body` 的 13px，与正文糊在一起；
     票面要"术语表条目与正文区分得开"。（术语表在**生成页侧栏**也渲染一份：
     `.gen-sidebar .glossary-card`——**跨页共享**，账里点名。）

完整性证明（照 06c 的加严版）：对账用 `Counter` 比 **(作用域, 行号, 取值)** 的重数、
按 `(作用域, 行号, 选择器片段)` 认人、口径用 `scope_lib.full_borders`；替换串不含换行。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-07c-borders.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-07c-borders.py --write
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

EOL = "\r\n"
SCOPES = ["master", "guide", "changelog"]
FLAT = "border: none;"
DASHED_LEFT = "border: none; border-left: 3px dashed var(--border-strong);"

# (作用域, 行号) → [(选择器片段, 取值（不含分号）, 换成, 理由)]
FIX: dict[tuple[str, int], list[tuple[str, str, str, str]]] = {
    ("master", 1420): [(".decision", "1px solid var(--border)", FLAT,
                        "决策行块：去框留 panel-2 淡底（它在一张卡里）")],
    ("master", 1457): [(".distill-progress", "1px solid var(--border)", FLAT,
                        "提炼进度区：去框留 panel-2 淡底（卡内的一块）")],
    ("master", 1943): [(".master-file-pre", "1px solid var(--border)", FLAT,
                        "弹层里的文件内容阅读面：去框留 --bg 淡底（弹层才是那一层）")],
    ("guide", 2971): [(".guide-empty-hint", "1px dashed var(--border)", DASHED_LEFT,
                       "空态：虚线整圈 → 3px 虚线左条（照 03 单空态口径）")],
    ("guide", 2983): [(".guide-note", "1px dashed var(--border)", FLAT,
                       "提醒框：去掉虚线整圈，留它自己那条 3px accent 左条")],
}

# (作用域, 行号) → (选择器片段, 取值, 保留理由)
KEEP: dict[tuple[str, int], tuple[str, str, str]] = {
    ("master", 1463): (".stepper .step .dot", "2px solid var(--border)", "② 形状：stepper 圆点"),
    ("master", 1478): (".prog-badge", "1px solid var(--warn-border)", "① 语义告警徽章（补问）"),
    ("master", 1845): (".rel-tag.tag-other", "1px solid var(--border)", "② 语义标签胶囊"),
    ("master", 1903): (".master-file-btn", "1px solid var(--border)", "② 可点控件（关键文件行）"),
    ("master", 1909): (".master-health-pill", "1px solid transparent",
                       "④ 非框（透明，悬停才染色）"),
    ("guide", 2960): (".guide-tab", "1px solid var(--border)", "② 可点胶囊（子页签）"),
    ("guide", 2990): (".guide-table th", "1px solid var(--border)", "⑤ 表格网格"),
    ("guide", 2992): (".guide-table td", "1px solid var(--border)", "⑤ 表格网格"),
    ("changelog", 1815): (".release-card", "1px solid var(--border)",
                          "⑥ 顶层块：`#tab-changelog` 里没有外层 `.card`，这张卡就是那一层"),
}

# [(锚点（单行、全文唯一）, 换成, 过后的标记, 理由)] —— 口径那一处
MODIFY: list[tuple[str, str, str, str]] = [
    ("  .glossary-card .glossary-item { margin-top: var(--space-2); line-height: 1.65; }",
     "  /* 词表条目（工单 ui-density-sitewide/07）：给**正文档**字号、术语走 accent——\n"
     "     它原先继承 `.card-details-body` 的 13px，与正文糊在一起（票面要「术语表条目与正文\n"
     "     区分得开」）。术语表在**生成页侧栏**也渲染一份（`.gen-sidebar .glossary-card`）。 */\n"
     "  .glossary-card .glossary-item { margin-top: var(--space-2); line-height: 1.65;\n"
     "    font-size: var(--fs-body); }\n"
     "  .glossary-card .glossary-item b { color: var(--accent); }",
     "font-size: var(--fs-body); }",
     "B 词表条目：正文档字号 + 术语走 accent（与正文区分得开）"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()
    problems: list[str] = []

    # ① 改前完整性：**连作用域、取值一起**对账（多重集 == FIX ∪ KEEP）
    before = [(sc, line, value) for sc in SCOPES for line, _, value in full_borders(text, sc)]
    before_counts = Counter(before)
    fix_pairs = Counter((sc, line, value) for (sc, line), rows in FIX.items() for _, value, _, _ in rows)
    keep_pairs = Counter((sc, line, value) for (sc, line), (_, value, _) in KEEP.items())
    declared = fix_pairs + keep_pairs
    if before_counts != declared:
        problems.append("改前的整圈完整框 (作用域, 行号, 取值) 重数与申报不符："
                        f"多出 {sorted((before_counts - declared).elements())}、"
                        f"少了 {sorted((declared - before_counts).elements())}")

    # ② 逐条锚点
    border_edits: list[tuple[int, int, str, str]] = []
    modify_edits: list[tuple[int, int, str, str]] = []
    hit: Counter = Counter()
    for line, sel, b0, b1 in rules_of(text):
        sc = scope_of(sel, scopes)
        if (sc, line) not in FIX:
            continue
        body = text[b0:b1]
        for frag, value, new, why in FIX[(sc, line)]:
            if frag not in sel:
                continue
            anchor = f"border: {value};"
            hit[(sc, line, value)] += 1
            if body.count(anchor) != 1:
                problems.append(f"{sc} L{line} {frag}: 锚点 {anchor!r} 出现 {body.count(anchor)} 次（期望 1）")
                continue
            at = b0 + body.index(anchor)
            border_edits.append((at, at + len(anchor), new,
                                 f"{sc:<9} L{line}  {sel.split('*/')[-1].strip()[:34]:<34} → {why}"))
    for (sc, line), rows in sorted(FIX.items()):
        for frag, value, _, _ in rows:
            if hit[(sc, line, value)] != 1:
                problems.append(f"{sc} L{line}（{frag}）的锚点命中 {hit[(sc, line, value)]} 次（期望 1）")

    # ③ 口径那一处
    done: list[str] = []
    for old, new, marker, why in MODIFY:
        if old not in text:
            if marker in text:
                done.append(f"已应用（{why}）")
            else:
                problems.append(f"锚点 {old[:60]!r}… 没命中，新形态也不在")
            continue
        if text.count(old) != 1:
            problems.append(f"锚点 {old[:60]!r}… 命中 {text.count(old)} 次（期望 1）")
            continue
        at = text.index(old)
        modify_edits.append((at, at + len(old), new.replace("\r\n", "\n").replace("\n", EOL), why))

    # ④ 编辑区间不许重叠（04 账第 9 条）——两类编辑一起查
    edits = border_edits + modify_edits
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== 三页描边 / 口径：改 {len(edits)} 处（{len(FIX)} 条去框 + {len(done)} 处已应用）"
          f" / 保留 {len(KEEP)} 条（改前整圈完整框 {len(before)} 处）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改  " + note)
    for (sc, line) in sorted(KEEP):
        print(f"  留  {sc:<9} L{line}  {KEEP[(sc, line)][0]}  {KEEP[(sc, line)][2]}")
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(border_edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ⑤ 改后复扫：只剩 KEEP（取值逐字相同）
    #    ⚠ **必须排在插入行的口径那一步之前**：`MODIFY` 会插入 5 行（注释 + 拆开的规则），
    #    先插进去会让下面这张**按行号对账**的表整体错位（本支第一版就这么栽的——
    #    报出一串"+5 行"的假不符，当场停手才没写坏）。
    after_counts = Counter((sc, line, value) for sc in SCOPES for line, _, value in full_borders(text, sc))
    if after_counts != keep_pairs:
        print("\n== **停下**：改后剩下的整圈完整框与申报不符（没写盘）==")
        print(f"  多出 {sorted((after_counts - keep_pairs).elements())}")
        print(f"  少了 {sorted((keep_pairs - after_counts).elements())}")
        return 1

    # ⑥ 口径那一处（会插行，放在描边对账之后）
    for start, end, new, _ in sorted(modify_edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]
    for old, new, marker, why in MODIFY:      # 双向复扫（06 账第 9 条：别只比一个片段）
        if old in text or marker not in text:
            print(f"\n== **停下**：复扫失败（{why}）（没写盘）==")
            return 1

    if not args.write or args.dry_run:      # --dry-run 说了算
        print(f"\n（--dry-run：没有写盘。复扫三页整圈完整框 = {sum(after_counts.values())} 处，"
              f"全部在申报的例外里、取值逐字未变 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：改 {len(edits)} 处；"
          f"复扫整圈完整框 = {sum(after_counts.values())} 处（全在申报的例外里）✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
