"""临时探针：批次 sweep 脚本各钉了哪些不变量（第 3 批工单 03 的范围界定）。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYWORDS = (
    "delay", "kit", "source_url", "verified", "hardware_bound", "pins",
    "dependencies", "notes", "files", "platforms", "description", "slug",
    "lib_modules", "category", "syscfg", "include", "orphan", "循环", "悬空",
)

scripts = sorted(ROOT.glob(".scratch/wiki-*/sweep_*.py"))
print(f"sweep 脚本 {len(scripts)} 个\n")
for path in scripts:
    text = path.read_text(encoding="utf-8", errors="replace")
    # 找断言/报错行（problems.append / assert / raise）
    checks = [
        line.strip()
        for line in text.splitlines()
        if ("problems.append" in line or line.strip().startswith("assert "))
        and len(line.strip()) > 12
    ]
    doc = text.split('"""')
    title = doc[1].strip().splitlines()[0] if len(doc) > 1 else ""
    print(f"=== {path.parent.name}/{path.name}")
    print(f"    {title[:100]}")
    for check in checks[:8]:
        print(f"    · {check[:130]}")
    if len(checks) > 8:
        print(f"    … 另 {len(checks) - 8} 条")
    print()
