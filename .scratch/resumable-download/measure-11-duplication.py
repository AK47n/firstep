"""工单 11「先量再动」的取证脚本（只读，不改仓库）。

量 `_resolve_download` 与 `_restore_snapshot` 这两处**同形重复**：
  1. **代码行数**（不含 docstring / 注释——措辞不算重复，代码才算）；
  2. 去噪后**逐行完全相同**的行、以及各自独有的行（哪几行是真的同一件事）；
  3. **AST 归一化**：变量名换掉之后两处是不是**同一棵树**（`full` vs `materials`、
     扁平 `parts` vs 两层 `batches` 各不相同，故这一项是「去名之后还差多少」的判据）；
  4. git 历史：这两对函数被**同一提交同时改过几次**（「两边各改一次」的代价证据）。

改动前那份从 `git show <ref>:<path>` 取，所以重排之后仍然可复现。

用法：
  python .scratch/resumable-download/measure-11-duplication.py            # 基线 = 工单 10 的收口提交
  python .scratch/resumable-download/measure-11-duplication.py HEAD
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 工单 10 的收口提交 = 本单动手之前的形状
DEFAULT_BASE = "3fc218b4"
TARGETS = {
    "full": "src/contest_generator/full_task.py",
    "materials": "src/contest_generator/materials_task.py",
}
FUNCS = ("_resolve_download", "_restore_snapshot")


def from_git(ref: str, rel_path: str) -> str:
    out = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        raise SystemExit(f"git show {ref}:{rel_path} 失败：{out.stderr.strip()}")
    return out.stdout


def from_disk(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def function_node(source: str, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def function_source(source: str, name: str) -> tuple[int, int, list[str]]:
    """→（起始行, 结束行, 行文本），按 AST 取函数全文（不靠手数行号）。"""
    lines = source.splitlines()
    node = function_node(source, name)
    if node is None:
        return 0, 0, []
    start, end = node.lineno, node.end_lineno or node.lineno
    return start, end, lines[start - 1:end]


def code_lines(source: str, name: str) -> list[str]:
    """函数里的**代码**行：docstring 整段与注释行都去掉，空白全平。

    为什么按 AST 去 docstring 而不是「以三引号开头的行」：docstring 是多行字符串，
    逐行看会把里面的要点行当成代码（工单 10 的量具在这点上吃过亏）。
    """
    node = function_node(source, name)
    if node is None:
        return []
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        doc = body[0]
        body = body[1:]
    drop = set(range(doc.lineno, (doc.end_lineno or doc.lineno) + 1)) if body != list(node.body) else set()
    lines = source.splitlines()
    out = []
    for idx in range(node.lineno - 1, (node.end_lineno or node.lineno)):
        if idx + 1 in drop:
            continue
        text = lines[idx].split("#", 1)[0].strip() if not lines[idx].lstrip().startswith("#") else ""
        if not text:
            continue
        out.append("".join(text.split()))
    # 函数签名（含 return 注解）也算代码：它是契约的一部分，多行签名压成一行
    sig_src = ast.get_source_segment(source, node) or ""
    head = sig_src.split(":", 1)[0] if "->" not in sig_src else sig_src.split("->", 1)[0]
    sig = "".join(head.split()) + (
        "->" + "".join(sig_src.split("->", 1)[1].split(":", 1)[0].split())
        if "->" in sig_src else ""
    )
    return [sig] + out


def shape(source: str, name: str) -> str:
    """AST 归一化形状：变量名 / 属性名 / docstring 先抹平，剩下的就是**结构骨架**。"""
    node = function_node(source, name)
    if node is None:
        return ""
    clone = ast.parse(ast.unparse(node)).body[0]
    body = list(clone.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        clone.body = body[1:]
    for child in ast.walk(clone):
        if isinstance(child, ast.Name):
            child.id = "_"
        elif isinstance(child, ast.Attribute):
            child.attr = "_"
        elif isinstance(child, ast.arg):
            child.arg = "_"
    return ast.unparse(clone)


def compare(label: str, sources: dict[str, str]) -> None:
    print(f"\n===== {label} =====")
    for token in FUNCS:
        bodies, codes = {}, {}
        for key, source in sources.items():
            start, end, lines = function_source(source, token)
            bodies[key] = lines
            codes[key] = code_lines(source, token)
            print(f"[{token}] {key:9s} {start}-{end}  共 {end - start + 1} 行"
                  f"（代码 {len(codes[key])} 行）")
        if not all(bodies.values()):
            print("  （这个时刻没有该函数）")
            continue
        full, mats = codes["full"], codes["materials"]
        same = [line for line in full if line in mats]
        only_full = [line for line in full if line not in mats]
        only_mats = [line for line in mats if line not in full]
        same_shape = shape(sources["full"], token) == shape(sources["materials"], token)
        print(f"  代码行：完全相同 {len(same)} 行 / full 独有 {len(only_full)} 行 / "
              f"materials 独有 {len(only_mats)} 行；AST 去名后同形：{'是' if same_shape else '否'}")
        for line in only_full:
            print(f"    只 full: {line}")
        for line in only_mats:
            print(f"    只 materials: {line}")


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    compare(f"改动前（git {base}）", {k: from_git(base, v) for k, v in TARGETS.items()})
    compare("改动后（工作区现状）", {k: from_disk(v) for k, v in TARGETS.items()})

    print("\n== git 历史：这两对函数所在文件被同一提交同时改过几次 ==")
    log = subprocess.run(
        ["git", "log", "--format=%h|%s", "--name-only", "-60", "--",
         *TARGETS.values()],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    blocks: list[tuple[str, set[str]]] = []
    current: tuple[str, set[str]] | None = None
    for line in log.splitlines():
        if "|" in line and len(line.split("|")[0]) == 8:
            current = (line, set())
            blocks.append(current)
        elif line.strip() and current is not None:
            current[1].add(line.strip())
    for subject, files in blocks:
        if len(files) < 2:
            continue
        names = sorted(Path(f).name for f in files)
        print(f"  {subject[:78]}")
        print(f"      {names}")

    print("\n== 逐提交：谁改过这两对函数本体 ==")
    for token in FUNCS:
        print(f"[{token}]")
        for ref in ("918f25b4", "3fc218b4", "HEAD"):
            for key, rel in TARGETS.items():
                source = from_git(ref, rel)
                node = function_node(source, token)
                if node is None:
                    print(f"  {ref} {key}: （无）")
                    continue
                print(f"  {ref} {key}: {node.lineno}-{node.end_lineno} 行"
                      f"（代码 {len(code_lines(source, token))} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
