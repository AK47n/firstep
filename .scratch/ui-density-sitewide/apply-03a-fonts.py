r"""工单 03 施工脚本（一）：`generate` 作用域的字号 → `--fs-*`（111 处）。

做法（照 01a / 02a 的手法）：**逐条显式锚点**——行号 → (期望原值, 令牌, 角色理由)，
替换在该行那条**规则块**的声明体里做，并断言锚点**恰好命中一次**；命中数不对就整支停手、
一个字节都不写。改完再**回头复扫**：`generate` 作用域里剩下的裸 px 字号必须是 0。

角色判定（口径 = spec 的「字号角色表」+ 用户拍板的抬高地板）：
  · 取值给基准档：11/11.5 → tag；12/12.5 → note；13 → note；14 → body；18 → icon 邻域；20/16.5 → page
  · 角色定档（spec「按角色判，不按数值换算」）——**可以跳级，理由逐条写在表里**（评审口径更正：
    本支第一版 docstring 写"相邻一档之内"，而 `.pin-subtitle` 12→16 / `.gen-recent-title` 13→16
    是票面「四级可辨（小节标题 16）」直接要求的跳级，那句话与实做不符）：
      徽章 / 标签 / chip / 图例 / 计数 / 小胶囊按钮 / 行内小字   → `--fs-tag`(12)
      说明句 / 元信息 / 时间戳 / 提示行                        → `--fs-note`(13)
      正文（读得下去的那一层：条目、条目正文、表单行、对话）    → `--fs-body`(14)
      **小节标题**（它给一整块命名）                           → `--fs-block`(16)
      **行内小图标**（✕ 这类）随正文 → `--fs-body`（口径单源 = 02 单修正 + 守卫文件头）
  · **不做**"按页面前缀的例外"：全部就地换令牌，不引覆盖层（上一轮 01 的账）。
  · 停在 13 的三处**申报判断**（评审问过，如实记账）：`.res-board-caption` / `.wiring-caption` /
    `.res-toolbar-title` 虽然也在"给一块命名"，但它们是**面板内的行首小标签**（旁边就挤着按钮 /
    图例），升 16 会把任务卡里的密度拉爆——按"面板内标签"档留在 `--fs-note`。

覆盖完整性：本表与**探针现算的**该作用域裸字号明细逐条对账（行号集合与取值都要相等），
少一条 / 多一条 / 取值对不上都停手——避免"改完了其实漏了三条"。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03a-fonts.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-03a-fonts.py --write
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

# 行号 → (期望原值, 令牌, 角色理由)
FONT_BY_LINE: dict[int, tuple[str, str, str]] = {
    244: ("13", "--fs-tag", "步骤编号徽章（24px 圆点里的数字）"),
    584: ("13", "--fs-body", "结构化错误列表条目（可点行的主字）"),
    590: ("11", "--fs-tag", "错误条目类型标签"),
    603: ("12", "--fs-note", "源码行（mono 小字）"),
    646: ("11", "--fs-tag", "方案计数（挂在 chip 里的小字）"),
    652: ("12", "--fs-note", "选型面板小标题"),
    657: ("12", "--fs-note", "选型元信息（mono）"),
    659: ("12.5", "--fs-note", "选型说明句"),
    660: ("12", "--fs-note", "适用范围说明"),
    665: ("11", "--fs-tag", "徽章（AI 审核结论）"),
    674: ("12.5", "--fs-tag", "商量开关（小胶囊按钮）"),
    684: ("13", "--fs-body", "对话气泡正文"),
    692: ("11", "--fs-tag", "对话角色标签"),
    694: ("12.5", "--fs-note", "系统提示行"),
    697: ("11", "--fs-tag", "行内小字（时间戳一类）"),
    700: ("11.5", "--fs-note", "对话区的提示说明"),
    720: ("13", "--fs-tag", "对话发送按钮"),
    728: ("12.5", "--fs-tag", "自定义发送（小胶囊）"),
    750: ("12", "--fs-note", "任务编辑表单的表签"),
    764: ("12", "--fs-tag", "「更多」菜单里的按钮"),
    789: ("12", "--fs-tag", "参数名 slug（mono 小标签）"),
    791: ("13", "--fs-body", "参数中文名（卡头主字）"),
    798: ("12", "--fs-note", "参数提示句"),
    800: ("12", "--fs-tag", "参数失效徽章"),
    804: ("11", "--fs-tag", "参数单位 chip"),
    809: ("11", "--fs-tag", "「当前值」小标签"),
    825: ("13", "--fs-body", "评分点行正文"),
    835: ("12", "--fs-note", "功能组「必须显式选择」提示行"),
    836: ("13", "--fs-body", "功能组成员行主字"),
    841: ("12", "--fs-note", "成员角色说明"),
    842: ("12", "--fs-note", "成员推荐理由"),
    871: ("12.5", "--fs-note", "题面提醒横幅正文"),
    876: ("11.5", "--fs-note", "题面引用（要读的小字引文）"),
    884: ("12.5", "--fs-note", "main.c 磁盘状态行"),
    891: ("11.5", "--fs-note", "磁盘目录路径（mono 说明）"),
    1035: ("11", "--fs-tag", "结果块的大写小标签"),
    1038: ("13", "--fs-body", "结果块正文"),
    1377: ("12.5", "--fs-body", "评分点核对清单行主字"),
    1480: ("12", "--fs-note", "LLM 遥测行（mono 说明）"),
    1633: ("12", "--fs-tag", "引脚图例"),
    1643: ("12", "--fs-note", "引脚角色状态行"),
    1644: ("12", "--fs-tag", "状态行里的小按钮"),
    1645: ("12", "--fs-tag", "可选引脚开关按钮"),
    1649: ("12", "--fs-tag", "固定脚 chip"),
    1653: ("12", "--fs-tag", "警告脚 chip"),
    1656: ("14", "--fs-body", "卡 7 说明正文"),
    1660: ("12", "--fs-note", "引脚工具栏提示"),
    1662: ("12", "--fs-tag", "图例胶囊"),
    1667: ("12", "--fs-block", "**小节标题**（引脚卡里的分区名）"),
    1676: ("11", "--fs-tag", "板图说明文字（SVG caption）"),
    1686: ("13", "--fs-body", "引脚菜单列表主字"),
    1693: ("11", "--fs-tag", "候选不可用原因 / 功能组名"),
    1697: ("12", "--fs-tag", "解绑小按钮"),
    2502: ("14", "--fs-body", "快速打开输入框"),
    2505: ("18", "--fs-body", "快速打开关闭 ✕（**行内图标随正文**）"),
    2509: ("13", "--fs-body", "快速打开结果项（mono 主字）"),
    2515: ("12", "--fs-body", "结果项图标（**行内小图标随正文**）"),
    2518: ("13", "--fs-note", "快速打开空态说明"),
    2693: ("11.5", "--fs-tag", "步骤导航圆点里的数字"),
    2699: ("12", "--fs-note", "步骤导航名"),
    2745: ("12", "--fs-tag", "就绪总览 chip"),
    2752: ("11", "--fs-tag", "chip 里的序号点"),
    2779: ("12.5", "--fs-note", "就绪摘要行"),
    2790: ("12.5", "--fs-tag", "一键补齐（小胶囊按钮）"),
    2795: ("12.5", "--fs-tag", "就绪生成（胶囊按钮）"),
    2808: ("13", "--fs-block", "**小节标题**（最近生成）"),
    2814: ("12.5", "--fs-note", "最近记录条目"),
    2824: ("11", "--fs-tag", "平台徽章"),
    2830: ("12", "--fs-tag", "删除小按钮"),
    2834: ("12.5", "--fs-note", "最近记录空态"),
    2867: ("12.5", "--fs-tag", "卡内页签胶囊"),
    2877: ("11", "--fs-tag", "页签徽章"),
    2885: ("12.5", "--fs-note", "页签空态引导"),
    2975: ("12.5", "--fs-note", "执行中阶段文案"),
    2986: ("12", "--fs-tag", "「去交付」小按钮"),
    3000: ("12", "--fs-tag", "资源 chip"),
    3003: ("13", "--fs-body", "使用任务正文"),
    3006: ("12", "--fs-note", "冲突提示"),
    3010: ("12", "--fs-note", "软资源说明"),
    3016: ("12", "--fs-note", "资源工具栏小标题"),
    3018: ("12", "--fs-tag", "视图切换按钮"),
    3024: ("11", "--fs-tag", "资源分组小标题（大写标签）"),
    3037: ("12", "--fs-note", "板图标题"),
    3038: ("11", "--fs-tag", "板图图例"),
    3045: ("12", "--fs-note", "板图缺数据说明"),
    3046: ("12", "--fs-note", "板图消息"),
    3055: ("11", "--fs-note", "接线图标题"),
    3056: ("11", "--fs-tag", "接线图例"),
    3070: ("12", "--fs-tag", "「显示全部接线」开关行"),
    3072: ("12", "--fs-note", "接线空态"),
    3081: ("12", "--fs-tag", "评分点 chip"),
    3084: ("12", "--fs-tag", "评分点编号"),
    3085: ("12", "--fs-tag", "评分点分值"),
    3086: ("13", "--fs-body", "评分点描述"),
    3087: ("13", "--fs-body", "评分点涉及任务"),
    3090: ("12", "--fs-note", "无覆盖提示"),
    3093: ("12", "--fs-note", "未知引用提示"),
    3096: ("12.5", "--fs-note", "上板自检折叠摘要"),
    3104: ("13", "--fs-body", "自检清单项"),
    3107: ("12", "--fs-note", "下一步引导行"),
    3120: ("12", "--fs-note", "任务卡元信息"),
    3133: ("12.5", "--fs-note", "轮次行"),
    3138: ("12", "--fs-note", "轮次详情"),
    3141: ("11", "--fs-tag", "轮次时间 / 备份小字"),
    3155: ("12", "--fs-note", "编译错误列表（mono）"),
    3167: ("12.5", "--fs-note", "「本轮变化」折叠摘要"),
    3172: ("12.5", "--fs-note", "变化详情"),
    3173: ("12.5", "--fs-note", "备份回滚行"),
    3223: ("13", "--fs-body", "就绪检查行主字"),
    3234: ("12", "--fs-tag", "「去第 N 步 / 补推荐」小按钮"),
}

FONT_RE = re.compile(r"font-size:\s*([0-9.]+)px")


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
    """[(行号, 选择器, 声明体起, 声明体止)]。"""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text, re.S):
        out.append((text.count("\n", 0, m.start()) + 1,
                    " ".join(m.group(1).split()), m.start(2), m.end(2)))
    return out


def bare_fonts(text: str) -> list[tuple[int, str]]:
    """该作用域里现算的裸 px 字号：**每处一条** [(行号, 取值)]（一条规则里写两处就出两条）。"""
    scopes = load_scopes()
    found: list[tuple[int, str]] = []
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        found.extend((line, v) for v in FONT_RE.findall(text[b0:b1]))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    problems: list[str] = []

    # ① 覆盖率对账：表里的 (行号, 取值) 与现算的裸字号**逐条相等**
    #    用 Counter 比**重数**，不是比两个 set 的差集——同一行两条规则写了同一个字号时，
    #    (行号, 取值) 会在 found 里出现两次而集合看不出差别（评审抓到的静默缝：
    #    "多一条少一条都停手"这句话在那种形状下不成立）。
    found = bare_fonts(text)
    expect = sorted((line, v[0]) for line, v in FONT_BY_LINE.items())
    if sorted(found) != expect:
        fc, ec = Counter(found), Counter(expect)
        for key in sorted(set(fc) | set(ec)):
            if fc[key] != ec[key]:
                side = "盘上有、表里没有" if fc[key] > ec[key] else "表里有、盘上没有"
                problems.append(f"{side}：L{key[0]} 的 {key[1]}px 出现 {fc[key]} 次（表里 {ec[key]} 次）")

    # ② 逐条锚点：在该行那条规则体内做唯一替换
    #    键是 (行号, 取值)——**不是行号**：这段样式块里有两条规则落在同一行
    #    （L2745 `.ov-chips` / `.ov-chip`、L3120 `.task-card-highlight` / `.task-meta`），
    #    只按行号找会挑中不带字号的那条，锚点当场落空（本支第一版就是这么被抓的）。
    table = {(line, v[0]): (v[1], v[2]) for line, v in FONT_BY_LINE.items()}
    if len(table) != len(FONT_BY_LINE):
        problems.append("表里有 (行号, 取值) 撞车——同一行两条规则都写了同一个字号，改按选择器区分")
    edits: list[tuple[int, int, str, str]] = []
    used: set[tuple[int, str]] = set()
    scopes = load_scopes()
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != SCOPE:
            continue
        body = text[b0:b1]
        for m in FONT_RE.finditer(body):
            key = (line, m.group(1))
            if key not in table:
                continue
            token, why = table[key]
            anchor = f"font-size: {key[1]}px"
            if body.count(anchor) != 1:
                problems.append(f"L{line}: 规则体内 {anchor!r} 出现 {body.count(anchor)} 次（期望 1）")
                continue
            used.add(key)
            at = b0 + body.index(anchor)
            edits.append((at, at + len(anchor), f"font-size: var({token})",
                          f"L{line}  {sel}  →  {token:<11} {why}"))
    unused = sorted(set(table) - used)
    if unused:
        problems.append(f"表里这些锚点一次都没命中：{unused}")

    print(f"== generate 字号：{len(edits)} 处（表 {len(FONT_BY_LINE)} 条 / 盘上现算 {len(found)} 条）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ③ 复扫：改完该作用域的裸 px 字号必须是 0
    left = bare_fonts(text)
    if left:
        print("\n== **停下**：改完仍有裸字号（没写盘）==")
        for line, value in sorted(left):
            print(f"  ✗ L{line}: {value}px")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫 {SCOPE} 裸字号 = 0 ✅；确认无误后加 --write）")
        return 0
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；复扫 {SCOPE} 裸字号 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
