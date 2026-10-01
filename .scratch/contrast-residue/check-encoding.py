"""contrast-residue 轮 · 通用小工具：列出本目录文件的 BOM / 大小（本地卫生检查用）。

跑法（仓库根）：`python .scratch\\contrast-residue\\check-encoding.py [目录]`
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
BOM = b"\xef\xbb\xbf"


def main() -> None:
    bad = 0
    for p in sorted(TARGET.iterdir()):
        if not p.is_file() or p.suffix not in (".txt", ".json", ".md", ".py", ".mjs", ".png"):
            continue
        b = p.read_bytes()
        has = b[:3] == BOM
        if has and p.suffix != ".ps1":
            bad += 1
        print(f"{p.name:46} BOM={has!s:5} size={len(b)}")
    print(f"\n多余 BOM 的文件数 = {bad}（`.ps1` 要 BOM，其余不需要）")


if __name__ == "__main__":
    main()
