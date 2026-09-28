r"""工单 05 施工脚本（一）：`settings` 作用域的字号 → `--fs-*`（10 处）。

做法照 04a：**逐条显式锚点**（行号 → (期望原值, 令牌, 角色理由)），替换在该行那条**规则块**的
声明体里做，断言锚点**恰好命中一次**；命中数不对就整支停手。改完**回头复扫**：本作用域剩下的
裸 px 字号必须是 0。**编辑区间不许重叠**（04 单的账第 9 条：apply-04a 第一版就是在这里
两条编辑互相啃出一个 `;m;`，而两道门禁全绿）。

角色判定（口径 = spec 的「字号角色表」+ 04 单落地的「mono 走代码档 / 散文条目走正文档」）：

  · `.env-row`（体检行主字：名称 + 详情）→ `--fs-body`(14)：它是这一页要读的条目正文；
  · `.materials-batch-row`（批次勾选行主字）→ `--fs-body`(14)；
  · `.env-badge`（圆徽章里的字形）/ `.env-jump`（缺失项跳转小胶囊）→ `--fs-tag`(12)；
  · `.recent-wf-summary`（mono 仪表盘块）/ `.materials-batch-meta`（体量元信息）/
    `.materials-part-row`（分卷明细，mono）/ `.delivery-zip`（产物路径，mono）→ `--fs-note`(13)；
  · `.delivery-incomplete`（交付状态提示行）→ `--fs-note`(13)；
  · **`.settings-section`（卡内小节标题）→ `--fs-block`(16)**：它给一整块命名（"连接" / "计费" /
    "Keil UV4（stm32）/ gmake（mspm0）"），12px muted 在那个位置弱到看不出分组——而本单的验收
    就是"分组靠大间距 + **分组标题**表达"。口径同样板 `#tab-hwcheck .card h3`（`.card h3` 那一档）；
    配色也跟着改成正文色（"小节标题（正文色 + 加粗，不是灰字）"是 03 单立的账），在
    `apply-05d-new-rules.py` 里改。

覆盖完整性：本表与**现算的**（`scope_lib.bare_fonts`，与守卫/探针同一处判据）裸字号明细逐条
对账，用 `Counter` 比重数。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05a-fonts.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05a-fonts.py --write
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import (PAGE, ROOT, bare_fonts, load_scopes, read_page,  # noqa: E402
                       rules_of, scope_of, write_page)

SCOPE = "settings"

# 行号 → (期望原值, 令牌, 角色理由)
FONT_BY_LINE: dict[int, tuple[str, str, str]] = {
    # ---- 环境体检（一键体检那段结果）----
    362: ("13", "var(--fs-body)", "体检行主字（名称 + 详情，读得下去的那一层）"),
    364: ("11", "var(--fs-tag)", "圆形体检徽章里的字形（✓ / ! / ✕）"),
    370: ("11", "var(--fs-tag)", "缺失项「去设置填」小胶囊按钮"),
    # ---- 最近 LLM 工作流（03 单从生成页挪回来的三处之一）----
    1484: ("12", "var(--fs-note)", "mono 只读仪表盘块（代码/数据面那一档）"),
    # ---- 资料库更新 ----
    1517: ("13", "var(--fs-body)", "批次勾选行主字"),
    1522: ("12", "var(--fs-note)", "批次体量元信息（右对齐小字）"),
    1528: ("12", "var(--fs-note)", "分卷明细行（mono）"),
    # ---- 设置页卡内小节标题 ----
    1584: ("12", "var(--fs-block)", "**卡内小节标题**（给一整块命名；配色在 05d 里改成正文色）"),
    # ---- 交付卡（设置页的交付结果行）----
    3180: ("13", "var(--fs-note)", "交付不完整提示行"),
    3181: ("12", "var(--fs-note)", "交付产物路径（mono）"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()
    problems: list[str] = []

    # ① 覆盖率对账：表里的 (行号, 取值) 与现算的裸字号逐条相等（比重数，不比集合）
    found = bare_fonts(text, SCOPE)
    expect = sorted((line, v[0]) for line, v in FONT_BY_LINE.items())
    if sorted(found) != expect:
        fc, ec = Counter(found), Counter(expect)
        for key in sorted(set(fc) | set(ec)):
            if fc[key] != ec[key]:
                side = "盘上有、表里没有" if fc[key] > ec[key] else "表里有、盘上没有"
                problems.append(f"{side}：L{key[0]} 的 {key[1]}px 出现 {fc[key]} 次（表里 {ec[key]} 次）")

    # ② 逐条锚点：键是 (行号, 取值)——不是行号（同一行可能落两条规则）
    table = {(line, v[0]): (v[1], v[2]) for line, v in FONT_BY_LINE.items()}
    if len(table) != len(FONT_BY_LINE):
        problems.append("表里有 (行号, 取值) 撞车——同一行两条规则写了同一个字号，得改按选择器区分")
    edits: list[tuple[int, int, str, str]] = []
    used: set[tuple[int, str]] = set()
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        body = text[b0:b1]
        for value in {v for ln, v in table if ln == line}:
            anchor = f"font-size: {value}px"
            if anchor not in body:
                continue
            if body.count(anchor) != 1:
                problems.append(f"L{line}: 规则体内 {anchor!r} 出现 {body.count(anchor)} 次（期望 1）")
                continue
            repl, why = table[(line, value)]
            used.add((line, value))
            at = b0 + body.index(anchor)
            edits.append((at, at + len(anchor), f"font-size: {repl}",
                          f"L{line}  {sel.split('*/')[-1].strip()[:44]:<44} {value}px → {repl:<16} {why}"))
    unused = sorted(set(table) - used)
    if unused:
        problems.append(f"表里这些锚点一次都没命中：{unused}")

    # ③ **编辑区间不许重叠**（04 单的账第 9 条：锚点唯一 ≠ 区间不打架）
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1!r} 与 [{s2},…) —— 两条编辑打在同一段字节上")

    print(f"== {SCOPE} 字号：{len(edits)} 处（表 {len(FONT_BY_LINE)} 条 / 盘上现算 {len(found)} 条）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ④ 复扫：改完该作用域的裸 px 字号必须是 0
    left = bare_fonts(text, SCOPE)
    if left:
        print("\n== **停下**：改完仍有裸字号（没写盘）==")
        for line, value in sorted(left):
            print(f"  ✗ L{line}: {value}px")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫 {SCOPE} 裸字号 = 0 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；复扫 {SCOPE} 裸字号 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
