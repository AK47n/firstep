"""浅色调色板轮 · 施工脚本（02 单 d）：修 `--on-ok-deep` 的**渐变底退步**（02 单双轴评审 Spec 轴点名）。

## 问题（评审实测）

`.step-nav .step-dot.done .dot` / `.card.done .step-no` / `.ov-chip.done .ov-dot` 的底是
`linear-gradient(135deg, var(--ok-bright), var(--ok))`。浅色下两个端点 **#2da44e / #1a7f37**
亮度太接近：白字在最亮端只有 **3.22**、深墨在最暗端只有 **3.65**——**没有任何一种单色字能同时过两个端点**。
02 单把 `--on-ok-deep` 改白，等于拿 3.65 换成 3.22：债摘了、实际更差；
而 `ruleBackground()` 对渐变返回 `null` ⇒ **机械面根本看不见这一格**。

## 修法（修在**填充层**，不是换字色）

- 新增 `--ok-fill`（**按主题给渐变**）：暗色 `linear-gradient(135deg, var(--ok-bright), var(--ok))`、
  浅色 `linear-gradient(135deg, var(--ok), var(--ok-text))`——浅色把亮端压到 `--ok`、暗端到 `--ok-text`，
  白字两端都过（5.08 / 4.84）；暗色保持原渐变，深墨两端都过（12.06 / 7.30）。
- `--on-ok-deep` → 更名 **`--on-ok`**（与 `--on-accent` / `--on-danger` 同族命名），
  浅色 `#ffffff` / 暗色 `#04170c`。
- 三条规则改用 `var(--ok-fill)` + `var(--on-ok)`（`.card.done .step-no` 原本没写 `color`，补上）。
- 守卫新增**渐变端点检查**（`CONTRAST_GRADIENT_ENDS`）——不然这一格永远在射程外。

跑法（仓库根）：
    python .scratch/light-contrast/apply-02d-ok-gradient.py --check
    python .scratch/light-contrast/apply-02d-ok-gradient.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

EDITS = [
    # ① 两块主题各加 `--ok-fill` + `--on-ok-deep` 更名 `--on-ok`（暗色沿用原渐变；浅色两个端点都压到白字能过）
    ("    --on-accent-deep: #001018; --on-ok-deep: #04170c;",
     "    --on-accent-deep: #001018; --on-ok: #04170c;\n"
     "    --ok-fill: linear-gradient(135deg, var(--ok-bright), var(--ok));", 1),
    ("    --on-accent-deep: #001018; --on-ok-deep: #ffffff;   /* 浅色实心块是暗的 → 块上改白字 */",
     "    --on-accent-deep: #001018; --on-ok: #ffffff;   /* 浅色实心块是暗的 → 块上改白字 */\n"
     "    /* 浅色 ok 渐变：亮端压到 --ok、暗端到 --ok-text —— 白字两端都过"
     "（原渐变两端太接近，没有单色字能同时过） */\n"
     "    --ok-fill: linear-gradient(135deg, var(--ok), var(--ok-text));", 1),
    # ② 消费方：字色令牌 + 填充令牌（逐条按出现次数核，锚点取**单行片段**，不赌缩进）
    ("color: var(--on-ok-deep);", "color: var(--on-ok);", 3),
    ("background: linear-gradient(135deg, var(--ok-bright), var(--ok));",
     "background: var(--ok-fill);", 3),
    # ③ `.card.done .step-no` 原本没写 color（继承 `--on-accent`），补成 `--on-ok`
    (".card.done .step-no { background: var(--ok-fill);",
     ".card.done .step-no { background: var(--ok-fill); color: var(--on-ok);", 1),
]


def main() -> None:
    check = "--check" in sys.argv
    raw = L.PAGE.read_bytes()
    nls = ("\r\n" if b"\r\n" in raw else "\n")
    text = raw.decode("utf-8")

    if check:
        # 复核 = **后置条件**（不是比"旧串在不在"：新串里可能恰好含旧串，会自己咬自己）
        problems = []
        if "--on-ok-deep" in text:
            problems.append(f"  还有 {text.count('--on-ok-deep')} 处 --on-ok-deep 没更名")
        if text.count("--ok-fill") != 5:      # 2 处定义 + 3 处消费
            problems.append(f"  --ok-fill 出现 {text.count('--ok-fill')} 次（应为 5 = 2 定义 + 3 消费）")
        if text.count("color: var(--on-ok)") < 3:
            problems.append(f"  `color: var(--on-ok)` 出现 {text.count('color: var(--on-ok)')} 次（应 ≥3）")
        if ".card.done .step-no { background: var(--ok-fill); color: var(--on-ok);" not in text:
            problems.append("  .card.done .step-no 没补上 color: var(--on-ok)")
        if problems:
            raise SystemExit("复核发现问题：\n" + "\n".join(problems))
        print("复核 OK：渐变走 `--ok-fill`（两主题各一份）、字色走 `--on-ok`，`--on-ok-deep` 已全部更名")
        return

    problems = []
    for old, new, want in EDITS:
        old, new = old.replace("\n", nls), new.replace("\n", nls)
        n = text.count(old)
        if n != want:
            problems.append(f"  命中 {n} 次（期望 {want}）：{old[:70]}")
            continue
        text = text.replace(old, new)
    if problems:
        raise SystemExit("锚点没命中，一个字节都没写：\n" + "\n".join(problems))
    if "--on-ok-deep" in text:
        leftover = text.count("--on-ok-deep")
        raise SystemExit(f"还有 {leftover} 处 `--on-ok-deep` 没改完——本脚本不该留半成品")
    L.PAGE.write_bytes(text.encode("utf-8"))
    print(f"已写盘：{L.PAGE.relative_to(L.ROOT)}；改了 {len(EDITS)} 处")


if __name__ == "__main__":
    main()
