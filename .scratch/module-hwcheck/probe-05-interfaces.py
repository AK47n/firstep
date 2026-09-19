import sys, json
sys.path.insert(0, "src")
from pathlib import Path
from contest_generator.library import list_modules
from contest_generator.hwcheck_recipe import interface_names
from contest_generator.master_store import master_project_dir
from contest_generator.treewalk import iter_project_files

lib = Path("library/modules")
manifests = list_modules(lib)
for platform in ("stm32", "mspm0"):
    md = master_project_dir(Path("library/masters"), platform)
    headers = []
    if md.is_dir():
        headers = [(p.relative_to(md).as_posix(), p.read_text(encoding="utf-8", errors="replace"))
                   for p in iter_project_files(md, pattern="*.h")]
    names = interface_names(manifests, lib, platform, headers)
    mpu = sorted(names.get("ml_mpu6050", frozenset()))
    print("=" * 20, platform, "master headers:", len(headers), "names:", len(mpu))
    print(", ".join(mpu))
