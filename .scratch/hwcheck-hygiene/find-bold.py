"""find-bold.py — 临时量具：列出**会进页面的文案串**里的 markdown 粗体标记（`**`）。

为什么：工单 02 立的口径是"产品串里不许出现 markdown 标记"（前端 `esc()` 之后就是两个字面
星号），但那条守卫只扫了 `static/js/{fx,ui}/**` 的字符串字面量，**没扫服务端下发的文案**。
本单（08）顺手量一遍检测栏目服务端的可见串，看还有没有回潮。

判据面：只列**函数返回值 / 追加进页面载荷的字符串字面量**（AST 里是 Constant 且含 `**` 且
不含换行缩进特征），docstring 与注释不算。
用法：python .scratch/hwcheck-hygiene/find-bold.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FILES = ("hwcheck_board.py", "hwcheck.py", "hwcheck_console.py", "hwcheck_generic.py",
         "hwcheck_custom.py", "hwcheck_recipe.py", "hwcheck_triage.py")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name in FILES:
        path = REPO / "src" / "contest_generator" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docs.add(doc)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            text = node.value
            if text in docs or "**" not in text:
                continue
            print(f"{name}:{node.lineno}: {text[:150]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
