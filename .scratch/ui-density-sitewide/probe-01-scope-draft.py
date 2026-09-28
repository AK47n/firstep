r"""分区读数 + 明细（工单 ui-density-sitewide 每单施工用，只读）。

**单一出处**：分区表与进度清单从守卫 `tests/js/css-tokens.test.mjs` 解析
（`PAGE_SCOPES` 格式固定 `["id", /正则/],` 一行一条；`SITEWIDE_BACKLOG` 是 id 字符串列表）
——改守卫就等于改这把尺子，两处不会各说各话。

三种用法：

    # 总账：每个作用域的规则数 / 裸 px 字号 / 完整描边 / 裸令牌间距值
    python .scratch\ui-density-sitewide\probe-01-scope-draft.py

    # 某一页的裸字号明细（施工清单）
    python .scratch\ui-density-sitewide\probe-01-scope-draft.py --show shell --kind fonts

    # 某一页的裸令牌间距值 / 完整描边明细（拆框与间距令牌化用）
    python .scratch\ui-density-sitewide\probe-01-scope-draft.py --show shell --kind spaces
    python .scratch\ui-density-sitewide\probe-01-scope-draft.py --show shell --kind borders

    # 内联 style 属性里的裸字号（不在样式块里，按出现行列出）
    python .scratch\ui-density-sitewide\probe-01-scope-draft.py --kind inline
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"

TOKEN_VALUES = {4, 8, 12, 16, 20, 24}
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
FONT_RE = re.compile(r"font-size:\s*([0-9.]+)px")
SPACE_RE = re.compile(r"(?:padding|margin|gap)(?:-top|-right|-bottom|-left)?:\s*([^;]+);")
BORDER_RE = re.compile(r"(?<![\w-])border(?:-(?:top|right|bottom|left))?:\s*([^;]+);")


def load_scopes() -> list[tuple[str, re.Pattern[str]]]:
    """从守卫源码解析分区表（单一出处；守卫那边格式是 `["id", /正则/],`）。"""
    text = GUARD.read_text(encoding="utf-8")
    block = re.search(r"const PAGE_SCOPES = \[(.*?)\n\];", text, re.S)
    if not block:
        raise SystemExit("守卫里找不到 PAGE_SCOPES —— 解析失败，别拿空表当读数")
    scopes = [(m.group(1), re.compile(m.group(2)))
              for m in re.finditer(r'\["([\w-]+)", /(.*?)/\]', block.group(1))]
    if not scopes:
        raise SystemExit("PAGE_SCOPES 解析出 0 条 —— 格式变了，改本探针")
    return scopes


def load_backlog() -> list[str]:
    """进度清单（页面尺）——**条目数本身就是进度**，读数里必须带上它。"""
    text = GUARD.read_text(encoding="utf-8")
    block = re.search(r"const SITEWIDE_BACKLOG = new Set\(\[(.*?)\]\);", text, re.S)
    if not block:
        raise SystemExit("守卫里找不到 SITEWIDE_BACKLOG —— 格式变了，改本探针")
    return re.findall(r'"([\w-]+)"', block.group(1))


def scope_of(sel: str, scopes: list[tuple[str, re.Pattern[str]]]) -> str:
    for name, rx in scopes:
        if rx.search(sel):
            return name
    return scopes[-1][0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--show", default="", help="作用域 id（shell / components / generate …）")
    ap.add_argument("--kind", default="", choices=["", "fonts", "spaces", "borders", "inline"])
    args = ap.parse_args()

    text = PAGE.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", text, re.S)
    css = css.group(1) if css else ""
    offset = text[: text.index(css)].count("\n") + 1 if css else 0
    scopes = load_scopes()

    out: list[str] = []

    if args.kind == "inline":
        out.append("== 内联 style 属性里的裸字号（不在样式块里，站点腿看不到、只有取值尺看得到）==")
        for i, line in enumerate(text.splitlines(), 1):
            for m in re.finditer(r'style="[^"]*font-size:\s*([0-9.]+)px', line):
                out.append(f"  L{i}: {m.group(1)}px  |  {line.strip()[:120]}")
        report = "\n".join(out)
        print(report)
        if args.out:
            (Path(__file__).resolve().parent / args.out).write_text(report + "\n", encoding="utf-8")
        return 0

    rules: list[tuple[int, str, str]] = []
    for m in RULE_RE.finditer(css):
        sel = " ".join(m.group(1).split())
        rules.append((offset + css[: m.start()].count("\n"), sel, m.group(2)))

    if args.show and args.kind:
        out.append(f"== {args.show} 作用域的 {args.kind} ==")
        for line_no, sel, body in rules:
            if scope_of(sel, scopes) != args.show:
                continue
            if args.kind == "fonts":
                hits = FONT_RE.findall(body)
                if hits:
                    out.append(f"  L{line_no}  {sel}  →  {'/'.join(hits)}px")
            elif args.kind == "spaces":
                vals = [n for sm in SPACE_RE.finditer(body) for n in re.findall(r"(\d+)px", sm.group(1))
                        if int(n) in TOKEN_VALUES]
                if vals:
                    out.append(f"  L{line_no}  {sel}  →  {', '.join(v + 'px' for v in vals)}")
            elif args.kind == "borders":
                vals = [d.group(1).strip() for d in BORDER_RE.finditer(body)
                        if d.group(1).strip() not in ("none", "transparent")]
                if vals:
                    out.append(f"  L{line_no}  {sel}  →  {'; '.join(vals)}")
        report = "\n".join(out)
        print(report)
        if args.out:
            (Path(__file__).resolve().parent / args.out).write_text(report + "\n", encoding="utf-8")
        return 0

    counters = {name: Counter() for name, _ in scopes}
    for _, sel, body in rules:
        name = scope_of(sel, scopes)
        c = counters[name]
        c["rules"] += 1
        c["fonts"] += len(FONT_RE.findall(body))
        c["borders"] += sum(1 for d in BORDER_RE.finditer(body)
                            if d.group(1).strip() not in ("none", "transparent"))
        c["spaces"] += sum(1 for sm in SPACE_RE.finditer(body)
                           for n in re.findall(r"(\d+)px", sm.group(1)) if int(n) in TOKEN_VALUES)

    out.append(f"{'scope':<12}{'rules':>7}{'bareFont':>10}{'borders':>9}{'bareSpace':>11}")
    tot = Counter()
    for name, _ in scopes:
        c = counters[name]
        out.append(f"{name:<12}{c['rules']:>7}{c['fonts']:>10}{c['borders']:>9}{c['spaces']:>11}")
        tot.update(c)
    out.append(f"{'合计':<12}{tot['rules']:>7}{tot['fonts']:>10}{tot['borders']:>9}{tot['spaces']:>11}")
    backlog = load_backlog()
    done = [n for n, _ in scopes if n not in backlog]
    out.append("")
    out.append(f"页面尺 SITEWIDE_BACKLOG = {len(backlog)} 条（还剩这些没做完）：{', '.join(backlog)}")
    out.append(f"          已完工 = {len(done)} 条：{', '.join(done)}")
    inline = len(re.findall(r'style="[^"]*font-size:\s*[0-9.]+px', text))
    out.append(f"另有内联 style 属性里的裸字号 {inline} 处（不在样式块里，见 --kind inline）")
    out.append(f"全站 font-size 声明总处数（样式块 + 内联）: "
               f"{len(FONT_RE.findall(text))}；裸样式块内 {sum(counters[n]['fonts'] for n, _ in scopes)}")

    report = "\n".join(out)
    print(report)
    if args.out:
        target = Path(__file__).resolve().parent / args.out
        target.write_text(report + "\n", encoding="utf-8")
        print(f"\n[落盘] {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
