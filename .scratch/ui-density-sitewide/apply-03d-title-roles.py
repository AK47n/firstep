r"""工单 03 施工脚本（四）：**四级可辨**那一档（小节标题 16）补两处。

生成页 12 张步骤卡的标题是 `<h2>`（全局 `.card h2` = `--fs-page` 20，01 单已做），
说明行是 `.card-purpose`（`--fs-note` 13，01 单已做），正文层本单已归 `--fs-body`；
**缺的是"小节标题"那一档（16）**——这一页没有 `<h3>`，真正给一整块命名的是这几处：

  · `.score-panel .title`（评分点面板）/ `.group-card .title`（功能组卡）——本支要补
  · `.pin-subtitle`（引脚卡的分区名）/ `.gen-recent-title`（最近生成）——本单已在
    `apply-03a` 里换成 `--fs-block`

锚点仍是"该声明在该规则体内恰好命中一次"；改完复扫：这两条规则必须已有 `font-size: var(--fs-block)`。
替换串不含换行。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03d-title-roles.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03d-title-roles.py --write
"""

from __future__ import annotations

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

# 行号 → [(锚点原文, 换成, 理由)]
FIX: dict[int, list[tuple[str, str, str]]] = {
    824: [("font-weight: 600;", "font-size: var(--fs-block); font-weight: 600;",
           "评分点面板标题 → 小节标题那一档（16）")],
    834: [("font-weight: 600;", "font-size: var(--fs-block); font-weight: 600;",
           "功能组卡标题 → 小节标题那一档（16）")],
}


def rules_of(text: str) -> list[tuple[int, str, int, int]]:
    import re
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
    hit: dict[tuple[int, str], int] = {}
    for line, sel, b0, b1 in rules_of(text):
        if line not in FIX:
            continue
        body = text[b0:b1]
        for old, new, why in FIX[line]:
            if old not in body:
                continue
            hit[(line, old)] = hit.get((line, old), 0) + 1
            if body.count(old) != 1:
                print(f"✗ L{line}: 锚点 {old!r} 出现 {body.count(old)} 次（期望 1）")
                return 1
            at = b0 + body.index(old)
            edits.append((at, at + len(old), new, f"L{line}  {sel}  →  {why}"))

    print(f"== 小节标题那一档：{len(edits)} 处 ==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)

    for line, fixes in sorted(FIX.items()):
        for old, _, _ in fixes:
            if hit.get((line, old), 0) != 1:
                print(f"\n== **停下**：L{line} 的锚点 {old!r} 命中 {hit.get((line, old), 0)} 次 "
                      f"（期望 1），一个字节都没写 ==")
                return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    for line, sel, b0, b1 in rules_of(text):
        if line in FIX and "font-size: var(--fs-block);" not in text[b0:b1]:
            print(f"✗ 复扫：L{line} 改完仍没有 --fs-block（没写盘）")
            return 1

    if not args.write:
        print("\n（--dry-run：没有写盘；复扫两处都已是 --fs-block ✅；确认无误后加 --write）")
        return 0
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；{len(edits)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
