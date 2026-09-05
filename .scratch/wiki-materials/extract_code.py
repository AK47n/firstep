# -*- coding: utf-8 -*-
"""从 wiki 手册提取「代码块」章节的完整源码（工单 wiki-materials 用）。
用法：python .scratch/wiki-materials/extract_code.py <手册md> [输出目录]
"""
import re
import sys
from pathlib import Path

def extract(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    # 代码块章节格式：
    # ### 代码 1
    #
    # ```c
    # ...
    # ```
    blocks = []
    pattern = re.compile(r"^### 代码 (\d+)\s*\r?\n\s*\r?\n```c\s*\r?\n(.*?)\r?\n```", re.S | re.M)
    for m in pattern.finditer(text):
        n = int(m.group(1))
        code = m.group(2)
        blocks.append((n, code))
    return blocks

def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    blocks = extract(src)
    total = 0
    for n, code in blocks:
        fn = out / f"{src.stem.replace('--', '-')}-code{n}.txt"
        fn.write_text(code, encoding="utf-8")
        lines = code.splitlines()
        total += len(lines)
        print(f"代码 {n}: {len(lines)} 行 {len(code)} 字符 -> {fn.name}")
    print(f"共 {len(blocks)} 个代码块，合计 {total} 行")

if __name__ == "__main__":
    main()
