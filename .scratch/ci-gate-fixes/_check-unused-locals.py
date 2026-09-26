# -*- coding: utf-8 -*-
r"""改完闸门后的一次性自检：`config` / `library_dir` 这类局部变量有没有"赋值了没人用"
（工单 ci-gate-fixes/04 把若干 `config = _require_config(context)` 换成了
`library_dir = _library_dir(context)`，漏删旧赋值不会报错、只会留下静默垃圾）。

用法（仓库根）：python .scratch\ci-gate-fixes\_check-unused-locals.py
"""
import ast
import pathlib

TARGET = pathlib.Path(__file__).resolve().parents[2] / "src" / "contest_generator" / "webapp.py"
tree = ast.parse(TARGET.read_text(encoding="utf-8"))
found = 0
for node in ast.walk(tree):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    assigned: dict[str, int] = {}
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
            tgt = sub.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id in ("config", "library_dir",
                                                        "module_library_dir"):
                assigned.setdefault(tgt.id, sub.lineno)
    used: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            used.add(sub.id)
    for name, lineno in assigned.items():
        if name not in used:
            print(f"UNUSED  {node.name}():{lineno}  {name}")
            found += 1
print("unused locals:", found)
