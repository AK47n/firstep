"""红证复跑（只读工作区，内存内摘掉 beep 声明）：证明测试确实会红。

用法：python .scratch/beep-pin-declaration/probe_red.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import tests.test_library_invariants as inv  # noqa: E402

from contest_generator.manifest import ModuleManifest  # noqa: E402

beep = inv.MANIFESTS["beep"]
entry = beep.platforms[inv.PLATFORM]
inv.MANIFESTS["beep"] = replace(
    beep, platforms={**beep.platforms, inv.PLATFORM: replace(entry, pins=())}
)

for name in (
    "test_module_source_pin_macros_traceable_to_declarations",
    "test_beep_stm32_buzzer_macros_are_declared",
    "test_beep_and_jq8900_share_pa15_is_reported_as_conflict",
    "test_debug_uart_stays_green_via_dependency_closure",
):
    fn = getattr(inv, name)
    try:
        fn()
    except AssertionError as exc:
        lines = str(exc).splitlines() or [repr(exc)]
        print(f"RED  {name}: {lines[0]}")
    else:
        print(f"GREEN {name}")
