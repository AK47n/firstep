r"""工单 02 施工脚本（二）：组件的形状与动作三级。

五处改动（每处都断言"锚点唯一命中"，改完打印 diff 摘要）：

1. **`.item` 去整圈描边**——它是卡片内的条目盒（提炼报告），留 `--panel-2` 淡底；
   嵌在 `.selected-scroll` 里的那一支早就是"只留一条虚线下边"（既有口径，不动）。
2. **空态安静**：`.empty-state .es-icon` 的 `opacity: .8 → .5`（与检测页同款；图标本身
   由 30px 收到 `--fs-icon` 22px 是字号那一步做的）。
3. **动作三级之「不可逆」升到全局**：`button.danger` 从"只有红字"升为
   **红描边 + 淡红底，悬停实心红**（这就是检测页 02 定的口径，此前只写在 `#tab-hwcheck` 里）。
4. **删掉检测页那两条重复**：全局升级后它们与本条逐字相同（两处说同一件事 = 将来只改一处
   的经典坑），改由全局那条给。
5. **补上 `.ghost`（次要 = 描边幽灵）**：标记里两处 `class="ghost"`（顶部提示条里的
   「去设置 / 去填写」）此前是**死类**——没有对应规则，渲染成默认按钮，在琥珀提示条里很重。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02c-components.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02c-components.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

GHOST_RULE = """  /* 幽灵按钮（次要动作的第三形态，工单 ui-density-sitewide/02）：透明底 + 随文色描边。
     标记里两处 class="ghost"（顶部提示条里的「去设置 / 去填写」）此前**没有对应规则**，
     渲染成默认实心按钮、在琥珀提示条里很重——这条把那个意图补实。 */
  button.ghost { background: transparent; border-color: currentColor; color: inherit; }
  button.ghost:hover { background: rgba(var(--accent-rgb), .12); color: inherit; border-color: currentColor; }
"""

# (说明, 正则锚点, 替换)
EDITS: list[tuple[str, str, str]] = [
    (
        "动作三级：不可逆（危险）升到全局 —— 红描边 + 淡红底",
        r"button\.danger \{ color: var\(--danger\); \}",
        "button.danger { border-color: var(--danger); background: var(--danger-dim); color: var(--danger); }",
    ),
    (
        "动作三级：不可逆 —— 悬停实心红",
        r"button\.danger:hover \{ border-color: var\(--danger\); \}",
        "button.danger:hover { background: var(--danger); color: #fff; }",
    ),
    (
        "补上 .ghost（次要 = 描边幽灵；挂在 button.accent:hover 之后）",
        # ⚠ 换行写 `\r?\n`：本文件在盘上是 CRLF，锚点写死 `\n` 会**静默不中**
        # （`docs/agents/local-environment.md` 第 2 节那条纪律）
        r"(button\.accent:hover \{ background: var\(--accent\); color: var\(--on-accent\); \}\r?\n)",
        r"\1" + GHOST_RULE,
    ),
    (
        "删掉检测页那两条 danger 重复（全局已是同一份），留一句指路",
        r"[ \t]*/\* 动作三级：主（\.primary 实心）[^\n]*\n"
        r"[ \t]*#tab-hwcheck button\.danger \{[^\n]*\n"
        r"[ \t]*#tab-hwcheck button\.danger:hover \{[^\n]*\n",
        "  /* 动作三级（主实心 / 危险红描边淡红底 / 次要幽灵）的口径**单源在全局那三条**\n"
        "     （工单 ui-density-sitewide/02）：这里的两条覆盖与本条逐字相同，已删——\n"
        "     两处说同一件事，将来只会改一处。 */\n",
    ),
    (
        ".item 去整圈描边（卡片内的条目盒 → 留 --panel-2 淡底）",
        r"\.item \{ border: 1px solid var\(--border\); ",
        ".item { ",
    ),
    (
        "空态安静：图标透明度 .8 → .5（与检测页同款）",
        r"(\.empty-state \.es-icon \{ font-size: var\(--fs-icon\); line-height: 1; )opacity: \.8;",
        r"\1opacity: .5;",
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

    print(f"== components 形状与动作三级：{len(plan)} 处 ==")
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
