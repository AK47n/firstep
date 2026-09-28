r"""工单 07 施工脚本（一）：最后三页的字号 → `--fs-*`（36 处）。

三页：`master`（母版库 20）/ `guide`（使用指南 10）/ `changelog`（版本更新记录 6）。

做法照 04a / 05a / 06a：**逐条显式锚点**（(作用域, 行号) → (期望原值, 令牌, 角色理由)），
替换在该行那条**规则块**的声明体里做，断言锚点**恰好命中一次**；改完回头复扫：三个作用域的
裸 px 字号都必须是 0。**编辑区间不许重叠**（04 账第 9 条）。

角色判定（口径 = spec 的「字号角色表」+ 04/05/06 落地的本页口径）：

  · **正文 / 条目 / 要读的内容（含 mono 的代码、日志、文件内容）→ `--fs-body`(14)**：
    `.decision` 行主字、`.master-file-btn`、`.release-summary` / `.release-items li`、
    **使用指南的章节正文**（票面点名"章节正文 14px"：`.guide-chapter-intro` /
    `#tab-guide .guide-panel p, li` / `.guide-table`）。
  · **说明 / 元信息 / 状态 / 日志头 / 树行 / mono 档 → `--fs-note`(13)**：
    `.prog-batch` / `.prog-timers` / `.prog-log`（mono）/ `.prog-log-head` / `.prog-done`、
    `.master-tree-*`（树行与文件名，照 04 单代码页树的口径）、`.master-file-name` /
    `.master-file-pre`（mono 内容）、`.guide-empty-hint` / `.guide-note`、`.stepper .step`（步骤名）、
    `.release-date` / `.release-count`。
  · **徽章 / 胶囊 / 小按钮 / 小控件 / 箭头 → `--fs-tag`(12)**：
    `.prog-badge`、`.master-health-pill`、`.master-copy-btn`、`.decision button` /
    `input` / `select`（紧凑决策行里的小控件）、`.stepper .step .dot`（16px 圆点里的字形）、
    `.guide-tab`（子页签胶囊）、`.guide-jump`、`.release-card .collapse-ico`。
  · **标题那一级 → `--fs-block`(16)**：**`.guide-chapter-title`（16.5 → 16，票面点名"章节标题
    是小节标题那一级、正文色"；`16.5` 也是全站最后一处）、`.release-ver`（版本号胶囊 = 那张卡的
    标题那一档——票面要"版本号 / 日期 / 条目三级分明"）**。`.guide-head h2` 保持 `--fs-page`(20)。

覆盖完整性：本表与**现算的**（`scope_lib.bare_fonts`）三个作用域的裸字号明细逐条对账，
用 `Counter` 比重数。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-07a-fonts.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-07a-fonts.py --write
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

SCOPES = ["master", "guide", "changelog"]

# (作用域, 行号) → (期望原值, 令牌, 角色理由)
FONT: dict[tuple[str, int], tuple[str, str, str]] = {
    # ---------------- 母版库：提炼决策行 ----------------
    ("master", 1418): ("12", "var(--fs-tag)", "决策行小按钮"),
    ("master", 1419): ("12", "var(--fs-tag)", "决策行小输入框（与同行小按钮同档）"),
    ("master", 1420): ("14", "var(--fs-body)", "决策行主字（值不变）"),
    ("master", 1424): ("12", "var(--fs-tag)", "决策行小下拉"),
    # ---------------- 母版库：提炼进度（stepper + 批进度 + 计时器 + 日志）----------------
    ("master", 1461): ("12", "var(--fs-note)", "stepper 步骤名（进度指示，读得清那一档）"),
    ("master", 1463): ("11", "var(--fs-tag)", "16px 圆点里的字形（1/2/3/4）"),
    ("master", 1472): ("13", "var(--fs-note)", "批进度行（第 N/M 批 · 文件数）"),
    ("master", 1476): ("12", "var(--fs-note)", "双计时器（元信息）"),
    ("master", 1478): ("11", "var(--fs-tag)", "补问徽标"),
    ("master", 1481): ("12", "var(--fs-note)", "日志折叠头"),
    ("master", 1484): ("12", "var(--fs-note)", "mono 日志正文（代码档）"),
    ("master", 1494): ("13", "var(--fs-note)", "完成行（状态）"),
    # ---------------- 母版库：关键文件清单 / 文件树 / 内容箱 ----------------
    ("master", 1903): ("13", "var(--fs-body)", "关键文件清单按钮（条目主字）"),
    ("master", 1909): ("12", "var(--fs-tag)", "母版健康徽章"),
    ("master", 1920): ("12.5", "var(--fs-note)", "文件树目录行"),
    ("master", 1923): ("12.5", "var(--fs-note)", "文件树文件行"),
    ("master", 1928): ("12", "var(--fs-note)", "mono 文件名（代码档）"),
    ("master", 1932): ("12", "var(--fs-tag)", "复制小按钮"),
    ("master", 1942): ("12.5", "var(--fs-note)", "mono 关键文件名"),
    ("master", 1943): ("12.5", "var(--fs-note)", "mono 文件内容（代码档）"),
    # ---------------- 使用指南 ----------------
    ("guide", 2944): ("20", "var(--fs-page)", "页标题（值不变）"),
    ("guide", 2960): ("12.5", "var(--fs-tag)", "子页签胶囊（同 .revise-tab 协议）"),
    ("guide", 2971): ("12.5", "var(--fs-note)", "空态提示"),
    ("guide", 2974): ("16.5", "var(--fs-block)", "**章节标题**（票面点名：小节标题那一级；16.5 是全站最后一处）"),
    ("guide", 2977): ("13", "var(--fs-body)", "章节导语（票面点名：章节正文 14px）"),
    ("guide", 2978): ("14", "var(--fs-body)", "章节内小节标题（值不变，正文色）"),
    ("guide", 2979): ("13", "var(--fs-body)", "**章节正文**（p / li，票面点名 14px）"),
    ("guide", 2983): ("12.5", "var(--fs-note)", "提醒框（说明）"),
    ("guide", 2989): ("12.5", "var(--fs-body)", "指南表格（与全局 table 的 14 一致）"),
    ("guide", 2993): ("12.5", "var(--fs-tag)", "跳转小按钮"),
    # ---------------- 版本更新记录 ----------------
    ("changelog", 1825): ("13", "var(--fs-block)", "**版本号胶囊**（那张卡的标题那一档；三级里的最高一级）"),
    ("changelog", 1828): ("12", "var(--fs-note)", "日期（元信息）"),
    ("changelog", 1829): ("12", "var(--fs-note)", "条目计数"),
    ("changelog", 1830): ("12", "var(--fs-tag)", "折叠箭头"),
    ("changelog", 1835): ("13", "var(--fs-body)", "版本摘要（正文）"),
    ("changelog", 1837): ("13", "var(--fs-body)", "条目（正文）"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()
    problems: list[str] = []

    found: list[tuple[str, int, str]] = []
    for sc in SCOPES:
        found.extend((sc, line, value) for line, value in bare_fonts(text, sc))
    expect = sorted((sc, line, v[0]) for (sc, line), v in FONT.items())
    if sorted(found) != expect:
        fc, ec = Counter(found), Counter(expect)
        for key in sorted(set(fc) | set(ec)):
            if fc[key] != ec[key]:
                side = "盘上有、表里没有" if fc[key] > ec[key] else "表里有、盘上没有"
                problems.append(f"{side}：{key[0]} L{key[1]} 的 {key[2]}px 出现 {fc[key]} 次（表里 {ec[key]} 次）")

    edits: list[tuple[int, int, str, str]] = []
    used: set[tuple[str, int]] = set()
    for line, sel, b0, b1 in rules_of(text):
        sc = scope_of(sel, scopes)
        if sc not in SCOPES:
            continue
        body = text[b0:b1]
        for key, (value, token, why) in FONT.items():
            if key[0] != sc or key[1] != line:
                continue
            anchor = f"font-size: {value}px"
            if anchor not in body:
                continue
            if body.count(anchor) != 1:
                problems.append(f"{sc} L{line}: 规则体内 {anchor!r} 出现 {body.count(anchor)} 次（期望 1）")
                continue
            used.add(key)
            at = b0 + body.index(anchor)
            edits.append((at, at + len(anchor), f"font-size: {token}",
                          f"{sc:<9} L{line}  {sel.split('*/')[-1].strip()[:36]:<36} {value}px → {token:<16} {why}"))
    unused = sorted(set(FONT) - used)
    if unused:
        problems.append(f"表里这些锚点一次都没命中：{unused}")

    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== 三页字号：{len(edits)} 处（表 {len(FONT)} 条 / 盘上现算 {len(found)} 条）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    left = [(sc, line, v) for sc in SCOPES for line, v in bare_fonts(text, sc)]
    if left:
        print("\n== **停下**：改完仍有裸字号（没写盘）==")
        for sc, line, value in sorted(left):
            print(f"  ✗ {sc} L{line}: {value}px")
        return 1

    if not args.write or args.dry_run:      # --dry-run 说了算（评审：别让 `--write --dry-run` 照样写盘）
        print(f"\n（--dry-run：没有写盘。复扫三页裸字号 = 0 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；复扫三页裸字号 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
