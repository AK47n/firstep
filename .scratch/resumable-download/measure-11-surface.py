"""工单 11「先量再动」的**第二把量具**：两条任务链路之间**所有**同名函数的重复账。

工单只点了 `_resolve_download` 与 `_restore_snapshot` 两处，但「同形重复」这件事
不该按名字取样——先把两文件里**同名**函数全量对一遍，才知道这两处在这张账里排在哪儿
（也才知道评审该按哪个范围判「值不值得收」）。

判据三层，逐层加严：
  1. **同名**（两文件都有）；
  2. **去噪后代码行完全相同**（去 docstring / 注释 / 空白）；
  3. **AST 去名后同形**（变量名 / 参数名 / 属性名抹平后是同一棵树）——第 3 层才是
     「抄的」；只到第 2 层的是「长得像」（扁平 vs 两层、字段名不同）。

用法：python .scratch/resumable-download/measure-11-surface.py
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

spec = importlib.util.spec_from_file_location(
    "measure11", HERE / "measure-11-duplication.py"
)
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def functions(source: str) -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef):
            out.setdefault(node.name, node)
    return out


def main() -> int:
    sources = {k: measure.from_disk(v) for k, v in measure.TARGETS.items()}
    full, mats = functions(sources["full"]), functions(sources["materials"])
    print(f"full_task.py 顶层/类内函数 {len(full)} 个；materials_task.py {len(mats)} 个")

    common = sorted(set(full) & set(mats))
    print(f"同名函数 {len(common)} 个\n")
    header = f"{'函数':28s} {'full 代码行':>10s} {'mat 代码行':>10s} {'相同行':>7s} {'同形':>5s}"
    print(header)
    print("-" * len(header))
    rows = []
    for name in common:
        cf = measure.code_lines(sources["full"], name)
        cm = measure.code_lines(sources["materials"], name)
        same = sum(1 for line in cf if line in cm)
        same_shape = measure.shape(sources["full"], name) == measure.shape(
            sources["materials"], name
        )
        rows.append((name, len(cf), len(cm), same, same_shape))
        print(f"{name:28s} {len(cf):>10d} {len(cm):>10d} {same:>7d} "
              f"{'是' if same_shape else '否':>5s}")

    print("\n== 汇总 ==")
    copied = [r for r in rows if r[4]]
    lookalike = [r for r in rows if not r[4] and r[3] > 0]
    print(f"  AST 去名后同形（真抄）: {len(copied)} 个 -> "
          f"{', '.join(r[0] for r in copied)}")
    print(f"  只到「完全相同行」层（长得像）: {len(lookalike)} 个 -> "
          f"{', '.join(f'{r[0]}({r[3]}行)' for r in lookalike)}")
    print(f"  完全相同行总数（含长得像的部分）: {sum(r[3] for r in rows)} 行")
    print(f"  真抄那批的完全相同行总数: {sum(r[3] for r in copied)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
