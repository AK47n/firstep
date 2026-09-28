r"""工单 03 施工用：把某个作用域的规则逐条打出来（选择器 + 完整声明体 + 行号）。

只读，不落盘（要看哪一段直接管道 / 重定向）。分区表与归属口径**从 `scope_lib` 取**
（单一出处 = 守卫 `tests/js/css-tokens.test.mjs`），本工具不另抄一份。

    python .scratch\ui-density-sitewide\dump-03-rules.py --out x.txt   # 落到 UTF-8 文件
    python .scratch\ui-density-sitewide\dump-03-rules.py --from 570 --to 900
    python .scratch\ui-density-sitewide\dump-03-rules.py --grep sug-   # 只看某族
    python .scratch\ui-density-sitewide\dump-03-rules.py --scope topic --grep topic-

⚠ 落盘用 `--out`，**别用 PowerShell 的 `>`**（它写 UTF-16LE，`read` 工具当二进制拒读）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import load_scopes, read_page, rules_of, scope_of  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="generate")
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--to", dest="hi", type=int, default=0)
    ap.add_argument("--grep", default="")
    ap.add_argument("--out", default="", help="落盘（UTF-8）")
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()

    n = 0
    lines: list[str] = []
    for line, sel, b0, b1 in rules_of(text):
        if scope_of(sel, scopes) != args.scope:
            continue
        if args.lo and line < args.lo:
            continue
        if args.hi and line > args.hi:
            continue
        if args.grep and args.grep not in sel:
            continue
        n += 1
        lines.append(f"L{line}  {sel}")
        for decl in text[b0:b1].strip().split(";"):
            decl = decl.strip()
            if decl:
                lines.append(f"        {decl};")
    lines.append(f"\n[共 {n} 条]")
    report = "\n".join(lines)
    print(report)
    if args.out:
        target = HERE / args.out
        target.write_text(report + "\n", encoding="utf-8")
        print(f"\n[落盘] {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
