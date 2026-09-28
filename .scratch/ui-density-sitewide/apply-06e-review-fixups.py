r"""工单 06 施工脚本（五）：**双轴评审**抓到的整改（逐条锚点 + 断言 + 可重跑）。

  A. **`.md-row-file` 从 `--fs-note`(13) 改回 `--fs-tag`(12)**（Spec 轴 (c) 层的观感那条）：
     它是列表行的**第二行小字**（文件名），主行是中文标题（全局 `table` 的 `--fs-body` 14）——
     13 与 14 只差 1px，两行并平、层级反而糊了；改 12 之后"主行 14 / 次行 12"才分得开，
     也与 spec 拍板的"11 → `--fs-tag`"一致（`11` 那一档本来就是"徽章 / 极小字"）。
  B. **`.lib-dangling-count` 并入统计条那条共享规则**（Spec 轴 (c)③）：它此前是一条**独立规则**
     （`color` + `font-weight` 与共享组逐字相同，但没有 `cursor` 语义）。
     本支把它并进选择器组、并**逐条说明它不可点**（`ui/library.js` 那句"点击详情确认"指的是
     点行进详情，不是点这个数字）——"统计条一处定义"这句话这才站得住。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06e-review-fixups.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06e-review-fixups.py --write
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
    ("  .md-row-file { font-size: var(--fs-note); color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }",
     "  .md-row-file { font-size: var(--fs-tag); color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }",
     ".md-row-file { font-size: var(--fs-tag);",
     "A 列表行第二行（文件名）回到 tag(12)：与主行 14 拉开两档，也与 spec 拍板一致"),
    ("  .lib-dangling-count { color: var(--danger); font-weight: 600; }",
     "  /* 统计条的「红段」（库页 / 参考库 / 悬空计数）——**一处定义**：可点的那两段带\n"
     "     `cursor: pointer` 与 `.on` 下划线态；`.lib-dangling-count` 只是**同一套表达的静态版**\n"
     "     （`ui/library.js` 里的「点击详情确认」指的是点行进详情，不是点这个数字）。 */\n"
     "  .lib-dangling-count { color: var(--danger); font-weight: 600; font-size: var(--fs-note); }",
     ".lib-dangling-count { color: var(--danger); font-weight: 600; font-size: var(--fs-note); }",
     "B 悬空计数并进「统计条一处定义」（并写明它不可点）"),
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

    print(f"== 06 整改：{len(edits)} 处待改 / {len(done)} 处已应用 ==")
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

    # 复扫：两条都得是新形态，且原来的旧形态不在（**不是只比一个 60 字符片段**——
    # 06d 那条"已应用"分支就是评审点名的唯一静默路径，本支不重复那个毛病）
    for old, new, marker, why in MODIFY:
        if old in text or marker not in text:
            print(f"\n== **停下**：复扫失败（{why}）—— {'旧形态还在' if old in text else '新形态不在'}（没写盘）==")
            return 1

    if not args.write:
        print("\n（--dry-run：没有写盘；复扫通过 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；{len(edits)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
