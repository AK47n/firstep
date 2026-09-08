# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

lib = Path("library/modules")
for m in ["joystick", "hc05", "nrf24l01", "ir_remote"]:
    d = json.loads((lib / m / "manifest.json").read_text(encoding="utf-8"))
    plat = d["platforms"]["mspm0"]
    print(f"{m:<10} verified={plat['verified']} files={len(plat['files'])} pins={len(plat['pins'])} deps={d['dependencies']}")
