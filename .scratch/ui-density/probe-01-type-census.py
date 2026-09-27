r"""排版碎片化读数（工单 ui-density/01 的改前 / 改后共用探针）。

量的是 `index.html` 内联样式块里的两件事，只读、可复跑：

1. **字号分布**：所有 `font-size: <n>px` 按值分组计数（含 `!important`）。
     —— 碎片化的证据：取值种类多、且绝大多数 ≤13px（不存在"正文"这一级）。
2. **间距令牌引用**：`var(--space-N)` 按 N 分组计数。
     —— 「挤」的证据：`--space-2`（8px）被当成唯一档用，`--space-6`（24px）一次不用。
3. **检测页样式段**（`hwcheck-*` / `my-device-*` 选择器所在行）单独量一遍：
     看这一页自己用了哪几个字号与间距档。

用法（本机控制台是 GBK，必须显式 UTF-8，否则 ✗ 这类字符会抛 UnicodeEncodeError 并丢掉证据文件）：

    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-01-type-census.py
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-01-type-census.py --out 改前.txt

判据是**读数本身**：本探针不判红绿，只保证改前 / 改后两次量的是同一把尺子。
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

FONT_RE = re.compile(r"font-size:\s*([0-9.]+)px")
SPACE_RE = re.compile(r"var\(--space-([0-9])\)")
# 检测页自己的选择器前缀（用类名前缀圈出来）。
# **刻意不含 `module-card`**：器件网格用的是与「模块库」页同一个组件，
# 改它就是在改别的页（属全站轮），本页读数里混进它会把"这一页改没改干净"看糊。
HWCHECK_RE = re.compile(r"(?:hwcheck|my-device)")
SECTION_RE = re.compile(r"<section id=\"tab-([a-z-]+)\"")
# 规则块：`选择器 { 声明 }`。@media / @keyframes 的外层花括号匹配不上，
# 内层规则照旧能匹配到——本探针只关心顶层那批 hwcheck 规则，够用。
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def _fmt_counter(counter: Counter[str], unit: str) -> list[str]:
    lines: list[str] = []
    for value, count in sorted(counter.items(), key=lambda kv: float(kv[0])):
        lines.append(f"  {value:>6} {unit}  x{count}")
    return lines


def census(text: str) -> dict[str, object]:
    fonts = Counter(FONT_RE.findall(text))
    spaces = Counter(SPACE_RE.findall(text))

    # 检测页那几段：**按选择器归属**——每条 `font-size` / `var(--space-N)` 记在
    # 它所在规则块的选择器名下，只留选择器里含 hwcheck / my-device 的那些。
    # （早先的"命中选择器后往下抓 12 行"会扫到隔壁规则，读数看着像没改干净。）
    hw_fonts: Counter[str] = Counter()
    hw_spaces: Counter[str] = Counter()
    hw_offenders: list[str] = []
    for selector, body in RULE_RE.findall(text):
        sel = " ".join(selector.split())
        if not HWCHECK_RE.search(sel):
            continue
        for value in FONT_RE.findall(body):
            hw_fonts[value] += 1
            hw_offenders.append(f"{sel} → font-size: {value}px")
        for value in SPACE_RE.findall(body):
            hw_spaces[value] += 1

    total = sum(fonts.values())
    small = sum(c for v, c in fonts.items() if float(v) <= 13)
    return {
        "fonts": fonts,
        "spaces": spaces,
        "hw_fonts": hw_fonts,
        "hw_spaces": hw_spaces,
        "hw_offenders": sorted(hw_offenders),
        "total": total,
        "small": small,
        "sections": SECTION_RE.findall(text),
    }


def render(data: dict[str, object]) -> str:
    fonts: Counter[str] = data["fonts"]  # type: ignore[assignment]
    spaces: Counter[str] = data["spaces"]  # type: ignore[assignment]
    hw_fonts: Counter[str] = data["hw_fonts"]  # type: ignore[assignment]
    hw_spaces: Counter[str] = data["hw_spaces"]  # type: ignore[assignment]
    out: list[str] = []
    out.append("== 全站字号分布（index.html 内联样式）==")
    out += _fmt_counter(fonts, "px")
    out.append(
        f"  小计：{len(fonts)} 种取值 / {data['total']} 处声明；"
        f"其中 ≤13px 共 {data['small']} 处"
        f"（占 {100 * int(data['small']) / max(1, int(data['total'])):.1f}%）"
    )
    out.append("")
    out.append("== 全站间距令牌引用 ==")
    out += [f"  --space-{k} ({int(k) * 4}px 档)  x{v}"
            for k, v in sorted(spaces.items(), key=lambda kv: int(kv[0]))]
    out.append("")
    out.append("== 检测页样式段（选择器含 hwcheck / my-device 的规则）==")
    out.append("  字号：")
    out += _fmt_counter(hw_fonts, "px") or ["    （无）"]
    offenders: list[str] = data["hw_offenders"]  # type: ignore[assignment]
    if offenders:
        out.append("  ⚠ 仍在用裸 px 字号的规则（改后应为空）：")
        out += [f"    {line}" for line in offenders]
    else:
        out.append("  ✅ 裸 px 字号 = 0（全部走 --fs-* 令牌）")
    out.append("  间距：")
    out += [f"  --space-{k}  x{v}" for k, v in sorted(hw_spaces.items(), key=lambda kv: int(kv[0]))]
    out.append("")
    out.append("== 页面清单（section id，用于确认量的是同一份文件）==")
    out.append("  " + " / ".join(data["sections"]))  # type: ignore[arg-type]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="读数落盘文件名（相对本目录）")
    parser.add_argument("--rev", default="", help="改前基线：从 git 对象读（如 HEAD），默认读工作树")
    args = parser.parse_args()

    if args.rev:
        import subprocess
        text = subprocess.run(
            ["git", "show", f"{args.rev}:src/contest_generator/static/index.html"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        source = f"git {args.rev}:{PAGE.relative_to(ROOT).as_posix()}"
    else:
        text = PAGE.read_text(encoding="utf-8")
        source = f"工作树 {PAGE.relative_to(ROOT).as_posix()}"

    report = f"[来源] {source}\n\n" + render(census(text))
    print(report)
    if args.out:
        target = Path(__file__).resolve().parent / args.out
        target.write_text(report + "\n", encoding="utf-8")
        print(f"\n[落盘] {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
