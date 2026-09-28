r"""工单 06 取证脚本（只读）：五页**渲染方在输出、样式里却没有**的类名（死类普查）。

为什么要它：README 坑 3（"标记里有、样式里没有"的死类没有任何守卫会报）与 05 单的账第 9 条
（`.warning` 就是那么被发现的）。这一趟的验收里有一条"健康 / 状态徽章统一"，而那族类名全是
JS 渲染的——先把"渲染了但没人给形状"的清出来，再决定补实还是记账。

判据（机械、保守）：
  · 取 `src/contest_generator/static/js/**` 里 `class="…"` / `classList.add("…")` /
    `className = "…"` 三类写法里的**类名**；
  · 只留本单相关前缀（见 PREFIXES）；
  · 与 `index.html` 的 `<style>` 块里出现过的类名比：CSS 里从未出现的 = **候选死类**；
  · 输出里带上"它出现在哪个 JS 文件"，方便人判是"该补形状"还是"该删标记"。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\probe-06-dead-classes.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JS = ROOT / "src" / "contest_generator" / "static" / "js"
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

PREFIXES = ("lib-", "module-", "mc-", "mi-", "ref-", "pdf-", "md-", "topic-",
            "add-", "file-row", "proofread", "dangling")

CLASS_ATTR = re.compile(r'''class=["']([^"'$<>]*)''')   # 不要求闭合引号：渲染方常写 `class="a b' + …`
CLASS_JS = re.compile(r'classList\.(?:add|remove|toggle)\("([\w-]+)"')
CLASS_SET = re.compile(r'className\s*=\s*"([\w\s-]+)"')


def main() -> int:
    css = PAGE.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", css, re.S).group(1)
    # **先剥注释再收类名**（06 单评审 Standards 抓到的判据漏洞：在含注释的全文上抓，
    # 类名只要在注释里被提过一句就算"CSS 里出现过"——06d 新加的注释就提了 `.topic-warn`）。
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css_classes = set(re.findall(r"\.([A-Za-z][\w-]*)", css))

    used: dict[str, set[str]] = defaultdict(set)
    for f in sorted(JS.rglob("*.js")):
        t = f.read_text(encoding="utf-8", errors="replace")
        names: set[str] = set()
        for m in CLASS_ATTR.finditer(t):
            names.update(m.group(1).split())
        names.update(CLASS_JS.findall(t))
        for m in CLASS_SET.finditer(t):
            names.update(m.group(1).split())
        for n in names:
            if n.startswith(PREFIXES):
                used[n].add(f.relative_to(ROOT).as_posix())

    dead = {n: v for n, v in used.items() if n not in css_classes}
    print(f"== 五页相关类名：渲染方用了 {len(used)} 个；其中 CSS（**已剥注释**）里从未出现的 {len(dead)} 个 ==")
    for n in sorted(dead):
        print(f"  {n:<28} ← {', '.join(sorted(x.split('/')[-1] for x in dead[n]))}")
    if not dead:
        print("  （无：这一族里没有'渲染了但没形状'的类名）")
    print("\n注：这一支是**取证**不是闸门（恒退出 0）——它只回答'哪些类名渲染了却没样式'，"
          "'该补形状还是本来就是 JS 挂钩'由人判（见工单 06 的账第 5 条）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
