"""候选逐条取证：打印指定模块的 description / 平台条目 notes 全文 / 默认脚。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch/exclusive-group-gap-audit/dump.py <slug> [...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for slug in argv:
        path = MODULES / slug / "manifest.json"
        if not path.exists():
            print(f"!! 无此模块：{slug}")
            continue
        mod = json.loads(path.read_text(encoding="utf-8"))
        print("=" * 100)
        print(f"### {slug}  （{path}）")
        print(f"description: {mod.get('description')}")
        print(f"dependencies: {mod.get('dependencies')}")
        print(f"exclusive_group: {mod.get('exclusive_group')}")
        for plat, entry in (mod.get("platforms") or {}).items():
            print(f"--- platform {plat}")
            if not isinstance(entry, dict):
                continue
            print(f"  files={entry.get('files')} verified={entry.get('verified')}")
            pins = entry.get("pins") or []
            print(f"  pins={[(p.get('id'), p.get('type'), p.get('default')) for p in pins]}")
            print(f"  notes: {entry.get('notes')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
