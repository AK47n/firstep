# -*- coding: utf-8 -*-
"""真红证：把**收走前**（工单 01/02 落地之前那个提交）的 webapp.py 与全部测试源码喂给
`tests/test_webapp_state_home.py` 的同一套判据（工单 webapp-state-into-ctx/03）。

只读：用 `git show <base>:<path>` 取收走前的源码，不碰工作区、不改仓库文件。
**判据不是副本**：这里直接调守卫那边的 `state_violations`（评审实测过一次"探针自己再写一遍
聚合逻辑"的代价——那份副本已经漂了，漏掉一条判据腿）。

**base 不能写 HEAD**：本系列提交之后 HEAD 就是收走后的代码，拿 HEAD 当「收走前」会让红证
静默失效（先例 `release-channel-dedupe/01` 踩过一次：提交后重跑，第二段凭空变绿）。
缺省 base = **显式钉**的 `5c9fc8b0`（01/02 之前那个提交），并**自校验**：base 版里若找不到那
三处模块级会话态（按名字逐个查，不只查"有没有别的会话态"）就大声失败——选错 base 不许产假绿。

用法：
    python .scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py [--out red-proof.txt]
    python .scratch/webapp-state-into-ctx/probe-01-red-proof.py --base <rev>

`--out` 的理由：PowerShell 5.1 的 `>` 重定向写 UTF-16LE（`read` 工具当二进制拒读；这条坑的
真源与判据在 `tests/js/windows-text-encoding.test.mjs` 的文件头 ②），所以让探针自己按 UTF-8 落盘。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from test_webapp_state_home import (  # noqa: E402
    _MOVED_STATE,
    global_names,
    global_statements,
    module_level_names,
    session_state_assignments,
    state_violations,
)

# 收走前那个提交（工单 01 的 base）：01/02 都在这之后落地。**显式钉，不写 HEAD。**
DEFAULT_BASE = "5c9fc8b0"

# base 自校验要逐个查到的名字（收走前那三处模块级全局）。
_REQUIRED_BASE_NAMES = frozenset({
    "_running_task_execs", "_MATERIALS_LAST_CHECK", "_materials_task",
})

WEBAPP_PATH = "src/contest_generator/webapp.py"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def base_source(rev: str, path: str) -> str:
    return git("show", f"{rev}:{path}")


def test_paths() -> list[str]:
    """仓库里全部测试源码（与守卫同口径：`tests/**/*.py`，含 conftest 与子目录）。

    路径用 **POSIX 形式**（`as_posix()`）：`git show <rev>:<path>` 认正斜杠，
    Windows 的 `str(Path)` 会给反斜杠，那条路会静默取不到文件（本探针第一版就栽在这，
    红证的测试侧两条腿凭空消失）。
    """
    return [
        path.relative_to(REPO).as_posix()
        for path in sorted((REPO / "tests").rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def base_tests(base: str) -> dict[str, str]:
    """base 版的测试源码；base 里还没有的文件（如本单新增的守卫）跳过。"""
    out: dict[str, str] = {}
    for rel in test_paths():
        try:
            out[rel] = base_source(base, rel)
        except subprocess.CalledProcessError:
            continue
    return out


def now_tests() -> dict[str, str]:
    return {rel: (REPO / rel).read_text(encoding="utf-8") for rel in test_paths()}


def name_counts(sources: dict[str, str]) -> dict[str, int]:
    """三个名字在源码里的引用处数（含历史私有拼法；**人读读数，不是判据**）。"""
    out: dict[str, int] = {}
    for name, source in sources.items():
        for state_name in _MOVED_STATE:
            hits = len(re.findall(rf"\b{re.escape(state_name)}\b", source))
            if hits:
                out[f"{name}::{state_name}"] = hits
    return out


def main() -> int:
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else DEFAULT_BASE
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else None

    before_webapp = base_source(base, WEBAPP_PATH)
    now_webapp = (REPO / WEBAPP_PATH).read_text(encoding="utf-8")
    before_all = {WEBAPP_PATH: before_webapp} | base_tests(base)
    now_all = {WEBAPP_PATH: now_webapp} | now_tests()

    lines: list[str] = []

    # base 自校验：收走前那个提交里必须**逐个**真有那三处模块级会话态 + 那 3 处 global
    missing = _REQUIRED_BASE_NAMES - (module_level_names(before_webapp) | global_names(before_webapp))
    if missing or not global_statements(before_webapp):
        msg = (
            f"✗ base {base[:8]} 里找不到模块级会话态 {sorted(missing)}"
            f"（global 语句 {len(global_statements(before_webapp))} 处）"
            " —— 这不是收走前的提交，换 --base"
        )
        print(msg, file=sys.stderr)
        return 2

    lines.append(f"== ① 引用面普查（base={base[:8]} vs 当前工作树；人读读数，不是判据）==")
    before_counts, now_counts = name_counts(before_all), name_counts(now_all)
    lines.append("  收走前：" + ("，".join(f"{k}={v}" for k, v in sorted(before_counts.items())) or "（无）"))
    lines.append("  收走后：" + ("，".join(f"{k}={v}" for k, v in sorted(now_counts.items())) or "（无）"))
    lines.append(
        f"  webapp 模块级会话态：收走前 {sorted(session_state_assignments(before_webapp))}"
        f" → 收走后 {sorted(session_state_assignments(now_webapp)) or '（无）'}"
    )
    lines.append(
        f"  webapp global 语句：收走前 {len(global_statements(before_webapp))} 处"
        f" → 收走后 {len(global_statements(now_webapp))} 处"
    )

    red = state_violations(before_webapp, base_tests(base))
    lines.append(f"\n== ② 同一套判据作用在 base 上（应红）：{len(red)} 条 ==")
    lines += [f"  ✗ {line}" for line in red]

    green = state_violations(now_webapp, now_tests())
    lines.append("\n== ③ 同一套判据作用在当前工作树上（应绿）==")
    lines.append("  （无违规）" if not green else "\n".join(f"  ✗ {line}" for line in green))

    ok = bool(red) and not green
    lines.append("\n" + ("RED→GREEN 成立（红证 + 绿证同源）" if ok else "异常：红或绿不符合预期"))

    report = "\n".join(lines)
    print(report)
    if out_path is not None:
        out_path.write_text(report + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
