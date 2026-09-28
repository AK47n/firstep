r"""工单 02 施工脚本（三）：**口径修正后露出来的四处**（评审整改）。

背景（02 单评审抓到的真漏洞）：守卫/probe 原先按**原始选择器**判归属，而这段样式块大量规则
写成「注释 + 选择器」——注释正文里提到别的页的类名，规则就被判给了那一页。剥掉注释后，
`components` 与已完工的 `shell` 各露出两条裸字号：

  · components L714 `.btn-global-chat-*` / `.btn-params-chat-send`（按钮一族，此前被注释里的
    `.task-dialog-box` 带到 generate 去了）
  · components L730 `.btn-param-ref`
  · shell      L252 `header nav button`（注释里写着「生成页 .step-nav」→ 被带到 generate）
  · shell      L2943 `.card-details`（注释里写着 `.revise-details` → 被带到 generate）

这四条既然落在**已完工**的作用域里，就得当场改掉（否则那两条腿是"有水分的绿"）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02d-scope-fixups.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-02d-scope-fixups.py --write
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

# 行号 → [(期望原串, 换成), …]（都在**该行那条规则**的声明块里做唯一替换）
FIXUPS: dict[int, list[tuple[str, str]]] = {
    252: [("font-size: 14px;", "font-size: var(--fs-body);")],           # 顶栏导航胶囊 = 正文
    714: [("font-size: 12px;", "font-size: var(--fs-tag);"),             # 小字按钮
          ("padding: 1px 8px;", "padding: 1px var(--space-2);")],
    730: [("font-size: 12px;", "font-size: var(--fs-tag);")],            # 参数名 pill
    2943: [("font-size: 12.5px;", "font-size: var(--fs-note);")],        # 卡内说明折叠摘要
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
    for line_no, pairs in sorted(FIXUPS.items()):
        if line_no not in rules:
            problems.append(f"L{line_no}: 这里没有规则块")
            continue
        body_start, body_end = rules[line_no]
        body = text[body_start:body_end]
        for old, new in pairs:
            if body.count(old) != 1:
                problems.append(f"L{line_no}: {old!r} 出现 {body.count(old)} 次（期望 1）")
                continue
            at = body_start + body.index(old)
            edits.append((at, at + len(old), new, f"L{line_no}: {old!r} → {new!r}"))

    print(f"== 口径修正后的四处补丁：{len(edits)} 处 ==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1
    if not args.write:
        print("\n（--dry-run：没有写盘。确认无误后加 --write）")
        return 0
    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
