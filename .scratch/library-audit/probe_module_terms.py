"""临时探针：为「骨架模块→例程映射」扩展生成候选（只读，输出可复制进源码）。

口径：每个模块给一组 PERIPHERAL_TERMS 里已有的词项（或建议新增的词项），
使 related_references 能在骨架阶段按选中模块自动关联例程。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.library import list_modules  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    MODULE_PERIPHERAL_TERMS,
    PERIPHERAL_TERMS,
)

manifests = sorted(list_modules(ROOT / "library" / "modules"), key=lambda m: m.slug)
print(f"模块 {len(manifests)} 个；已映射 {len(MODULE_PERIPHERAL_TERMS)} 个")
print(f"现有 PERIPHERAL_TERMS {len(PERIPHERAL_TERMS)} 项\n")
print("slug | 平台 | 简介首段")
for m in manifests:
    first = m.description.split("：")[0][:38]
    mark = "✓" if m.slug in MODULE_PERIPHERAL_TERMS else " "
    print(f"{mark} {m.slug:<18} {'/'.join(sorted(m.platforms)):<12} {first}")
