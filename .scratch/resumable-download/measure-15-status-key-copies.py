"""工单 15「先量再动」的取证脚本（只读，不改仓库）。

问的问题：**「状态载荷 12 个键」这条契约在仓内一共有几份副本、各份断言到什么强度、
各覆盖哪一侧哪一态、哪几份会被端点测试真的跑到？** 分六节：

  A. **扫描面**——扫了哪些文件、跳过什么（跳过必须写出来，否则「一共几份」不可信）；
  B. **每一份副本**（表）：位置 / 形状（常量 / 内联字面 / fixture 输入 / 产品侧投影）/
     它写下来的键集合（保序）；
  C. **断言强度**（表）：`==`（严格）/ `<=` `>=`（子集超集）/ `只读不判`，
     以及**覆盖哪一侧**（`full_task_status` / `task_status` / 端点）与**哪一态**
     （空态 `None` / 有态 / 两态）；
  D. **端点测试覆盖**：哪些用例真的打到 `/api/update/*/status`，它们各自碰到哪一份；
  E. **`_RETRY_FIELDS` 与 12 键的重叠面**：名字交集 / 语义关系（内部属性名 vs 载荷键名）/
     各自被谁消费——**别拿「名字像」当成「同一份契约」**；
  F. **基线对照**：按 `git show <base>:<文件>` 取改动前那份，同样跑一遍（重排后可复现）。

**契约本体不写死在量具里**：12 键 = 两处**产品侧投影**各自写下的键集合（空态 + 有态）——
量具从产品源码里现算，免得量具自己成为第 N 份副本。

用法：
  python .scratch/resumable-download/measure-15-status-key-copies.py                  # 基线 = 工单 14 之前的 HEAD
  python .scratch/resumable-download/measure-15-status-key-copies.py <ref>
  python .scratch/resumable-download/measure-15-status-key-copies.py <ref> <证据文件>
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = "0344eb61"

PRODUCT_FILES = {
    "full": "src/contest_generator/full_task.py",
    "materials": "src/contest_generator/materials_task.py",
}
STATUS_FUNCS = {"full": "full_task_status", "materials": "task_status"}
TEST_FILES = [
    "tests/test_download_status_surface.py",
    "tests/test_full_task.py",
    "tests/test_materials_task.py",
]
JS_FILES = [
    "tests/js/download-progress.test.mjs",
    "tests/js/full-update.test.mjs",
    "tests/js/materials-update.test.mjs",
]
# 端点路径（D 节用）——写成常量便于将来端点改名时一眼看到量具的扫描面。
STATUS_ENDPOINTS = ("/api/update/full/status", "/api/update/materials/status")


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{out.stderr.strip()}")
    return out.stdout


def from_git(ref: str, rel: str) -> str | None:
    """按 `git show <ref>:<路径>` 取改动前那份（不读工作区现状）。"""
    out = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return None
    return out.stdout


def from_disk(rel: str) -> str | None:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


def function_node(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def payload_dicts(node: ast.AST) -> list[tuple[int, list[str]]]:
    """`*_status` 里的**载荷** dict —— 口径 = 「被 `return` 直接返回的那个 dict」。

    第一版把函数里所有 dict 都算了进去：格式化成 15 个键（卷条目那条
    `{name, downloaded_bytes, total_bytes, ok}` 也被算成契约的一份）。
    第二版改成「祖先里有 dict 的不算」，**仍然错**——卷条目是
    `parts = [{...} for p in task.parts]` 里的**列表推导元素**，祖先里没有 dict。
    量具自己制造的两次假账，故改成最直白的规则：**`return {...}` 的 value 是 Dict 才算载荷**
    （两侧的 idle / live 分支都是直接 `return {...}`）。
    """
    out: list[tuple[int, list[str]]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
            keys = [k.value for k in child.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if keys:
                out.append((child.value.lineno, keys))
    return sorted(out)


def status_projection_shape(source: str, fn_name: str) -> list[tuple[int, list[str]]]:
    """→ [(行号, 键序列)]，产品侧 `*_status` 里**每个返回载荷**的键。"""
    tree = ast.parse(source)
    node = function_node(tree, fn_name)
    if node is None:
        return []
    return payload_dicts(node)


def set_literal_keys(node: ast.AST, consts: dict[str, set[str]]) -> set[str] | None:
    """把 `{...}` / `A | B` / `set(...)` 之类的表达式解析成键集合（认不出 → None）。"""
    if isinstance(node, ast.Set):
        keys = {e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        return keys or None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = set_literal_keys(node.left, consts)
        right = set_literal_keys(node.right, consts)
        if left is not None and right is not None:
            return left | right
        return None
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def enclosing_function(tree: ast.AST, line: int) -> str:
    best = "<模块级>"
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.lineno <= line <= (node.end_lineno or node.lineno):
                if best == "<模块级>" or node.lineno > 0:
                    best = node.name
                    break
    return best


def scan_test_file(rel: str, source: str) -> dict[str, object]:
    """一份测试文件里的：模块级键集合常量 / 集合比较断言 / 端点用例。"""
    tree = ast.parse(source)
    consts: dict[str, set[str]] = {}
    const_lines: dict[str, int] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name):
            keys = set_literal_keys(stmt.value, consts)
            if keys:
                consts[stmt.targets[0].id] = keys
                const_lines[stmt.targets[0].id] = stmt.lineno

    compares: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        left, right = node.left, node.comparators[0]
        lk, rk = set_literal_keys(left, consts), set_literal_keys(right, consts)
        if lk is None and rk is None:
            continue
        op = type(node.ops[0]).__name__
        compares.append({
            "line": node.lineno,
            "func": enclosing_function(tree, node.lineno),
            "op": {"Eq": "==", "LtE": "<=", "GtE": ">=", "Lt": "<", "Gt": ">"}.get(op, op),
            "left": ast.unparse(left), "right": ast.unparse(right),
            "left_keys": lk, "right_keys": rk,
            "载荷侧": "set(" in ast.unparse(left) or "set(" in ast.unparse(right),
        })

    endpoint_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            body = ast.get_source_segment(source, node) or ""
            hits = [p for p in STATUS_ENDPOINTS if p in body]
            if hits:
                endpoint_funcs.append((node.name, hits))
    return {"consts": consts, "const_lines": const_lines, "compares": compares,
            "endpoint_funcs": endpoint_funcs}


KEY_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*:\s*")
# 「这一份是 12 键契约的副本」的判据：名字里带 STATUS_KEYS，或**枚举了契约的 ≥8 个键**。
# 阈值 8 不是随手取的：实测 `_RETRY_FIELDS` 与契约只重叠 4 个（那是另一件事的字段集），
# 而真正的契约副本一律 ≥11 —— 中间留出空档，避免把「部分重叠」误判成副本。
CONTRACT_COPY_MIN_OVERLAP = 8


def scan_js_key_blocks(source: str) -> list[tuple[int, list[str]]]:
    """JS 里**连续成块的 `key: value` 行**（= 有人在文件里把载荷键拼了一遍）。

    JS 侧有两种形态，都要认：`tests/js/download-progress.test.mjs` 用
    `function fullStatus(){ return {...} }` 造 fixture；`full-update.test.mjs` /
    `materials-update.test.mjs` 则把对象字面量**内联在调用点上**
    （`fullProgressHTML({ state: …, parts: […] })`）。第一版只认前者，
    后两个文件数出 0 个键——量具自己的假账（第二版也栽过一次）。
    """
    lines = source.splitlines()
    blocks: list[tuple[int, list[str]]] = []
    run: list[str] = []
    start = 0
    for idx, line in enumerate(lines, 1):
        match = KEY_RE.match(line)
        if match:
            if not run:
                start = idx
            run.append(match.group(1))
            continue
        if len(run) >= 3:
            blocks.append((start, run))
        run = []
    if len(run) >= 3:
        blocks.append((start, run))
    return blocks


def product_keys(sources: dict[str, str]) -> dict[str, set[str]]:
    """两侧产品投影写下的键（并集）——**契约本体由它现算，量具不自带副本**。"""
    out: dict[str, set[str]] = {}
    for flavor, rel in PRODUCT_FILES.items():
        source = sources.get(rel)
        if source is None:
            continue
        keys: set[str] = set()
        for _, seq in status_projection_shape(source, STATUS_FUNCS[flavor]):
            keys |= set(seq)
        out[flavor] = keys
    return out


def report(title: str, sources: dict[str, str]) -> None:
    print(f"\n########## {title} ##########")
    pk = product_keys(sources)
    contract = set().union(*pk.values()) if pk else set()
    print("\n===== B. 契约本体（从产品侧投影现算，量具不自带副本） =====")
    for flavor, keys in pk.items():
        print(f"  [{flavor}] `{STATUS_FUNCS[flavor]}` 写下的键 {len(keys)} 个：{sorted(keys)}")
    print(f"  两侧并集（= 本量具口径的「12 键契约」）：{len(contract)} 个")

    print("\n===== B′. 每一份副本 =====")
    rows: list[str] = []
    for flavor, rel in PRODUCT_FILES.items():
        source = sources.get(rel)
        if source is None:
            continue
        for line, seq in status_projection_shape(source, STATUS_FUNCS[flavor]):
            rows.append(f"  产品侧  {rel}:{line}  {STATUS_FUNCS[flavor]} 里的 dict 字面量")
            rows.append(f"          形状=产品投影（每个分支一份字面键表） 键 {len(seq)} 个：{seq}")
    for rel in TEST_FILES:
        source = sources.get(rel)
        if source is None:
            continue
        info = scan_test_file(rel, source)
        for name, keys in info["consts"].items():          # type: ignore[union-attr]
            line = info["const_lines"][name]              # type: ignore[index]
            overlap = len(keys & contract)
            hit = ("★契约副本" if overlap >= CONTRACT_COPY_MIN_OVERLAP
                   else f"（与契约重叠 {overlap} 个——不足副本阈值 {CONTRACT_COPY_MIN_OVERLAP}，"
                        f"不是契约副本）")
            rows.append(f"  测试常量 {rel}:{line}  {name} = {len(keys)} 个键 {hit}")
            rows.append(f"          键：{sorted(keys)}")
    for rel in JS_FILES:
        source = sources.get(rel)
        if source is None:
            continue
        for start, keys in scan_js_key_blocks(source):
            overlap = sorted(set(keys) & contract)
            rows.append(f"  前端对象字面量 {rel}:{start} 起  {len(keys)} 个键"
                        f"（**只读不判**：渲染用例的输入）与契约重叠 {len(overlap)}：{overlap}")
    print("\n".join(rows) if rows else "  （无）")

    print("\n===== C. 断言强度（集合比较逐条列出） =====")
    print(f"  *分类判据*：`★契约` = 两侧里有一侧名字含 `STATUS_KEYS`，"
          f"或**枚举了契约 ≥{CONTRACT_COPY_MIN_OVERLAP} 个键**（真正的契约副本）；"
          "其余列为 `其它集合断言`（例如 `_RETRY_FIELDS` 那条结构守卫——另一件事，"
          "列出来只为看重叠面）。")
    for rel in TEST_FILES:
        source = sources.get(rel)
        if source is None:
            continue
        info = scan_test_file(rel, source)
        compares = info["compares"]                          # type: ignore[assignment]
        if not compares:
            print(f"  {rel}: （没有集合比较断言）")
            continue
        print(f"  {rel}:")
        for c in compares:                                   # type: ignore[union-attr]
            lk, rk = c["left_keys"], c["right_keys"]
            text = str(c["left"]) + str(c["right"])
            overlaps = [len(k & contract) for k in (lk, rk) if k]
            is_copy = "STATUS_KEYS" in text or any(
                n >= CONTRACT_COPY_MIN_OVERLAP for n in overlaps)
            label = "★契约" if is_copy else "其它集合断言"
            covered = ""
            if lk is not None and rk is not None:
                if c["op"] == "==":
                    covered = "两侧相等" if lk == rk else "**两侧不等（断言自相矛盾？）**"
                elif c["op"] == "<=":
                    covered = f"子集：左含于右？{lk <= rk}；右多余 {sorted(rk - lk)}"
                elif c["op"] == ">=":
                    covered = f"超集：左含右？{rk <= lk}；左多余 {sorted(lk - rk)}"
            side = "载荷" if c["载荷侧"] else "字面"
            print(f"    [{label}] 行 {c['line']}（{c['func']}）"
                  f"`{c['left']}` {c['op']} `{c['right']}`"
                  f"  → 强度 {c['op']}（{side}侧 vs 字面侧）{('；' + covered) if covered else ''}")

    print("\n===== D. 端点测试覆盖（哪几份副本会被端点用例真的跑到） =====")
    print("  *口径*：端点用例 = 正文里出现 `%s` 之一的用例；"
          "「跑到哪一份副本」= 它内部**有没有**与契约相交的集合比较断言"
          "（有 → 断言作用在载荷上，至少要有一份副本提供期望值）。"
          % " / ".join(STATUS_ENDPOINTS))
    for rel in TEST_FILES:
        source = sources.get(rel)
        if source is None:
            continue
        info = scan_test_file(rel, source)
        funcs = info["endpoint_funcs"]                          # type: ignore[assignment]
        compares = info["compares"]                             # type: ignore[assignment]
        if not funcs:
            print(f"  {rel}: （没有用例直接打 status 端点）")
            continue
        for name, hits in funcs:                                # type: ignore[union-attr]
            mine = [c for c in compares if c["func"] == name]   # type: ignore[union-attr]
            if not mine:
                print(f"  {rel}::{name} → {hits}；**不断言键集合**（只读几个字段值）"
                      f"→ 不依赖任何一份契约副本")
                continue
            for c in mine:
                text = str(c["left"]) + str(c["right"])
                named = "STATUS_KEYS" if "STATUS_KEYS" in text else "内联字面"
                print(f"  {rel}::{name} → {hits}；`{c['left']}` {c['op']} `{c['right']}`"
                      f" → 用到的副本：**{named}**")

    print("\n===== F. 结构守卫的爆炸半径（全 tests 树扫一遍） =====")
    print(f"  问题：若立一条「12 键契约只许有一处副本」的守卫（判据 = 字面集合**或其联合**"
          f"枚举了契约 ≥{CONTRACT_COPY_MIN_OVERLAP} 个键），它今天会**命中谁**？")
    print("  *口径*：与守卫**同口径**（字面量 + 模块级 `A | B` 联合）——"
          "第一版只认字面量，于是连契约本体 `STATUS_KEYS = EXISTING_KEYS | NEW_KEYS` 都认不出来。"
          "**按文件归并**：同一个文件里 `名字 / 字面量 / 联合` 三种节点会把同一份契约数三次，"
          "逐节点印会印出十几行假账（第一版就是这样），故只报「哪些文件里有 ≥8 键的副本」。")
    per_file: dict[str, set[int]] = {}
    for rel in tracked_python_under("tests/"):
        source = sources.get(rel, from_disk(rel))
        if source is None:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        consts: dict[str, set[str]] = {}
        assigns = [stmt for stmt in ast.walk(tree)
                   if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)]
        for _ in range(2):
            for stmt in assigns:
                keys = _expr_keys(stmt.value, consts)
                if keys:
                    consts[stmt.targets[0].id] = keys
        for node in ast.walk(tree):
            keys = _expr_keys(node, consts)
            if keys and len(keys & contract) >= CONTRACT_COPY_MIN_OVERLAP:
                per_file.setdefault(rel, set()).add(len(keys & contract))
    print(f"  命中 {len(per_file)} 个文件：")
    for rel in sorted(per_file):
        counts = "、".join(f"{n} 键" for n in sorted(per_file[rel], reverse=True))
        print(f"    {rel}（{counts}）")
    print("  （阈值 8：`_RETRY_FIELDS` 那类「部分重叠」的集合因此不会被误伤——"
          "实测它与契约只重叠 4 个。）")

    print("\n===== E. `_RETRY_FIELDS` 与 12 键的重叠面 =====")
    surface = (ROOT / "tests/test_download_status_surface.py")
    if surface.is_file() and "tests/test_download_status_surface.py" in sources:
        info = scan_test_file("tests/test_download_status_surface.py",
                              sources["tests/test_download_status_surface.py"])
        retry = info["consts"].get("_RETRY_FIELDS")             # type: ignore[union-attr]
        if retry:
            print(f"  `_RETRY_FIELDS` = {sorted(retry)}（{len(retry)} 个）")
            print(f"  与 12 键的**名字**交集 = {sorted(retry & contract)}")
            print(f"  只在 `_RETRY_FIELDS` 里（**不是载荷键**）= {sorted(retry - contract)}")
            print(f"  只在契约里（不是重试观测字段）= {sorted(contract - retry)}")
            print("  语义差异（量出来的一对一关系）：`_RETRY_FIELDS` 那一侧是**内部属性名**"
                  "（`task_retry.TaskRetryState` 的字段），契约那一侧是**载荷键名**——"
                  "`last_error_kind`（属性）对应 `error_kind`（载荷键），"
                  "`last_retry_at` 根本不进载荷。")
        else:
            print("  （`_RETRY_FIELDS` 不在该文件里）")


def _expr_keys(node: ast.AST, consts: dict[str, set[str]]) -> set[str] | None:
    """一个表达式能解出的「字面键」：`{…}` / `A | B` / 已在 consts 里的名字；解不出 → None。"""
    if isinstance(node, ast.Set):
        keys = {e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        return keys or None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _expr_keys(node.left, consts), _expr_keys(node.right, consts)
        if left is not None and right is not None:
            return left | right
        return None
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def tracked_python_under(prefix: str) -> list[str]:
    """tracked 的 `.py` 文件（用于 F 节的全树扫描；扫描面写进输出，别藏）。"""
    out = subprocess.run(["git", "ls-files", prefix], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    return [line for line in (out.stdout or "").splitlines()
            if line.endswith(".py") and line.strip()]


def main() -> int:
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
    rels = list(PRODUCT_FILES.values()) + TEST_FILES + JS_FILES
    print(f"仓库根：{ROOT}")
    print(f"基线：{base}（改动前那一份走 `git show <ref>:<文件>`，不读工作区现状）")
    print("\n===== A. 扫描面 =====")
    print(f"  产品侧投影：{list(PRODUCT_FILES.values())}")
    print(f"  测试文件：{TEST_FILES}")
    print(f"  前端 fixture：{JS_FILES}")
    print("  **扫描面就是这些**：本量具不搜全仓找「第 N 份副本」，"
          "而是按「状态载荷键会出现在哪些地方」逐个点名（产品投影 / 测试断言 / 前端输入）。")

    current = {rel: text for rel in rels if (text := from_disk(rel)) is not None}
    before = {rel: text for rel in rels if (text := from_git(base, rel)) is not None}
    missing = [rel for rel in rels if rel not in current]
    if missing:
        print(f"  （工作区缺这些文件：{missing}）")
    report(f"改动前（git {base}）", before)
    report("现状（工作区）", current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
