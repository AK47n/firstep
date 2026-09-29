r"""描边守卫轮 · 侦察读数：把"整圈完整框"逐个 dump 出来，按作用域分组。

口径 = `.scratch/ui-density-sitewide/scope_lib.py` 的 `full_borders`（单一出处，不另抄一份）。
输出是**施工前的照片**，用来回答一个问题：那 115 处能不能按类判（而不是逐条背下来）。
"""

from __future__ import annotations

import collections
import datetime
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "ui-density-sitewide"))

from scope_lib import PAGE, full_borders, load_scopes, read_page, scope_of  # noqa: E402

OUT = HERE / "probe-00-borders.txt"


def main() -> int:
    text = read_page()
    scopes = load_scopes()
    rows = full_borders(text)
    lines: list[str] = []
    add = lines.append
    add("# 读数：描边守卫轮 · 整圈完整框逐条登记（施工前）")
    add("# 命令：python .scratch/border-guard/probe-00-borders.py")
    add(f"# 口径：.scratch/ui-density-sitewide/scope_lib.py 的 full_borders（完整 border: 声明、值非 none/0）")
    add(f"# 文件：{PAGE.relative_to(ROOT).as_posix()}")
    add(f"# 时间：{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}")
    add(f"# 总计：{len(rows)} 处")
    by_scope: dict[str, list[tuple[int, str, str]]] = collections.OrderedDict()
    for line, sel, value in rows:
        by_scope.setdefault(scope_of(sel, scopes), []).append((line, sel, value))
    add("# 按作用域：" + " / ".join(f"{s} {len(v)}" for s, v in by_scope.items()))
    for scope, items in by_scope.items():
        add(f"\n### {scope}（{len(items)} 处）")
        for line, sel, value in items:
            add(f"  {line:6d}  {value:34s}  {' '.join(sel.split())}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"总计 {len(rows)} 处；按作用域：" + " / ".join(f"{s} {len(v)}" for s, v in by_scope.items()))
    print(f"已落盘：{OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
