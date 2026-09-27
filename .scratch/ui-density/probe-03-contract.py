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
BASE_REV = "HEAD"

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


def diff_removed_lines(before: str, after: str) -> list[str]:
    """改前后逐行 diff 里"被删掉且含中文"的行（文案零删除的判据）。"""
    proc = subprocess.run(
        ["git", "diff", "--no-color", "-U0", BASE_REV, "--", REL],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    removed = []
    for line in proc.stdout.splitlines():
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

    seq_before = tag_sequence(hwcheck_slice(before))
    seq_after = tag_sequence(hwcheck_slice(after))
    out.append("")
    out.append("== 2. 检测页 DOM 标签顺序 ==")
    out.append(f"  改前 {len(seq_before)} 个标签 / 改后 {len(seq_after)} 个")
    if seq_before == seq_after:
        out.append("  逐项相等 ✅")
    else:
        failed = True
        out.append("  **不相等**——第一处差异：")
        for i, (a, b) in enumerate(zip(seq_before, seq_after)):
            if a != b:
                out.append(f"    第 {i + 1} 项：改前 {a} / 改后 {b}")
                break
        if len(seq_before) != len(seq_after):
            out.append(f"    （长度不同：{len(seq_before)} vs {len(seq_after)}）")

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
    out.append(f"  · 本轮改动文件（{len(changed)} 个）：{changed or '（无）'}")
    if changed != [REL]:
        out.append("    ⚠ 与「只改 index.html」不符——请核对是否夹带了别的改动")

    report = "\n".join(out)
    print(report)
    if args.out:
        target = Path(__file__).resolve().parent / args.out
        target.write_text(report + "\n", encoding="utf-8")
        print(f"\n[落盘] {target}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
