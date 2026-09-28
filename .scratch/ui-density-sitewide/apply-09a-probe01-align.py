r"""工单 09 施工脚本（一）：`probe-01` 整支对齐 `scope_lib`（08 账第 9 条）。

`probe-01-scope-draft.py` 是 01 单立的草稿探针，自带 `load_scopes` / `load_backlog` /
`scope_of` 三份**逐字副本**（README 的 `scope_lib` docstring 里记着"四份逐字相同"那段历史）。
08 单只纠了它的标题词、没动内部；这一单把三份副本换成 import。

**判据**：改前 / 改后各跑一次 `probe-01-scope-draft.py`（**两次都看退出码与空输出**，
不是只比 stdout —— 09 单评审 Standards 抓过这个洞），两份输出**逐字节相同**才算通过。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-09a-probe01-align.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-09a-probe01-align.py --write
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGET = HERE / "probe-01-scope-draft.py"

# 三个要搬走的本地件（含它们上面的注释块，直到下一个 def / 顶层语句）
BLOCKS = [
    r"def load_scopes\(\) -> list\[tuple\[str, re\.Pattern\[str\]\]\]:.*?\n\n\n",
    r"def load_backlog\(\) -> list\[str\]:.*?\n\n\n",
    r"def scope_of\(sel: str, scopes: list\[tuple\[str, re\.Pattern\[str\]\]\]\) -> str:.*?\n\n\n",
]


def run_probe() -> str:
    """跑一次探针并**同时看退出码与 stderr**（09 单评审 Standards：
    只比 stdout 的话，两次都崩（stdout 皆空）也会打印"逐字节相同 ✅"）。"""
    p = subprocess.run([sys.executable, str(TARGET)], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0 or not p.stdout.strip():
        raise SystemExit(f"== **停下**：探针没跑成（exit={p.returncode}）==\n{p.stderr[:800]}")
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = TARGET.read_text(encoding="utf-8")
    if "from scope_lib import" in text and "def load_scopes" not in text:
        print("== 已经对齐过（import 在、本地副本不在）——幂等退出 ✅ ==")
        return 0
    pending = text
    moved = []
    for pat in BLOCKS:
        m = re.search(pat, pending, re.S)
        if not m:
            print(f"== **停下**：找不到这一段（格式变了）：{pat[:60]}… ==")
            return 1
        moved.append(m.group(0).splitlines()[0])
        pending = pending[:m.start()] + pending[m.end():]

    if "from scope_lib import" in pending:
        print("== 已经 import 过了（幂等）——不重复插 ==")
        import_line = [ln for ln in pending.splitlines() if "from scope_lib import" in ln][0]
    else:
        # 插在它自己那段 ROOT / PAGE / GUARD 之后（probe-01 原先没有 sys.path 那两行）
        anchor = ('GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"\n')
        if anchor not in pending:
            print("== **停下**：没找到插 import 的锚点（GUARD = … 那一行）==")
            return 1
        import_line = ("\nimport sys\nsys.path.insert(0, str(Path(__file__).resolve().parent))\n"
                       "from scope_lib import load_backlog, load_scopes, scope_of  # 单一出处（09 单对齐）\n")
        pending = pending.replace(anchor, anchor + import_line, 1)

    print(f"== probe-01 对齐：搬走 {len(moved)} 个本地件 ==")
    for head in moved:
        print(f"  搬  {head}")
    print(f"  加  {import_line.strip()}")

    before = run_probe()
    if not args.write or args.dry_run:
        print("\n（--dry-run：没有写盘；确认无误后加 --write）")
        return 0

    # 按**盘上原有的行尾**写回（08 单 Std-2 记过：`read_text` + `newline=""` 会把整支变成 LF）
    raw = TARGET.read_bytes()
    eol = "\r\n" if b"\r\n" in raw else "\n"
    TARGET.write_bytes(pending.replace("\r\n", "\n").replace("\n", eol).encode("utf-8"))
    after = run_probe()
    if before != after:
        print("\n== **停下**：改前 / 改后输出不一致（已写盘，逐行 diff 如下）==")
        for line in list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                              "before", "after", lineterm=""))[:40]:
            print("  " + line)
        return 1
    print(f"\n[已写盘] {TARGET.name}；改前 / 改后输出**逐字节相同** ✅（{len(before.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
