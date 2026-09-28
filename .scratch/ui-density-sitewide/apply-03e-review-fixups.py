r"""工单 03 施工脚本（五）：**双轴评审的逐条整改**。

评审（Standards + Spec 两轴）抓到的、需要动产品文件的几条，逐条显式锚点 + 断言：

  A1  **分区表漏判**（Spec 轴 (a)1）：`.topic-preread*`（步骤 2 那块预读面板，渲染方 =
      `ui/generate-recommend.js` + `fx/topic-preread.js`）此前按类名前缀判给了**赛题库页**，
      于是三条裸字号一直在生成页上而腿③放行。谓词已按渲染方改（`\.topic-(?!preread)` +
      `\.topic-preread` 挂 generate），这三条在这里补上令牌。
  B1  `.rc-summary` 的边框要回来（Spec 轴 (c)1）：它是**语义状态条**（"硬判据全部就绪 /
      还有未就绪项"），属申报的例外①；上一支把它抹成 `border: none` 之后
      `.rc-summary.ok { border-color: … }` 成了**永不生效的死声明**。
  B2  悬停反馈（Spec 轴 (c)2）：`.score-panel` / `.group-card` 的整圈框换成 3px 左条之后，
      悬停那条 `border-color: var(--border-strong)` 与左条**同色** ⇒ 静默失效。
      改成悬停时左条转 accent —— "重点会跳"在这两处才成立。
  B3  四个发送胶囊（Spec 轴 (c)3）：13px 掉到 `--fs-tag`(12) 与 `.btn-task-dialog-adopt`
      同级，主次倒挂。改 `--fs-note`(13)：比紧凑胶囊高一档，也不往输入行里塞 16。
  C1  `.group-card.needs-choice`（Spec 轴 (c)2 后半）：琥珀告警由整圈框降成 3px 左条。
      例外①允许语义告警块留框 ⇒ 恢复整圈琥珀框 + 加粗左条。
  C2  `.recent-chip`（Standards 轴判断项 5）：与 `.fix-row` / `.pin-role` / `.sp-item`
      **形状同构的整宽可点行**，此前按"可点控件"留了整圈实框 —— 对齐成透明框（悬停染色照旧）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03e-review-fixups.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03e-review-fixups.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

# 行号（探针口径，= 规则起点的前一行号）→ [(选择器里必须出现的片段, 锚点, 换成, 理由)]
FIX: dict[int, list[tuple[str, str, str, str]]] = {
    859: [(".topic-preread", "font-size: 13px;", "font-size: var(--fs-body);",
           "A1 步骤 2 预读面板正文（归回生成页）")],
    866: [(".preread-group-title", "font-size: 12.5px;", "font-size: var(--fs-note);",
           "A1 面板内的分组小标题"),
          (".preread-group-title", "margin: 8px 0 2px;", "margin: var(--space-2) 0 2px;",
           "A1 同上：等于令牌的间距（腿②）")],
    870: [(".preread-quote", "font-size: 12px;", "font-size: var(--fs-note);",
           "A1 题面引用小字（与 .preread-slot-quote 同档）")],
    1726: [(".item:hover", "border-color: var(--border-strong);",
            "border-color: var(--border-strong); border-left-color: var(--accent);",
            "B2 悬停时左条转 accent（面板/功能组卡）")],
    720: [(".btn-task-dialog-send", "font-size: var(--fs-tag);", "font-size: var(--fs-note);",
           "B3 发送胶囊 12 → 13（主次不倒挂）")],
    826: [(".group-card.needs-choice", "border-color: var(--warn-border, rgba(210,153,34,.55));",
           "border: 1px solid var(--warn-border, rgba(210,153,34,.55)); "
           "border-left: 3px solid var(--warn);",
           "C1 语义告警块恢复整圈琥珀框（例外①）")],
    2814: [(".recent-chip", "border: 1px solid var(--border);", "border: 1px solid transparent;",
            "C2 整宽可点行与 .fix-row/.pin-role 对齐")],
    3214: [(".rc-summary", "border: none;", "border: 1px solid var(--border);",
            "B1 语义状态条恢复边框（并救活 .rc-summary.ok 的 border-color）")],
}


def rules_of(text: str) -> list[tuple[int, str, int, int]]:
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text, re.S):
        out.append((text.count("\n", 0, m.start()) + 1,
                    " ".join(m.group(1).split()), m.start(2), m.end(2)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

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
            # **可重跑**：锚点没了但新形态已在 ⇒ 这条已经改过了（本支第一版就跑过一遍）
            if old not in body and new in body:
                hit[(line, old)] = 1
                done.append(f"L{line}  {sel[:60]}  →  已应用（{why}）")
                continue
            hit[(line, old)] = hit.get((line, old), 0) + 1
            if body.count(old) != 1:
                problems.append(f"L{line} {sel[:60]}: 锚点 {old!r} 出现 {body.count(old)} 次（期望 1）")
                continue
            at = b0 + body.index(old)
            edits.append((at, at + len(old), new, f"L{line}  {sel[:72]}  →  {why}"))

    print(f"== 评审整改：{len(edits)} 处待改 / {len(done)} 处已应用 ==")
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
                print(f"✗ 复扫：L{line} 的 {old!r} 还在（没写盘）")
                return 1

    if not args.write:
        print("\n（--dry-run：没有写盘；复扫通过 ✅；确认无误后加 --write）")
        return 0
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；{len(edits)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
