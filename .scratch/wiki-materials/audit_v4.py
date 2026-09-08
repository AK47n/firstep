# -*- coding: utf-8 -*-
"""审计 v4：70 篇手册 — 判定「页内自包含完整源码」。

规则：
- defined = 页内代码块中定义的函数名（排除 C 关键字与 main，任意函数体）；
- called = main 演示代码块里被调用的名字（排除类型名/关键字/常用库函数与 board_init/delay_ms/printf）；
- 若 called ⊆ defined∪allowlist → 自包含（可直接提炼入库，无需网盘）；
- 若 called 有未定义项 → 演示依赖页外源码（厂家例程在网盘）→ 需网盘。
输出两类清单 + 每页明细。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
KEYWORDS = {"if", "for", "while", "switch", "return", "else", "do", "sizeof", "case", "int", "char", "void", "unsigned", "uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t", "int32_t", "uint8_t", "float", "double", "short", "long", "struct", "typedef", "enum", "const", "static", "register", "volatile", "u8", "u16", "u32", "u64", "s8", "s16", "s32"}
ALLOW = {"printf", "delay_ms", "board_init", "sprintf", "memset", "memcpy", "strcpy", "strlen", "strcmp", "Delay", "SysTick_Delay", "delay", "delay_us", "Delay_ms", "Delay_us"}
FUNC_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
MAIN_RE = re.compile(r"\b(?:void|int)\s+main\s*\([^)]*\)\s*\{")
CALL_RE = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*\(")


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


def main() -> None:
    files = sorted(f for f in BATCH.glob("*.md") if f.name not in ("模块索引.md", "网盘索引.md"))
    need = []
    ok = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        blks = blocks(text)
        defined = set()
        for b in blks:
            for m in FUNC_RE.finditer(b):
                n = m.group(1)
                if n not in KEYWORDS and n != "main":
                    defined.add(n)
        main_blk = ""
        for b in blks:
            if MAIN_RE.search(b):
                main_blk = b
                break
        if main_blk:
            body = main_blk[main_blk.index("{") + 1:] if "{" in main_blk else main_blk
            called = set(CALL_RE.findall(body)) - KEYWORDS - ALLOW - defined
        else:
            called = set()
        missing = sorted(called)
        (need if missing else ok).append((f.stem, sorted(defined), missing))

    def cat(slug: str) -> str:
        for c in ("control", "rf", "screen", "sensor"):
            if (BATCH / f"{c}--{slug}.md").exists():
                return c
        return "?"

    print(f"== 自包含（{len(ok)}），可直接提炼入库 ==")
    for slug, defined, _ in ok:
        print(f"  {slug}")
    print()
    print(f"== 需网盘完整工程（{len(need)}），main 调用页外函数 ==")
    for slug, defined, missing in need:
        print(f"  {slug}  ← 未定义调用: {', '.join(missing[:12])}{' ...' if len(missing) > 12 else ''}")


if __name__ == "__main__":
    main()
