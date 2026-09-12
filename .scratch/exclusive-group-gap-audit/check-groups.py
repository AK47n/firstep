"""改动后自查：打印真库全部功能组的 id / label / 成员 + 平台投影。

用法：$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; python .scratch/exclusive-group-gap-audit/check-groups.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(ROOT / "src"))
    from contest_generator.manifest import ModuleManifest, collect_exclusive_groups

    manifests = [
        ModuleManifest.load(p) for p in sorted(MODULES.iterdir()) if p.is_dir()
    ]
    print(f"模块总数：{len(manifests)}")
    for platform in ("", "stm32", "mspm0"):
        label = platform or "全平台"
        groups = collect_exclusive_groups(manifests, platform=platform)
        members = sum(len(g.members) for g in groups)
        print(f"\n== {label}：{len(groups)} 组 / {members} 个成员位 ==")
        for group in groups:
            print(f"  {group.id:14s} {group.label}")
            for m in group.members:
                print(f"      - {m.slug:16s} {m.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
