"""临时探针：豁免候选模块的硬件身份（kit / source_url）+ 与映射/互斥组的关系。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.library import list_modules  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    MODULE_PERIPHERAL_TERMS,
    SKELETON_MAPPING_EXEMPT,
)

CANDIDATES = (
    "config", "coord_detect", "delay", "ec01g", "esp01s", "filter", "huidu",
    "ir_beam", "ir_remote", "ir_remote_tx", "neo_6m", "ntb_time", "open_mv4",
    "pid", "tp_xpt2046", "zigbee_link",
)

by = {m.slug: m for m in list_modules(ROOT / "library" / "modules")}
for slug in CANDIDATES:
    manifest = by.get(slug)
    if manifest is None:
        print(f"{slug:<14} 不在库内")
        continue
    identities = []
    for platform, entry in sorted(manifest.platforms.items()):
        if entry.kit or entry.source_url:
            identities.append(f"{platform}: kit={bool(entry.kit)} url={bool(entry.source_url)}")
    group = manifest.exclusive_group.id if manifest.exclusive_group else ""
    print(
        f"{slug:<14} 映射={'是' if slug in MODULE_PERIPHERAL_TERMS else '否'} "
        f"豁免={'是' if slug in SKELETON_MAPPING_EXEMPT else '否'} "
        f"互斥组={group or '-'} 硬件身份[{'；'.join(identities) or '无'}]"
    )
