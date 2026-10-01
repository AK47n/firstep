"""contrast-residue 轮 · 小工具：给工单文件勾选验收框（本地卫生用）。

为什么不用 PowerShell 做：本机控制台是 GBK，`Get-Content -Raw` → `Set-Content -Encoding utf8`
会把 UTF-8 中文按 GBK 解码再写回（乱码 + 吞行尾换行符，见 `local-environment.md`）。
一律走 Python，显式 `encoding="utf-8"`。

跑法（仓库根）：`python .scratch\\contrast-residue\\tick-ticket.py <工单文件名>`
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent / "issues"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：tick-ticket.py <工单文件名，如 02-undefined-token-leg.md>")
    path = HERE / sys.argv[1]
    text = path.read_text(encoding="utf-8")
    n = text.count("- [ ]")
    path.write_text(text.replace("- [ ]", "- [x]"), encoding="utf-8")
    print(f"{path.name}：勾选 {n} 条未完成项（全部转 [x]）")


if __name__ == "__main__":
    main()
