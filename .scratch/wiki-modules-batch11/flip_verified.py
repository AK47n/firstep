# -*- coding: utf-8 -*-
"""批次 11 编译矩阵 PASS 后回填：verified=true + notes 追加编译记录。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODS = ROOT / "library" / "modules"

ITEMS = [
    ("mq3", "01"), ("mq4", "02"), ("mq6", "03"), ("mq7", "04"),
    ("mq8", "05"), ("mq9", "06"), ("ms1100", "07"),
]

for slug, num in ITEMS:
    p = MODS / slug / "manifest.json"
    man = json.loads(p.read_text(encoding="utf-8"))
    mp = man["platforms"]["mspm0"]
    assert mp["verified"] is False, slug
    mp["verified"] = True
    marker = f"wiki-modules-batch11/{num} 编译矩阵"
    assert marker not in mp["notes"], slug
    mp["notes"] += (
        f"{marker}（2026-09-11）：单选生成 → SysConfig CLI → gmake 0 error、"
        f"0 warning（PASS）；未上板（ADC 换算/预热真机验证留后续）。\n"
    )
    p.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("verified:", slug)
