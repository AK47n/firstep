"""把「本次解释器眼里的工具根 / 资料库目录 / 基线」写进文件，供跨方式核对。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("resolve-dump.json")

info: dict[str, object] = {
    "sys_executable": sys.executable,
    "sys_path_head": sys.path[:4],
}
try:
    import contest_generator
    from contest_generator.materials_update import (
        load_local_manifest,
        materials_library_dir,
    )
    from contest_generator.tool_root import tool_root

    info["package_file"] = str(Path(contest_generator.__file__).resolve())
    info["tool_root"] = str(tool_root())
    materials = materials_library_dir()
    info["materials_dir"] = str(materials)
    info["materials_dir_exists"] = materials.is_dir()
    manifest = load_local_manifest(materials)
    info["baseline"] = (
        None
        if manifest is None
        else {
            "version": manifest["version"],
            "batches": len(manifest["batches"]),
            "files": sum(len(b["files"]) for b in manifest["batches"]),
        }
    )
    info["baseline_file_exists"] = (materials / ".materials-manifest.json").is_file()
except Exception as exc:  # noqa: BLE001 - 诊断脚本
    info["error"] = f"{type(exc).__name__}: {exc}"

out.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(info, ensure_ascii=False, indent=2))
