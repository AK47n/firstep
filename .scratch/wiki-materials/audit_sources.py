# -*- coding: utf-8 -*-
"""审计：70 篇立创 wiki 手册 vs 模块库入库状态。

对每篇手册：
- 提取代码围栏（``` 块）；
- 判定「是否自带完整驱动源码」：任一代码块同时满足
  (a) 含 `#include "` 或 `#include <`（真实 C 文件特征），且
  (b) 行数 >= 25，且
  (c) 含函数定义形态（`xxx(` 后跟 `{`，且行内含 return / 赋值 / 调用之一）。
- 判定「是否有 main.c 演示」：任一代码块含独立 main( 调用形态。
- 输出每篇分类：FULL（自带完整源码）/ FRAG（仅片段）/ NONE。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"
LIB = Path(__file__).resolve().parents[2] / "library" / "modules"

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
INCLUDE_RE = re.compile(r'#\s*include\s*[<"]')
FUNC_DEF_RE = re.compile(r"^\s*(?:[A-Za-z_][\w\s\*]*\s+)?[A-Za-z_]\w*\s*\([^;]*\)\s*\{", re.M)
MAIN_RE = re.compile(r"\b(?:void|int)\s+main\s*\(")


def code_blocks(md: str) -> list[str]:
    blocks: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            j = i + 1
            buf: list[str] = []
            while j < len(lines) and not FENCE_RE.match(lines[j]):
                buf.append(lines[j])
                j += 1
            blocks.append("\n".join(buf))
            i = j + 1
        else:
            i += 1
    return blocks


def classify(md: str) -> tuple[str, str]:
    blocks = code_blocks(md)
    if not blocks:
        return "NONE", ""
    has_full = False
    main_demo = False
    for b in blocks:
        n = len([l for l in b.splitlines() if l.strip()])
        if n >= 25 and INCLUDE_RE.search(b) and FUNC_DEF_RE.search(b):
            has_full = True
        if MAIN_RE.search(b):
            main_demo = True
    lines = [l for l in md.splitlines() if l.strip() and not FENCE_RE.match(l)]
    has_main_txt = any("main(" in l and "int main" in l.replace(" ", "").replace("\t", "") or "main(" in l and ("void main" in l or "int main" in l) for l in lines)
    if has_full:
        return "FULL", ("含 main 演示" if (main_demo or has_main_txt) else "纯库文件")
    # 片段判定：含 #define 引脚宏 / typedef 之类
    if any(INCLUDE_RE.search(b) for b in blocks):
        return "FRAG+INC", ""
    if any(FUNC_DEF_RE.search(b) for b in blocks):
        return "FRAG+FUNC", ""
    return "FRAG", ""


def main() -> None:
    slug_by_file: dict[str, str] = {}
    idx = (BATCH / "模块索引.md").read_text(encoding="utf-8")
    for m in re.finditer(r"- ([A-Za-z0-9\-]+)：\[原页\]", idx):
        slug_by_file[m.group(1)] = m.group(1)
    # 文件名 → slug
    files = sorted(f for f in BATCH.glob("*.md") if f.name not in ("模块索引.md", "网盘索引.md"))

    lib_slugs = sorted(d.name for d in LIB.iterdir() if d.is_dir())
    print("== 模块库现有条目 ==")
    print(" | ".join(lib_slugs))
    print()

    rows: list[tuple[str, str, str, list[str]]] = []
    for f in files:
        slug = f.stem.split("--", 1)[-1]
        text = f.read_text(encoding="utf-8")
        cls, extra = classify(text)
        # 找语义相近的库条目
        near = []
        key = slug.lower()
        for ls in lib_slugs:
            k = ls.lower()
            words = re.split(r"[^a-z0-9]+", key)
            if any(len(w) >= 4 and (w in k or k in w) for w in words):
                near.append(ls)
            elif any(w[0] in k for w in words if len(w) >= 5):
                near.append(ls)
        rows.append((slug, cls, extra, sorted(set(near))))

    cat_order = ["control", "rf", "screen", "sensor"]
    def cat_of(slug: str) -> str:
        for c in cat_order:
            if (BATCH / f"{c}--{slug}.md").exists():
                return c
        return "?"
    for c in cat_order:
        print(f"=== {c} ===")
        for slug, cls, extra, near in rows:
            if cat_of(slug) != c:
                continue
            near_s = ",".join(near) if near else "-"
            print(f"{cls:<10} {extra:<8} {slug:<45} 库内近似: {near_s}")
        print()

    print("== 汇总 ==")
    from collections import Counter
    cnt = Counter(cls for _, cls, _, _ in rows)
    print(dict(cnt))


if __name__ == "__main__":
    main()
