"""临时探针：6 个死映射模块的候选条目标题 → 词项命中试算（工单 04 预备）。

只读：不写库，只按 related_references 的同一套判据（_term_matches_token /
_synonym_group）算「候选标题能不能让这些词项命中」。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    MODULE_PERIPHERAL_TERMS,
    _entry_score,
    _synonym_group,
    _text_has_term,
    _term_matches_token,
)
from contest_generator.reference_library import ReferenceEntry  # noqa: E402

# 候选条目：标题 = 器件词 + 中文器件名（骨架关联只认标题）
CANDIDATES = [
    (
        "0.96 寸 OLED 单色屏器件手册（oled / 0.96 IIC 与 SPI 单色屏）",
        "lckfb-地猛星移植手册/screen--0-96-iic-single-screen.md",
    ),
    (
        "WS2812 幻彩灯带与 LED 数码管器件手册（led / ws2812 / 8 位 LED 数码管）",
        "lckfb-地猛星移植手册/screen--8-bit-led-tube.md",
    ),
    (
        "按键摇杆器件手册（key / button / 双轴按键摇杆）",
        "lckfb-地猛星移植手册/control--two-axis-keystroke-rocker-module.md",
    ),
    (
        "SG90 舵机器件手册（servo / 舵机角度控制）",
        "lckfb-地猛星移植手册/control--sg90-steering-engine.md",
    ),
    (
        "蜂鸣器驱动例程（beep / buzzer / 蜂鸣器声光提示）",
        "<库内 beep 模块代码汇编>",
    ),
]

DEAD_SLUGS = ("beep", "key", "led", "led_beep", "oled", "servo")

print("=== 候选标题对每个死映射模块的词项命中（含同义词组）===")
for title, source in CANDIDATES:
    tokens = [token for token in re.split(r"[-_\s()（）]+", title.lower()) if token]
    print(f"\n标题：{title}\n素材：{source}")
    for slug in DEAD_SLUGS:
        terms = MODULE_PERIPHERAL_TERMS[slug]
        hits = [
            term
            for term in terms
            if any(
                _term_matches_token(synonym, token)
                for synonym in _synonym_group(term)
                for token in tokens
            )
        ]
        mark = "✓" if hits else "✗"
        print(f"  {mark} {slug:<10} 词项 {'、'.join(terms)} → 命中 {hits or '无'}")
    entry = ReferenceEntry(
        id="candidate",
        title=title,
        type="器件手册",
        description="候选",
        anchor_kind="none",
        anchor_value="",
        files=("x.md",),
    )
    activated = frozenset(
        term for slug in DEAD_SLUGS for term in MODULE_PERIPHERAL_TERMS[slug]
    )
    print(f"  _entry_score = {_entry_score(entry, activated)}")
