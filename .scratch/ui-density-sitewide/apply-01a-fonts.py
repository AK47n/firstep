r"""工单 01 施工脚本（一）：shell 作用域的字号 + 标记上的内联取值。

**为什么用脚本而不是一条条手改**：这一单要动 37 条规则 + 31 处内联 `style=`，
手改容易漏、也容易改错行；脚本把**每一处的目标令牌写成显式表**（按行号 + 期望原值），
跑的时候逐条断言"这一行确实还是那个值"，改完打印逐行 diff 摘要。
—— 这与仓库既有做法一致（`.scratch/*/apply-*.py`）。

**判据边界**：本脚本只做两件事：
1. 把 shell 作用域规则里的 `font-size: <n>px` 换成角色表里的 `var(--fs-*)`（**就地替换**，
   不新增覆盖层——上一轮 01 的账：叠覆盖层会让同一条规则两处说它多大）；
2. 把标记上内联 `style=` 里的裸字号换成令牌（少数几处直接**删掉**——`class="muted"`
   已经说了它的角色，内联那句是第二处说同一件事）。

间距令牌化与拆框不在本脚本（见 apply-01b）。

用法（先 --dry-run 看清要动哪些行）：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-01a-fonts.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-01a-fonts.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

# --- 一、shell 作用域规则的字号：行号 → (期望原值, 目标令牌) ---------------------
# 角色判定（口径见 spec 的「字号角色表」）：按**这条规则在讲什么**判，不按现值换算。
FONT_BY_LINE: dict[int, tuple[str, str]] = {
    232: ("20", "--fs-page"),      # header h1：站名
    241: ("11", "--fs-tag"),       # 站名旁的 EN 小标
    275: ("15", "--fs-block"),     # 主题切换按钮（与导航胶囊同高）
    308: ("16", "--fs-page"),      # .card h2：**卡片标题升到页标题那一档**（本轮最大的观感变化）
    309: ("13", "--fs-block"),     # .card h3：小节标题升格（原 13px 灰字，比正文还弱）
    310: ("14", "--fs-body"),      # label
    319: ("14", "--fs-body"),      # textarea
    354: ("12", "--fs-note"),      # .muted：说明
    355: ("14", "--fs-body"),      # .error
    370: ("14", "--fs-body"),      # .banner
    372: ("14", "--fs-body"),      # .welcome-card
    374: ("15", "--fs-block"),     # .welcome-title
    425: ("12", "--fs-note"),      # .selected-scroll .desc：说明
    567: ("13", "--fs-note"),      # #compile-banner
    604: ("12.5", "--fs-note"),    # .rec-covered-note：信息性说明
    623: ("11", "--fs-tag"),       # .mod-info-btn：极小字按钮
    872: ("14", "--fs-body"),      # .warn-box
    889: ("13", "--fs-body"),      # table：表格 = 正文
    897: ("12", "--fs-tag"),       # table td button：行内紧凑按钮
    1018: ("12", "--fs-note"),     # pre.result：只读结果块
    1363: ("12", "--fs-tag"),      # #btn-score-export
    1382: ("11", "--fs-tag"),      # .file-row-x：行内小叉
    1421: ("13", "--fs-note"),      # .ai-action-banner
    1554: ("13", "--fs-body"),     # input[type=file]
    1558: ("13", "--fs-body"),     # input[type=file]::file-selector-button
    1641: ("11", "--fs-tag"),      # .role-type：mono 小标
    1672: ("12", "--fs-note"),      # #pin-board-caption：图注
    1785: ("11", "--fs-tag"),      # .rel-tag
    1885: ("12", "--fs-body"),     # .import-platform-field label：字段标签
    1966: ("12", "--fs-tag"),      # #code-bottom-panels：底部面板页签条
    2038: ("11.5", "--fs-tag"),    # #btn-code-ai-send
    2804: ("12", "--fs-tag"),      # #btn-recent-refresh
    2830: ("11", "--fs-tag"),      # .card-step-status：状态徽章
    2851: ("11", "--fs-note"),     # .card-group-title：分组标题（弱化的次级标题）
    2950: ("12.5", "--fs-note"),   # .card-purpose / .handoff-note：人话副标题
    3239: ("11", "--fs-tag"),      # #gen-progress .gp-text
    3304: ("13", "--fs-note"),     # .card-collapse：折叠小按钮
}

# --- 二、标记上的内联 style：行号 → (期望原串, 替换成) ---------------------------
# `None` = 连整个属性一起删（`class="muted"` 已经说了它的角色，内联那句是第二处说同一件事）。
INLINE_BY_LINE: dict[int, tuple[str, str | None]] = {
    3620: ("font-size:12px", "font-size:var(--fs-tag)"),      # banner 里的「去设置」小按钮
    3625: ("font-size:13px", "font-size:var(--fs-note)"),     # 草稿说明条
    3627: ("font-size:12px", "font-size:var(--fs-tag)"),      # 「清除草稿」按钮
    3731: ("font-size:12px", "font-size:var(--fs-note)"),     # summary：说明
    3831: (";font-size:11px", ""),                          # .muted 长说明（删内联，交给 .muted）
    3895: ("font-size:12px", "font-size:var(--fs-tag)"),      # 「复制路径」按钮
    4106: (";font-size:12px", ""),                            # .muted 说明
    4155: (";font-size:12px", ""),                            # .muted 说明
    4737: ("font-size:12px", "font-size:var(--fs-tag)"),      # banner 小按钮
    4739: ("font-size:12px", "font-size:var(--fs-note)"),     # 说明 span
    4750: ("font-size:13px", "font-size:var(--fs-note)"),     # 用量读数
    4754: ("font-size:13px", "font-size:var(--fs-note)"),     # 用量读数
    4758: ("font-size:12px", "font-size:var(--fs-tag)"),      # 「重置统计」按钮
    4786: ("font-size:12px", "font-size:var(--fs-note)"),     # 「计费时段」标注
    4787: ("font-size:12px", "font-size:var(--fs-body)"),     # radio label
    4788: ("font-size:12px", "font-size:var(--fs-body)"),     # radio label
    4799: ("font-size:12px", "font-size:var(--fs-note)"),     # summary
    4800: ("font-size:12px", "font-size:var(--fs-note)"),     # 价格参考块
    4827: ("font-size:12px;", ""),                          # .muted 说明（删掉这一句，交给 .muted）
    4842: (' style="font-size:12px"', None),                  # .muted 探针行
    4843: (' style="font-size:12px"', None),
    4849: (' style="font-size:12px"', None),
    4850: (' style="font-size:12px"', None),
    4854: (' style="font-size:12px"', None),
    4860: (' style="font-size:12px"', None),
    4861: (' style="font-size:12px"', None),
    4865: (' style="font-size:12px"', None),
    4909: ("font-size:12px", "font-size:var(--fs-body)"),     # label（长说明也是 label）
    4931: ("font-size:12px", "font-size:var(--fs-body)"),     # label
    4934: ("font-size:12px", "font-size:var(--fs-body)"),     # label
    4936: ("font-size:12px", "font-size:var(--fs-body)"),     # select 控件
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # **逐字节保真**：`read_text()` 默认走 universal newlines（把 CRLF 归一成 LF），
    # 写回时再还原——混合换行的文件会被整档改写。本工作树的换行本来就是混的
    # （见 `docs/agents/local-environment.md` 第 2 节），所以一律 `newline=""` 进出。
    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    changes: list[str] = []
    problems: list[str] = []

    # 规则块的行号 → 它在文本里的区间（**只解析一次**；改完再解析一遍会把 628 KB
    # 的样式块反复扫成 O(n²)——第一版就是这么跑了 2 分钟还没完）。
    # 替换按**偏移倒序**应用，前面的偏移因此不会失效。
    rules: dict[int, tuple[int, int]] = {}
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text, re.S):
        rules[text.count("\n", 0, m.start()) + 1] = (m.start(2), m.end(2))

    edits: list[tuple[int, int, str, str]] = []  # (start, end, 新文本, 说明)
    for line_no, (old_value, token) in sorted(FONT_BY_LINE.items()):
        if line_no not in rules:
            problems.append(f"L{line_no}: 这里没有规则块 —— 行号变了，停手核对")
            continue
        body_start, body_end = rules[line_no]
        body = text[body_start:body_end]
        anchor = f"font-size: {old_value}px"
        if body.count(anchor) != 1:
            problems.append(f"L{line_no}: 规则体内 {anchor!r} 出现 {body.count(anchor)} 次（期望 1）")
            continue
        at = body_start + body.index(anchor)
        edits.append((at, at + len(anchor), f"font-size: var({token})",
                      f"L{line_no}: {anchor} → font-size: var({token})"))

    for start, end, new, note in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]
        changes.append(note)

    lines = text.split("\n")
    for line_no, (old, new) in sorted(INLINE_BY_LINE.items()):
        idx = line_no - 1
        line = lines[idx]
        if line.count(old) != 1:
            problems.append(f"L{line_no}: 内联锚 {old!r} 出现 {line.count(old)} 次（期望 1）")
            continue
        lines[idx] = line.replace(old, new or "")
        changes.append(f"L{line_no}: {old!r} → {new!r}")

    print(f"== 计划改动 {len(changes)} 处 ==")
    for c in changes:
        print("  " + c)
    if problems:
        print("\n== **停下**：以下锚点对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    if not args.write:
        print("\n（--dry-run：没有写盘。确认无误后加 --write）")
        return 0

    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines))
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
