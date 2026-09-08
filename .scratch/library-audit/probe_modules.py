"""临时探针：关键模块的描述 / 平台 / pins 声明一览（只读）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for slug in ("motor", "servo", "pid", "xunji", "step_motor", "key", "led", "oled", "beep"):
    path = ROOT / "library" / "modules" / slug / "manifest.json"
    if not path.is_file():
        print(f"{slug:<12} 无 manifest")
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"{slug:<12} platforms={list(data.get('platforms', {}))}")
    print(f"{'':<12} pins={data.get('pins')!r}")
    print(f"{'':<12} deps={data.get('dependencies')!r}")
    print(f"{'':<12} desc={data.get('description', '')[:78]}")
