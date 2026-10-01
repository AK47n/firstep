"""contrast-residue 轮 · 02 号探针：**页面上第二个 `:root` 块**的真文件反证（工单 01）。

做一件事：把页面里**第二个** `:root {` 改名成 `:root-x {`（模拟"第二块被搬走/改名"），
跑完门禁再复原。`inject` / `restore` 两个子命令，两侧都打印 sha256——复原必须逐字节一致。

跑法（仓库根）：
    python .scratch\\contrast-residue\\probe-02-page-injection.py inject
    node --test "tests/js/css-tokens.test.mjs"      # 期望：红（解析面又只剩第一块）
    python .scratch\\contrast-residue\\probe-02-page-injection.py restore
    node --test "tests/js/css-tokens.test.mjs"      # 期望：绿
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
NEEDLE = "\n  :root {"
BROKEN = "\n  :root-x {"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("inject", "restore"):
        raise SystemExit("用法：probe-02-page-injection.py inject|restore")
    text = PAGE.read_text(encoding="utf-8")
    if sys.argv[1] == "inject":
        hits = text.count(NEEDLE)
        if hits < 2:
            raise SystemExit(f"页面里只找到 {hits} 处 `{NEEDLE!r}`——第二块已经不在原位，反证无从做起")
        at = text.index(NEEDLE)                      # 第一处
        at = text.index(NEEDLE, at + 1)              # 第二处
        PAGE.write_text(text[:at] + BROKEN + text[at + len(NEEDLE):], encoding="utf-8")
        print(f"注入完成：第二个 `:root` → `:root-x`（共 {hits} 处，改的是第 2 处）")
        print(f"sha256 = {sha(PAGE)}")
    else:
        # 复原那一步**不能**再要求"两处 `:root`"（注入之后盘上只剩一处，那是预期的）
        if BROKEN not in text:
            raise SystemExit("盘上没有 `:root-x`——没东西可复原（是不是已经复原过了？）")
        broken_at = text.index(BROKEN)
        PAGE.write_text(text[:broken_at] + NEEDLE + text[broken_at + len(BROKEN):], encoding="utf-8")
        print("复原完成：`:root-x` → `:root`")
        print(f"sha256 = {sha(PAGE)}（必须与注入前那一行相同）")


if __name__ == "__main__":
    main()
