r"""工单 08 施工脚本（一）：`static/js/**` 里最后 **7 处内联 `font-size: <n>px`** 收进令牌。

这是"全站零裸 px 字号"这条线的最后一段：`index.html` 的 `<style>` 块在 07 单已经归零，
剩下的是**渲染方写死的内联取值**（`style="…"` 与 `el.style.cssText = "…"` 两种写法，
分布在 5 个文件里）。

口径：11 / 12px → `var(--fs-tag)`(12)（"抬高地板"那一档：徽章 / 小标签 / 小提示都是它）。
**内联样式里用 `var()` 是合法的**（自定义属性在 `:root` 上定义，内联样式照常解析）。

⚠ 这三处 **不是** CSS px、**不碰**：`fx/resource-board.js` / `fx/wiring.js` / `fx/generate-pins.js`
里那些 `font-size="8.5"` 之类是 **SVG 用户单位**（矢量图里的字号属性，随图缩放），
跟"裸 px 字号"不是一个口径（票面 ① 说的也是 `font-size: <n>px`）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-08a-js-inline.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-08a-js-inline.py --write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JS = ROOT / "src" / "contest_generator" / "static" / "js"

# (相对 js/ 的路径, 行号锚点片段, 旧串, 新串, 说明)
EDITS: list[tuple[str, str, str, str, str]] = [
    ("fx/recommend.js", "本区只谈选型与买件",
     'style="font-size:11px;margin-top:var(--space-1)"',
     'style="font-size:var(--fs-tag);margin-top:var(--space-1)"',
     "选区提示行（11 → tag）"),
    ("ui/generate-core.js", "cursor:pointer",
     '"margin-left:6px;padding:2px 8px;font-size:12px;cursor:pointer"',
     '"margin-left:6px;padding:2px 8px;font-size:var(--fs-tag);cursor:pointer"',
     "步骤标题旁的用量 chip（12 → tag）"),
    ("ui/generate-pins.js", "word-break:break-all",
     'style="padding:6px 14px;font-size:12px;font-family:var(--mono);word-break:break-all"',
     'style="padding:6px 14px;font-size:var(--fs-tag);font-family:var(--mono);word-break:break-all"',
     "能力清单行（mono 小字，12 → tag）"),
    ("ui/generate-recommend.js", "text-align:center",
     '"text-align:center;font-size:12px;margin:4px 0 8px"',
     '"text-align:center;font-size:var(--fs-tag);margin:4px 0 8px"',
     "空态 / 提示行（12 → tag）"),
    ("ui/generate-recommend.js", "副产物模板",
     'style="font-size:12px;color:var(--muted)"',
     'style="font-size:var(--fs-tag);color:var(--muted)"',
     "「副产物模板」标签（12 → tag）"),
    ("ui/generate-recommend.js", "max-width:260px",
     'style="font-size:12px;max-width:260px"',
     'style="font-size:var(--fs-tag);max-width:260px"',
     "模板下拉框（12 → tag）"),
    ("ui/step-state.js", "border-radius:var(--radiu",
     "font-size:11px;",
     "font-size:var(--fs-tag);",
     "步骤卡的展开 / 收起小按钮（11 → tag）"),
]

# 复扫判据：JS 里**任何** `font-size: <n>px`（内联样式或 cssText）都不许再出现
BARE = re.compile(r"font-size:\s*[0-9.]+px")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    problems: list[str] = []
    pending: list[tuple[Path, str, str, str]] = []
    done: list[str] = []
    for rel, near, old, new, why in EDITS:
        path = JS / rel
        text = path.read_text(encoding="utf-8")
        if old not in text:
            if new in text:
                done.append(f"已应用（{rel} {why}）")
            else:
                problems.append(f"{rel}: 找不到 {old[:50]!r}（就近锚点 {near!r}）")
            continue
        if text.count(old) != 1:
            problems.append(f"{rel}: {old[:50]!r} 命中 {text.count(old)} 次（期望 1；换更长的串）")
            continue
        if near not in text:
            problems.append(f"{rel}: 就近锚点 {near!r} 不在文件里——怕改错地方，停手")
            continue
        pending.append((path, old, new, f"{rel:<26} {why}"))

    # 复扫基线：改之前 JS 里到底还有几处
    before = []
    for p in sorted(JS.rglob("*.js")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if BARE.search(line):
                before.append((p.relative_to(ROOT).as_posix(), i))
    print(f"== JS 内联裸 px 字号：改前 {len(before)} 处 / 本次改 {len(pending)} 处 / 已应用 {len(done)} 处 ==")
    for rel, i in before:
        print(f"  盘上  {rel}:{i}")
    for *_, note in pending:
        print("  改    " + note)
    for note in done:
        print("  跳过  " + note)
    if len(before) != len(pending) + 0 and not done:
        problems.append(f"改前盘上 {len(before)} 处，本表只认领 {len(pending)} 处——数目对不上，停手")
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    if not args.write or args.dry_run:
        print("\n（--dry-run：没有写盘；复扫 JS 内联裸 px 字号 = 0 ✅；确认无误后加 --write）")
        return 0

    # ⚠ **写盘放在闸门之后**（08 单评审 Standards 抓到第一版把写入排在 `--dry-run` 判断之前——
    # 那样 `--dry-run` 会真的改树，还打印"没有写盘"；07 账 Std-7 刚整改过同一个毛病）
    for path, old, new, _ in pending:
        raw = path.read_bytes()
        eol = "\r\n" if b"\r\n" in raw else "\n"          # 按**盘上原有的行尾**写回
        text = raw.decode("utf-8").replace("\r\n", "\n")
        path.write_bytes(text.replace(old, new, 1).replace("\n", eol).encode("utf-8"))

    left = []
    for p in sorted(JS.rglob("*.js")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if BARE.search(line):
                left.append(f"{p.relative_to(ROOT).as_posix()}:{i}")
    if left:
        print("\n== **停下**：改完 JS 里还有裸 px 字号（已写盘，逐条列出）==")
        for s in left:
            print("  ✗ " + s)
        return 1

    print(f"\n[已写盘] {len(pending)} 处；复扫 JS 内联裸 px 字号 = 0 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
