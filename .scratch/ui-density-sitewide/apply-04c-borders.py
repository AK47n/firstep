r"""工单 04 施工脚本（三）：`code` 作用域**内层完整描边**的逐条处置（照 apply-03c 的模板）。

口径（spec「描边规矩」+ 检测页样板 + 03 单的逐层清单）：
**一屏一层完整描边**——一个页面页签 / 一个弹层内，完整矩形描边只有最外层容器那一条。
内层一律换成本轮既有的语言：留白 / **淡底**（`--panel-2` / `--code-bg`）/ **单条分隔线** / **左条 3px**。

**这一页的家底要说清（03 单账第 1 条）**：探针的"border 声明"口径 = **67** 处，其中大部分是
**单边分隔线**（IDE 骨架天生如此：状态条 `border-top`、标签条 `border-bottom`、三栏 `border-right/left`）
与 `border: 0`。本支按 **整圈完整框**口径复算 = **24** 处，逐条处置如下：

  · 改 **5** 条（内层盒去框）：引用代码片段 / 冲突对比列标题 / 冲突对比 pre / md 预览代码块 /
    效果 diff hunk —— 全部换成"淡底"或"左条 + 淡底"。
  · 留 **19** 条，逐条写理由（下表 KEEP）。例外面临三个新类别，一并写在这里：
      ⑤ **文档渲染元素**：`.code-md-preview` 的表格网格线 / 图片边框 —— markdown 预览是**渲染文档**，
         网格与图框是文档语法（去掉以后 md 表格就散了）；这个件还是**跨页共享**的（md 资料 tab
         的预览弹窗也用它），本页无权把它拆掉。
      ⑥ **浮层提示 / 浮标**：`.code-ro-note`（只读标注）、`.code-zoom-badge`（缩放百分比）——
         它们浮在**代码面之上**，没有自己的面就与背后的代码糊在一起。
      ⑦ **编辑器控件形状**：`.code-wrap`（main.c 编辑器）/ `.code-zoom`（悬浮工具条）——
         04 票面点名要如实保留的那一类。

完整性证明（不是"我觉得改完了"）：
  · 改前：本作用域里**所有完整 `border:` 声明**的行号集合 == FIX ∪ KEEP（多一条少一条都停手）
  · 每条改动：锚点是**该条声明的完整原文**，要求在该规则体内恰好命中一次
  · 改后：完整 `border:` 声明只剩 KEEP——否则停手
  · 替换串**不含换行**（02 单那条"替换侧写进裸 LF"的坑在本支不可能发生）
  · **去框之后的死声明按坑 5 扫过**：这 5 条身上/族里没有任何 `border-*-color` 声明
    （全站 `border-color` 逐行核过：1934/1936/1989/2043/2200-2201/2245/2533-2535 都在**保留**的控件上），
    也不靠边框做悬停反馈（坑 6：这 5 条没有 `:hover` 改 `border-color` 的兄弟规则）。
    唯一清掉的死声明是 `.code-conflict-col-title` 的 `border-bottom: 0`（它连着 `border:` 一起走）。

> **评审后的两条更正（05–07 单照后者写；本支已执行完、锚点已消费，按 03 单账第 6 条不回头改写）**：
> ① 口径函数 `full_border_lines` 已提到 **`scope_lib.full_borders`**（单一出处）——本支就地保留一份
>    是"已执行证据"的一部分，新脚本请 `from scope_lib import full_borders`；
> ② 本支的两处弱点（评审 Standards 点名）：改后对账**只比行号集合、不比取值**；`TO_TRANSPARENT`
>    恒为空集（死参数）；`hit` 只扫"起始行 ∈ FIX"的规则。新脚本：对账连**取值**一起比、删掉死参数、
>    认人一律按选择器片段（本支 ② 那条 `border-bottom: 0; ` 就是按行号认的）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04c-borders.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04c-borders.py --write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import PAGE, ROOT, load_scopes, read_page, rules_of, scope_of, write_page  # noqa: E402

SCOPE = "code"
FLAT = "border: none;"
LEFT_BAR = "border: none; border-left: 3px solid var(--border-strong);"

# 行号 → [(锚点原文, 换成, 理由)]
FIX: dict[int, list[tuple[str, str, str]]] = {
    2024: [("border: 1px solid var(--border);", FLAT,
            "引用代码片段：照样板 `pre.result`——代码块不自己画框，留 --code-bg 底")],
    2405: [("border: 1px solid var(--border);", FLAT,
            "冲突对比列标题：去掉标题帽那条框（它下面 pre 的框也一起去）"),
           ("border-bottom: 0; ", "",
            "死声明（坑 5）：`border:` 一去，这条 border-bottom 再没有框可染")],
    2408: [("border: 1px solid var(--border);", FLAT,
            "冲突对比 pre：两列靠 10px 间隙 + 各自 code-bg 底分界，不各画一圈")],
    2617: [("border: 1px solid var(--border);", FLAT,
            "md 预览的代码块：同 `.code-ai-ref-code`（文档里的代码块 = 淡底 + 圆角）")],
    3189: [("border: 1px solid var(--border);", LEFT_BAR,
            "效果 diff hunk：去整圈框 → 左条 + 淡底（照 .res-block；它在 --panel-2 的底部面板里，"
            "光去框会与面板底糊在一起）")],
}

# 行号 → 保留理由（完整 border: 声明，不改）
KEEP: dict[int, str] = {
    1924: "② 可点控件：面板头 / 状态条按钮（.code-pane-action / .code-compile-head button / .code-statusbar button）",
    1968: "② 控件形状：键帽 .code-kbd（标签胶囊一族）",
    1982: "④ 非框：底部面板页签的透明框（选中/悬停才染色）",
    2029: "② 可点控件：「预览改动」按钮（accent 主按钮）",
    2038: "② 控件形状：AI 对话输入框",
    2077: "② 控件形状：removed 状态徽章",
    2192: "④ 非框：编辑器文件标签的透明框（.on 才染色）",
    2204: "② 控件形状：只读标徽章 .code-tab-ro",
    2238: "② 可点控件：信息条小按钮（返回预览 / 编辑源码）",
    2386: "④ 非框：滚动条 thumb 的透明边（3px transparent）",
    2393: "⑥ 浮层提示：只读标注 .code-ro-note（浮在代码面上，需要自己的面）",
    2416: "⑥ 浮标：缩放百分比 .code-zoom-badge（同上）",
    2478: "③ 弹层外壳：文件树右键菜单",
    2498: "③ 弹层外壳：Ctrl+P 快速打开（03 单从生成页移交过来的那族）",
    2519: "② 控件形状：树操作输入框",
    2627: "⑤ 文档渲染：md 表格网格线（th/td；跨页共享件，去掉 md 表格就散了）",
    2631: "⑤ 文档渲染：md 图片边框（浅色主题下白底截图与页面同色，靠这条分界）",
    3320: "⑦ 编辑器控件形状：main.c 编辑器 .code-wrap（票面点名保留）",
    3367: "⑦ 悬浮控件：字号缩放 / 操作工具条 .code-zoom",
}

FULL_BORDER_RE = re.compile(r"(?<![\w-])border:\s*([^;]+);")
DEAD = ("none", "0")
TO_TRANSPARENT: set[int] = set()   # 本支没有"改成透明框"的条目（改的都是去框 / 左条）


def full_border_lines(text: str) -> list[tuple[int, str, str]]:
    """本作用域里**完整 `border:`**（不含 -top/-left 那类单边）的行号 + 选择器 + 取值。"""
    scopes = load_scopes()
    out: list[tuple[int, str, str]] = []
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        for m in FULL_BORDER_RE.finditer(text[b0:b1]):
            value = m.group(1).strip()
            if value.split()[0] in DEAD:      # border: none / border: 0
                continue
            out.append((line, sel, value))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    problems: list[str] = []

    # ① 改前完整性：完整 border: 声明的行号集合 == FIX ∪ KEEP
    before = full_border_lines(text)
    before_lines = sorted({line for line, _, _ in before})
    declared = sorted(set(FIX) | set(KEEP))
    if before_lines != declared:
        problems.append(f"改前的完整描边行号集合与申报不符："
                        f"多出 {sorted(set(before_lines) - set(declared))}、"
                        f"少了 {sorted(set(declared) - set(before_lines))}")

    # ② 逐条锚点：**扫每一条规则体**，锚点在谁身上命中就算谁的（03c 的账：按行号挑会挑错人）
    edits: list[tuple[int, int, str, str]] = []
    hit: dict[tuple[int, str], int] = {}
    for line, sel, b0, b1 in rules_of(text):
        if line not in FIX:
            continue
        body = text[b0:b1]
        for old, new, why in FIX[line]:
            if old not in body:
                continue
            key = (line, old)
            hit[key] = hit.get(key, 0) + 1
            if body.count(old) != 1:
                problems.append(f"L{line}: 锚点 {old!r} 在该规则体内出现 {body.count(old)} 次（期望 1）")
                continue
            at = b0 + body.index(old)
            edits.append((at, at + len(old), new, f"L{line}  {sel.split('*/')[-1].strip()[:44]:<44} → {why}"))
    for line, fixes in sorted(FIX.items()):
        for old, _, _ in fixes:
            if hit.get((line, old), 0) == 0:
                problems.append(f"L{line}: 锚点 {old!r} 一次都没命中（行号变了 / 规则已被改过）")
            elif hit[(line, old)] > 1:
                problems.append(f"L{line}: 锚点 {old!r} 命中 {hit[(line, old)]} 条规则（期望 1）")

    print(f"== {SCOPE} 描边：改 {len(edits)} 条 / 保留 {len(KEEP)} 条（改前整圈完整框 {len(before)} 处）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改  " + note)
    for line in sorted(KEEP):
        print(f"  留  L{line}  {KEEP[line]}")

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ③ 改后复扫：完整 border: 声明只应剩 KEEP
    after = full_border_lines(text)
    after_lines = sorted({line for line, _, _ in after})
    expect_after = sorted(set(KEEP) | TO_TRANSPARENT)
    if after_lines != expect_after:
        print("\n== **停下**：改后剩下的完整描边与申报不符（没写盘）==")
        print(f"  多出 {sorted(set(after_lines) - set(expect_after))}")
        print(f"  少了 {sorted(set(expect_after) - set(after_lines))}")
        for line, sel, value in after:
            print(f"  · L{line}  {sel[:70]}  →  {value}")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫 {SCOPE} 整圈完整框 = {len(after)} 处，全部在申报的例外里 ✅；"
              f"确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：改 {len(edits)} 条；"
          f"复扫整圈完整框 = {len(after)} 处（全部在申报的例外里）✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
