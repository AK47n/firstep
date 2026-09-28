r"""判据强度自证（临时件）：往 shell 作用域塞一个越界字号，守卫必须判红；复原后转绿。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\probe-red-shell.py in
    node --test tests/js/css-tokens.test.mjs      # 期望：红
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\probe-red-shell.py out
    node --test tests/js/css-tokens.test.mjs      # 期望：绿
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
# 备份件**放本目录**，不落在产品目录里（评审整改：上一版把 `.html.redbak` 写在产品树）
BAK = Path(__file__).resolve().parent / "probe-red-shell.bak"
OLD = ".card h3 { font-size: var(--fs-block); margin: 14px 0 var(--space-2); color: var(--muted); font-weight: 600; }"
NEW = ".card h3 { font-size: 17px; margin: 14px 0 var(--space-2); color: var(--muted); font-weight: 600; }"


def read() -> str:
    # 逐字节保真：本工作树的换行是混的，`read_text()` 的 universal newlines 会把 CRLF
    # 归一成 LF，写回时整档改写（`docs/agents/local-environment.md` 第 2 节）
    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(text: str) -> None:
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    text = read()
    if mode == "in":
        n = text.count(OLD)
        if n != 1:
            print(f"锚点出现 {n} 次（期望 1）—— 停手，别拿没注入的读数当红证")
            return 1
        BAK.write_text(text, encoding="utf-8", newline="")
        write(text.replace(OLD, NEW))
        print("已注入：.card h3 → font-size: 17px（shell 作用域）")
        return 0
    if mode == "out":
        if not BAK.exists():
            print("没有备份件，无从复原")
            return 1
        with BAK.open("r", encoding="utf-8", newline="") as fh:
            write(fh.read())
        BAK.unlink()
        print("已复原")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
