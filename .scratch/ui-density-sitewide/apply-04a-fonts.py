r"""工单 04 施工脚本（一）：`code` 作用域的字号 → `--fs-*`（66 处）+ 三处派生 / 例外。

做法照 03a：**逐条显式锚点**（行号 → (期望原值, 换成的声明值, 角色理由)），替换在该行那条
**规则块**的声明体里做，断言锚点**恰好命中一次**；命中数不对就整支停手、一个字节都不写。
改完**回头复扫**：`code` 作用域剩下的裸 px 字号必须是 0。

角色判定（口径 = spec 的「字号角色表」+ 检测页样板 + 03 单的落地口径）——**这一页是 IDE**，
条目本身就是代码与文件路径，所以多两条本页口径（写在下面，评审按这两条核）：

  ① **代码 / 路径 / mono 内容走 `--fs-note`(13)**：与编辑器正文 `--code-font-size`
     （= 13 档）**同源** —— 树里的文件名与打开后的代码不一样大，是 IDE 的一致性 bug。
     这一条与样板一致：检测页的代码块 `pre.result` 就是 `font-size: var(--fs-note)`。
  ② **散文（说明 / 状态 / 空态 / 元信息）也走 `--fs-note`(13)**；**用户要读的条目主字
     （非 mono）走 `--fs-body`(14)**；**徽章 / 标签 / 键帽 / 小按钮 / 图标字走 `--fs-tag`(12)**；
     **给一整块命名的标题走 `--fs-block`(16)**（三个面板块标题 / 底部面板标题 / 快捷键分组 /
     冲突对比列标题——照样板 `#tab-hwcheck .card h3` 的小节标题语义）。
  ③ 页签（编辑器文件标签 `.code-tab` / 底部面板页签 `.code-bottom-tab` / 侧栏视图 tab）
     统一 `--fs-note`(13)：它们是 mono 文件名与面板名，属口径①那一档。
     （03 单把生成页的卡内小页签 `.revise-tab` 归了 `--fs-tag`——那是卡片里的一颗胶囊，
     与本页"编辑器文件标签"不是一回事；两处口径不同的理由写在这里，不藏着。）
  ④ `.code-tab-close`（✕）与 `.code-zoom button`（＋/−）走 `--fs-note`(13)：**行内图标随它
     附着的那一面**，不是随正文——14 会把 33px 的标签条撑高（02 单「行内小图标随正文」
     那条口径讲的是 toast 里的 ✕，那里的父级正文就是 14）。

两处**派生**（**不在** 66 处之内——它们写在 `calc()` 里，探针的 px 判据天然看不到，
所以逐条单列、各自断言，免得"机器绿了、人眼还能看见一个裸值"）：

  · `--code-font-size: calc(13px * var(--code-zoom, 1))` → `calc(var(--fs-note) * …)`：
    票面点名的验收项（13px 那个裸值消失，字号台阶整体调整时它跟着走）。
    **缩放链路一字不动**：JS 只读写 `--code-zoom`（ui/codeview.js），不解析这里的 13px。
  · `.code-md-preview { font-size: calc(15px * var(--code-zoom, 1)) }` → `calc(var(--fs-body) * …)`：
    15px 是**全站 13 种待清取值之一**，藏在这个 calc 里、探针看不见；md 预览是散文，
    取全站正文档 14（代码档 13 与它原来就差一档，关系保持）。缩放仍走同一个 `--code-zoom`。

> **⚠ 更正（双轴评审抓到，2026-09-29）——两处，都记在这里，别只看代码**：
> ① **`.code-gutter-line.code-err-line::after` 的 `8px → .62em` 原本被本支列了两次**
>    （`FONT_BY_LINE[2282]` 与 `DERIVE` 的第三条各一条），两条编辑区间**重叠**，后一条按旧下标
>    多吃一个字符，盘上留下 `font-size: .62em;m;`（CSS 非法声明：浏览器丢弃、两道门禁都看不见）。
>    本支的断言只看"锚点各命中一次"、复扫只看"还剩没剩裸 px"，两关都过 —— 是**静默写坏**。
>    修法（已就地改在下面）：那条 em 例外**只留在 `FONT_BY_LINE` 表里**（它本来就是 66 处之一，
>    docstring 原来说"三处派生不在 66 处之内"是错的），并新增**编辑区间不许重叠**的断言
>    （见 `main()` 的 ③）。盘上那一个 `m` 由 `apply-04d-review-fixups.py` 修回。
> ② **教训**：保值/派生混在一支脚本里时，"锚点唯一"**不等于**"编辑区间不打架"——
>    锚点唯一只保证每条各自命中一次，两条同址的编辑照样会互相啃。<br>
>    05–07 单：任何一支脚本同时改"表里列过的"和"派生清单里的"内容时，先跑那条重叠断言。
>
> 另：`.code-gutter-line.code-err-line::after` 的 `8px → .62em` 是 **spec「字号角色表」里
> em 例外的第二例**（第一例是 `.badge` 邻域那个 8px 上标星号）：**装饰性字形随父级缩放**，
> 不进令牌表——守卫按 px 取值判，em 天然不在它射程内（spec 与守卫文件头两处已同步写明）。

覆盖完整性：本表与**现算的**（`scope_lib.bare_fonts`，与守护/探针同一处判据）裸字号明细逐条
对账，用 `Counter` 比重数（同 03a 评审整改后的口径——集合差集在"同一行两条规则同值"时会静默放行）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04a-fonts.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-04a-fonts.py --write
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

SCOPE = "code"

# 行号 → (期望原值, 换成的声明值, 角色理由)
FONT_BY_LINE: dict[int, tuple[str, str, str]] = {
    # ---- 状态条 / 快捷键弹窗 ----
    1913: ("12", "var(--fs-note)", "状态条（mono 目录路径 + 行列/编码信息 + 小按钮同排）"),
    1938: ("12", "var(--fs-note)", "状态条右侧动态信息段（VSCode 式小字）"),
    1959: ("12", "var(--fs-block)", "快捷键弹窗的**分组小节标题**（给一组命名）"),
    1962: ("12", "var(--fs-body)", "快捷键条目（键帽 + 说明，用户要读的那一层）"),
    1968: ("11", "var(--fs-tag)", "键帽标签"),
    # ---- 底部面板（编译 / 变更 / 对话 / 修复 / 烧录）----
    1982: ("11.5", "var(--fs-note)", "底部面板页签（口径③：页签一档）"),
    1993: ("11", "var(--fs-block)", "底部面板的**块标题**（编译输出 / 磁盘变更 / AI 对话 …）"),
    1999: ("11.5", "var(--fs-tag)", "面板头小按钮"),
    2018: ("12", "var(--fs-note)", "AI 对话空态说明"),
    2019: ("11.5", "var(--fs-note)", "引用卡片摘要（mono 路径 + 行区间）"),
    2024: ("12", "var(--fs-note)", "引用代码片段（mono，口径①代码档）"),
    2029: ("11.5", "var(--fs-tag)", "「预览改动」小按钮"),
    2038: ("12", "var(--fs-note)", "AI 提问输入框（mono，与代码档同源）"),
    2047: ("11.5", "var(--fs-tag)", "选区浮动小按钮"),
    2055: ("11.5", "var(--fs-note)", "修复轮次条（元信息）"),
    2059: ("12", "var(--fs-note)", "修复状态提示行"),
    2069: ("12", "var(--fs-note)", "磁盘变更条目（行主字是 mono 路径，口径①）"),
    2073: ("11", "var(--fs-tag)", "新增/修改/删除徽章"),
    2081: ("12", "var(--fs-note)", "变更路径（mono）"),
    2082: ("11.5", "var(--fs-note)", "变更元信息（+N −M 统计）"),
    2084: ("11.5", "var(--fs-note)", "行级 diff 折叠摘要"),
    2086: ("12", "var(--fs-note)", "编译错误行（mono，可点）"),
    # ---- 三栏与面板标题 ----
    2117: ("11", "var(--fs-block)", "**面板块标题**（资源管理器 / 大纲 / 搜索）"),
    2124: ("11.5", "var(--fs-tag)", "面板头小按钮（选择文件夹 / 收起）"),
    2140: ("12.5", "var(--fs-note)", "树 / 侧栏空态说明"),
    # ---- 标签条 / 面包屑 / 信息条 ----
    2169: ("12", "var(--fs-note)", "标签条里的 muted 提示"),
    2170: ("12", "var(--fs-note)", "面包屑路径（mono 元信息）"),
    2192: ("12", "var(--fs-note)", "编辑器文件标签（mono 文件名，口径③）"),
    2202: ("11", "var(--fs-tag)", "「新 / 变」标签徽章"),
    2204: ("11", "var(--fs-tag)", "只读标（RO）"),
    2207: ("11", "var(--fs-tag)", "未保存点"),
    2208: ("11", "var(--fs-tag)", "「磁盘已变更」徽章"),
    2214: ("14", "var(--fs-body)", "关闭 ✕（口径④：行内图标随所附的那一面；值不变）"),
    2226: ("12", "var(--fs-note)", "标签条下方信息条（muted 小字）"),
    2238: ("11.5", "var(--fs-tag)", "信息条小按钮（返回预览 / 编辑源码）"),
    # ---- 编辑器骨架 ----
    2264: ("11", "var(--fs-tag)", "gutter 折叠小三角"),
    2282: ("8", ".62em", "编译错误行的 ● 色点：**装饰字形随父级缩放**（spec 的 em 例外第二例——gutter 字号跟着 Ctrl+滚轮变，写死 px 放大后会变成一个小点）"),
    2301: ("13", "var(--fs-note)", "编辑器空态"),
    2307: ("13", "var(--fs-note)", "编辑器空态里的错误句"),
    2393: ("11.5", "var(--fs-note)", "只读标注浮条（说明）"),
    # ---- 保存冲突模态 ----
    2400: ("12", "var(--fs-note)", "冲突模态说明段"),
    2405: ("11.5", "var(--fs-block)", "对比**列标题**（给一整列命名）"),
    2408: ("12", "var(--fs-note)", "对比内容 pre（mono，口径①代码档）"),
    2416: ("11", "var(--fs-tag)", "缩放百分比浮标"),
    # ---- 文件树 ----
    2429: ("12.5", "var(--fs-note)", "树目录行（与文件行同档，口径①）"),
    2434: ("12.5", "var(--fs-note)", "树文件行（口径①）"),
    2443: ("12", "var(--fs-note)", "文件名（mono，口径①）"),
    2445: ("11", "var(--fs-tag)", "「新 / 变」树徽章"),
    2472: ("12.5", "var(--fs-note)", "行操作按钮（✎ 重命名 / 🗑 删除）"),
    # ---- 右键菜单 / 树操作输入 ----
    2486: ("13", "var(--fs-body)", "右键菜单项（用户要读的动作名；值不变）"),
    2519: ("13", "var(--fs-note)", "树操作输入框（mono；值不变）"),
    # ---- 侧栏（大纲 / 搜索 / 替换）----
    2529: ("12", "var(--fs-note)", "侧栏视图 tab（口径③）"),
    2546: ("12", "var(--fs-note)", "侧栏收起后的竖排 rail 按钮"),
    2559: ("12.5", "var(--fs-note)", "大纲条目行（mono 函数名，口径①）"),
    2565: ("11", "var(--fs-tag)", "大纲 kind 图标字（f / # / <>）"),
    2568: ("12", "var(--fs-note)", "大纲里的名字（mono，口径①）"),
    2570: ("12.5", "var(--fs-note)", "侧栏空态"),
    2578: ("12", "var(--fs-tag)", "替换动作按钮"),
    2579: ("11.5", "var(--fs-note)", "查找计数「第 N / 共 M 处」（mono 元信息）"),
    2583: ("12.5", "var(--fs-note)", "搜索结果 / 查找结果列表（mono 命中行）"),
    2592: ("11.5", "var(--fs-note)", "搜索命中路径（mono 元信息）"),
    # ---- 效果 diff（与生成页共享的件，按分区表归本页）----
    3191: ("12.5", "var(--fs-note)", "diff hunk 折叠摘要（mono）"),
    3197: ("12", "var(--fs-note)", "diff 正文（mono，口径①代码档）"),
    # ---- main.c 编辑器容器 + 缩放工具条（生成页 DOM，按分区表归本页）----
    3320: ("13", "var(--fs-note)", "main.c 编辑器字号基准（与 ui/generate-mainc.js 的 CODE_ZOOM_BASE 成对；值不变）"),
    3388: ("13", "var(--fs-note)", "缩放 / 操作按钮字形（口径④）"),
    3392: ("12", "var(--fs-tag)", "缩放百分比读数（标签）"),
}

# 两处派生：全文范围内的**唯一**锚点 → 换成（各自断言命中恰好一次）
# ⚠ em 那一条（`.code-err-line::after` 的 8px → .62em）**不在**这里——它本来就是 66 处之一，
#   列在 FONT_BY_LINE 表里；本支第一版两头都列，编辑区间重叠写出了 `;m;`（见 docstring 更正）。
DERIVE: list[tuple[str, str, str]] = [
    ("--code-font-size: calc(13px * var(--code-zoom, 1));",
     "--code-font-size: calc(var(--fs-note) * var(--code-zoom, 1));",
     "票面验收：编辑器字号基准改从字号台阶派生（缩放链路 --code-zoom 一字不动）"),
    ("font-size: calc(15px * var(--code-zoom, 1));",
     "font-size: calc(var(--fs-body) * var(--code-zoom, 1));",
     "md 预览根字号：15px 是全站待清取值之一、藏在 calc 里探针看不见 → 取正文档 14"),
]


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

    # ② 逐条锚点：键是 (行号, 取值)——不是行号（同一行可能落两条规则，03a 的账）
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
                          f"L{line}  {sel.split('*/')[-1].strip()[:46]:<46} {value}px → {repl:<16} {why}"))
    unused = sorted(set(table) - used)
    if unused:
        problems.append(f"表里这些锚点一次都没命中：{unused}")

    # ③ 两处派生：全文唯一锚点
    for old, new, why in DERIVE:
        if text.count(old) != 1:
            problems.append(f"派生锚点 {old!r} 在全文出现 {text.count(old)} 次（期望 1）")
            continue
        at = text.index(old)
        edits.append((at, at + len(old), new, f"派生  {old[:52]:<52} → {new[:46]:<46} {why}"))

    # ③b **编辑区间不许重叠**（评审抓到本支第一版就是在这一步静默写坏的：同址两条编辑
    #     各自"锚点唯一"，却互相啃出一个 `m`）——区间按起点排序，后一条的起点必须 >= 前一条的终点
    for (s1, e1, n1, _), (s2, e2, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1!r} 与 [{s2},{e2}) —— "
                            f"两条编辑打在同一个字节区间上（第一版就是这么写出 `;m;` 的）")

    print(f"== code 字号：{len(edits)} 处（表 {len(FONT_BY_LINE)} 条 / 盘上现算 {len(found)} 条 "
          f"/ 派生 {len(DERIVE)} 处）==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ④ 复扫：改完该作用域的裸 px 字号必须是 0，且两处派生锚点都不该在
    left = bare_fonts(text, SCOPE)
    if left:
        print("\n== **停下**：改完仍有裸字号（没写盘）==")
        for line, value in sorted(left):
            print(f"  ✗ L{line}: {value}px")
        return 1
    for old, _, _ in DERIVE:
        if old in text:
            print(f"\n== **停下**：派生锚点还在：{old!r}（没写盘）==")
            return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫 {SCOPE} 裸字号 = 0 ✅、{len(DERIVE)} 处派生的裸值都不在了 ✅；"
              f"确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；复扫 {SCOPE} 裸字号 = 0 ✅、派生 {len(DERIVE)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
