r"""全站推广轮开工前的摸底读数（只读，不判红绿）。

量 `index.html` 的三件事，按**页面作用域**分组：

1. 每个 `<section id="tab-*">` 的字节数与行数（工作量）。
2. 样式块里每条规则的选择器落在哪个页面的作用域（用 `#tab-xxx` 前缀判定），
   统计该页面的裸 px 字号 / 裸令牌间距值（改前家底）。
3. 全站裸 `font-size` 取值分布（与 `FROZEN_FONT_SIZES` 对照）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\probe-00-survey.py
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

SECTION_RE = re.compile(r'<section id="tab-([a-z0-9-]+)"')
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
FONT_RE = re.compile(r"font-size:\s*([0-9.]+)px")
TOKEN_VALUES = {4, 8, 12, 16, 20, 24}
TAB_RE = re.compile(r"#tab-([a-z0-9-]+)")


def sections(text: str) -> list[tuple[str, int, int]]:
    """返回 [(名字, 起, 止)]——每段到下一个 section 或文件末尾。"""
    marks = [(m.group(1), m.start()) for m in SECTION_RE.finditer(text)]
    out = []
    for i, (name, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out.append((name, start, end))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    text = PAGE.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []

    out.append("== 1. 页面（section id）体量 ==")
    total = 0
    for name, start, end in sections(text):
        chunk = text[start:end]
        n = chunk.count("\n")
        total += n
        out.append(f"  tab-{name:<12} {len(chunk.encode('utf-8')):>7} B  {n:>5} 行")
    out.append(f"  合计 {total} 行 / 文件 {len(lines)} 行")

    # 样式块范围
    styles = [(m.start(), m.end()) for m in re.finditer(r"<style>.*?</style>", text, re.S)]
    out.append("")
    out.append(f"== 2. 样式块 {len(styles)} 个，合计 "
               f"{sum(b - a for a, b in styles)} B ==")

    # 按作用域归并规则
    scope_fonts: dict[str, list[str]] = defaultdict(list)
    scope_spaces: dict[str, list[str]] = defaultdict(list)
    scope_rules: Counter[str] = Counter()
    unscoped_fonts = 0
    for a, b in styles:
        css = text[a:b]
        for m in RULE_RE.finditer(css):
            sel = " ".join(m.group(1).split())
            body = m.group(2)
            tabs = TAB_RE.findall(sel)
            key = ",".join(f"tab-{t}" for t in dict.fromkeys(tabs)) if tabs else "（无页面前缀）"
            scope_rules[key] += 1
            for v in FONT_RE.findall(body):
                scope_fonts[key].append(f"{sel} → {v}px")
                if not tabs:
                    unscoped_fonts += 1
            for sm in re.finditer(r"(?:padding|margin|gap)(?:-top|-right|-bottom|-left)?:\s*([^;]+);", body):
                for n in re.findall(r"(\d+)px", sm.group(1)):
                    if int(n) in TOKEN_VALUES:
                        scope_spaces[key].append(f"{sel} → {n}px")

    out.append("")
    out.append("== 3. 按作用域的规则数 / 裸 px 字号 / 裸令牌间距（改前家底）==")
    keys = sorted(scope_rules, key=lambda k: -len(scope_fonts[k]))
    for key in keys:
        out.append(
            f"  {key:<28} 规则 {scope_rules[key]:>4}  裸字号 {len(scope_fonts[key]):>3}"
            f"  裸令牌间距 {len(scope_spaces[key]):>3}"
        )
    out.append("")
    out.append(f"  其中**不带任何 `#tab-` 前缀**的规则里的裸字号：{unscoped_fonts} 处"
               "（全局基类 / 组件，属全站轮的核心）")

    out.append("")
    out.append("== 4. 全站裸字号取值分布（对照 FROZEN_FONT_SIZES）==")
    allfonts = Counter(FONT_RE.findall(text))
    for v, c in sorted(allfonts.items(), key=lambda kv: float(kv[0])):
        out.append(f"  {v:>6}px  x{c}")
    frozen = {"8", "11", "11.5", "12", "12.5", "13", "14", "15", "16", "16.5", "18", "20", "30"}
    out.append(f"  取值 {len(allfonts)} 种；清单外：{sorted(set(allfonts) - frozen) or '（无）'}")
    out.append(f"  --fs-* 令牌引用：{len(re.findall(r'var\(--fs-', text))} 处")

    report = "\n".join(out)
    print(report)
    if args.out:
        target = Path(__file__).resolve().parent / args.out
        target.write_text(report + "\n", encoding="utf-8")
        print(f"\n[落盘] {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
