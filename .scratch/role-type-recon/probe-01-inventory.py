# -*- coding: utf-8 -*-
"""recon：static/js/** 里「模板变量拼出来的内联取色」有多少处、什么形态。

口径（三条，与新腿⑨ 的认人面讨论同一把尺）：
  A. **字面令牌**：`color:var(--x)` —— 现腿⑨ 认得的（对照用）。
  B. **模板变量**：`color:${...}` / `background:${...}` / `border:1px solid ${...}` —— 现腿⑨ 认不到。
  C. **表驱动来源**：B 里的 `${st[...]}` 出自哪张表（本仓 = generate-pins.js 的 PIN_TYPE_STYLE）。

输出：逐文件计数 + 逐行明细 + PIN_TYPE_STYLE 表盘上实况 + 该族令牌在两主题下的现算比值。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JS = REPO / "src" / "contest_generator" / "static" / "js"
HTML = REPO / "src" / "contest_generator" / "static" / "index.html"

LITERAL_RE = re.compile(r"(?<![\w-])(color|background|background-color)\s*:\s*var\((--[a-z0-9-]+)\)")
TEMPLATE_RE = re.compile(r"(?<![\w-])(color|background|background-color|border)\s*:\s*[^;\"']*\$\{")
STYLE_ATTR_RE = re.compile(r"style=\"[^\"]*\$\{")


def js_files():
    return sorted(p for p in JS.rglob("*.js") if p.is_file())


def scan():
    literal, template = [], []
    for p in js_files():
        rel = p.relative_to(JS).as_posix()
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if LITERAL_RE.search(line):
                literal.append((rel, i, line.strip()))
            if TEMPLATE_RE.search(line):
                template.append((rel, i, line.strip()))
    return literal, template


# --- 颜色数学（与守卫同源：sRGB 相对亮度 + WCAG 比值） -----------------------
def _lin(v: float) -> float:
    s = v / 255.0
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def lum(rgb) -> float:
    r, g, b = (_lin(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def over(fg, bg):
    a = fg[3] if len(fg) > 3 else 1.0
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


def parse_color(raw: str):
    raw = raw.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", raw)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([^)]*)\)", raw)
    if m:
        parts = [x.strip() for x in m.group(1).replace("/", " ").split(",")]
        nums = [float(x) for x in parts[:3]]
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return (nums[0], nums[1], nums[2], a)
    return None


def token_tables(html_text: str):
    """两主题令牌表（解析面 = 全部 :root 块，后者覆盖前者；亮色块覆盖）——与腿⑧/⑨ 同口径。"""
    blocks = {}
    for m in re.finditer(r"\n {2}:root \{([\s\S]*?)\n {2}\}", html_text):
        for t in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", m.group(1)):
            blocks.setdefault("dark", {})[t.group(1)] = t.group(2).strip()
    for m in re.finditer(r"\n {2}html\[data-theme=\"light\"\] \{([\s\S]*?)\n {2}\}", html_text):
        for t in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", m.group(1)):
            blocks.setdefault("light", {})[t.group(1)] = t.group(2).strip()
    return {
        "dark": blocks.get("dark", {}),
        "light": {**blocks.get("dark", {}), **blocks.get("light", {})},
    }


def resolve(name: str, table: dict, depth: int = 0):
    if depth > 6 or name not in table:
        return None
    raw = table[name]
    m = re.fullmatch(r"var\((--[a-z0-9-]+)(?:\s*,[^)]*)?\)", raw.strip())
    if m:
        return resolve(m.group(1), table, depth + 1)
    return parse_color(raw)


def main() -> int:
    out = []
    literal, template = scan()
    out.append("=" * 100)
    out.append("§1 内联取色盘点（static/js/**，口径：字面令牌 vs 模板变量）")
    out.append("=" * 100)
    out.append(f"A. 字面 `color/background:var(--token)`：{len(literal)} 处（= 现腿⑨ 的认人面，应为 19~21）")
    per_file = {}
    for rel, i, _ in literal:
        per_file[rel] = per_file.get(rel, 0) + 1
    for rel, n in sorted(per_file.items()):
        out.append(f"     {rel}: {n}")
    out.append("")
    out.append(f"B. 模板变量取色（`prop: …${{…}}`）：{len(template)} 处")
    per_file = {}
    for rel, i, _ in template:
        per_file[rel] = per_file.get(rel, 0) + 1
    for rel, n in sorted(per_file.items()):
        out.append(f"     {rel}: {n}")
    out.append("")
    out.append("  逐行明细：")
    for rel, i, line in template:
        out.append(f"  {rel}:{i}  {line[:150]}")
    out.append("")

    out.append("=" * 100)
    out.append("§2 PIN_TYPE_STYLE 表盘上实况（角色类型 → 令牌对）")
    out.append("=" * 100)
    src = (JS / "ui" / "generate-pins.js").read_text(encoding="utf-8")
    block = re.search(r"const PIN_TYPE_STYLE = \{([\s\S]*?)\n\};", src).group(1)
    # ⚠ `[a-z0-9-]` 里的数字不能少：`--pin-i2c` 带数字（第一版写成 `[a-z-]`，i2c 整族被静默漏掉）
    table_rows = re.findall(
        r"(\w+)\s*:\s*\[\s*\"(var\(--pin-[a-z0-9-]+\))\"\s*,\s*\"(var\(--pin-[a-z0-9-]+\))\"\s*\]",
        block)
    table_rows = [(t, f[len("var("):-1], b[len("var("):-1]) for t, f, b in table_rows]
    for t, fg, bg in table_rows:
        out.append(f"  {t:<10} {fg:<16} {bg}")
    out.append(f"  共 {len(table_rows)} 条（类型 → 色对）；去重后色对数 = "
               f"{len({(a, b) for _, a, b in table_rows})}")

    out.append("")
    out.append("=" * 100)
    out.append("§3 该族令牌在两主题下的比值（.role-type 的真几何：字 = 主色，底 = dim 色叠在 --panel-2 上）")
    out.append("=" * 100)
    tables = token_tables(HTML.read_text(encoding="utf-8"))
    seen = []
    for _, fg, bg in table_rows:
        if (fg, bg) not in seen:
            seen.append((fg, bg))
    out.append(f"  {'色对':<34}{'dark':>10}{'light':>10}   （阈值 4.5）")
    for fg, bg in seen:
        row = f"  {fg + ' / ' + bg:<34}"
        for theme in ("dark", "light"):
            t = tables[theme]
            f = resolve(fg, t)
            b = resolve(bg, t)
            base = resolve("--panel-2", t)
            if not f or not b or not base:
                row += f"{'解不出':>10}"
                continue
            bg_eff = over(b, base)
            r = ratio(over(f, bg_eff), bg_eff)
            row += f"{r:>10.2f}"
        out.append(row)
    out.append("")
    out.append("  对照：底换成 --panel（机械面口径）")
    for fg, bg in seen:
        row = f"  {fg + ' / ' + bg:<34}"
        for theme in ("dark", "light"):
            t = tables[theme]
            f = resolve(fg, t)
            b = resolve(bg, t)
            base = resolve("--panel", t)
            if not f or not b or not base:
                row += f"{'解不出':>10}"
                continue
            bg_eff = over(b, base)
            r = ratio(over(f, bg_eff), bg_eff)
            row += f"{r:>10.2f}"
        out.append(row)

    out.append("")
    out.append("=" * 100)
    out.append("§4 同一族色当**无底色文字**（`已绑 X` / `现绑 X` 那两个 span，底 = --panel-2）")
    out.append("=" * 100)
    out.append(f"  {'主色':<20}{'dark':>10}{'light':>10}   （阈值 4.5）")
    for fg, _ in seen:
        row = f"  {fg:<20}"
        for theme in ("dark", "light"):
            t = tables[theme]
            f = resolve(fg, t)
            base = resolve("--panel-2", t)
            if not f or not base:
                row += f"{'解不出':>10}"
                continue
            row += f"{ratio(f, base):>10.2f}"
        out.append(row)

    out.append("")
    out.append("=" * 100)
    out.append("§5 同族**色点**（图例 / 菜单 dot，非文字：主色 vs --panel-2，阈值 3.0）")
    out.append("=" * 100)
    out.append(f"  {'主色':<20}{'dark':>10}{'light':>10}")
    for fg, _ in seen:
        row = f"  {fg:<20}"
        for theme in ("dark", "light"):
            t = tables[theme]
            f = resolve(fg, t)
            base = resolve("--panel-2", t)
            if not f or not base:
                row += f"{'解不出':>10}"
                continue
            row += f"{ratio(f, base):>10.2f}"
        out.append(row)

    text = "\n".join(out)
    print(text)
    dest = Path(__file__).with_suffix(".txt")
    dest.write_text(text + "\n", encoding="utf-8")
    print(f"\n[落盘] {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
