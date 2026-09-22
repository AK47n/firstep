# -*- coding: utf-8 -*-
"""真红证：把**收走前**（工单 full-update-state-into-ctx/01 之前那个提交）的 `full_task.py`、
`webapp.py` 与全部测试源码喂给 `tests/test_webapp_state_home.py` 的同一套判据
（工单 full-update-state-into-ctx/03）。

只读：用 `git show <base>:<path>` 取收走前的源码，不碰工作区、不改仓库文件。
**判据不是副本**：这里直接调守卫那边的 `full_chain_state_violations`（那条腿的聚合），
`webapp.py` 也一并喂进去——因为正向那条腿问的是「**`AppContext`** 有没有 `full_last_check` /
`full_task`」，而 `AppContext` 定义在 webapp 里（第一版没喂，当场缺字段假红）。

**base 不能写 HEAD**：本系列提交之后 HEAD 就是收走后的代码，拿 HEAD 当「收走前」会让红证
静默失效（先例 `release-channel-dedupe/01` 踩过一次）。缺省 base = **显式钉**的 `c6040566`
（01 之前那个提交），并**自校验**：base 版里若找不到那两处模块级会话态（按名字逐个查）就大声
失败——选错 base 不许产假绿。

用法：
    python .scratch/full-update-state-into-ctx/probe-01-pin-red-proof.py --out red-proof.txt
    python .scratch/full-update-state-into-ctx/probe-01-pin-red-proof.py --base <rev>

`--out` 的理由：PowerShell 5.1 的 `>` 重定向写 UTF-16LE（`read` 工具当二进制拒读），
所以让探针自己按 UTF-8 落盘。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

# 本机控制台是 GBK：报告里带 `✗` / `→`，不重设就会在 print 上抛 UnicodeEncodeError
# （第一版实测丢了整份证据文件）。证据文件本身一律 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # 被重定向到非文本流时不管
        pass

from test_webapp_state_home import (  # noqa: E402
    _FULL_TASK_MOVED_STATE,
    full_chain_state_violations,
    global_names,
    global_statements,
    module_level_names,
    session_state_assignments,
    src_global_statements,
)

# 收走前那个提交（工单 01 的 base）。**显式钉，不写 HEAD。**
DEFAULT_BASE = "c6040566"

# base 自校验要逐个查到的名字（收走前那两处模块级全局）。
_REQUIRED_BASE_NAMES = frozenset({"_LAST_CHECK", "_FULL_TASK"})

FULL_TASK_PATH = "src/contest_generator/full_task.py"
WEBAPP_PATH = "src/contest_generator/webapp.py"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def base_source(rev: str, path: str) -> str:
    return git("show", f"{rev}:{path}")


def test_paths() -> list[str]:
    """仓库里全部测试源码（与守卫同口径：`tests/**/*.py`，含 conftest 与子目录）。

    路径用 **POSIX 形式**（`as_posix()`）：`git show <rev>:<path>` 认正斜杠，Windows 的
    `str(Path)` 会给反斜杠，那条路会静默取不到文件（先例探针栽过，红证的测试侧两条腿凭空消失）。
    """
    return [
        path.relative_to(REPO).as_posix()
        for path in sorted((REPO / "tests").rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def base_tests(base: str) -> dict[str, str]:
    """base 版的测试源码；base 里还没有的文件（如本单新增的守卫腿）跳过。"""
    out: dict[str, str] = {}
    for rel in test_paths():
        try:
            out[rel] = base_source(base, rel)
        except subprocess.CalledProcessError:
            continue
    return out


def now_tests() -> dict[str, str]:
    return {rel: (REPO / rel).read_text(encoding="utf-8") for rel in test_paths()}


def base_src(base: str) -> dict[str, str]:
    """base 版 `src/**/*.py` 的源码（给 `src/` 全域「`global` = 0」那条腿出前后读数）。

    文件清单也取自 base（`git ls-tree -r --name-only <rev> src`）——不能拿当前树的清单去 base 里
    取文件：base 里有、今天已删的文件会静默漏掉，反过来会 `git show` 报错。
    """
    listing = git("ls-tree", "-r", "--name-only", base, "src").splitlines()
    out: dict[str, str] = {}
    for rel in listing:
        rel = rel.strip()
        if rel.endswith(".py"):
            out[rel] = base_source(base, rel)
    return out


def now_src() -> dict[str, str]:
    return {
        path.relative_to(REPO).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((REPO / "src").rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def name_counts(sources: dict[str, str]) -> dict[str, int]:
    """搬走的那批名字在源码里的引用处数（**人读读数，不是判据**）。"""
    out: dict[str, int] = {}
    for name, source in sources.items():
        for state_name in _FULL_TASK_MOVED_STATE:
            hits = len(re.findall(rf"\b{re.escape(state_name)}\b", source))
            if hits:
                out[f"{name}::{state_name}"] = hits
    return out


def main() -> int:
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else DEFAULT_BASE
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else None

    before_task = base_source(base, FULL_TASK_PATH)
    before_webapp = base_source(base, WEBAPP_PATH)
    now_task = (REPO / FULL_TASK_PATH).read_text(encoding="utf-8")
    now_webapp = (REPO / WEBAPP_PATH).read_text(encoding="utf-8")
    before_all = {FULL_TASK_PATH: before_task, WEBAPP_PATH: before_webapp} | base_tests(base)
    now_all = {FULL_TASK_PATH: now_task, WEBAPP_PATH: now_webapp} | now_tests()

    lines: list[str] = []

    # base 自校验：收走前那个提交里必须**逐个**真有那两处模块级会话态 + 那 1 处 global
    missing = _REQUIRED_BASE_NAMES - (
        module_level_names(before_task) | global_names(before_task)
    )
    if missing or not global_statements(before_task):
        msg = (
            f"✗ base {base[:8]} 里找不到模块级会话态 {sorted(missing)}"
            f"（global 语句 {len(global_statements(before_task))} 处）"
            " —— 这不是收走前的提交，换 --base"
        )
        print(msg, file=sys.stderr)
        return 2

    lines.append(f"== ① 引用面普查（base={base[:8]} vs 当前工作树；人读读数，不是判据）==")
    before_counts, now_counts = name_counts(before_all), name_counts(now_all)
    lines.append("  收走前：" + ("，".join(f"{k}={v}" for k, v in sorted(before_counts.items())) or "（无）"))
    lines.append("  收走后：" + ("，".join(f"{k}={v}" for k, v in sorted(now_counts.items())) or "（无）"))
    lines.append(
        f"  full_task 模块级会话态：收走前 {sorted(session_state_assignments(before_task))}"
        f" → 收走后 {sorted(session_state_assignments(now_task)) or '（无）'}"
    )
    lines.append(
        f"  full_task global 语句：收走前 {len(global_statements(before_task))} 处"
        f" → 收走后 {len(global_statements(now_task))} 处"
    )

    red = full_chain_state_violations(before_task, base_tests(base), before_webapp)
    lines.append(f"\n== ② 同一套判据作用在 base 上（应红）：{len(red)} 条 ==")
    lines += [f"  ✗ {line}" for line in red]

    green = full_chain_state_violations(now_task, now_tests(), now_webapp)
    lines.append("\n== ③ 同一套判据作用在当前工作树上（应绿）==")
    lines.append("  （无违规）" if not green else "\n".join(f"  ✗ {line}" for line in green))

    # ④ `src/` 全域「global 语句 = 0」那条腿的真读数（评审指出：它此前只有合成红证）
    before_src = base_src(base)
    now_srcs = now_src()
    before_globals = src_global_statements(before_src)
    now_globals = src_global_statements(now_srcs)
    lines.append(
        f"\n== ④ src/ 全域 global 腿（base {len(before_src)} 个文件 vs 当前 {len(now_srcs)} 个）=="
    )
    lines.append(f"  收走前：{before_globals or '（无）'}")
    lines.append(f"  收走后：{now_globals or '（无）'}")
    src_ok = bool(before_globals) and not now_globals

    ok = bool(red) and not green and src_ok
    lines.append(
        "\n"
        + (
            "RED→GREEN 成立（两条腿的红证 + 绿证同源）"
            if ok
            else "异常：红 / 绿 / src 全域读数不符合预期"
        )
    )

    report = "\n".join(lines)
    # **先落盘再打印**：本机控制台是 GBK，报告里的 `✗`（U+2717）打不出来会抛
    # UnicodeEncodeError——第一版就是这么丢了证据文件的。文件一律 UTF-8。
    if out_path is not None:
        out_path.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
