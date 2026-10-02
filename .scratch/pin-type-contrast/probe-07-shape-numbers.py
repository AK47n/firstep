# -*- coding: utf-8 -*-
"""引脚配色 05 单 · 形状数复算（与 v1.4.3 冻结值对照）。"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "light-contrast"))
import probe_lib as L  # noqa: E402

page = L.read_page()
tok = L.Tokens(L.contrast_style_text(page))
css = L.contrast_style_text(page)
print(f"机械面对数      = {len(L.contrast_pairs(page, tok))}（上一批 394）")
print(f"族面格数        = {len(L.contrast_family_cells(page, tok))}（上一批 172；族表 {len(L.CONTRAST_FAMILIES)} 条）")
used = L.unbased_color_tokens(page)
print(f"无底规则文字令牌 = {len(used)} 个（令牌面表 {len(L.CONTRAST_TOKEN_BASES)} 行）")
print(f"例外表          = {len(L.load_exceptions())} 条")
print(f"颜色族          = {len({L.token_family_of(n) for n in L.theme_block_token_names(css)['dark']})}"
      f"（颜色族里含色件的：{sum(1 for f in {L.token_family_of(n) for n in L.theme_block_token_names(css)['dark']} if any(L.value_looks_like_color(tok.raw['dark'].get(n), 'dark', tok) for n in L.theme_block_token_names(css)['dark'] if L.token_family_of(n) == f))}）")
print(f"亮色块定义       = {len(L.theme_block_token_names(css)['light'])} 个")
