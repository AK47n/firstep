"""临时探针：关键模块的简介全文 vs 首句（评估摘要行瘦身的信息损失）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402

mods = [m for m in list_modules(ROOT / "library" / "modules") if "stm32" in m.platforms]
by = {x.slug: x for x in build_manifest_summaries(mods)}

for slug in (
    "motor", "pid", "servo", "xunji", "led", "key", "oled", "beep",
    "uwb_uart", "imu_uart", "step_motor", "k230", "ml_mpu6050",
):
    x = by.get(slug)
    if x is None:
        continue
    first = x.description
    for sep in ("。", "；", "：", "，"):
        if sep in first:
            first = first.split(sep)[0]
            break
    print(f"=== {slug}  kits={x.kits[:2]} deps={x.dependencies} multi={bool(x.multi_instance)}")
    print(f"  全文 {len(x.description)}字: {x.description}")
    print(f"  首句 {len(first)}字: {first}")
