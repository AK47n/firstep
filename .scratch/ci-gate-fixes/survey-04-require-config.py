# -*- coding: utf-8 -*-
r"""工单 ci-gate-fixes/04 的盘点量具（只读，不改任何文件）。

三张表：

* **表 1** 每一处 `_require_config(` 落在哪个函数 / 哪个路由上 → 人工分成
  「真需要 AI」与「只需要库在哪」两类，写进工单 Comments 当判据。
* **表 2** 路由端点的闸门来源矩阵：`cfg` = 直接调 `_require_config`（现有 key 闸门）、
  `lib` = 只经 `_library_dir` / `_masters_dir`（本单要改成"只解析库在哪"的两处）。
* **表 3** **传递闭包**：端点**经由辅助函数**（不直接出现 `_llm(` 的）是否也会派发 LLM。
  这是本单真正的安全边界——表 2 的字符串匹配看不见 `references` → helper → `_llm`
  这类路径，只按字面判会把 AI 端点误放进"只读库"那一类。

用法（仓库根）：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ci-gate-fixes\survey-04-require-config.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "webapp.py"

LLM_ENTRY = ("_llm(", "LLMRun(", "_assemble_topic_context(")
LIB_ACCESSOR = ("_library_dir(", "_masters_dir(")


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()

    funcs: dict[str, dict] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = node.end_lineno or node.lineno
        body = "\n".join(lines[node.lineno - 1 : end])
        decs = []
        for dec in node.decorator_list:
            text = ast.get_source_segment(src, dec) or ""
            decs.append(" ".join(text.split()))
        # 同名函数取首个（webapp.py 里重名只出现在不同作用域，本盘点够用）
        funcs.setdefault(
            node.name,
            {
                "line": node.lineno,
                "end": end,
                "body": body,
                "decs": decs,
                "node": node,
            },
        )

    def enclosing(lineno: int) -> tuple[str, list[str]]:
        best = None
        for name, info in funcs.items():
            if info["line"] <= lineno <= info["end"]:
                span = info["end"] - info["line"]
                if best is None or span < best[0]:
                    best = (span, name, info["decs"])
        if best is None:
            return ("<模块级>", [])
        return (best[1], best[2])

    # ---------- 表 1 ----------
    rows = []
    for i, line in enumerate(lines, start=1):
        if "_require_config(" not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("def _require_config"):
            kind = "定义"
        elif stripped.startswith("#"):
            kind = "注释"
        else:
            kind = "调用"
        name, decs = enclosing(i)
        route = " ".join(d for d in decs if d.startswith("app."))
        rows.append((i, kind, f"{name}{('  ' + route) if route else ''}", stripped))

    calls = [r for r in rows if r[1] == "调用"]
    print("# 表 1 — `_require_config` 调用点盘点\n")
    print(
        f"命中总行数 {len(rows)}：调用 {len(calls)} / 定义 "
        f"{sum(1 for r in rows if r[1] == '定义')} / 注释 "
        f"{sum(1 for r in rows if r[1] == '注释')}；"
        f"涉及 {len({r[2] for r in calls})} 个不同函数。\n"
    )
    print("| 行 | 种类 | 所属函数 / 路由 | 源码片段 |")
    print("|---|---|---|---|")
    for lineno, kind, owner, snippet in rows:
        print(f"| {lineno} | {kind} | {owner} | `{snippet.replace('|', chr(92) + '|')}` |")
    print()

    # ---------- 传递闭包：谁能走到 LLM ----------
    names = set(funcs)

    def callees(name: str) -> set[str]:
        out: set[str] = set()
        for node in ast.walk(funcs[name]["node"]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in names and node.func.id != name:
                    out.add(node.func.id)
        return out

    direct_llm = {
        n for n, info in funcs.items() if any(tok in info["body"] for tok in LLM_ENTRY)
    }
    reaches: dict[str, bool] = {}

    def reaches_llm(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name in reaches:
            return reaches[name]
        if name in direct_llm:
            reaches[name] = True
            return True
        if name in seen:
            return False
        for callee in callees(name):
            if reaches_llm(callee, seen | {name}):
                reaches[name] = True
                return True
        reaches[name] = False
        return False

    # ---------- 表 2 + 表 3 ----------
    print("\n# 表 2 — 路由端点的闸门来源 + LLM 可达性（传递闭包）\n")
    print(
        "`派发LLM` = **经调用图传递**能不能走到 `_llm(` / `LLMRun(` / "
        "`_assemble_topic_context(`（不只看函数体内字面）。\n"
    )
    print("| 行 | 端点函数 | 路由 | 派发LLM | 直接 cfg | 经 lib |")
    print("|---|---|---|---|---|---|")
    risk: list[tuple[str, str]] = []
    lib_only: list[tuple[str, str, str]] = []
    for name, info in sorted(funcs.items(), key=lambda kv: kv[1]["line"]):
        routes = [d for d in info["decs"] if d.startswith("app.")]
        if not routes:
            continue
        has_llm = reaches_llm(name)
        has_cfg = "_require_config(" in info["body"]
        has_lib = any(tok in info["body"] for tok in LIB_ACCESSOR)
        print(
            f"| {info['line']} | `{name}` | {routes[0]} | {'是' if has_llm else ''} | "
            f"{'是' if has_cfg else ''} | {'是' if has_lib else ''} |"
        )
        if has_llm and not has_cfg:
            risk.append((name, routes[0]))
        if has_lib and not has_llm:
            lib_only.append((name, routes[0], info["line"]))

    print()
    print("## ⚠ A. 派发 LLM 但**没有**直接 `_require_config` 的端点（改 lib 前必查）\n")
    if risk:
        for name, route in risk:
            print(f"- `{name}`（{route}）")
    else:
        print("（无）")
    print()
    print("## B. 经 `_library_dir`/`_masters_dir` 取库路径、且**不派发 LLM** 的端点\n")
    print("这些就是「只把闸门收窄」会直接受益的端点；它们今天因为 helpers 要 key 而 400。\n")
    if lib_only:
        for name, route, line in lib_only:
            print(f"- `{name}`（{route}，行 {line}）")
    else:
        print("（无）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
