# -*- coding: utf-8 -*-
"""引脚配色 03 单 · **候选色值验证**（把手上这一套值逐格算一遍，不改盘）。

判据（与守卫三条面同源）：
  · 主色 `--pin-X`（非文字）≥ 3.0 压 `--panel-2`（图例 / 菜单色点、焊盘描边）；
  · 文字档 `--pin-X-text` ≥ 4.5 压三种真实几何：状态文字（`--panel-2`）、
    板上引脚名（`--panel+--pin-pcb`）、类型标（`--panel-2 + --pin-X-dim`）。
本脚本只吃"我要写进去的那套值"（手挑，含色相意图），算完打印逐格读数与最低格。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "light-contrast"))
import probe_lib as L  # noqa: E402

PAGE = Path(__file__).resolve().parents[2] / "src" / "contest_generator" / "static" / "index.html"
FAMILIES = ["gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"]

# ---- 提案（light / dark）-----------------------------------------------------
# 键 = 令牌名；值 = CSS 取值（`var(...)` 由脚本解）
LIGHT = {
    "--pin-gpio-text": "var(--info-text)",
    "--pin-pwm-text": "var(--ok-text)",
    "--pin-adc-text": "var(--warn-text)",
    "--pin-uart": "#8250df", "--pin-uart-dim": "rgba(130, 80, 223, .12)", "--pin-uart-text": "#6639ba",
    "--pin-i2c": "#0f766e", "--pin-i2c-dim": "rgba(15, 118, 110, .12)", "--pin-i2c-text": "#0b5a54",
    "--pin-spi": "#0550ae", "--pin-spi-dim": "rgba(5, 80, 174, .12)", "--pin-spi-text": "#033d82",
    "--pin-enc": "#c9245f", "--pin-enc-dim": "rgba(201, 36, 95, .12)", "--pin-enc-text": "#9c1a4a",
    "--pin-exti": "#6f42c1", "--pin-exti-dim": "rgba(111, 66, 193, .12)", "--pin-exti-text": "#5a34a0",
}
DARK = {
    "--pin-gpio-text": "var(--info-text)",
    "--pin-pwm-text": "var(--ok-text)",
    "--pin-adc-text": "var(--warn-text)",
    "--pin-uart-text": "#b98bfa",
    "--pin-i2c-text": "#39d2c0",
    "--pin-spi-text": "#79c0ff",
    "--pin-enc-text": "#f06a9b",
    "--pin-exti-text": "#d2a8ff",
}


def rgb_hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c[:3])


def over(fg, bg):
    return tuple(round(v) for v in L.over(fg, bg)[:3])


def main() -> int:
    text = PAGE.read_text(encoding="utf-8")
    tok = L.Tokens(text)
    # 提案的覆盖层：先按令牌名解析（支持 var 链）
    for theme, table in (("light", LIGHT), ("dark", DARK)):
        for name, raw in table.items():
            tok.raw.setdefault(theme, {})[name] = raw      # 覆盖现有定义（模拟"写进亮色块/基块"）

    out, bad = [], []
    for theme in ("light", "dark"):
        panel2 = tok.value("--panel-2", theme)
        pcb = over(tok.value("--pin-pcb", theme), tok.value("--panel", theme))
        out.append(f"\n【{theme}】--panel-2 = {rgb_hex(panel2)}；--panel+--pin-pcb = {rgb_hex(pcb)}")
        out.append(f"  {'族':<6}{'主色':<10}{'×panel-2':>10}{'文字档':<10}{'状态':>8}{'板上':>8}{'类型标':>8}   最低格")
        for fam in FAMILIES:
            main = tok.value(f"--pin-{fam}", theme)
            dim = tok.value(f"--pin-{fam}-dim", theme)
            txt = tok.value(f"--pin-{fam}-text", theme)
            if not (main and dim and txt):
                out.append(f"  {fam:<6}（解不出：main={main} dim={dim} text={txt}）")
                bad.append(f"{theme}/{fam} 解不出")
                continue
            r_main = L.contrast(main, panel2)
            r_status = L.contrast(txt, panel2)
            r_pcb = L.contrast(txt, pcb)
            r_badge = L.contrast(txt, over(dim, panel2))
            worst = min(r_status, r_pcb, r_badge)
            out.append(f"  {fam:<6}{rgb_hex(main):<10}{r_main:>10.2f}{rgb_hex(txt):<10}"
                       f"{r_status:>8.2f}{r_pcb:>8.2f}{r_badge:>8.2f}   {worst:.2f}"
                       + ("  ⚠ 文字档低于 4.5" if worst < 4.5 else "")
                       + ("  ⚠ 主色低于 3.0" if r_main < 3.0 else ""))
            if worst < 4.5:
                bad.append(f"{theme}/{fam} 文字档 {worst:.2f} < 4.5")
            if r_main < 3.0:
                bad.append(f"{theme}/{fam} 主色 {r_main:.2f} < 3.0")
    out.append("")
    out.append("结论：" + ("✅ 八族 × 两主题全部过线" if not bad else "⚠ 还有不达标：\n  " + "\n  ".join(bad)))
    body = "\n".join(out)
    print(body)
    (HERE / "probe-04-candidates.txt").write_text(body + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
