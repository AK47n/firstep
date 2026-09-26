"""find-labels.py — 量具：列出会进**学生可见文本**的「工单」字样（字符串字面量里的）。

只列**字符串字面量**，不列 docstring / 注释——本单要清的只有"渲染进产物或页面"的那几处，
而源码注释里那 400+ 处「工单」是给维护者读的"为什么"，该留。

判据面（AST，不是 grep 行）：
  * 遍历所有 `ast.Constant(str)`；
  * 排除**docstring**（模块 / 类 / 函数体的第一条语句）；
  * 剩下的字符串常量里含「工单」的才算命中。

⚠ 第一版是"该行含引号就算"的**行启发式**——评审 Standards 轴当场抓到：ticket 里把它写成
"按 AST 全列了一遍"，而脚本根本不是（这正是本批存在的理由：账本描述的工具必须真是那个
工具）。所以这里改成真 AST，并重跑确认结论不变。
用法：python .scratch/hwcheck-hygiene/find-labels.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FILES = ("hwcheck.py", "hwcheck_console.py", "hwcheck_generic.py",
         "hwcheck_board.py", "hwcheck_custom.py", "hwcheck_recipe.py",
         "hwcheck_triage.py", "my_devices.py")


def _docstring_ids(tree: ast.AST) -> set[int]:
    """所有 docstring 节点的 `id()`（模块 / 类 / 函数体的第一条语句是字符串常量）。"""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            ids.add(id(body[0].value))
    return ids


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    total = 0
    for name in FILES:
        path = REPO / "src" / "contest_generator" / name
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstring_ids(tree)
        hits = sorted(
            (node.lineno, node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docs and "工单" in node.value
        )
        print(f"== {name}：字符串字面量里 {len(hits)} 处")
        for lineno, text in hits:
            print(f"  {lineno}: {text.strip()[:150]}")
        total += len(hits)
    print(f"\n=== 合计 {total} 处（docstring / 注释不计） ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
