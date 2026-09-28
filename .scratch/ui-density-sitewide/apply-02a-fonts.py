r"""工单 02 施工脚本（一）：components 作用域的字号。

行号 + 期望原值逐条断言（同 01a 的手法），区间按**规则块**定位——一条规则的声明块常跨多行。

角色判定（口径 = spec 的「字号角色表」）：
  · 极小字按钮 / 徽章 / 行内小叉 / toast 动作 → `--fs-tag`(12)
  · chip / 说明类 → `--fs-note`(13)
  · 正文（条目说明 / 确认文案 / 服务停止页正文）→ `--fs-body`(14)
  · 空态图标 → `--fs-icon`(22)；**行内小图标**（toast 的 ico / ✕）随正文 → `--fs-body`
    （`--fs-icon` 只管"大号装饰图标"——这条口径修正写进守卫文件头与票尾）

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02a-fonts.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02a-fonts.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

FONT_BY_LINE: dict[int, tuple[str, str]] = {
    351: ("12", "--fs-tag"),      # .btn-pill--sm（小胶囊）
    398: ("11", "--fs-tag"),      # .badge
    416: ("14", "--fs-body"),     # .item .reason（条目说明）
    606: ("13", "--fs-note"),     # .chip（紧凑标签，比 badge 大一档）
    612: ("11", "--fs-tag"),      # .chip.rec .chip-x（行内小叉）
    706: ("12", "--fs-tag"),      # 任务对话 采纳/清除
    749: ("12", "--fs-tag"),      # 任务编辑 保存/取消
    751: ("12", "--fs-tag"),      # 任务卡「更多」
    772: ("12", "--fs-tag"),      # 草稿 分析/删除/全部
    797: ("12", "--fs-tag"),      # 参数 应用
    798: ("12", "--fs-tag"),      # 参数 回滚
    809: ("11.5", "--fs-tag"),    # 参数 重置
    1384: ("12", "--fs-tag"),     # .btn-mini（列表内迷你胶囊）
    1757: ("30", "--fs-icon"),    # .empty-state .es-icon：**大号装饰图标**那一档
    1759: ("13", "--fs-body"),    # .empty-state .es-title
    1760: ("12", "--fs-note"),    # .empty-state .es-hint
    1882: ("13", "--fs-body"),    # .confirm-message（确认弹窗正文）
    3251: ("16", "--fs-page"),    # .service-stopped-box h2（整屏提示的标题）
    3252: ("13", "--fs-body"),    # .service-stopped-box p
    3253: ("12", "--fs-note"),    # .service-stopped-box code
    3262: ("13", "--fs-body"),    # .toast（通知正文）
    3268: ("11", "--fs-tag"),     # .toast-copy
    3273: ("11", "--fs-tag"),     # .toast-action
    3278: ("11", "--fs-tag"),     # .wait-clock
    3281: ("11", "--fs-tag"),     # .wait-cancel
    3295: ("14", "--fs-body"),    # .toast .toast-ico（**行内**图标，随正文）
    3297: ("14", "--fs-body"),    # .toast .toast-close（行内 ✕）
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    rules: dict[int, tuple[int, int]] = {}
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text, re.S):
        rules[text.count("\n", 0, m.start()) + 1] = (m.start(2), m.end(2))

    edits: list[tuple[int, int, str, str]] = []
    problems: list[str] = []
    for line_no, (old_value, token) in sorted(FONT_BY_LINE.items()):
        if line_no not in rules:
            problems.append(f"L{line_no}: 这里没有规则块 —— 行号变了，停手核对")
            continue
        body_start, body_end = rules[line_no]
        body = text[body_start:body_end]
        anchor = f"font-size: {old_value}px"
        if body.count(anchor) != 1:
            problems.append(f"L{line_no}: 规则体内 {anchor!r} 出现 {body.count(anchor)} 次（期望 1）")
            continue
        at = body_start + body.index(anchor)
        edits.append((at, at + len(anchor), f"font-size: var({token})",
                      f"L{line_no}: {anchor} → font-size: var({token})"))

    for start, end, new, note in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    print(f"== components 字号：{len(edits)} 处 ==")
    for *_, note in sorted(edits, key=lambda e: int(e[3].split(":")[0][1:])):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1
    if not args.write:
        print("\n（--dry-run：没有写盘。确认无误后加 --write）")
        return 0
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
