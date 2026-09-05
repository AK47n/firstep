# -*- coding: utf-8 -*-
"""批次 4 收尾：15 件模块 manifest 状态快照（全量测试之外的快速核对）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.library import list_modules

BATCH = [
    "joystick", "hc05", "nrf24l01", "ir_remote",
    "dht11", "us016", "bh1750", "ir_distance",
    "max7219", "pca9685", "ir_remote_tx",
    "jq8900", "syn6288", "rc522", "fingerprint",
]
mods = {m.slug: m for m in list_modules(Path(__file__).resolve().parents[2] / "library" / "modules")}
ok = True
for slug in BATCH:
    m = mods[slug]
    e = m.platforms["mspm0"]
    print(
        f"{slug:<14} verified={e.verified} deps={m.dependencies} "
        f"pins={len(e.pins)} kit={'Y' if e.kit else 'N'} url={'Y' if e.source_url else 'N'}"
    )
    if not e.verified or not e.kit or not e.source_url:
        ok = False
print("ALL15_OK" if ok else "SOME_INCOMPLETE")
