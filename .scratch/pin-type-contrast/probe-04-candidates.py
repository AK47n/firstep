# -*- coding: utf-8 -*-
"""引脚配色 03 单 · 色值候选搜索（读盘现算，不改盘）。

## 要满足的三条（八族 × 两主题）

  ① **主色** `--pin-X`（非文字档）：≥ 3.0 —— 色点压 `--panel-2`（图例在卡片上）。
  ② **文字档** `--pin-X-text`：≥ 4.5 —— 压三种真实几何：
     `--panel-2`（状态文字）/ `--panel+--pin-pcb`（板上引脚名）/ `--panel-2+--pin-X-dim`（类型标自带淡底）。
  ③ **淡化色** `--pin-X-dim`：类型标的底（保持"同色系淡底"的观感）。

## 搜法

按**色相不变、只压亮度**（HSL 的 L 从 1.0 往下扫）找：
  · 亮色主题：**最亮的那个仍满足 ② 的颜色**当文字档（余量留给抗锯齿），
    **最亮的那个仍满足 ① 的颜色**当主色；淡化色 = rgba(主色, .12)。
  · 暗色主题：先看现值满不满足 ②；不满足（enc / uart）就**提亮**到刚好过线 + 余量。
"""
from __future__ import annotations

import colorsys
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "light-contrast"))
import probe_lib as L  # noqa: E402

PAGE = Path(__file__).resolve().parents[2] / "src" / "contest_generator" / "static" / "index.html"
FAMILIES = ["gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"]


def hex2rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c[:3])


def over(fg, bg):
    return tuple(round(v) for v in L.over(fg, bg)[:3])


def with_lightness(rgb, l_new: float):
    r, g, b = (v / 255 for v in rgb[:3])
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(h, l_new, s)
    return (r2 * 255, g2 * 255, b2 * 255, 1.0)


def main() -> int:
    text = PAGE.read_text(encoding="utf-8")
    tok = L.Tokens(text)
    tables = {"dark": {}, "light": {}}
    for theme in tables:
        tables[theme] = {n: tok.value(n, theme) for n in tok.names()}

    def value(name, theme):
        v = tables[theme].get(name)
        return v

    out = []
    out.append("=" * 100)
    out.append("引脚配色 03 · 色值候选（口径：主色 ≥3.0 压 --panel-2；文字档 ≥4.5 压三种真实几何）")
    out.append("=" * 100)
    for theme in ("light", "dark"):
        # 三种几何的底
        base_status = value("--panel-2", theme)
        pcb = over(value("--pin-pcb", theme), value("--panel", theme))
        out.append(f"\n【{theme}】--panel-2 = {rgb2hex(base_status)}；--panel+--pin-pcb = {rgb2hex(pcb)}")
        out.append(f"  {'族':<6}{'现值':<22}{'主色候选':<22}{'文字档候选':<22}备注")
        for fam in FAMILIES:
            main_now = value(f"--pin-{fam}", theme)
            if main_now is None:
                out.append(f"  {fam:<6}（令牌不在表里）")
                continue
            main_now = tuple(main_now)
            dim_now = value(f"--pin-{fam}-dim", theme)

            def ratios(cand, dim):
                b_status = base_status
                b_badge = over(dim, base_status)
                return (L.contrast(cand, b_status), L.contrast(cand, pcb), L.contrast(cand, b_badge))

            # 主色：最亮的仍 ≥3.0（压 --panel-2）
            main_cand, text_cand = None, None
            for i in range(0, 101):
                l_new = 1.0 - i / 100.0
                c = with_lightness(main_now, max(0.02, l_new))
                if main_cand is None and L.contrast(c, base_status) >= 3.0:
                    main_cand = c
                if text_cand is None:
                    # 文字档按"淡化色 = rgba(该主色, .12)"自洽地算：先拿主色候选，再算淡底
                    cand_dim = (*c[:3], 0.12)
                    r_status, r_pcb, r_badge = ratios(c, cand_dim)
                    if min(r_status, r_pcb, r_badge) >= 4.5:
                        text_cand = c
                if main_cand and text_cand:
                    break
            note = ""
            if main_cand and L.contrast(main_now, base_status) < 3.0:
                note += "主色现值不达标；"
            r_now = ratios(main_now, dim_now) if dim_now else None
            if r_now and min(r_now) < 4.5:
                note += f"现值最低格 {min(r_now):.2f}；"
            out.append(f"  {fam:<6}{rgb2hex(main_now) + ' ' + f'{L.contrast(main_now, base_status):.2f}':<22}"
                       f"{(rgb2hex(main_cand) + ' ' + f'{L.contrast(main_cand, base_status):.2f}') if main_cand else '—':<22}"
                       f"{(rgb2hex(text_cand) + ' ' + f'{min(ratios(text_cand, (*text_cand[:3], 0.12))):.2f}') if text_cand else '—':<22}"
                       f"{note}")
        out.append("")
        out.append("  注：文字档候选那一列的第二个数是**三几何最低格**（自洽淡化色 = rgba(候选, .12)）。")

    body = "\n".join(out)
    dest = HERE / "probe-04-candidates.txt"
    dest.write_text(body + "\n", encoding="utf-8")
    print(body.encode("utf-8", "replace").decode("utf-8", "replace"))
    print(f"\n[落盘] {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
