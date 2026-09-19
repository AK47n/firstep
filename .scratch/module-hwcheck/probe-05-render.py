import sys
sys.path.insert(0, "src")
from pathlib import Path
from contest_generator.library import list_modules
from contest_generator.hwcheck_recipe import interface_names, load_recipes, render_recipe_section
from contest_generator.master_store import master_project_dir
from contest_generator.treewalk import iter_project_files
from contest_generator.platforms import KNOWN_PLATFORMS

lib = Path("library/modules")
manifests = list_modules(lib)
def headers_for(name):
    md = master_project_dir(Path("library/masters"), name)
    if not md.is_dir():
        return []
    return [(p.relative_to(md).as_posix(), p.read_text(encoding="utf-8", errors="replace"))
            for p in iter_project_files(md, pattern="*.h")]
interfaces = {p: interface_names(manifests, lib, p, headers_for(p)) for p in sorted(KNOWN_PLATFORMS)}
recipes = load_recipes(lib, manifests, interfaces)
print("ok, slugs:", sorted(recipes))
for platform in ("stm32", "mspm0"):
    mpu = recipes["ml_mpu6050"].for_platform(platform)
    print("=" * 30, platform)
    body = "\n".join(render_recipe_section(mpu))
    # 只印代码行（注释行太长），并把 \xNN 还原成人话
    import re
    def unesc(t):
        return re.sub(r"\\x([0-9a-f]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("latin-1"), t)
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("/*"):
            continue
        print(unesc(line).encode("latin-1", "replace").decode("utf-8", "replace"))
