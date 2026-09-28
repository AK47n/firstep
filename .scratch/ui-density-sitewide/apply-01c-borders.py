r"""工单 01 施工脚本（三）：shell 作用域拆**内层**完整描边。

口径（照检测页 02/05 定稿）：一屏内**只有最外层容器**有完整矩形描边；内层改留白 /
单条分隔线 / 淡底。保留的例外如实列出（见下）。

**只删整圈 `border: 1px solid var(--border);`**——单边分隔线（`border-bottom` 之类）、
可点控件、语义告警块一个字不碰。改动按**规则区间**定位（同名声明在别的规则里也有，
全局替换会误伤）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-01c-borders.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-01c-borders.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

DROP = "border: 1px solid var(--border);"

# 选择器（按结尾匹配，避开规则前的中文注释）→ 为什么它该去框
TARGETS: dict[str, str] = {
    "header h1 .brand-cn": "顶栏小徽章：靠 --panel-2 淡底成胶囊，不必再描一圈",
    ".selected-scroll": "步骤 6 已选清单的滚动框：卡片里的一层小盒子 → 留淡底",
    "pre.result": "只读结果块：本来就有 --code-bg 底色，边框是第二层边界",
    ".instance-mod": "多实例配置容器：卡片内的分组 → 留淡底",
    ".card-details-body": "卡片内详情体：已有 --panel-2 淡底 → 去框",
    "#readiness-check": "检查单面板：卡片内的面板 → 留淡底 + 轻阴影",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    edits: list[tuple[int, int, str]] = []
    problems: list[str] = []
    notes: list[str] = []
    seen: set[str] = set()

    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text, re.S):
        sel = " ".join(m.group(1).split())
        hit = next((name for name in TARGETS if sel.endswith(name)), None)
        if not hit:
            continue
        body = m.group(2)
        if body.count(DROP) != 1:
            # 同一个名字可能被多条规则用（如 `pre.result` 与 `.res-side pre.result`）：
            # 只要**有**一条命中就算命中，其余没这条声明的照实跳过（不猜）。
            notes.append(f"      （跳过一条没有该声明的：{sel[:60]}）")
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        at = m.start(2) + body.index(DROP)
        end = at + len(DROP)
        # 顺手吃掉紧邻的一个空格，别在声明块里留双空格 / 行尾空格
        if text[end : end + 1] == " ":
            end += 1
        elif text[at - 1 : at] == " ":
            at -= 1
        edits.append((at, end, ""))
        seen.add(hit)
        notes.append(f"L{line_no}  {hit}  ← {TARGETS[hit]}")

    print(f"== shell 拆内层描边：{len(edits)} 处 ==")
    for note in notes:
        print("  " + note)
    missing = set(TARGETS) - seen
    if missing:
        problems.append("这些选择器没找到（改名了？）：" + ", ".join(sorted(missing)))

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1
    if not args.write:
        print("\n（--dry-run：没有写盘。确认无误后加 --write）")
        return 0

    for start, end, new in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
