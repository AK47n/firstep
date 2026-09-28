r"""工单 03 施工脚本（三）：`generate` 作用域**内层完整描边**的逐条处置。

口径（spec「描边规矩」+ 检测页样板 + 02 单的逐层清单）：
**一屏一层完整描边**——一个页面页签 / 一个弹层内，完整矩形描边只有最外层容器那一条。
内层一律换成本轮既有的三种语言之一：

  · **左条 3px + 淡底**（分组 / 小节 / 说明块）——照样板 `.hwcheck-hint` / `.hwcheck-group`
  · **淡底**（条目盒 / 面板底）——`--panel` / `--panel-2` 已经在，去掉框就够
  · **`1px solid transparent`**（可点行）——把"可点"的悬停染色留着，但不画那一圈
  · **`3px dashed` 左条**（"还没确认 / 空态"这一档）——照样板 `.my-device-draft`

**保留的例外**（每条都在 KEEP 里点名 + 写理由，票尾逐层清单与它同源）：
  ① 语义告警 / 状态条（`.preread-slot` / `.pin-warn-list .wx` / `.task-phase` / `.task-next-hint` …）
  ② 可点控件与控件形状（按钮 / 输入框 / chip / 页签 / 胶囊 / 图例点 / spinner 圆环）
  ③ 弹层外壳（`.pin-menu` / `.quick-open-box` / `.task-more-menu`——弹层自己算一屏）
  ④ 单边（`border-top/bottom/left` 那类分隔线与语义左条）与非框（`border: 0` / `transparent`）
  ⑤ **顶层块**（`.gen-overview` / `.gen-recent`）：与 12 张步骤卡同级，不是"卡里套面板"

完整性证明（不是"我觉得改完了"）：
  · 改前：本作用域里**所有完整 `border:` 声明**的行号集合 == FIX ∪ KEEP（多一条少一条都停手）
  · 每条改动：锚点是**该条声明的完整原文**，要求在该规则体内恰好命中一次
  · 改后：完整 `border:` 声明只剩 KEEP ∪（FIX 里改成透明框的那几条）——否则停手
  · 替换串**不含换行**（02 单那条"替换侧写进裸 LF"的坑在本支不可能发生）

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03c-borders.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03c-borders.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"
SCOPE = "generate"

LEFT_BAR = "border: none; border-left: 3px solid var(--border-strong);"
LEFT_BAR_DASHED = "border: none; border-left: 3px dashed var(--border-strong);"
FLAT = "border: none;"

# 行号 → [(锚点原文, 换成, 理由)]
FIX: dict[int, list[tuple[str, str, str]]] = {
    584: [("border: 1px solid var(--border);", "border: 1px solid transparent;",
           "结构化错误条目：可点行 → 透明框（悬停染色保留）")],
    646: [("border: 1px solid var(--border);", FLAT, "方案计数：chip 内的小字，不再自己画一圈")],
    648: [("border: 1px dashed var(--border);", LEFT_BAR_DASHED,
           "选型参考面板：整圈虚线 → 虚线左条（'展开的补充材料'）")],
    657: [("border: 1px solid var(--border);", FLAT, "选型元信息：mono + muted 已够区分")],
    677: [("border: 1px solid var(--border);", FLAT, "商量面板：留 --panel 底即边界")],
    686: [("border: 1px solid var(--accent);", FLAT, "用户气泡：留 accent-dim 底（与 AI 气泡靠底色分）")],
    689: [("border: 1px solid var(--border);", FLAT, "AI 气泡：留 panel-2 底")],
    705: [("border: 1px solid var(--border);", "border: none; border-top: 1px solid var(--border);",
           "任务卡商量面板：**票面点名那一笔**——留 --panel 底 + 一条上分隔线")],
    744: [("border: 1px solid var(--border);", FLAT, "任务微编辑表单：留 panel-2 底（输入框自己还有框）")],
    784: [("border: 1px solid var(--border);", FLAT, "参数卡：一格一张，去框留淡底")],
    821: [("border: 1px solid var(--border);", LEFT_BAR, "评分点面板：左条 + 淡底")],
    830: [("border: 1px solid var(--border);", LEFT_BAR, "功能组卡：左条 + 淡底（照 .hwcheck-group）")],
    884: [("border: 1px solid var(--border);", FLAT, "main.c 磁盘状态行：留淡底")],
    1033: [("border: 1px solid var(--border);", LEFT_BAR, "结果块：左条 + 淡底（卡里 6 个并排的块）")],
    1638: [("border: 1px solid var(--border);", "border: 1px solid transparent;",
            "引脚角色行：可点 → 透明框；.bound 那条 3px 左条照旧")],
    2850: [("border: 1px solid var(--border);", LEFT_BAR,
            "**票面点名的硬骨头** `.card-group`：卡内分组 → 左条 + 淡底")],
    2885: [("border: 1px dashed var(--border);", LEFT_BAR_DASHED, "页签空态引导：虚线整圈 → 虚线左条")],
    2992: [("border: 1px solid var(--border);", FLAT, "资源总览表：留淡底（行间已有虚线分隔）")],
    3033: [("border: 1px solid var(--border);", FLAT, "板图包裹：留淡底（图自己就是一块）")],
    3074: [("border: 1px solid var(--border);", FLAT, "评分点覆盖表：同 .res-table")],
    3094: [("border: 1px solid var(--border);", FLAT, "上板自检折叠：留淡底（.card-details 同款）")],
    3131: [("border: 1px solid var(--border);", FLAT, "轮次记录：留 panel 底")],
    3162: [("border: 1px solid var(--border);", FLAT, "「本轮变化」区：留淡底")],
    3214: [("border: 1px solid var(--border);", FLAT, "就绪摘要条：留它自己的深色底")],
}

# 行号 → 保留理由（完整 border: 声明，不改）
KEEP: dict[int, str] = {
    760: "③ 弹层外壳：「⋯ 更多」下拉菜单",
    804: "② 标签胶囊：参数单位 chip",
    871: "① 语义告警块：题面提醒（amber）",
    1372: "④ 非框：可点行的透明框",
    1649: "② 标签胶囊：固定脚 chip",
    1653: "① 语义告警 chip：不可绑的脚",
    1662: "② 标签胶囊：引脚图例",
    1680: "③ 弹层外壳：引脚锚定浮层",
    2498: "③ 弹层外壳：Ctrl+P 快速打开",
   2502: "④ 非框：输入框自带 border: 0",  # 值不是完整 border 声明（是 0），不进"完整描边"集合
   2505: "④ 非框：关闭钮 border: 0",  # 同上
    2688: "④ 非框：步骤导航圆点（透明框）",
    2693: "② 控件形状：导航圆点",
    2733: "⑤ 顶层块：就绪总览条（与步骤卡同级）",
    2745: "② 可点控件：步骤 chip",
    2752: "② 控件里的序号点",
    2790: "② 可点控件：一键补齐按钮",
    2802: "⑤ 顶层块：最近生成（与步骤卡同级）",
    2814: "② 可点控件：最近记录条目",
    2824: "② 标签胶囊：平台徽章",
    2867: "② 可点控件：卡内页签",
    2877: "② 标签胶囊：页签徽章",
    2975: "① 语义状态条：执行中阶段槽",
    2981: "④ 非框：spinner 圆环",
    2986: "② 可点控件：去交付按钮",
    3000: "② 标签胶囊：资源 chip",
    3018: "② 可点控件：视图切换",
    3041: "② 图例点",
    3043: "① 语义图例：冲突标记",
    3081: "② 标签胶囊：评分点 chip",
    3107: "① 语义提示条：下一步引导",
}

FULL_BORDER_RE = re.compile(r"(?<![\w-])border:\s*([^;]+);")
DEAD = ("none", "0")
# 改成透明框的那几条：改后它们仍然是"完整 border: 声明"，要算进改后的期望集合
TO_TRANSPARENT = {line for line, fixes in FIX.items()
                  for _, new, _ in fixes if new.startswith("border: 1px solid transparent")}


def load_scopes() -> list[tuple[str, re.Pattern[str]]]:
    text = GUARD.read_text(encoding="utf-8")
    block = re.search(r"const PAGE_SCOPES = \[(.*?)\n\];", text, re.S)
    if not block:
        raise SystemExit("守卫里找不到 PAGE_SCOPES")
    return [(m.group(1), re.compile(m.group(2)))
            for m in re.finditer(r'\["([\w-]+)", /(.*?)/\]', block.group(1))]


def scope_of(sel: str, scopes: list[tuple[str, re.Pattern[str]]]) -> str:
    clean = re.sub(r"^(?:/\*.*?\*/\s*)+", "", sel, flags=re.S).strip()
    for name, rx in scopes:
        if rx.search(clean):
            return name
    return scopes[-1][0]


def rules_of(text: str) -> list[tuple[int, str, int, int]]:
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text, re.S):
        out.append((text.count("\n", 0, m.start()) + 1,
                    " ".join(m.group(1).split()), m.start(2), m.end(2)))
    return out


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

    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    problems: list[str] = []

    # ① 改前完整性：完整 border: 声明的行号集合 == FIX ∪ KEEP
    before = full_border_lines(text)
    before_lines = sorted({line for line, _, _ in before})
    declared = sorted(set(FIX) | (set(KEEP) - {2502, 2505}))
    if before_lines != declared:
        problems.append(f"改前的完整描边行号集合与申报不符："
                        f"多出 {sorted(set(before_lines) - set(declared))}、"
                        f"少了 {sorted(set(declared) - set(before_lines))}")

    # ② 逐条锚点：在该行那条规则体内做唯一替换
    #    ⚠ 不能"按行号挑规则"：这段样式块有两条规则落在同一行（L705 `.sugg-discuss-note:not(.muted)`
    #    与 `.task-dialog-box`、L2745、L3120 …）。按行号挑会挑中不带该声明的那条，锚点当场落空。
    #    正确做法：扫**每一条**规则体，锚点在谁身上命中就算谁的。
    edits: list[tuple[int, int, str, str]] = []
    hit_count: dict[tuple[int, str], int] = {}
    for line, sel, b0, b1 in rules_of(text):
        if line not in FIX:
            continue
        body = text[b0:b1]
        for old, new, why in FIX[line]:
            if old not in body:
                continue
            key = (line, old)
            hit_count[key] = hit_count.get(key, 0) + 1
            if body.count(old) != 1:
                problems.append(f"L{line}: 锚点 {old!r} 在该规则体内出现 {body.count(old)} 次（期望 1）")
                continue
            at = b0 + body.index(old)
            edits.append((at, at + len(old), new, f"L{line}  {sel}  →  {why}"))
    for line, fixes in sorted(FIX.items()):
        for old, _, _ in fixes:
            if hit_count.get((line, old), 0) == 0:
                problems.append(f"L{line}: 锚点 {old!r} 一次都没命中（行号变了 / 规则已被改过）")
            elif hit_count[(line, old)] > 1:
                problems.append(f"L{line}: 锚点 {old!r} 命中 {hit_count[(line, old)]} 条规则（期望 1）")

    print(f"== generate 描边：改 {len(edits)} 条 / 保留 {len(KEEP)} 条（改前完整描边 {len(before)} 处）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改  " + note)

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ③ 改后复扫：完整 border: 声明只应剩 KEEP ∪ 改成透明框的那几条
    after = full_border_lines(text)
    after_lines = sorted({line for line, _, _ in after})
    expect_after = sorted((set(KEEP) - {2502, 2505}) | TO_TRANSPARENT)
    if after_lines != expect_after:
        print("\n== **停下**：改后剩下的完整描边与申报不符（没写盘）==")
        print(f"  多出 {sorted(set(after_lines) - set(expect_after))}")
        print(f"  少了 {sorted(set(expect_after) - set(after_lines))}")
        for line, sel, value in after:
            print(f"  · L{line}  {sel[:70]}  →  {value}")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫 generate 完整描边 = {len(after)} 处，全部在申报的例外里 ✅；"
              f"确认无误后加 --write）")
        return 0
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：改 {len(edits)} 条；"
          f"复扫完整描边 = {len(after)} 处（全部在申报的例外里）✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
