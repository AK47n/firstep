"""工单 12「先量再动」的取证脚本（只读，不改仓库）。

工单 11 在备注里留了四类「同形重复」候选，并逐条给了「当时为什么不动」的理由。
**那些理由不作数**——本量具把它们各量一遍，量出来的账才是判据：

  1. `full_task_status` / `task_status`（状态视图，两处各约 26 行）；
  2. `run()` / `_write_snapshot` / `__init__`（长得像但承载真实不同的状态机与快照封套）；
  3. `_PartState` 数据形状（两文件各一份 dataclass + `to_dict` / `from_dict`）；
  4. `state` / `error` / `cancel` / `_retry_state`（单行取值器）。

量六件事（与工单 11 的两把量具同口径，便于对账）：

  A. **代码行**（去 docstring / 注释 / 空白）与**逐行完全相同**的行数——
     「抄了多少字」；
  B. **语句级 AST 同形**：两处函数体逐条语句抹平名字后是不是同一串
     （比整棵树同形更松一点，用来认「除了取值源不同，其余一模一样」）；
  C. **抄写代价** = 两处代码行之和（重复量）；**真正不同** = 仅在一侧出现的行数；
  D. **数据形状**：`_PartState` 的字段名序列 / 默认值 / `to_dict` 键序列 /
     `from_dict` 键序列 / 转换表达式，逐个对；
  E. **git 历史**：这套东西被改过几次、有几次是「两边各改一次」
     （工单 10 第三节的判据：没有这个先例就不该动热路径）；
  F. **判据强度**（另一支探针 `probe-12-guard-strength.py` 负责，见那份文件）。

改动前那一份从 `git show <ref>:<path>` 取，所以量完/改完之后**仍然可复现**。

用法：
  python .scratch/resumable-download/measure-12-twin-candidates.py            # 基线 = 工单 11 的收口提交
  python .scratch/resumable-download/measure-12-twin-candidates.py HEAD
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 工单 11 的收口提交（`1e5ff9d0` 只是 CHANGELOG 自动提交，取代码收口那一支）
DEFAULT_BASE = "5461f39d"
TARGETS = {
    "full": "src/contest_generator/full_task.py",
    "materials": "src/contest_generator/materials_task.py",
}
TASK_MODULE = "src/contest_generator/task_download.py"

# 四类候选（逐条对应工单 11 备注里的四个「不动」）。
# 每一组 = (标签, full 侧名字, materials 侧名字或 None=同名)
CANDIDATES: list[tuple[str, str, str | None]] = [
    ("① 状态视图", "full_task_status", "task_status"),
    ("② 主流程 run()", "run", None),
    ("② 快照封套", "_write_snapshot", None),
    ("② 构造 __init__", "__init__", None),
    ("③ 数据形状 to_dict", "to_dict", None),
    ("③ 数据形状 from_dict", "from_dict", None),
    ("④ 取值器 state", "state", None),
    ("④ 取值器 error", "error", None),
    ("④ 取值器 cancel", "cancel", None),
    ("④ 取值器 _retry_state", "_retry_state", None),
    # 工单 11 已收的两处（留作对照：壳与家各是什么形状）
    ("已收 _resolve_download", "_resolve_download", None),
    ("已收 _restore_snapshot", "_restore_snapshot", None),
]

# `_PartState` 的形状字段（工单 03 定的七字段契约）
PART_FIELDS = ("name", "url", "size", "sha256",
               "downloaded_bytes", "ok", "dest")


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


def code_lines(source: str, name: str) -> list[str]:
    """函数里的**代码**行（去 docstring 整段 / 注释行 / 空白；空白全平）。"""
    node = function_node(source, name)
    if node is None:
        return []
    body = list(node.body)
    doc_range: set[int] = set()
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        doc = body[0]
        doc_range = set(range(doc.lineno, (doc.end_lineno or doc.lineno) + 1))
    lines = source.splitlines()
    out = []
    for idx in range(node.lineno - 1, (node.end_lineno or node.lineno)):
        if idx + 1 in doc_range:
            continue
        raw = lines[idx]
        text = "" if raw.lstrip().startswith("#") else raw.split("#", 1)[0].strip()
        if not text:
            continue
        out.append("".join(text.split()))
    return out


def signature(source: str, name: str) -> str:
    node = function_node(source, name)
    if node is None:
        return ""
    segment = ast.get_source_segment(source, node) or ""
    head = segment.split(":", 1)[0]
    if "->" in segment:
        ret = segment.split("->", 1)[1].split(":", 1)[0]
        head = segment.split("->", 1)[0]
        return "".join(head.split()) + "->" + "".join(ret.split())
    return "".join(head.split())


def canonical(node: ast.AST, *, names: bool = False) -> str:
    """AST 抹平：默认把变量/属性/参数名抹成 `_`；`names=True` 保留名字。"""
    clone = ast.parse(ast.unparse(node)).body[0]
    if not names:
        for child in ast.walk(clone):
            if isinstance(child, ast.Name):
                child.id = "_"
            elif isinstance(child, ast.Attribute):
                child.attr = "_"
            elif isinstance(child, ast.arg):
                child.arg = "_"
    return ast.unparse(clone)


def body_statements(source: str, name: str) -> list[str]:
    """函数体**逐条语句**的归一化形状（去掉 docstring）——比整树同形更松。"""
    node = function_node(source, name)
    if node is None:
        return []
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return [canonical(stmt) for stmt in body]


def dataclass_shape(source: str, cls_name: str) -> dict[str, object]:
    """→ `_PartState` / `_BatchState` 的形状：字段名序列 / 默认值 / 两个转换方法。"""
    tree = ast.parse(source)
    cls = next((n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == cls_name), None)
    if cls is None:
        return {}
    fields: list[str] = []
    defaults: list[str] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields.append(stmt.target.id)
            defaults.append(ast.unparse(stmt.value) if stmt.value is not None else "<必填>")
    defs: dict[str, list[str]] = {}
    for stmt in cls.body:
        if isinstance(stmt, ast.FunctionDef):
            body = [s for s in stmt.body if not (
                isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                and isinstance(s.value.value, str))]
            defs[stmt.name] = [canonical(s) for s in body]
    return {"fields": fields, "defaults": defaults, "methods": defs}


def dict_literal_keys(source: str, name: str) -> list[str]:
    """`to_dict` / `from_dict` 里出现的**字面键名**（保序、去重）。"""
    node = function_node(source, name)
    if node is None:
        return []
    keys: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if child.value in PART_FIELDS and child.value not in keys:
                keys.append(child.value)
    return keys


def row(label: str, full_src: str, mats_src: str, name_f: str,
        name_m: str | None) -> dict[str, object]:
    name_m = name_m or name_f
    nf = function_node(full_src, name_f)
    nm = function_node(mats_src, name_m)
    if nf is None or nm is None:
        return {"label": label, "missing": True,
                "full": nf is not None, "materials": nm is not None}
    cf, cm = code_lines(full_src, name_f), code_lines(mats_src, name_m)
    same = [line for line in cf if line in cm]
    only_f = [line for line in cf if line not in cm]
    only_m = [line for line in cm if line not in cf]
    tree_shape = (canonical(nf) == canonical(nm))
    stmts_f, stmts_m = body_statements(full_src, name_f), body_statements(mats_src, name_m)
    stmt_same = sum(1 for s in stmts_f if s in stmts_m)
    return {
        "label": label, "missing": False,
        "lines_f": nf.end_lineno - nf.lineno + 1,
        "lines_m": nm.end_lineno - nm.lineno + 1,
        "code_f": len(cf), "code_m": len(cm),
        "same": len(same), "only_f": only_f, "only_m": only_m,
        "tree": tree_shape,
        "stmts_f": len(stmts_f), "stmts_m": len(stmts_m), "stmts_same": stmt_same,
        "stmt_shape": stmts_f == stmts_m,
        "sig_f": signature(full_src, name_f), "sig_m": signature(mats_src, name_m),
    }


def print_rows(title: str, sources: dict[str, str]) -> None:
    print(f"\n===== {title} =====")
    header = (f"{'候选':26s} {'full 行':>7s} {'mat 行':>7s} {'代码行':>9s} "
              f"{'相同行':>6s} {'抄写代价':>8s} {'不同行':>6s} {'AST同形':>7s} {'语句同形':>8s}")
    print(header)
    print("-" * len(header))
    for label, name_f, name_m in CANDIDATES:
        data = row(label, sources["full"], sources["materials"], name_f, name_m)
        if data.get("missing"):
            print(f"{label:26s} （缺：full={data['full']} materials={data['materials']}）")
            continue
        cost = int(data["code_f"]) + int(data["code_m"])  # type: ignore[arg-type]
        print(f"{label:26s} {data['lines_f']:>7} {data['lines_m']:>7} "
              f"{data['code_f']:>4}/{data['code_m']:<4} {data['same']:>6} "
              f"{cost:>8} {len(data['only_f']) + len(data['only_m']):>6} "  # type: ignore[arg-type]
              f"{'是' if data['tree'] else '否':>7} "
              f"{'是' if data['stmt_shape'] else '否':>8}")
        if data["only_f"]:
            for line in data["only_f"]:  # type: ignore[union-attr]
                print(f"      只 full : {line}")
        if data["only_m"]:
            for line in data["only_m"]:  # type: ignore[union-attr]
                print(f"      只 mats : {line}")
        if data["sig_f"] != data["sig_m"]:
            print(f"      签名差异: {data['sig_f']}")
            print(f"                {data['sig_m']}")


def print_part_shape(sources: dict[str, str]) -> None:
    print("\n===== ③ `_PartState` 数据形状逐字段对 =====")
    shapes = {k: dataclass_shape(v, "_PartState") for k, v in sources.items()}
    for key, shape in shapes.items():
        print(f"[{key}] 字段 {shape.get('fields')}")
        print(f"        默认 {shape.get('defaults')}")
    f, m = shapes["full"], shapes["materials"]
    print(f"  字段名序列相同: {'是' if f.get('fields') == m.get('fields') else '否'}")
    print(f"  默认值序列相同: {'是' if f.get('defaults') == m.get('defaults') else '否'}")
    methods_f = f.get("methods") or {}
    methods_m = m.get("methods") or {}
    for name in sorted(set(methods_f) | set(methods_m)):
        a, b = methods_f.get(name), methods_m.get(name)
        print(f"  方法 {name}: 同形 {'是' if a == b else '否'}"
              f"（full {len(a) if a else 0} 句 / mats {len(b) if b else 0} 句）")
    for key, source in sources.items():
        for name in ("to_dict", "from_dict"):
            print(f"  [{key}] {name} 字面键序 {dict_literal_keys(source, name)}")
            print(f"  [{key}] {name} 在类外的同名函数数 = "
                  f"{sum(1 for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name)}")


def git_history() -> None:
    print("\n===== E. git 历史：这套东西被改过几次、几次是「两边各改一次」 =====")
    log = subprocess.run(
        ["git", "log", "--format=%h|%s", "--name-only", "-80", "--",
         *TARGETS.values()],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    blocks: list[tuple[str, set[str]]] = []
    current: tuple[str, set[str]] | None = None
    for line in log.splitlines():
        head = line.split("|")[0]
        if "|" in line and len(head) == 8:
            current = (line, set())
            blocks.append(current)
        elif line.strip() and current is not None:
            current[1].add(line.strip())
    both = [b for b in blocks if len(b[1]) >= 2]
    print(f"  两文件被**同一提交**一起改过 {len(both)} 次（总提交 {len(blocks)} 次）：")
    for subject, files in both:
        print(f"    {subject[:80]}")

    print("\n  逐个关键字：这套东西本体被哪几次提交改过（-S 逐字改）")
    keywords = {
        "状态视图": 'def full_task_status',
        "状态视图(mats)": 'def task_status',
        "run": 'def run(self)',
        "快照封套": 'def _write_snapshot',
        "数据形状": 'class _PartState',
        "取值器": 'def cancel(self)',
        "目标共享件": 'def restore_snapshot_parts',
    }
    for label, needle in keywords.items():
        out = subprocess.run(
            ["git", "log", "--oneline", "-20", f"-S{needle}", "--",
             *TARGETS.values(), TASK_MODULE],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        count = len(out.splitlines()) if out else 0
        print(f"    [{label}] `{needle}` 命中 {count} 次")
        for line in (out.splitlines() if out else []):
            print(f"        {line}")


def main() -> int:
    # 第二个参数 = 证据文件（UTF-8 由脚本自己落盘，不走 shell 重定向：
    # PowerShell 的 `>` 在 5.1 下写 UTF-16，仓内 evidence 的口径是 UTF-8）。
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as handle:
            original = sys.stdout
            sys.stdout = handle
            try:
                return _run()
            finally:
                sys.stdout = original
    return _run()


def _run() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    before = {k: from_git(base, v) for k, v in TARGETS.items()}
    after = {k: from_disk(v) for k, v in TARGETS.items()}
    print_rows(f"改动前（git {base}）", before)
    print_rows("现状（工作区）", after)
    print_part_shape(before)
    print("\n----- 现状的 `_PartState`（改动后如有） -----")
    print_part_shape(after)
    git_history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
