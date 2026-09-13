"""工单 10「先量再动」的取证脚本（只读，不改仓库）。

量两件事：
  1. **改动前**与**改动后**两个时刻，`full_task._download_one` /
     `materials_task._download_one` 两个函数体各自多大、彼此有多少行完全相同
     （去空白 / 注释 / docstring 后按行比对）。改动前那份从 `git show <ref>:<path>` 取，
     所以重排之后仍然可复现（工单验收记录里那张表就是它跑出来的）。
  2. git 历史：这套序列被同一提交同时改过几次（「两边各改一次」的代价证据）。

用法：
  python .scratch/resumable-download/measure-10-duplication.py            # 基线 = 工单 09 的提交
  python .scratch/resumable-download/measure-10-duplication.py HEAD~1
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 工单 09 的收口提交 = 本单动手之前的形状
DEFAULT_BASE = "918f25b4"
TARGETS = {
    "full": "src/contest_generator/full_task.py",
    "materials": "src/contest_generator/materials_task.py",
}
FUNCS = ("_download_one", "_resolve_download")


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


def function_source(source: str, name: str) -> tuple[int, int, list[str]]:
    """→（起始行, 结束行, 行文本），按 AST 取函数全文（不靠手数行号）。"""
    lines = source.splitlines()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = node.lineno
            end = node.end_lineno or start
            return start, end, lines[start - 1:end]
    return 0, 0, []


def normalized(lines: list[str]) -> list[str]:
    """去空白 / 整行注释 / docstring 正文之后再比——比的是**代码**，不是措辞。"""
    out = []
    for raw in lines:
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith('"""') or text.startswith("'''"):
            continue
        if text.startswith("-") or text.startswith("|"):
            continue        # docstring 里的要点 / 表格行
        out.append("".join(text.split()))
    return out


def compare(label: str, sources: dict[str, str]) -> None:
    print(f"\n===== {label} =====")
    for token in FUNCS:
        bodies = {}
        for key, source in sources.items():
            start, end, lines = function_source(source, token)
            bodies[key] = lines
            print(f"[{token}] {key:9s} {start}-{end}  共 {end - start + 1} 行")
        if not all(bodies.values()):
            print("  （这个时刻没有该函数）")
            continue
        full, mats = normalized(bodies["full"]), normalized(bodies["materials"])
        same = [line for line in full if line in mats]
        only_full = [line for line in full if line not in mats]
        only_mats = [line for line in mats if line not in full]
        print(f"  去噪后：完全相同 {len(same)} 行 / full 独有 {len(only_full)} 行 / "
              f"materials 独有 {len(only_mats)} 行")
        for line in only_full:
            print(f"    只 full: {line}")
        for line in only_mats:
            print(f"    只 materials: {line}")


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    compare(f"改动前（git {base}）", {k: from_git(base, v) for k, v in TARGETS.items()})
    compare("改动后（工作区现状）", {k: from_disk(v) for k, v in TARGETS.items()})

    print("\n== git 历史：同一提交同时改两条任务链路 ==")
    log = subprocess.run(
        ["git", "log", "--format=%h|%s", "--name-only", "-40", "--",
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
    for subject, files in blocks[:10]:
        names = sorted(Path(f).name for f in files)
        flag = "  ← 两边都动" if len(files) >= 2 else ""
        print(f"  {subject[:70]}{flag}")
        print(f"      {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
