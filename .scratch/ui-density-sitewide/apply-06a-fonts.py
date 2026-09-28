r"""工单 06 施工脚本（一）：五个素材/库页作用域的字号 → `--fs-*`（63 处）。

五页：`library`（模块库 32）/ `reference`（参考文件库 14）/ `pdf`（PDF 资料库 1）/
`md`（Markdown 资料 2）/ `topic`（赛题库 14）。

做法照 04a / 05a：**逐条显式锚点**（(作用域, 行号) → (期望原值, 令牌, 角色理由)），
替换在该行那条**规则块**的声明体里做，断言锚点**恰好命中一次**；改完回头复扫：五个作用域的
裸 px 字号必须都是 0。**编辑区间不许重叠**（04 账第 9 条）。

角色判定（口径 = spec 的「字号角色表」+ 04/05 落地的两条本页口径）：

  · **条目主字 / 正文 / 要读的内容（含 mono 的代码、路径、预览）→ `--fs-body`(14)**：
    详情弹窗正文、键值行、平台块名、弹层清单行、筛选输入框、题号、**题面全文与题面预览**、
    「当前简介」原文块……
  · **说明 / 元信息 / 表头 / 提示 / 空态 / 计数 → `--fs-note`(13)**：`.muted` 一族、脚注、
    统计条、状态行、卡片简介、四问小标签、mono 清单（清单本身是"读得到就行"的那一档）。
  · **徽章 / 标签 / chip / 胶囊 / 箭头 / 行内警示标 / 小按钮 → `--fs-tag`(12)**：
    `.mc-plat` `.mc-offtag` `.mc-deps` `.mc-pa` `.mc-info` `.lib-chip` `.topic-year`
    `.dangling-tag` `.topic-warn` `.mi-pin-id` `.file-del` `.add-section-arrow`、图注……
  · **弹层 / 区块的标题（给一整块命名、独占一行）→ `--fs-block`(16)**：
    `.module-info-title .slug`（详情弹窗标题）、`.ref-detail-title`（详情弹窗标题）、
    `.add-section-head`（"添加模块"的分区块头）、`.topic-detail-*title`（详情弹窗分段标题）。
  · 两处**行内警示标**（`.dangling-tag` / `.ref-dangling-tag` 与 `.topic-warn`）统一走
    `--fs-tag`：它们是"同一套表达"里最轻的那一档（验收「健康 / 状态徽章统一」）。

覆盖完整性：本表与**现算的**（`scope_lib.bare_fonts`，与守卫/探针同一处判据）五个作用域的
裸字号明细逐条对账，用 `Counter` 比重数。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06a-fonts.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-06a-fonts.py --write
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

SCOPES = ["library", "reference", "pdf", "md", "topic"]

# (作用域, 行号) → (期望原值, 令牌, 角色理由)
FONT: dict[tuple[str, int], tuple[str, str, str]] = {
    # ---------------- 模块库 / module-card（生成页模块池 + 检测页器件网格两处渲染）----------------
    ("library", 450): ("13", "var(--fs-note)", "卡片 slug（mono 标识符）"),
    ("library", 452): ("11", "var(--fs-tag)", "平台不兼容胶囊"),
    ("library", 455): ("12", "var(--fs-note)", "卡片简介（两行截断的说明）"),
    ("library", 459): ("11", "var(--fs-tag)", "平台胶囊"),
    ("library", 464): ("11", "var(--fs-tag)", "依赖胶囊"),
    ("library", 466): ("11", "var(--fs-tag)", "引脚胶囊"),
    ("library", 468): ("11", "var(--fs-tag)", "「说明」小按钮"),
    # ---------------- 模块详情弹窗（模块库 / 生成页 / 检测页共用）----------------
    ("library", 486): ("13", "var(--fs-body)", "详情弹窗正文"),
    ("library", 487): ("14", "var(--fs-block)", "**弹层标题**（mono slug，独占一行）"),
    ("library", 490): ("12", "var(--fs-note)", "平台不兼容警示块（语义告警，例外①）"),
    ("library", 497): ("12", "var(--fs-note)", "四问分段小标签（accent 强调色）"),
    ("library", 499): ("12.5", "var(--fs-note)", "「为什么推荐它」块"),
    ("library", 504): ("12", "var(--fs-note)", "键值行（k + 文）"),
    ("library", 510): ("13", "var(--fs-body)", "平台块名（h4）"),
    ("library", 511): ("11", "var(--fs-tag)", "平台胶囊（弹窗内复用 .mc-plat）"),
    ("library", 515): ("12", "var(--fs-note)", "mono 文件清单"),
    ("library", 518): ("12.5", "var(--fs-note)", "mono 可点文件名"),
    ("library", 526): ("12", "var(--fs-note)", "mono 源码区头"),
    ("library", 528): ("12", "var(--fs-note)", "说明句"),
    ("library", 530): ("12", "var(--fs-note)", "引脚表"),
    ("library", 534): ("11", "var(--fs-tag)", "引脚 id 小字"),
    # ---------------- 改简介 / 编辑模块弹窗 ----------------
    ("library", 547): ("13", "var(--fs-body)", "「当前简介」原文块（要读的正文）"),
    ("library", 551): ("12.5", "var(--fs-note)", "错误 / 提示行"),
    ("library", 554): ("12", "var(--fs-note)", "状态行"),
    ("library", 556): ("12.5", "var(--fs-note)", "mono 文件清单"),
    ("library", 561): ("11", "var(--fs-tag)", "文件行小删除按钮"),
    ("library", 563): ("12.5", "var(--fs-note)", "提示行"),
    # ---------------- 添加模块分区折叠 ----------------
    ("library", 569): ("13", "var(--fs-block)", "**分区块头**（「添加模块」①②③ 给一整块命名）"),
    ("library", 573): ("11", "var(--fs-tag)", "▾ 折叠箭头"),
    # ---------------- 模块库工具栏 / 统计条 ----------------
    ("library", 925): ("12.5", "var(--fs-tag)", "过滤 chip"),
    ("library", 930): ("12.5", "var(--fs-note)", "统计条"),
    ("library", 3032): ("12", "var(--fs-note)", "统计条「可点击筛选」提示"),
    # ---------------- 参考文件库 ----------------
    ("reference", 853): ("12", "var(--fs-note)", "选择列表表头行（勾选|资料|平台|说明）"),
    ("reference", 858): ("13", "var(--fs-body)", "条目标题（mono）"),
    ("reference", 860): ("12", "var(--fs-note)", "说明列"),
    ("reference", 913): ("12", "var(--fs-tag)", "行内 ⚠ 悬空警示标（与 .topic-warn 同族）"),
    ("reference", 979): ("15", "var(--fs-block)", "**详情弹窗标题**"),
    ("reference", 981): ("13", "var(--fs-body)", "详情键值行"),
    ("reference", 983): ("12", "var(--fs-note)", "键"),
    ("reference", 991): ("12", "var(--fs-note)", "脚注"),
    ("reference", 993): ("12", "var(--fs-note)", "脚注里的 mono code"),
    ("reference", 1509): ("18", "var(--fs-body)", "弹层关闭 ✕（行内图标随弹层正文档）"),
    ("reference", 1512): ("13", "var(--fs-body)", "弹层文件清单行（mono）"),
    ("reference", 1517): ("12", "var(--fs-note)", "mono 文本预览（代码档）"),
    ("reference", 1546): ("12", "var(--fs-note)", "mono 路径行"),
    ("reference", 1554): ("13", "var(--fs-body)", "过滤输入框"),
    # ---------------- PDF 资料库 ----------------
    ("pdf", 987): ("12", "var(--fs-note)", "确认弹窗里的成员清单（滚动小字）"),
    # ---------------- Markdown 资料 ----------------
    ("md", 1025): ("11", "var(--fs-note)", "文件名小字第二行（元信息）"),
    ("md", 1027): ("13", "var(--fs-note)", "预览状态 / 空态行"),
    # ---------------- 赛题库 ----------------
    ("topic", 1850): ("13", "var(--fs-body)", "题号（mono 700，卡片主标识）"),
    ("topic", 1853): ("12", "var(--fs-tag)", "年份 chip（描边胶囊）"),
    ("topic", 1855): ("11.5", "var(--fs-note)", "元数据小行（字数 / 程序数 / 图注）"),
    ("topic", 1859): ("11.5", "var(--fs-tag)", "行内 ⚠ 警示标（与 .dangling-tag 同族）"),
    ("topic", 1867): ("12", "var(--fs-block)", "**详情弹窗分段标题**（题面全文 / 页图）"),
    ("topic", 1871): ("11.5", "var(--fs-note)", "分段标题旁的计数"),
    ("topic", 1872): ("12", "var(--fs-tag)", "展开 / 收起小按钮"),
    ("topic", 1876): ("13", "var(--fs-body)", "题面全文（弹窗主内容）"),
    ("topic", 1881): ("12", "var(--fs-note)", "mono 程序行"),
    ("topic", 1888): ("11", "var(--fs-tag)", "页图图注"),
    ("topic", 2702): ("12", "var(--fs-note)", "编辑弹窗表单标签"),
    ("topic", 2703): ("12", "var(--fs-body)", "题面输入框（mono 内容）"),
    ("topic", 2706): ("12.5", "var(--fs-note)", "功能组勾选行"),
    ("topic", 2709): ("13", "var(--fs-body)", "题面预览（卡片主内容）"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()
    problems: list[str] = []

    # ① 覆盖率对账：五个作用域的现算裸字号（多重集）== 表
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

    # ② 逐条锚点（键 = (作用域, 行号)——同一行可能落两条规则，且五个作用域行号各自独立）
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
                          f"{sc:<9} L{line}  {sel.split('*/')[-1].strip()[:38]:<38} {value}px → {token:<16} {why}"))
    unused = sorted(set(FONT) - used)
    if unused:
        problems.append(f"表里这些锚点一次都没命中：{unused}")

    # ③ 编辑区间不许重叠（04 账第 9 条）
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== 五页字号：{len(edits)} 处（表 {len(FONT)} 条 / 盘上现算 {len(found)} 条）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ④ 复扫：五个作用域的裸 px 字号都必须是 0
    left = [(sc, line, v) for sc in SCOPES for line, v in bare_fonts(text, sc)]
    if left:
        print("\n== **停下**：改完仍有裸字号（没写盘）==")
        for sc, line, value in sorted(left):
            print(f"  ✗ {sc} L{line}: {value}px")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫五页裸字号 = 0 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；复扫五页裸字号 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
