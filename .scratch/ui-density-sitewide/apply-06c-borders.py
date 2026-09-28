r"""工单 06 施工脚本（三）：五个素材/库页作用域**内层完整描边**的逐条处置。

口径（spec「描边规矩」+ 04 单补的三类例外 ④⑤⑥）：**一屏一层完整描边**。

**这一趟的家底（两个口径）**：探针"border 声明"口径 24 处（票面那个数），**整圈完整框 20 处**：
library 12 / reference 3 / pdf 0 / md 1 / topic 4。逐条处置：**改 7 条、留 13 条**。

  改（内层盒去框，留淡底；`add-section` 给左条——它是"三块表单的分组"）：
    `.mi-reason`（推荐理由块）/ `.mi-plat`（平台小卡）/ `.lib-edit-old`（"当前简介"原文块）/
    `.add-section`（"添加模块"的三个分区块）/ `.ref-scroll`（步骤 4 参考资料滚动清单）/
    `.md-preview-body`（md 预览内容面）/ `.topic-detail-problem`（题面全文阅读面）
  留（逐条写理由）：
    ② 可点控件 / 卡片：`.module-card`（生成页模块池 + 检测页器件网格共用）/ `.mc-info` /
       `.lib-chip` / `.topic-card` / `.topic-year` / `.ref-files-filter`（输入框）
    ① 语义告警：`.mc-offtag`（平台不兼容）/ `.module-info-off`
    ③ 弹层外壳：`.module-info-modal` / `.lib-edit-modal` / `.ref-files-modal`（**跨页共享**：6 个
       `ui/*.js` 都在用它）
    ⑤ 文档渲染 / 表格网格：`.mi-pins th, td`（引脚表）/ `.topic-page img`（扫描件图片框）

完整性证明（照 05c 的加严版）：对账用 `Counter` 比 **(作用域, 行号, 取值)** 的**重数**、
按 `(作用域, 行号, 选择器片段)` 认人、口径用 `scope_lib.full_borders`；替换串不含换行。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06c-borders.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06c-borders.py --write
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

SCOPES = ["library", "reference", "pdf", "md", "topic"]
FLAT = "border: none;"
LEFT_BAR = "border: none; border-left: 3px solid var(--border-strong);"

# (作用域, 行号) → [(选择器片段, 取值（不含分号）, 换成, 理由)]
FIX: dict[tuple[str, int], list[tuple[str, str, str, str]]] = {
    ("library", 499): [(".mi-reason", "1px solid var(--border)", FLAT,
                        "推荐理由块：去框留 ok-dim 淡底（弹层才是那一层）")],
    ("library", 508): [(".mi-plat", "1px solid var(--border)", FLAT,
                        "平台小卡：去框留 panel-2 淡底（块之间已有 10px 间距）")],
    ("library", 547): [(".lib-edit-old", "1px solid var(--border)", FLAT,
                        "「当前简介」原文块：去框留 panel-2 淡底")],
    ("library", 565): [(".add-section", "1px solid var(--border)", LEFT_BAR,
                        "「添加模块」三个分区块：整圈 → 左条 + 淡底（照 03 单 `.card-group` 先例）")],
    ("reference", 862): [(".ref-scroll", "1px solid var(--border)", FLAT,
                          "步骤 4 参考资料滚动清单：去框留 panel-2 淡底（它在一张步卡里）")],
    ("md", 1021): [(".md-preview-body", "1px solid var(--border)", FLAT,
                    "md 预览内容面：去框留 code-bg 淡底（文档面照样板 `pre.result`）")],
    ("topic", 1876): [(".topic-detail-problem", "1px solid var(--border)", FLAT,
                       "题面全文阅读面：去框留 --bg 淡底（弹层才是那一层）")],
}

# (作用域, 行号) → (选择器片段, 取值, 保留理由)
KEEP: dict[tuple[str, int], tuple[str, str, str]] = {
    ("library", 442): (".module-card", "1px solid var(--border)",
                       "② 可点卡片（生成页模块池 + 检测页器件网格共用，形态必须一致）"),
    ("library", 452): (".mc-offtag", "1px solid var(--warn-border)", "① 语义告警胶囊（平台不兼容）"),
    ("library", 468): (".mc-info", "1px solid var(--border)", "② 小按钮（「说明」）"),
    ("library", 479): (".module-info-modal", "1px solid var(--border)", "③ 弹层外壳（模块详情）"),
    ("library", 490): (".module-info-off", "1px solid var(--warn-border)", "① 语义告警块"),
    ("library", 531): (".mi-pins th, .mi-pins td", "1px solid var(--border)",
                       "⑤ 表格网格（引脚表；文档/数据渲染那一类）"),
    ("library", 540): (".lib-edit-modal", "1px solid var(--border)", "③ 弹层外壳（改简介 / 编辑模块）"),
    ("library", 925): (".lib-chip", "1px solid var(--border)", "② 可点过滤 chip"),
    ("reference", 1503): (".ref-files-modal", "1px solid var(--border)",
                          "③ 弹层外壳（**跨页共享**：master / md / pdf / topic / code 都在用）"),
    ("reference", 1554): (".ref-files-filter", "1px solid var(--border)", "② 输入框"),
    ("topic", 1842): (".topic-card", "1px solid var(--border)", "② 可点卡片"),
    ("topic", 1853): (".topic-year", "1px solid var(--border)", "② 标签胶囊（年份 chip）"),
    ("topic", 1886): (".topic-page img", "1px solid var(--border)", "⑤ 文档渲染（扫描件图片框）"),
}


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

    # ② 逐条锚点：按 (作用域, 行号, 选择器片段) 认人
    edits: list[tuple[int, int, str, str]] = []
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
            edits.append((at, at + len(anchor), new,
                          f"{sc:<9} L{line}  {sel.split('*/')[-1].strip()[:38]:<38} → {why}"))
    for (sc, line), rows in sorted(FIX.items()):
        for frag, value, _, _ in rows:
            if hit[(sc, line, value)] != 1:
                problems.append(f"{sc} L{line}（{frag}）的锚点 {value!r} 命中 {hit[(sc, line, value)]} 次（期望 1）")

    # ③ 编辑区间不许重叠（04 账第 9 条）
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== 五页描边：改 {len(edits)} 条 / 保留 {len(KEEP)} 条（改前整圈完整框 {len(before)} 处）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改  " + note)
    for (sc, line) in sorted(KEEP):
        print(f"  留  {sc:<9} L{line}  {KEEP[(sc, line)][0]}  {KEEP[(sc, line)][2]}")
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ④ 改后复扫：只剩 KEEP，且取值逐字相同（同样比重数）
    after = [(sc, line, value) for sc in SCOPES for line, _, value in full_borders(text, sc)]
    after_counts = Counter(after)
    if after_counts != keep_pairs:
        print("\n== **停下**：改后剩下的整圈完整框与申报不符（没写盘）==")
        print(f"  多出 {sorted((after_counts - keep_pairs).elements())}")
        print(f"  少了 {sorted((keep_pairs - after_counts).elements())}")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫五页整圈完整框 = {sum(after_counts.values())} 处，"
              f"全部在申报的例外里、取值逐字未变 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：改 {len(edits)} 条；"
          f"复扫整圈完整框 = {sum(after_counts.values())} 处（全在申报的例外里）✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
