# -*- coding: utf-8 -*-
"""引脚配色 04 单 · 读数：亮色覆盖的**族盘点**（腿⑪ 的 Python 侧，与 JS 守卫同源）。

⚠ 盘点**全部走 `probe_lib`**（`family_inventory` / `theme_coverage_problems`）——
本脚本**不自己重算**族、色件、缺亮色定义（双轴评审整改：那会造出第三份口径，镜像守卫钉不到）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "light-contrast"))
import probe_lib as L  # noqa: E402


def main() -> int:
    css = L.contrast_style_text(L.read_page())
    tok = L.Tokens(css)
    blocks = L.theme_block_token_names(css)
    inv = L.family_inventory(css, tok)
    color_fams = {f: v for f, v in inv.items() if v["colors"]}
    non_color_fams = [f for f, v in inv.items() if not v["colors"]]
    partial = {f: v["missing_light"] for f, v in color_fams.items() if v["missing_light"]}
    only_light = sorted(blocks["light"] - blocks["dark"])

    out = []
    out.append("=" * 100)
    out.append("引脚配色 04 · 亮色覆盖盘点（腿⑪：颜色族必须两主题成套）")
    out.append("=" * 100)
    out.append(f"  `:root` 令牌 {len(blocks['dark'])} 个；亮色块另有定义 {len(blocks['light'])} 个；"
               f"亮色独有（畸形）{len(only_light)} 个 {only_light}")
    out.append(f"  族合计 {len(inv)}：颜色族 **{len(color_fams)}** / 非颜色族 {len(non_color_fams)}"
               f"（不判：{'、'.join(non_color_fams)}）")
    out.append("")
    out.append(f"  {'颜色族':<12}{'色件数':>6}  成员（⭐ = 亮色块里没有自己的定义）")
    for fam, info in color_fams.items():
        marks = [(n + "⭐") if n in info["missing_light"] else n for n in info["colors"]]
        out.append(f"  {fam:<12}{len(info['colors']):>6}  " + "、".join(marks))
    out.append("")
    out.append(f"  不成套的颜色族：{sorted(partial) or '（无）'}")
    out.append(f"  判据现算：{L.theme_coverage_problems(css, tok=tok) or '（无问题）'}")
    out.append(f"  向量表自证：{L.theme_coverage_vector_problems() or '（无问题）'}")

    body = "\n".join(out)
    (HERE / "probe-05-light-coverage.txt").write_text(body + "\n", encoding="utf-8")
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
