# -*- coding: utf-8 -*-
"""审计 v3：70 篇手册 — 是否自带「驱动实现源码」（非 main 演示 / 非移植片段）。

判定（针对每个代码围栏，正则作用于整块文本）：
- 提取函数定义（排除 C 关键字 if/for/while/switch/return/else/sizeof/do）；
- 非 main 函数集合 nonmain；
- has_impl：存在任一非 main 函数，函数体行数 >= 5（真实实现，排除空 init 桩）
  或 nonmain 中 >= 2 个函数（每个 >=1 行）；
- demo_only：有 main 演示调用了页内未定义的函数，但没有上述实现 → 网盘页。
输出每页：nonmain 函数（名:体行数）+ has_impl + demo + 是否有完整 .h 头（#ifndef guard 或 typedef）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
KEYWORDS = {"if", "for", "while", "switch", "return", "else", "do", "sizeof", "case"}
FUNC_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
MAIN_RE = re.compile(r"\b(?:void|int)\s+main\s*\(")
HDR_GUARD_RE = re.compile(r"#ifndef\s+\w+|typedef\s+struct|#include\s+[<\"]")


def blocks(md: str) -> list[str]:
    out, i, lines = [], 0, md.splitlines()
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            j, buf = i + 1, []
            while j < len(lines) and not FENCE_RE.match(lines[j]):
                buf.append(lines[j])
                j += 1
            out.append("\n".join(buf))
            i = j + 1
        else:
            i += 1
    return out


def func_bodies(blk: str) -> dict[str, int]:
    """函数名 -> 体行数（从函数头行到闭合括号所在行）。"""
    lines = blk.splitlines()
    res: dict[str, int] = {}
    for m in FUNC_RE.finditer(blk):
        name = m.group(1)
        if name in KEYWORDS or name == "main":
            continue
        start_line = blk[: m.start()].count("\n")
        # 从函数头开始找平衡括号
        depth, j, started = 0, start_line, False
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            if depth > 0:
                started = True
            if started and depth <= 0:
                break
            j += 1
        res.setdefault(name, max(j - start_line, 1))
    return res


def main() -> None:
    files = sorted(f for f in BATCH.glob("*.md") if f.name not in ("模块索引.md", "网盘索引.md"))
    rows = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        blks = blocks(text)
        funcs: dict[str, int] = {}
        for b in blks:
            funcs.update(func_bodies(b))
        has_impl = any(v >= 5 for v in funcs.values()) or len(funcs) >= 2 and sum(funcs.values()) >= 4
        demo = any(MAIN_RE.search(b) for b in blks)
        hdr = any(HDR_GUARD_RE.search(b) for b in blks)
        rows.append((f.stem, has_impl, demo, hdr, funcs))

    def cat(slug: str) -> str:
        for c in ("control", "rf", "screen", "sensor"):
            if (BATCH / f"{c}--{slug}.md").exists():
                return c
        return "?"

    need = []
    for slug, has_impl, demo, hdr, funcs in rows:
        fn = ", ".join(f"{k}:{v}" for k, v in sorted(funcs.items()))
        print(f"{cat(slug):<8} impl={'Y' if has_impl else 'N'} demo={'Y' if demo else 'N'} hdr={'Y' if hdr else 'N'}  {slug} | {fn}")
        if not has_impl:
            need.append((slug, demo, hdr, funcs))
    print()
    print(f"== 无实现源码（{len(need)} 篇，需网盘完整工程才能入库） ==")
    for slug, demo, hdr, funcs in need:
        print(f"- {slug}  demo={demo} hdr={hdr}")


if __name__ == "__main__":
    main()
