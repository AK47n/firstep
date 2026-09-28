r"""工单 07 施工脚本（四）：**双轴评审**抓到的整改（逐条锚点 + 双向复扫 + 可重跑）。

  A. **文件树改"只靠缩进"，不靠逐层描边**（票面点名，Spec 轴 (a)③）：
     `.master-tree .master-tree` 每层一条 `border-left: 1px` ——
     全框口径看不见它（单边），票面那句"层级靠缩进 + 留白，不靠逐层描边"因此没落地。
     改成 `border-left: none` + 缩进从 8px 提到 14px（层级照样看得见，但不再画线）。
  B. **stepper 的"主字"升到正文档**（Spec 轴 (a)④）：步骤名 13 → 14（`--fs-body`）——
     票面要"stepper 与检测页分组带同一套层级"，落点现在是"**步骤名 = 正文 14（这一块的主字）**、
     批进度 / 计时器 / 日志 = 说明 13、圆点字形 / 补问徽标 = 徽章 12"（分组带那一档 16 是
     "给一整块命名"的标题，stepper 是**进度指示**，不占标题那一档——这句话写进票尾）。
  C. **版本卡的整圈框去掉**（Spec 轴 (c)①）：`apply-07c` 把 `.release-card` 留框的理由写成
     "⑥ 顶层块：`#tab-changelog` 里没有外层 `.card`"——**那句是错的**，`index.html` 里
     `#tab-changelog` 确实有一层 `<div class="card">`。八张版本卡是"卡中卡"⇒ 按一屏一层去框，
     留 `panel-2` 淡底（同 06 单 `.mi-reason` / `.mi-plat` 的处置）。
  D. **术语表归属注释写错了**（Spec 轴 (b)）：`.glossary-card` 的**唯一渲染方是生成页侧栏**
     （`index.html` 的 `#glossary-card` 在 `.gen-sidebar` 里），CSS 注释却写"指南页也渲染一份"。
     按分区表它归 `guide`（前缀 `.glossary`），**但改了它等于改生成页**——注释与账都要说实话。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-07d-review-fixups.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-07d-review-fixups.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import PAGE, ROOT, read_page, write_page  # noqa: E402

EOL = "\r\n"

# [(锚点（**单行**、全文唯一）, 换成, 过后的标记, 理由)]
MODIFY: list[tuple[str, str, str, str]] = [
    # A：每层的引导线去掉，缩进加深
    ("  .master-tree .master-tree { border-left: 1px solid var(--border); padding-left: var(--space-2); }",
     "  .master-tree .master-tree { border-left: none; padding-left: 14px; }",
     ".master-tree .master-tree { border-left: none; padding-left: 14px; }",
     "A 文件树：去掉每层的引导线，层级靠缩进（票面点名「不靠逐层描边」）"),
    # B：步骤名升到正文档
    ("  .stepper .step { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-note);",
     "  .stepper .step { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-body);",
     ".stepper .step { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-body);",
     "B stepper 步骤名升到正文档（进度区的主字；落点见票尾）"),
    # C：版本卡去内框
    ("  .release-card { margin-bottom: var(--space-3); border: 1px solid var(--border);",
     "  .release-card { margin-bottom: var(--space-3); border: none;",
     ".release-card { margin-bottom: var(--space-3); border: none;",
     "C 版本卡去内框（它在外层 `.card` 里，是卡中卡——评审抓到原先的保留理由写错了）"),
    # D：术语表归属注释
    ("     区分得开」）。术语表在**生成页侧栏**也渲染一份（`.gen-sidebar .glossary-card`）。 */",
     "     区分得开」）。**它按分区表归 `guide`（前缀 `.glossary`），但唯一渲染方是生成页侧栏**\n"
     "     （`index.html` 的 `#glossary-card` 在 `.gen-sidebar` 里）——**改了它等于改生成页**，\n"
     "     账里点名（07 单评审抓到注释原先写反了）。 */",
     "账里点名（07 单评审抓到注释原先写反了）。 */",
     "D 术语表归属注释改成实话（渲染方是生成页侧栏）"),
    # E：去框之后收掉死过渡（03 账第 5 条的姊妹情形）
    ("  .pin-role, .decision, .ref-pick-row, .instance-mod, .score-panel {",
     "  .pin-role, .ref-pick-row, .instance-mod, .score-panel {",
     "  .pin-role, .ref-pick-row, .instance-mod, .score-panel {",
     "E 收掉 `.decision` 的死过渡（C 去框之后它既没边框也没 :hover——照 03 账第 5 条）"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    edits: list[tuple[int, int, str, str]] = []
    problems: list[str] = []
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
        edits.append((at, at + len(old), new.replace("\r\n", "\n").replace("\n", EOL), why))

    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== 07 整改：{len(edits)} 处待改 / {len(done)} 处已应用 ==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改    " + note)
    for note in done:
        print("  跳过  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # 双向复扫（06 账第 9 条：旧形态不在 + 新形态在）
    for old, new, marker, why in MODIFY:
        if old in text or marker not in text:
            print(f"\n== **停下**：复扫失败（{why}）（没写盘）==")
            return 1

    if not args.write or args.dry_run:      # --dry-run 说了算
        print("\n（--dry-run：没有写盘；双向复扫通过 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；{len(edits)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
