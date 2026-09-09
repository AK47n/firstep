"""核对 batch9 七个模块的 stm32 平台条目状态（manifest 事实）。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch/tracker-audit/check_batch9.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ("jq8900", "syn6288", "fingerprint", "l298n", "neo_6m", "esp01s", "ec01g")


def main() -> int:
    for slug in MODULES:
        manifest = json.loads(
            (ROOT / "library" / "modules" / slug / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        platforms = manifest.get("platforms", {})
        stm32 = platforms.get("stm32", {})
        pins = stm32.get("pins", [])
        print(
            f"{slug:12s} platforms={sorted(platforms)} "
            f"stm32_files={len(stm32.get('files', []))} "
            f"verified={stm32.get('verified')} "
            f"hardware_bound={stm32.get('hardware_bound')} "
            f"pins={[p['id'] for p in pins]} "
            f"kit={'有' if stm32.get('kit') else '无'} "
            f"source_url={'有' if stm32.get('source_url') else '无'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
