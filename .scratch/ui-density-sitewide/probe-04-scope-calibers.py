r"""读数量具（只读）：某个（或全部）作用域的**三条口径**一次算清 + 明细。

为什么要有它（04 单评审的两条）：
  · 票面写的"63 处描边"是**探针口径**（含单边分隔线与 `border: 0`），而施工要的是
    **整圈完整框**口径（03 单立的那条：完整 `border:` 且值不是 none/0，实测 24 处）——
    两个口径差一倍以上，混着读就会把"没有 63 个盒子"当成漏改。**票面的数要按脚本复算**
    （README 坑 7）。这一支把两条口径摆在一起。
  · 上一版（`recon-04-code.py`）把某个作用域的东西又抄了一遍——与 `dump-03-rules.py`
    重复，且"按行号取首条规则"在同一行落两条规则时会张冠李戴（README 明写别那么干）。
    现在：口径全部 `from scope_lib import …`（整圈完整框那一条已提到 `scope_lib.full_borders`），
    **要看完整声明体请用 `dump-03-rules.py --scope X`**，本支只管"算数"。

三类用法：

    # 总账（每个作用域四条数：规则 / 裸 px 字号 / 裸令牌间距 / 整圈完整框）+ 两条进度尺
    python .scratch\ui-density-sitewide\probe-04-scope-calibers.py

    # 某一页的明细（三条一起看）
    python .scratch\ui-density-sitewide\probe-04-scope-calibers.py --scope code

    # 只要某一类明细
    python .scratch\ui-density-sitewide\probe-04-scope-calibers.py --scope code --kind borders

⚠ 读的是**工作树**（与 `probe-01` 同）：整改后重跑只会显示 0/0——它不会告诉你
"这不是改前那一版"。要看改前那一版的数，先 `git checkout <固定点> -- <文件>`（或 `git stash`），
04 单就是这么量"改前 24 处整圈框"的。
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import (PAGE, bare_fonts, bare_token_spaces, full_borders,  # noqa: E402
                       load_scopes, read_page, rules_in)


def load_backlog() -> list[str]:
    """进度清单（页面尺）——条目数本身就是进度（单一出处 = 守卫源码）。"""
    import re
    text = (HERE.parents[1] / "tests" / "js" / "css-tokens.test.mjs").read_text(encoding="utf-8")
    block = re.search(r"const SITEWIDE_BACKLOG = new Set\(\[(.*?)\]\);", text, re.S)
    if not block:
        raise SystemExit("守卫里找不到 SITEWIDE_BACKLOG —— 格式变了")
    return re.findall(r'"([\w-]+)"', block.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="", help="只看某个作用域（空 = 全部）")
    ap.add_argument("--kind", default="", choices=["", "fonts", "spaces", "borders"])
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()

    if args.scope and args.kind:
        rules = rules_in(text, args.scope)
        print(f"== {args.scope} 作用域的 {args.kind} ==")
        if args.kind == "fonts":
            rows: dict[int, list[str]] = {}
            for line, value in bare_fonts(text, args.scope):
                rows.setdefault(line, []).append(value)
            # **按规则体认人**：同一行可能落两条规则（README 的账），所以这里逐条规则打印，
            # 不按行号去"取首条"（上一版就是那么张冠李戴的）
            for line, sel, b0, b1 in rules:
                values = [v for v in rows.get(line, [])]
                if values:
                    print(f"  L{line}  {'/'.join(v + 'px' for v in values):<12} {sel[:96]}")
            print(f"  [共 {len(bare_fonts(text, args.scope))} 处]")
        elif args.kind == "spaces":
            for line, sel, value in bare_token_spaces(text, args.scope):
                print(f"  L{line}  {value}px  {sel[:96]}")
            print(f"  [共 {len(bare_token_spaces(text, args.scope))} 处取值]")
        else:
            for line, sel, value in full_borders(text, args.scope):
                print(f"  L{line}  {value:<38} {sel[:90]}")
            print(f"  [共 {len(full_borders(text, args.scope))} 处整圈完整框]")
        return 0

    names = [args.scope] if args.scope else [n for n, _ in scopes]
    print(f"{'scope':<12}{'rules':>7}{'bareFont':>10}{'bareSpace':>11}{'fullBoxes':>11}")
    tot = Counter()
    for name in names:
        c = Counter(rules=len(rules_in(text, name)),
                    fonts=len(bare_fonts(text, name)),
                    spaces=len(bare_token_spaces(text, name)),
                    boxes=len(full_borders(text, name)))
        print(f"{name:<12}{c['rules']:>7}{c['fonts']:>10}{c['spaces']:>11}{c['boxes']:>11}")
        tot.update(c)
    print(f"{'合计':<12}{tot['rules']:>7}{tot['fonts']:>10}{tot['spaces']:>11}{tot['boxes']:>11}")
    print("（`fullBoxes` = **整圈完整框**；探针的 borders 那一栏含单边分隔线与 `border: 0`，"
          "两个口径别混着读）")

    backlog = load_backlog()
    done = [n for n, _ in scopes if n not in backlog]
    print(f"\n页面尺 SITEWIDE_BACKLOG = {len(backlog)} 条：{', '.join(backlog)}")
    print(f"          已完工 = {len(done)} 条：{', '.join(done)}")
    print(f"文件：{PAGE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
