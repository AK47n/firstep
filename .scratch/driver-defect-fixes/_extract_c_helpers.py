# -*- coding: utf-8 -*-
"""把 `tests/test_module_joystick.py` / `test_module_hx711.py` 里逐字重复的
C 源码解析助手收敛到 `tests/_c_macros.py`（双轴评审的 Duplicated Code 意见，
照 `tests/_c_escape.py` 先例）。

判据：两个文件里那三段函数定义整段删掉、改从共用件导入；调用点名字同步换掉
（`_c_defines` → `c_defines`、`_c_int` → `c_int`、`_c_functions` → `c_functions`）。

按**顶格行**切函数块（不是按 `\\n\\n\\ndef ` 数空行）——三段助手的结尾后面跟的是常量
还是函数，两个文件并不一样。
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGETS = ("tests/test_module_joystick.py", "tests/test_module_hx711.py")
HELPERS = ("_c_defines", "_c_functions", "_c_int")
IMPORT_LINE = "from tests._c_macros import c_defines, c_functions, c_int\n"


def remove_function(text: str, name: str) -> str:
    """删掉 `def <name>(...)` 那一整块（到下一個顶格行为止）与它前面的空行。"""
    marker = f"def {name}("
    start = text.index(marker)
    lines = text[start:].split("\n")
    end = 1
    while end < len(lines) and (lines[end] == "" or lines[end][0] in " \t"):
        end += 1
    block = "\n".join(lines[:end])
    assert block.startswith(marker), block[:60]
    head = text[:start]
    # 连同块前的空行一起删掉（块与块之间原本隔一个空行）
    head = head.rstrip("\n") + "\n\n"
    return head + text[start + len(block):].lstrip("\n")


def main() -> int:
    for rel in TARGETS:
        path = REPO / rel
        text = path.read_text(encoding="utf-8", newline="")
        for name in HELPERS:
            text = remove_function(text, name)
        for old, new in (("_c_defines(", "c_defines("), ("_c_int(", "c_int("),
                         ("_c_functions(", "c_functions(")):
            text = text.replace(old, new)
        # 导入插在第一个 `def _read(` 之前（那之前都是模块级 import 与常量）
        anchor = text.index("def _read(")
        head = text[:anchor].rstrip("\n") + "\n"
        text = head + IMPORT_LINE + "\n" + text[anchor:]
        path.write_text(text, encoding="utf-8", newline="")
        print(f"已改 {rel}：删三段助手 + 从 tests._c_macros 导入")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
