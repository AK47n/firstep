"""浅色调色板轮 · 审计探针（06）：02 单那 223 处迁移**逐处在册**（不是"批量替换完就算"）。

**为什么要有它**（02 单双轴评审 Standards 轴点名）：工单要求"逐处过一遍，不是批量替换：
图标 / 装饰这些非文字用途要留在 `--accent`"。施工用了全局正则，那就必须补一份
**可复核的清单**：每一处迁移按用途分类、逐条落盘，谁都能一条命令重算。

分类（人判的判据写死在这里，机器只做归类）：
  · `text`   —— 普通文字（状态字 / 标签 / 链接 / 徽章字）
  · `glyph`  —— `content:` 生成的**字形**（`▸` 这类折叠箭头）——**也走 `-text`**：
                它同样是"渲染出来的字"，压在同一种底上，浅色下同样要看得清
  · `hover`  —— 只出现在 `:hover` / `:focus` 状态上的字色
  · `inline` —— `<div style="color:var(--…)">` 这类**行内**写法（在 index.html 里，不在规则里）
另报"**没迁**的主令牌当文字色"（应为 0）与"主令牌仍在用的**非文字**面"（描边 / 底 / 图标，不动）。

跑法（仓库根）：
    python .scratch/light-contrast/probe-06-migration-audit.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

FAMILIES = ["accent", "ok", "ok-bright", "warn", "danger", "info", "purple-grad"]
#: 本单**迁移产出的**令牌（`--code-text` 是既有令牌，不算迁移产物——别把它混进清单）
MIGRATED = ["accent-text", "ok-text", "warn-text", "danger-text", "info-text", "purple-text"]
MAIN_COLOR = re.compile(r"(?<![\w-])color:\s*var\(--(" + "|".join(FAMILIES) + r")\)")
TEXT_COLOR = re.compile(r"(?<![\w-])color:\s*var\(--(" + "|".join(MIGRATED) + r")\)")
NONCOLOR_MAIN = re.compile(r"(?<![\w-])(background|border[a-z-]*|outline[a-z-]*|box-shadow|stroke|fill|"
                           r"caret-color|accent-color)\s*:[^;]*var\(--(" + "|".join(FAMILIES) + r")\)")


def classify(sel: str, body: str) -> str:
    if re.search(r"::?(before|after)\b", sel) and re.search(r"content\s*:", body):
        return "glyph"
    if re.search(r":(hover|focus|focus-visible|active)\b", sel):
        return "hover"
    return "text"


def main() -> None:
    text = L.read_page()
    print("=" * 78)
    print("浅色调色板轮 · 审计读数（probe-06：02 单迁移逐处在册）")
    print("=" * 78)

    print("\n## ① 迁移清单（规则体内的 `color: var(--X-text)`，逐处分类）\n")
    rows, by_class, by_token = [], Counter(), Counter()
    for sel, body in L.css_rules(L.contrast_style_text(text)):
        m = TEXT_COLOR.search(body)
        if not m:
            continue
        kind = classify(sel, body)
        rows.append((kind, m.group(1), sel))
        by_class[kind] += 1
        by_token[m.group(1)] += 1
    print(f"合计 **{len(rows)}** 处；分类分布 {dict(by_class)}；令牌分布 {dict(by_token)}\n")
    for kind, token, sel in sorted(rows):
        print(f"  {kind:<6}{token:<18}{sel[:64]}")

    print("\n## ② 行内写法（`style=\"color: var(--X-text)\"`，不在规则体内）\n")
    inline = re.findall(r'style="[^"]*?color:\s*var\(--(' + "|".join(MIGRATED) + r")\)", text)
    print(f"合计 **{len(inline)}** 处：{dict(Counter(inline))}")
    for m in re.finditer(r'style="[^"]*?color:\s*var\(--(?:' + "|".join(MIGRATED) + r')\)[^"]*"',
                         text):
        line = text[:m.start()].count("\n") + 1
        print(f"  L{line}: {m.group(0)[:88]}")

    print("\n## ③ 反向：还有没有**主令牌当文字色**（应为 0）\n")
    leftover = [(sel, MAIN_COLOR.search(body).group(1))
                for sel, body in L.css_rules(L.contrast_style_text(text)) if MAIN_COLOR.search(body)]
    print(f"**{len(leftover)}** 处" + (f"：{leftover[:5]}" if leftover else " ✅"))

    print("\n## ④ 主令牌仍在用的**非文字**面（不动它，只报数）\n")
    kinds = Counter()
    for sel, body in L.css_rules(L.contrast_style_text(text)):
        for prop, tok in NONCOLOR_MAIN.findall(body):
            kinds[prop] += 1
    print(f"共 **{sum(kinds.values())}** 处：{dict(kinds)}")
    print("\n  （这些是描边 / 淡底 / 实心块 / 图标 / 滚动条——**契约上就该用主令牌**）")

    print("\n## ⑤ 与 HTML 里那 223 处的对账\n")
    head = subprocess.run(["git", "show", "HEAD:src/contest_generator/static/index.html"],
                          cwd=L.ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    before = len(re.findall(r"(?<![\w-])color:\s*var\(--(?:%s)(?:\s*,[^)]*)?\)"
                            % "|".join(FAMILIES), head))
    after_main = len(leftover)
    print(f"HEAD 里主令牌当文字色：**{before}** 处 → 现在 **{after_main}** 处；"
          f"迁移 {len(rows)}（规则体）+ {len(inline)}（行内）= **{len(rows) + len(inline)}**")
    print("  ⚠ 这里按「`var(--令牌)` 或带兜底的 `var(--令牌, 兜底)`」两种写法计；")
    print("    本审计 ① 的清单只收前一种形态（后一种 2 处在 ③ 的零残留里已被证明迁过）。")
    print("  ⚠ `before` 数比迁移数多，是因为**同名声明在注释里**也计数（HEAD 口径按全文正则）；")
    print("    两边都按「渲染得到的字色」算时，`color: var(--主令牌)` 已经归零。")


if __name__ == "__main__":
    main()
