r"""工单 06 施工脚本（四）：**行内警示标统一**（验收「健康 / 状态徽章统一」的那一半）。

这一趟的"统一"分三种落点，前两种**本来就已经是一处定义**（本支只把证据写清，不改）：
  ① 徽章一族：`.badge` 是全局基类，五个页面的具体徽章只声明**语义色对**
     （`--danger-dim/--danger`、`--warn-dim/--warn`、`--accent-dim/--accent`、
     `--info-dim/--info`、`--ok-dim/--ok-bright`）——pdf 的损坏 / 疑似重复、ref 的锚定三色、
     lib 的平台胶囊、topic 的年份 chip 全是这一套，**没有一处自造颜色**（本支用 grep 复核，
     见票尾「结论 · 徽章统一」那一段）；
  ② 统计条：`.lib-stats` / `.lib-stats-red` / `.lib-dangling-count` / `.ref-dangling-count`
     本来就是**同一条规则**（选择器组共用，见 `L932` 的注释）——库页与参考库的"红段计数"
     因此天然一致。
  ③ **行内 ⚠ 警示标**（`.dangling-tag` / `.ref-dangling-tag` / `.topic-warn`）：三处语义同族
     （悬空锚定 / 程序悬空），此前**字重不一致**（前者 400、后者 600）——本支把字重、字号
     （06a 已统一到 `--fs-tag`）、颜色（都是 `--danger`）三项对齐成同一套表达。
     **不合并成一条规则**：它们分属 `reference` 与 `topic` 两个作用域，合成一条会让分区表的
     归属（第一命中）与两条腿的射程一起变味——两处各自的声明**逐字相同**、并各自写明
     "这一族是同一套表达"。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06d-new-rules.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06d-new-rules.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import PAGE, ROOT, read_page, write_page  # noqa: E402

EOL = "\r\n"

# [(锚点（全文唯一、**单行**——锚点里不带换行，免得踩 CRLF/LF 的坑）, 换成, 过后的标记, 理由)]
MODIFY: list[tuple[str, str, str, str]] = [
    ("  .dangling-tag, .ref-dangling-tag { color: var(--danger); cursor: help; font-size: var(--fs-tag); margin-left: 2px; }",
     "  .dangling-tag, .ref-dangling-tag { color: var(--danger); cursor: help;\n"
     "    font-weight: 600; font-size: var(--fs-tag); margin-left: 2px; }\n"
     "  /* 这一族是**同一套表达**（工单 ui-density-sitewide/06）：悬空依赖 / 悬空锚定 /\n"
     "     程序悬空（`topic` 作用域的 `.topic-warn`）三处的**字号 / 字重 / 颜色逐字相同**\n"
     "     （`--fs-tag` / 600 / `--danger`），只有 `cursor` 按语义分（这里有 `title` 提示 → `help`；\n"
     "     赛题那条是纯标注 → `default`）。**不合并成一条规则**：它们分属两个作用域，\n"
     "     合并会动分区表的归属与两条腿的射程。 */",
     "font-weight: 600; font-size: var(--fs-tag); margin-left: 2px; }",
     "行内警示标统一：字重对齐 .topic-warn（600）＋把'同一套表达'写进注释"),
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

    print(f"== 06 新增 / 口径：{len(edits)} 处待改 / {len(done)} 处已应用 ==")
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

    if not args.write:
        print("\n（--dry-run：没有写盘；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；{len(edits)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
