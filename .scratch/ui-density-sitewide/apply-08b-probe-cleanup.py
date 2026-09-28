r"""工单 08 施工脚本（二）：两笔探针内务（07 单账第 7 条点名的）。

  A. **`load_backlog()` 提成单一出处**：`probe-01-scope-draft.py` 与
     `probe-04-scope-calibers.py` 里各有一份**逐字相同**的实现（07 单评审 Standards 点名）。
     现在提到 `scope_lib.load_backlog()`，两支探针改成 import。
  B. **`probe-01` 末行标题纠词**：那句"全站 font-size 声明总处数"打印的其实是**裸 px** 计数
     （清空之后盘上还有 428 处 `--fs-*`，字面意思与内容不符——07 单评审 눈에 걸린那句）。

⚠ 这两笔**不动产品面**，只动取证工具；改完两支探针都要重跑一遍确认读数不变。

**范围说明**：`load_backlog()` 只从 **`probe-04`（保管版）** 里提掉——
`probe-01` 是 01 单立的**草稿探针**（它自带一份 `rules_of` / `scope_of` / `load_backlog`，
README 的 `scope_lib` docstring 里记着"四份逐字相同"那段历史）。本轮只纠它的**标题词**
（那是会误导读数的），**不重写它的内部**：要么下一轮整支对齐 `scope_lib`，要么直接弃用
（`probe-04` 就是它的加严版）。这条判断写进 08 票尾的账。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-08b-probe-cleanup.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-08b-probe-cleanup.py --write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BLOCK = re.compile(r"def load_backlog\(\) -> list\[str\]:.*?\n\n\n", re.S)

TARGETS = ["probe-04-scope-calibers.py"]

# (文件, 旧串, 新串, 说明)
LABEL = [
    ("probe-01-scope-draft.py",
     "全站 font-size 声明总处数",
     "全站**裸 px** font-size 声明处数（0 = 这条线收口；样式块里的 `--fs-*` 引用另计）",
     "B 末行标题纠词（说清它数的是裸 px，不是全部 font-size 声明）"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    problems: list[str] = []
    notes: list[str] = []
    pending: list[tuple[Path, str]] = []

    for name in TARGETS:
        path = HERE / name
        text = path.read_text(encoding="utf-8")
        if "def load_backlog" not in text:
            if "load_backlog," in text or "load_backlog," in text or "load_backlog" in text:
                notes.append(f"已应用（{name}：已从 scope_lib import）")
                continue
            problems.append(f"{name}: 找不到本地 load_backlog，也没看到 import")
            continue
        m = BLOCK.search(text)
        if not m:
            problems.append(f"{name}: load_backlog 块的边界没匹配上（格式变了）")
            continue
        if "from scope_lib import (" not in text:
            problems.append(f"{name}: 没找到 `from scope_lib import (` 这行，别乱插 import")
            continue
        pending.append((path, text[:m.start()] + text[m.end():]))

    for name, old, new, why in LABEL:
        path = HERE / name
        text = path.read_text(encoding="utf-8")
        if old not in text:
            if new in text:
                notes.append(f"已应用（{why}）")
            else:
                problems.append(f"{name}: 找不到 {old!r}")
            continue
        notes.append(f"改    {why}")

    print(f"== 探针内务：{len(pending)} 个文件要改（import 化）/ {len(LABEL)} 处纠词 ==")
    for path, _ in pending:
        print(f"  改    {path.name}：删掉本地 load_backlog，改成 from scope_lib import")
    for n in notes:
        print("  " + n)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    if not args.write or args.dry_run:
        print("\n（--dry-run：没有写盘；确认无误后加 --write）")
        return 0

    # ⚠ 写盘放在闸门之后（08 单评审 Standards：第一版把写入排在 `--dry-run` 判断之前）
    for path, new_text in pending:
        new_text = new_text.replace("from scope_lib import (", "from scope_lib import (load_backlog, ", 1)
        path.write_text(new_text, encoding="utf-8", newline="")
    for name, old, new, _ in LABEL:
        path = HERE / name
        text = path.read_text(encoding="utf-8")
        if old in text:
            path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")

    # 复扫：本地定义必须没了、import 必须在
    for name in TARGETS:
        text = (HERE / name).read_text(encoding="utf-8")
        if "def load_backlog" in text or "load_backlog" not in text:
            print(f"\n== **停下**：{name} 复扫失败 ==")
            return 1
    print("\n[已写盘] 两支探针 ✅（改完记得重跑：读数应当**一个字都不变**）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
