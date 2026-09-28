r"""把施工脚本写进去的**裸 LF** 归一成 CRLF（工单 02 评审整改）。

怎么来的：`apply-02c-components.py` 的**替换串**里写的是 `\n`，而这个文件在盘上是 CRLF
（`core.autocrlf=true`；blob 里是 LF、checkout 出来是 CRLF）。脚本只在**匹配**侧写了
`\r?\n`，替换侧没有——于是新插进去的那几行是裸 LF（实测 8 行：ghost 段 5 行 + 指路注释 3 行）。

修法：把**只含漂 LF** 的行补上 `\r`。只动裸 LF，已有 `\r\n` 一个字节不碰。
**教训（写进票尾）**：施工脚本的匹配与**替换**两侧都要按文件实际换行走。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\fix-crlf.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\fix-crlf.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw = PAGE.read_bytes()
    fixed = re.sub(rb"(?<!\r)\n", b"\r\n", raw)
    lone = raw.count(b"\n") - raw.count(b"\r\n")
    added = fixed.count(b"\r\n") - raw.count(b"\r\n")
    print(f"裸 LF {lone} 处 → 补 \\r 后 CRLF {fixed.count(b'\r\n')} 行（净增 {added} 处 \\r）")
    if lone != added:
        print("✗ 数目对不上（说明还有别的形态），停手")
        return 1
    if not args.write:
        print("\n（--dry-run：没有写盘。确认无误后加 --write）")
        return 0
    PAGE.write_bytes(fixed)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
