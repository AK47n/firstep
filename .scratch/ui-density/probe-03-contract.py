r"""契约机械对账（工单 ui-density/01 的验收件）：改前 vs 改后逐项比对 index.html。

判据三条（都是机械可判的，不看"好不好看"）：

1. **id 集合完全相同**——页面声明了哪些 id，一个不多一个不少。
2. **检测页段落的 DOM 顺序完全相同**——按出现顺序抽出该 section 内的标签序列
   （`<section id="tab-hwcheck">` 到它闭合为止），逐项相等。
3. **被守卫点名的类名出现次数不变**——`hwcheck-section` / `hwcheck-generic` /
   `hwcheck-my-device` / `hwcheck-custom-plan` / `hwcheck-handoff` 等。

外加一条**文案零删除**：从 diff 里挑出"以 `-` 开头且含中日韩文字"的行，逐条打印
（空清单 = 本轮没删过任何一句中文文案）。

基线取自 git 对象（`git show <rev>:<path>`），因此**不需要 stash / 不依赖工作树干净**。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-03-contract.py
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-03-contract.py --out contract.txt
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from html.parser import HTMLParser   # 2b 的"既有兄弟相对顺序"检查（10 单）
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REL = "src/contest_generator/static/index.html"
PAGE = ROOT / REL
# 基线**钉死在本轮改造开始之前那一版**（bd478720），不是 "HEAD"。
#
# 为什么（工单 05 复查抓到的自毁）：基线写 HEAD 时，改动一提交，探针就变成"量本轮没改什么"
# ——读数永远"零差异"，谁也复核不了 01/02/04 的契约结论。钉死之后，任何人在任何时刻
# 跑它，量的都是"相对改造前那一版"的累计差异。
BASE_REV = "bd478720"

ID_RE = re.compile(r'\bid="([^"]+)"')
TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)")
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")
WATCHED_CLASSES = (
    "hwcheck-section", "hwcheck-generic", "hwcheck-my-device", "hwcheck-custom-plan",
    "hwcheck-handoff", "hwcheck-table", "hwcheck-check", "hwcheck-recent-row",
    "hwcheck-hint", "hwcheck-group", "hwcheck-order-row",
)


def base_text() -> str:
    return subprocess.run(
        ["git", "show", f"{BASE_REV}:{REL}"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout


def hwcheck_slice(text: str) -> str:
    start = text.index('<section id="tab-hwcheck"')
    end = text.index("</section>", start)
    return text[start:end]


#: 12 个页签（顺序 = 顶部导航从左到右）。09 单把"每页一节"补上：
#: 按页签切片逐段比 id 顺序 / 元素顺序 / 类名计数（spec L171 早就要求）。
TABS = ["generate", "hwcheck", "topic", "code", "settings", "library",
        "reference", "pdf", "md", "master", "guide", "changelog"]


def tab_slice(text: str, tab: str) -> str:
    """切出某个页签的 `<section>` 段（从它自己的 section 到下一个页签 section 之前）。

    为什么不用 `</section>` 收尾：这些 section 里**还有嵌套的 section**（页面内部的块），
    非贪婪匹配会提前截断；而十二个页签的 section 在文件里是**兄弟**、依次排列，
    按"下一个页签 section"切最稳（这一段的判据是"页面级 DOM 没被重排"，不需要精确闭合）。
    """
    start = text.find(f'<section id="tab-{tab}"')
    if start < 0:
        return ""
    nxt = [text.find(f'<section id="tab-{t}"', start + 1) for t in TABS]
    nxt = [p for p in nxt if p > start]
    return text[start:min(nxt)] if nxt else text[start:]


def tag_sequence(text: str) -> list[str]:
    """标签序列（开/闭都记），去掉属性——只关心结构与顺序。"""
    return [f"{'/' if close else ''}{name}" for close, name in TAG_RE.findall(text)]


def class_counts(text: str) -> Counter[str]:
    """按 `class="…"` 属性里的**整串**计数（不做子串匹配，避免 hwcheck-section
    把 hwcheck-section-tag 也算进去）。"""
    out: Counter[str] = Counter()
    for value in re.findall(r'\bclass="([^"]*)"', text):
        for name in value.split():
            out[name] += 1
    return out


class _Node:
    """DOM 树的一个元素实例（只留判据要用的三样：标签 / id / **直接文本**）。"""

    __slots__ = ("tag", "ident", "text", "kids")

    def __init__(self, tag: str, ident: str) -> None:
        self.tag = tag
        self.ident = ident
        self.text = ""
        self.kids: list["_Node"] = []


class _TreeBuilder(HTMLParser):
    """把 HTML 解析成 `_Node` 树（宽容版：闭合标签对不上就往上找，找不到就忽略）。

    ⚠ **不追求 HTML5 级正确**：两侧用同一把尺子解析、比的是"同一份文件的先后两版"，
    解析器只要**稳定**就够（不稳定的话两侧一起错，判据也就不成立——所以红证是必须的）。
    """

    VOID = {"br", "img", "input", "meta", "link", "hr", "source", "area", "base",
            "col", "embed", "param", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", "")
        self.stack = [self.root]
        self.last: _Node | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        node = _Node(tag, dict(attrs).get("id", ""))
        self.stack[-1].kids.append(node)
        if tag not in self.VOID:
            self.stack.append(node)
            self.last = node

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        # 文本只并进"当前最内层元素"——这样匿名兄弟之间不会互相挂错（10 单第二版踩过）
        node = self.stack[-1]
        node.text = (node.text + " " + text).strip() if node.text else text


def _key(node: "_Node") -> tuple[str, str, str]:
    """对齐键：标签 + id + 直接文本前 24 字（够区分同层兄弟，又不被长段落拖累）。"""
    return (node.tag, node.ident, node.text[:24])


def _path(stack: list["_Node"]) -> str:
    return "/".join(f"{n.tag}#{n.ident}" if n.ident else n.tag for n in stack if n.tag != "#document")


def _align(old: list["_Node"], new: list["_Node"]) -> list[tuple[int, int]]:
    """LCS：返回配上的 (旧下标, 新下标) 对（保序）。"""
    n, m = len(old), len(new)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = (dp[i + 1][j + 1] + 1 if _key(old[i]) == _key(new[j])
                        else max(dp[i + 1][j], dp[i][j + 1]))
    out, i, j = [], 0, 0
    while i < n and j < m:
        if _key(old[i]) == _key(new[j]):
            out.append((i, j)); i += 1; j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def sibling_order_problems(before: str, after: str) -> list[str]:
    """**既有元素的顺序与去留**（11 单：真树 + 逐层 LCS 对齐）。

    判据：对每一对"配上的父节点"，把两侧子节点用 `_key` 做 LCS 对齐；
      · 旧的有、新的没配上 ⇒ 既有元素**被删或被搬走** ⇒ 报出来（判红）；
      · 新的有、旧的没有 ⇒ 新增（本轮允许）⇒ 只记数量；
      · 配上的继续递归（更深一层的顺序照样要看）。
    **两个 `_key` 完全相同的兄弟必然整棵子树一致**（否则它们的 `_key` 会在某一层不同）——
    所以它们互换在语义上是恒等变换，不是"看不见"，是**没有可看的东西**（10 单的账第 1 条结了）。
    """
    ta, tb = _TreeBuilder(), _TreeBuilder()
    ta.feed(before)
    tb.feed(after)
    out: list[str] = []
    added = [0]

    def walk(a: _Node, b: _Node, stack: list[_Node]) -> None:
        pairs = _align(a.kids, b.kids)
        matched_old = {i for i, _ in pairs}
        matched_new = {j for _, j in pairs}
        for idx, kid in enumerate(a.kids):
            if idx not in matched_old:
                out.append(f"{_path(stack + [kid])}：改前有、改后不见了（被删或被搬走）")
        added[0] += len(b.kids) - len(matched_new)
        for i, j in pairs:
            walk(a.kids[i], b.kids[j], stack + [a.kids[i]])

    walk(ta.root, tb.root, [])
    if added[0]:
        out.append(f"（本轮新增元素 {added[0]} 个——契约允许，不算问题）")
    return out


def strip_style(text: str) -> str:
    """去掉 `<style>…</style>` 整块。

    为什么：判据是"**给用户看的文案**一个字没删"，而样式块里的**中文注释**也含中文——
    按整文件挑中文删除行会把"改了一条 CSS 注释"误报成"删了文案"（本轮实测：两条 CSS
    注释被当成违规）。文案只在标记里，所以对账只在标记面上做。"""
    return re.sub(r"<style>.*?</style>", "", text, flags=re.S)


def blank_inline_styles(text: str) -> str:
    """把**内联 `style="…"` 的属性值**抹成空串（标签、类名、文案一律不动）。

    为什么（工单 ui-density-sitewide/03 补）：spec 把"文案零删除"的口径写得很准——
    **剥掉内联 `style=` 串之后逐字节相同**（改动面明确允许动 `static/js/**` 与标记里那
    31 处内联取值）。而本探针原先按**原始行**做 diff：01 单把那 31 处内联 `font-size`
    换成令牌之后，凡是"同一行里既有中文文案又有内联取值"的行都被报成"删了文案"
    （14 行，01/02 两份读数里都挂着"契约对账 **失败**"，而票尾写的是"0 行"——
    两者对不上，是探针口径漏了这一层，不是产品删了字）。
    抹掉取值之后，"文案真的少了一句"照样会以"被删行"冒出来，判据没有被削弱。"""
    return re.sub(r'style="[^"]*"', 'style=""', text)


def strip_inline_fontsize(text: str) -> str:
    """把 `font-size: <n>px` **整条声明**去掉（08 单补）。

    为什么：08 单把 `static/js/**` 里最后 7 处内联取值收进了令牌（`var(--fs-tag)`）——
    这是"全站零裸 px 字号"这条线收口时**明确允许**的观感改动。原先那条判据是
    "前端 JS 一个字节没动"，在 08 单之后必须换成**更准的一句**：
    「**剥掉内联 `font-size: <n>px` 之后逐字节相同**」——除此之外任何一处改动都还算违约。
    （`style="…"` 与 `el.style.cssText = "…"` 两种写法都在射程里：本函数只认声明本身，
    不关心它写在哪。）

    ⚠ **两侧都要抹**：老形态是 `font-size:11px`、新形态是 `font-size:var(--fs-tag)`——
    只抹 px 那一侧会让两边永远不相等（08 单第一版就这么写的，当场报出"JS 被改了"）。
    """
    return re.sub(r"font-size:\s*(?:[0-9.]+px|var\(--fs-[\w-]+\));?", "", text)


def strip_test_hooks(text: str) -> str:
    """把 `// [test-hook]` … `// [test-hook] 结束` 之间的**整块**去掉（10 单补）。

    为什么：10 单给进度区开了测试钩子（`ui/master.js` 的 `masterProgressHooks`、
    `ui/generate-recommend.js` 的 `recProgressHooks`）——那是**产品面改动**，
    但只是"多挂了一个只读入口"、不改任何既有行为。契约判据相应放宽成
    "**钩子块之外**逐字节相同"。
    用**显式标记**而不是"允许这些函数名"：模糊判据会让下一轮的任意改动都溜过去。
    ⚠ 剥完还要**收掉结尾多出来的空行**（钩子块插在文件末尾时，剥掉它会留下一个空行——
    10 单第一版就因此报"JS 被改了"，逐行 diff 才看出来只差一个 `\\n`）。
    """
    out = re.sub(r"[ \t]*// \[test-hook\][^\n]*\n.*?[ \t]*// \[test-hook\] 结束[^\n]*\n", "", text, flags=re.S)
    return re.sub(r"\n{2,}\Z", "\n", out)


def strip_class_attrs(text: str) -> str:
    """把 `class="…"` **整个属性**去掉（工单 ui-density-sitewide/05 补）。

    为什么：05 单给「清空本地记录」那个按钮补了一个 `class="danger"`（不可逆动作的重量——
    **只新增类名**、文案一个字没动），而本探针按**原始行** diff —— 那一行当场被报成
    "删了一行中文"（契约对账 **失败**）。与 03 账第 8 条（内联 `style=`）同一类口径漏：
    **文案有没有删**要看文字，不看属性。
    注意两点：① 是**整个属性**去掉，不是把取值抹空——新增一个属性时两者仍然不等（本轮第一版
    就踩了这个：`blank` 成 `class=""` 之后 `data-ico` 前面多了一段，行照样对不上）；
    ② 类名的变动由第 3 节"被点名的类名出现次数"看着（那一节比的是计数，不受这里影响），
    而"删掉一个元素"会把整行带走，照样报得出来。"""
    return re.sub(r'\s+class="[^"]*"', "", text)


def strip_comments(text: str) -> str:
    """去掉 HTML 注释。

    为什么：标记计数要只数**真元素**。注释里出现 `<a href="#id">`（本轮那两个入口锚的
    说明就写了一个）会被标签正则当成一个开标签，于是"新增标签"多算一个、开闭还配不平
    （实测：`a: 3 / /a: 2`，看着像有标签没闭合）。"""
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def diff_removed_lines(before: str, after: str) -> list[str]:
    """改前后逐行 diff 里"被删掉且含中文"的**标记行**（文案零删除的判据）。

    样式块先剥掉（见 `strip_style`）、内联 `style=` 的取值先抹平、`class=` 整条属性先去掉
    （见 `blank_inline_styles` / `strip_class_attrs`），因此这里剩下的中文只可能是页面文案。"""
    import difflib

    removed: list[str] = []
    b = strip_class_attrs(blank_inline_styles(strip_style(before))).splitlines()
    a = strip_class_attrs(blank_inline_styles(strip_style(after))).splitlines()
    for line in difflib.unified_diff(b, a, lineterm="", n=0):
        if not line.startswith("-") or line.startswith("---"):
            continue
        body = line[1:]
        if CJK_RE.search(body):
            removed.append(body.strip())
    return removed


def _self_test_2c(markup: str, out: list[str], failed_flag: list[bool]) -> None:
    """2c 的自证：三条红证 + 一条绿证（11 单要求——判据换了实现，红证必须跟着换）。"""
    ok_th = "<th>文件名</th><th>批次</th>"
    cases = [
        ("对调两个无 id 兄弟 <th>（文件名 / 批次）",
         markup.replace(ok_th, "<th>批次</th><th>文件名</th>", 1) if ok_th in markup else "",
         True),
        ("删掉一个既有元素（lib-search 那个 input）",
         markup.replace('<input type="search" id="lib-search"', '<input type="search" id="lib-search-x"', 1),
         True),
        ("把一个既有元素的 id 改掉（= 旧的消失 + 新的出现；与「搬到别的父节点」同一路径）",
         markup.replace('<button id="btn-scan">', '<button id="btn-scan-moved">', 1),
         True),
        ("插入一个新兄弟（绿证：契约允许）",
         markup.replace(ok_th, "<th>新列</th>" + ok_th, 1) if ok_th in markup else "",
         False),
    ]
    for name, bad, want_red in cases:
        if not bad:
            out.append(f"  （红证「{name}」跳过：锚点不在盘上）")
            continue
        got = [p for p in sibling_order_problems(markup, bad) if not p.startswith("（本轮新增")]
        red = bool(got)
        mark = "✅" if red == want_red else "**✗ 不符合预期**"
        if red != want_red:
            failed_flag[0] = True
        out.append(f"  （自证「{name}」→ {'判红' if red else '未判红'}"
                   f"，期望 {'判红' if want_red else '不判红'} {mark}）")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    before = base_text()
    after = PAGE.read_text(encoding="utf-8")
    out: list[str] = []
    failed = False

    ids_before, ids_after = set(ID_RE.findall(before)), set(ID_RE.findall(after))
    out.append("== 1. id 集合 ==")
    out.append(f"  改前 {len(ids_before)} 个 / 改后 {len(ids_after)} 个")
    only_before, only_after = sorted(ids_before - ids_after), sorted(ids_after - ids_before)
    out.append(f"  只在改前有：{only_before or '（无）'}")
    out.append(f"  只在改后有：{only_after or '（无）'}")
    if only_before or only_after:
        failed = True

    # 判据 = **既有元素的 id 出现顺序**（"没被重排"），不是"标签序列逐项相等"。
    # 口径为什么改（工单 02）：02 要往页面里**插入**三个分组标题带（`.hwcheck-band`），
    # 那是"新增元素"而不是"重排既有元素"——按旧口径（全长标签序列相等）它会假红，
    # 而旧口径真正想守的是"既有元素一个没动、顺序没变"。新增/删除的元素单独如实报数。
    # 标记面：**去注释**之后再数（注释里写 `<a href="#id">` 会被当成一个元素）
    markup_before = strip_comments(before)
    markup_after = strip_comments(after)
    ids_seq_before = ID_RE.findall(hwcheck_slice(markup_before))
    ids_seq_after = ID_RE.findall(hwcheck_slice(markup_after))
    out.append("")
    out.append("== 2. 检测页既有元素的 id 出现顺序（没被重排）==")
    out.append(f"  改前 {len(ids_seq_before)} 个 id / 改后 {len(ids_seq_after)} 个")
    if ids_seq_before == ids_seq_after:
        out.append("  逐项相等 ✅（既有元素一个没动、顺序没变）")
    else:
        failed = True
        out.append("  **不相等**——第一处差异：")
        for i, (a, b) in enumerate(zip(ids_seq_before, ids_seq_after)):
            if a != b:
                out.append(f"    第 {i + 1} 项：改前 {a} / 改后 {b}")
                break
        if len(ids_seq_before) != len(ids_seq_after):
            out.append(f"    （长度不同：{len(ids_seq_before)} vs {len(ids_seq_after)}）")

    tag_before = Counter(tag_sequence(hwcheck_slice(markup_before)))
    tag_after = Counter(tag_sequence(hwcheck_slice(markup_after)))
    added = {k: tag_after[k] - tag_before.get(k, 0) for k in tag_after}
    added = {k: v for k, v in added.items() if v > 0}
    removed_tags = {k: tag_before[k] - tag_after.get(k, 0) for k in tag_before}
    removed_tags = {k: v for k, v in removed_tags.items() if v > 0}
    out.append(f"  本轮**新增**标签：{added or '（无）'}")
    out.append(f"  本轮**删除**标签：{removed_tags or '（无）'}")

    out.append("")
    out.append("== 2b. 每页一节：12 个页签各自的 id 顺序 / 元素与类名多重集（09 单补，spec L171）==")
    out.append("  （口径：把 `index.html` 按 `<section id=\"tab-…\">` 切成 12 段，逐段与基线比三项；")
    out.append("    这一节是**逐页**的细粒度检查——第 2 节只覆盖检测页那一段。）")
    out.append("  ⚠ **说清这一节看什么、不看什么**（09 单评审 Standards 抓过标题名不副实）：")
    out.append("    · `id` **按顺序**比（既有 id 一个不许动、顺序不许变）——这一项是真的顺序检查；")
    out.append("    · 元素与类名按**多重集**比：本轮的契约是**只新增**，所以新增报成事实、")
    out.append("      删除才判红（与第 2 节对 hwcheck 的口径同源）。**无 id 的兄弟元素之间对调**")
    out.append("      这一节看不出来（红证实测过：pdf 段两个 `<th>` 对调仍判 ✅）——")
    out.append("      要连那种也看住，得给它们加 id 或另立一笔逐标签序列比对。")
    for tab in TABS:
        b, a = tab_slice(markup_before, tab), tab_slice(markup_after, tab)
        if not b or not a:
            failed = True
            out.append(f"  ✗ {tab:<10} 页签切片为空（改前 {len(b)} / 改后 {len(a)} 字符）——先查选择器")
            continue
        ids_b = re.findall(r'\bid="([^"]+)"', b)
        ids_a = re.findall(r'\bid="([^"]+)"', a)
        # 元素与类名按**多重集**比：本轮的契约是"只新增"（只新增类名 / 分组带元素），
        # 所以**新增**报成事实、**删除**才算违约（同第 2 节对 hwcheck 的口径）。
        tag_b, tag_a = Counter(tag_sequence(b)), Counter(tag_sequence(a))
        cls_b, cls_a = class_counts(b), class_counts(a)
        tag_gone = {k: tag_b[k] - tag_a.get(k, 0) for k in tag_b}
        tag_gone = {k: v for k, v in tag_gone.items() if v > 0}
        tag_new = {k: tag_a[k] - tag_b.get(k, 0) for k in tag_a}
        tag_new = {k: v for k, v in tag_new.items() if v > 0}
        cls_gone = {k: cls_b[k] - cls_a.get(k, 0) for k in cls_b}
        cls_gone = {k: v for k, v in cls_gone.items() if v > 0}
        cls_new = {k: cls_a[k] - cls_b.get(k, 0) for k in cls_a}
        cls_new = {k: v for k, v in cls_new.items() if v > 0}
        ok = (ids_b == ids_a) and not tag_gone and not cls_gone
        out.append(f"  {'✅' if ok else '**变了**'} {tab:<10}"
                   f" id {len(ids_a):>3} 个（{'既有 id 顺序一致' if ids_b == ids_a else '**顺序/个数变了**'}）"
                   f" · 元素 {sum(tag_a.values()):>4} 个（新 {sum(tag_new.values())} / 删 {sum(tag_gone.values())}）"
                   f" · 类名 {len(cls_a):>3} 种（新 {sum(cls_new.values())} / 删 {sum(cls_gone.values())}）")
        if not ok:
            failed = True
            if ids_b != ids_a:
                for i, (p, q) in enumerate(zip(ids_b, ids_a)):
                    if p != q:
                        out.append(f"      id 顺序第 {i + 1} 项：改前 {p} / 改后 {q}")
                        break
                if len(ids_b) != len(ids_a):
                    out.append(f"      id 个数不同：{len(ids_b)} vs {len(ids_a)}")
            for label, gone in (("元素", tag_gone), ("类名", cls_gone)):
                if gone:
                    out.append(f"      **{label}被删**：{gone}")
            if cls_new:
                out.append(f"      （本轮新增类名：{cls_new}）")
            if tag_new:
                out.append(f"      （本轮新增元素：{tag_new}）")

    out.append("")
    _FAILED = [failed]
    out.append("== 2c. 既有元素的存在与顺序（11 单：真树 + 逐层 LCS 对齐）==")
    sib_all = sibling_order_problems(markup_before, markup_after)
    sib = [p for p in sib_all if not p.startswith("（本轮新增")]
    facts = [p for p in sib_all if p.startswith("（本轮新增")]
    if sib:
        failed = True
        out.append(f"  **{len(sib)} 处**既有元素不见了 / 被搬走了：")
        for line in sib[:12]:
            out.append("    " + line)
    else:
        out.append("  ✅ 改前就有的元素**一个都没少、也没被搬走**；同一父节点下的相对顺序不变")
    for line in facts:
        out.append("  " + line)
    _self_test_2c(markup_before, out, _FAILED)

    failed = _FAILED[0]
    out.append("== 3. 被点名的类名出现次数（整文件口径）==")
    cb, ca = class_counts(before), class_counts(after)
    for name in WATCHED_CLASSES:
        mark = "✅" if cb[name] == ca[name] else "**变了**"
        out.append(f"  .{name:<22} 改前 {cb[name]:>3} / 改后 {ca[name]:>3}  {mark}")
        if cb[name] != ca[name]:
            failed = True

    out.append("")
    out.append("== 4. 中文文案删除行（应为空）==")
    removed = diff_removed_lines(before, after)
    if removed:
        failed = True
        for line in removed:
            out.append(f"  - {line[:140]}")
    else:
        out.append("  （无）✅")

    out.append("")
    out.append("== 结论 ==")
    out.append("  契约对账 " + ("**失败**（见上）" if failed else "全部通过 ✅"))
    out.append("")
    out.append("== 附带事实（读的人别误读第 3 节）==")
    out.append("  · 上表里计数为 0 的类名（hwcheck-section / hwcheck-generic / hwcheck-my-device /")
    out.append("    hwcheck-custom-plan / hwcheck-handoff / hwcheck-table …）**不在 index.html 里**")
    out.append("    ——它们由 `static/js/fx/*.js` 渲染出来；本轮这些文件一个字节没改")
    out.append("    （见下一条），所以它们天然不变。")
    changed = subprocess.run(["git", "diff", "--name-only", BASE_REV], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8").stdout.split()
    product = [p for p in changed if not p.startswith(".scratch/")]
    evidence = [p for p in changed if p.startswith(".scratch/")]
    out.append(f"  · 产品面改动文件（{len(product)} 个）：{product or '（无）'}")
    # 真正要守的不是"只有 index.html"（那只是 01 那一单当时的实况），而是
    # **前端 JS 没有夹带行为改动**——它是"这一轮只改观感、没碰行为"的那条契约。
    # 口径（08 单更新）：**剥掉内联 `font-size: <n>px` 之后逐字节相同**——
    # 08 单把最后 7 处内联取值收进了令牌（`var(--fs-tag)`），那是本轮明确允许的观感改动；
    # 除它之外任何一处改动都仍然算违约（逐文件比对，不只看文件名）。
    js_touched = [p for p in product if p.startswith("src/contest_generator/static/js/")]
    js_bad: list[str] = []
    for rel in js_touched:
        old = subprocess.run(["git", "show", f"{BASE_REV}:{rel}"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8").stdout
        new = (ROOT / rel).read_text(encoding="utf-8")
        if strip_inline_fontsize(old) != strip_inline_fontsize(new) and \
           strip_test_hooks(strip_inline_fontsize(old)) != strip_test_hooks(strip_inline_fontsize(new)):
            js_bad.append(rel)
    if js_bad:
        out.append(f"    ⚠ 前端 JS 被改了（不是内联字号那一类）：{js_bad}——"
                   "本轮契约是「只改观感」，请核对")
        failed = True
    elif js_touched:
        out.append(f"    ✓ 前端 JS（static/js/**）{len(js_touched)} 个文件**只动了内联字号与标记过的"
                   "测试钩子块**（`strip_inline_fontsize` + `strip_test_hooks` 之后逐字节相同）"
                   "——没有夹带行为改动")
    else:
        out.append("    ✓ 前端 JS（static/js/**）一个字节没动——观感改动没有夹带行为改动")
    out.append(f"  · 本目录证据件改动（{len(evidence)} 个）：{evidence or '（无）'}"
               "——探针与证据自己也会被改，不算产品改动")

    report = "\n".join(out)
    print(report)
    if args.out:
        target = Path(__file__).resolve().parent / args.out
        target.write_text(report + "\n", encoding="utf-8")
        print(f"\n[落盘] {target}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
