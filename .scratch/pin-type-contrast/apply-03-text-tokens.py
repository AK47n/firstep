# -*- coding: utf-8 -*-
"""引脚配色 03 单 · 施工脚本：把**文字面**的取色从主色换成文字档（`--pin-X` → `--pin-X-text`）。

只改三类规则（非文字面一律不动）：
  ① `.role-type[data-pin-family=X]` 的 `color`（底仍是淡化色）
  ② `.pin-type-text[data-pin-family=X]` 的 `color`
  ③ `#pin-board-svg text[data-pin-family=X]` 的 `fill`
找不到任何一条就**大声失败**（锚点过期 = 本脚本得跟着产品面改）。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "src" / "contest_generator" / "static" / "index.html"
FAMS = ["gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"]

PAIRS = [
    ('.role-type[data-pin-family="{f}"] {{ color: var(--pin-{f}); background: var(--pin-{f}-dim); }}',
     '.role-type[data-pin-family="{f}"] {{ color: var(--pin-{f}-text); background: var(--pin-{f}-dim); }}'),
    ('.pin-type-text[data-pin-family="{f}"] {{ color: var(--pin-{f}); }}',
     '.pin-type-text[data-pin-family="{f}"] {{ color: var(--pin-{f}-text); }}'),
    ('#pin-board-svg text[data-pin-family="{f}"] {{ fill: var(--pin-{f}); }}',
     '#pin-board-svg text[data-pin-family="{f}"] {{ fill: var(--pin-{f}-text); }}'),
]


def main() -> int:
    s = PAGE.read_text(encoding="utf-8")
    n = 0
    for old_t, new_t in PAIRS:
        for f in FAMS:
            old, new = old_t.format(f=f), new_t.format(f=f)
            if old not in s:
                raise SystemExit(f"锚点不在盘上（{old}）——本脚本要跟着产品面改")
            s = s.replace(old, new)
            n += 1
    PAGE.write_text(s, encoding="utf-8", newline="")
    print(f"已替换 {n} 条规则（文字面 3 类 × 8 族）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
