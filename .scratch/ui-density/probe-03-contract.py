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
    out.append("== 3. 被点名的类名出现次数 ==")
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
    # **前端 JS 一个字节没动**——它是"这一轮只改观感、没碰行为"的那条契约。
    js_touched = [p for p in product if p.startswith("src/contest_generator/static/js/")]
    if js_touched:
        out.append(f"    ⚠ 前端 JS 被改了：{js_touched}——本轮契约是「只改观感」，请核对")
        failed = True
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
