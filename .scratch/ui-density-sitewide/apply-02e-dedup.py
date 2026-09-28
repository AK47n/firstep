r"""工单 02 施工脚本（四）：评审整改三件事。

1. **`.toast-copy` / `.toast-action` / `.wait-cancel` 三段近乎逐字重复** → 收成"形状单源 +
   各自只留位置与颜色两笔差异"（Standards 轴判的 Duplicated Code）。
2. **`button.ghost:hover` 的 `rgba(var(--accent-rgb), .12)` 与 `--accent-dim` 逐字同值** →
   改用 `var(--accent-dim)`（"等于令牌的必须走令牌"，与同族 `.pin-overview-on` / `button.accent` 一致）。
3. **空态标题的颜色没跟着降级** → 全局 `.empty-state .es-title` 的 `color: var(--text)`
   改 `var(--muted)`（检测页样板那一版就是 muted；Spec 轴抓到"比改前更响"）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02e-dedup.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02e-dedup.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

MERGED = """  /* toast / 长任务行内的小胶囊按钮（工单 ui-density-sitewide/02 评审整改）：
     原先三段近乎逐字重复，现在**形状单源**——各自只留"位置 + 颜色"两笔差异。
     形状：2px 10px 内边距 / --fs-tag / 全圆角 / 一条描边 / panel 底。 */
  .toast-copy, .toast-action, .wait-cancel {
    padding: 2px 10px; font-size: var(--fs-tag); border-radius: var(--radius-full);
    border: 1px solid var(--border); background: var(--panel); cursor: pointer; }
  .toast-copy, .toast-action { flex: none; margin-left: 2px; }
  .toast-copy { color: var(--accent); }
  .toast-action { color: var(--ok); }
  .wait-cancel { display: inline-block; margin-left: var(--space-2); color: var(--warn); }
  .toast-copy:hover { border-color: var(--accent); }
  .toast-action:hover { border-color: var(--ok); }
  .wait-cancel:hover { border-color: var(--warn); }
  .wait-cancel:disabled { opacity: .6; cursor: default; }
"""

# (说明, 正则, 替换)
EDITS: list[tuple[str, str, str]] = [
    (
        "三段行内胶囊按钮 → 形状单源",
        r"[ \t]*/\* 长错误 toast 的「复制」按钮[^\n]*\*/\r?\n[ \t]*\.toast-copy \{[^}]*\}\r?\n",
        MERGED,
    ),
    ("删掉原来的 .toast-copy:hover（已并入单源块）", r"[ \t]*\.toast-copy:hover \{[^}]*\}\r?\n", ""),
    (
        "删掉原来的 .toast-action（含注释，已并入）",
        r"[ \t]*/\* 删除类操作「撤销」按钮[^\n]*\*/\r?\n[ \t]*\.toast-action \{[^}]*\}\r?\n",
        "",
    ),
    ("删掉原来的 .toast-action:hover", r"[ \t]*\.toast-action:hover \{[^}]*\}\r?\n", ""),
    (
        "删掉原来的 .wait-cancel（含注释，已并入）",
        r"[ \t]*/\* 长任务取消按钮[^\n]*\*/\r?\n[ \t]*\.wait-cancel \{[^}]*\}\r?\n",
        "",
    ),
    ("删掉原来的 .wait-cancel:hover", r"[ \t]*\.wait-cancel:hover \{[^}]*\}\r?\n", ""),
    ("删掉原来的 .wait-cancel:disabled（已并入）", r"[ \t]*\.wait-cancel:disabled \{[^}]*\}\r?\n", ""),
    (
        "ghost 悬停改用 --accent-dim（与令牌逐字同值就别裸写）",
        r"(button\.ghost:hover \{ background: )rgba\(var\(--accent-rgb\), \.12\)",
        r"\1var(--accent-dim)",
    ),
    (
        "空态标题颜色也退一级（全局 .empty-state .es-title）",
        r"(\.empty-state \.es-title \{ font-size: var\(--fs-body\); font-weight: 600; )color: var\(--text\);",
        r"\1color: var(--muted);",
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    problems: list[str] = []
    plan: list[tuple[int, int, str, str]] = []
    for note, pattern, repl in EDITS:
        hits = list(re.finditer(pattern, text))
        if len(hits) != 1:
            problems.append(f"{note}：锚点命中 {len(hits)} 次（期望 1）")
            continue
        m = hits[0]
        plan.append((m.start(), m.end(), m.expand(repl), note))

    print(f"== 评审整改：{len(plan)} 处 ==")
    for *_, note in sorted(plan, key=lambda e: e[0]):
        print("  · " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1
    if not args.write:
        print("\n（--dry-run：没有写盘。确认无误后加 --write）")
        return 0
    for start, end, new, _ in sorted(plan, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
