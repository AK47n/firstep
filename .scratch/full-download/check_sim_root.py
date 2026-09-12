"""在沙箱（模拟用户机）里核对工具根与资料库基线解析。"""

from __future__ import annotations

import sys
from pathlib import Path

SIM = Path(r"C:\Users\luoji\Desktop\firstep-sim")
sys.path.insert(0, str(SIM / "src"))

from contest_generator.materials_update import (  # noqa: E402
    load_local_manifest,
    materials_library_dir,
)
from contest_generator.tool_root import tool_root  # noqa: E402
from contest_generator.webapp import tool_root as webapp_tool_root  # noqa: E402
from contest_generator.wordlist import _SOURCE_MODULES_DIR  # noqa: E402

print("沙箱工具根 =", tool_root())
print("webapp 口径 =", webapp_tool_root())
print("词表源码库 =", _SOURCE_MODULES_DIR, "存在?", _SOURCE_MODULES_DIR.is_dir())

materials = materials_library_dir()
print("资料库目录 =", materials, "存在?", materials.is_dir())
manifest = load_local_manifest(materials)
if manifest is None:
    print("基线解析 = None（仍被判 baseline-missing）")
else:
    print(
        f"基线解析 = version {manifest['version']} / "
        f"{len(manifest['batches'])} 批次 / "
        f"{sum(len(b['files']) for b in manifest['batches'])} 文件"
    )
print("基线文件 =", (materials / ".materials-manifest.json").is_file())
