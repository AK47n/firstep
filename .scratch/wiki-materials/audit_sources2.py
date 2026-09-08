# -*- coding: utf-8 -*-
"""审计 v2：70 篇立创 wiki 手册 → 是否有「完整驱动实现源码」（非 main 演示/非移植片段）。

判据（代码围栏内）：
- has_driver_impl：存在一个代码块，含 ≥2 个非 main 函数定义且每个函数体 ≥10 行，
  或 ≥1 个非 main 函数体 ≥25 行（真实驱动实现特征）；
- demo_main：代码块含 main(；
- netdisk_need_hint：正文明确写「例程下载见/网盘下载」（完整工程在网盘）；
- frag_only：以上都不是。

同时输出页面里所有代码块的函数名清单，便于人工复核。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
FUNC_HDR_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
MAIN_RE = re.compile(r"\b(?:void|int)\s+main\s*\(")


def blocks(md: str) -> list[str]:
    out, lines, i = [], md.splitlines(), 0
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
    """返回 {函数名: 函数体行数}（粗算：头行到函数结束，按缩进闭合括号计数）。"""
    lines = blk.splitlines()
    res: dict[str, int] = {}
    i = 0
    while i < len(lines):
        m = FUNC_HDR_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        depth = 0
        j = i
        started = False
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            if depth > 0:
                started = True
            if started and depth <= 0:
                break
            j += 1
        res[name] = j - i
        i = max(j, i + 1)
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
        non_main = {k: v for k, v in funcs.items() if k != "main"}
        impl_lines = [v for v in non_main.values() if v >= 10]
        driver = len(non_main) >= 2 and len(impl_lines) >= 2 or len(impl_lines) >= 1 and max(impl_lines) >= 25
        demo = any(MAIN_RE.search(b) for b in blks)
        netdisk = bool(re.search(r"(例程.*(下载|路径)|(下载|链接).*例程|百度网盘.*下载)", text))
        rows.append((f.stem, driver, demo, netdisk, funcs))

    def cat(slug: str) -> str:
        for c in ("control", "rf", "screen", "sensor"):
            if (BATCH / f"{c}--{slug}.md").exists():
                return c
        return "?"

    print(f"{'分类':<8} {'驱动源码':<6} {'main演示':<7} {'网盘提示':<6} 页名 / 代码函数")
    for slug, driver, demo, netdisk, funcs in rows:
        fn = ", ".join(f"{k}:{v}" for k, v in sorted(funcs.items()))
        print(f"{cat(slug):<8} {'YES' if driver else 'no ':<6} {'yes' if demo else 'no ': <7} {'yes' if netdisk else 'no ': <6} {slug} | {fn}")
    print()
    no_drv = [r for r in rows if not r[1]]
    print(f"无完整驱动实现源码的页（{len(no_drv)}）：")
    for slug, driver, demo, netdisk, funcs in no_drv:
        print(f"  - {slug} | 网盘提示={netdisk} | 函数={', '.join(f'{k}:{v}' for k, v in sorted(funcs.items()))}")


if __name__ == "__main__":
    main()
