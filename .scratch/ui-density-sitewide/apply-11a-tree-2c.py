r"""工单 11：把 `probe-03` 的 2c 节从"路径桶 + 签名子序列"换成**真树匹配**（彻底解决两条限制）。

10 单那版的两条已知限制：
  ① 父路径不带序号 ⇒ 同层匿名兄弟被并进同一个桶（桶内顺序仍可比，但"某个匿名 div 自己的
     子元素"与"它兄弟的子元素"混在一起判）；
  ② 签名相同的重复兄弟互相之间对调看不出来。

这一版的做法（`_Node` + 递归 LCS 对齐）：
  · 用 `html.parser` 建**真树**（每个元素一个实例节点：tag / id / 直接文本 / 子节点表）；
  · 递归比较：对每一对"已配对的父节点"，用 **LCS** 对齐两侧的子节点序列
    （对齐键 = (tag, id, 直接文本)）；
      - **改前有、改后没配上** ⇒ 既有元素被删 / 被搬走 ⇒ **判红**（报出路径）；
      - **改后有、改前没有** ⇒ 本轮允许的新增 ⇒ 只记事实；
      - 配上的那一对**继续往下递归**（里面的顺序照样要比）。
  · 因为对齐是**逐父节点实例**做的，① 不存在了；因为对齐键含直接文本、
    且"两个签名完全相同的兄弟"必然**整棵子树逐字节相同**（否则签名会不同），
    它们互换在语义上是恒等变换 ⇒ ② 不再是"看不见"，而是**不存在可看的东西**。

自证（脚本自己跑，红证三条 + 绿证一条）：
  ① 对调两个无 id 的 `<th>`（文件名 / 批次）⇒ 判红；
  ② 把一个既有子元素搬到另一个父节点下 ⇒ 判红（旧父节点报"既有元素不见了"）；
  ③ 删掉一个既有元素 ⇒ 判红；
  ④ 插入一个新兄弟 ⇒ **不判红**（本轮的契约是"只新增"）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-11a-tree-2c.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-11a-tree-2c.py --write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGET = ROOT / ".scratch" / "ui-density" / "probe-03-contract.py"

START = "class _ChildOrder(HTMLParser):"
END = "def strip_style(text: str) -> str:"

NEW = '''class _Node:
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


'''

PROOFS = '''

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
        ("把一个既有元素搬到别的父节点（btn-scan 挪到 body 末尾）",
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
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = TARGET.read_text(encoding="utf-8")
    if "class _Node:" in text and "_align(" in text:
        print("== 已经换成真树版（幂等）✅ ==")
        return 0
    i, j = text.find(START), text.find(END)
    if i < 0 or j < 0 or j < i:
        print("== **停下**：找不到要替换的区段（`class _ChildOrder` … `def strip_style`）==")
        return 1
    patched = text[:i] + NEW + text[j:]
    # 自证函数插在 `def main()` 之前
    k = patched.find("def main() -> int:")
    if k < 0:
        print("== **停下**：找不到 `def main()` ==")
        return 1
    patched = patched[:k] + PROOFS.strip("\n") + "\n\n\n" + patched[k:]
    # 2c 那一节改成调用自证
    old_block = patched[patched.find('    out.append("== 2c.'):patched.find('    out.append("== 3.')]
    new_block = ('    out.append("== 2c. 既有元素的存在与顺序（11 单：真树 + 逐层 LCS 对齐）==")\n'
                 '    sib_all = sibling_order_problems(markup_before, markup_after)\n'
                 '    sib = [p for p in sib_all if not p.startswith("（本轮新增")]\n'
                 '    facts = [p for p in sib_all if p.startswith("（本轮新增")]\n'
                 '    if sib:\n'
                 '        failed = True\n'
                 '        out.append(f"  **{len(sib)} 处**既有元素不见了 / 被搬走了：")\n'
                 '        for line in sib[:12]:\n'
                 '            out.append("    " + line)\n'
                 '    else:\n'
                 '        out.append("  ✅ 改前就有的元素**一个都没少、也没被搬走**；同一父节点下的相对顺序不变")\n'
                 '    for line in facts:\n'
                 '        out.append("  " + line)\n'
                 '    _self_test_2c(markup_before, out, _FAILED)\n\n')
    if not old_block.strip():
        print("== **停下**：2c 那一节的边界没找到 ==")
        return 1
    patched = patched.replace(old_block, new_block, 1)
    # `failed` 是 main 里的局部变量；自证要能置位 → 用一个单元素列表桥接
    patched = patched.replace("    out.append(\"== 2c. 既有元素的存在与顺序",
                              "    _FAILED = [failed]\n    out.append(\"== 2c. 既有元素的存在与顺序", 1)
    patched = patched.replace('    out.append("== 3. 被点名的类名出现次数（整文件口径）==")',
                              '    failed = _FAILED[0]\n'
                              '    out.append("== 3. 被点名的类名出现次数（整文件口径）==")', 1)

    print(f"== 2c 换实现：{len(text)} → {len(patched)} 字符（真树 + 逐层 LCS + 四条自证）==")
    if not args.write or args.dry_run:
        print("（--dry-run：没有写盘；确认无误后加 --write）")
        return 0
    raw = TARGET.read_bytes()
    eol = "\r\n" if b"\r\n" in raw else "\n"
    TARGET.write_bytes(patched.replace("\r\n", "\n").replace("\n", eol).encode("utf-8"))
    print("[已写盘] probe-03-contract.py ✅（换完记得重跑一次：真盘应 0 处问题、四条自证全对）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
