import sys
sys.path.insert(0, "src")
from pathlib import Path
from contest_generator.library import list_modules
from contest_generator.hwcheck_recipe import interface_names, load_recipes
from contest_generator.master_store import master_project_dir
from contest_generator.treewalk import iter_project_files
from contest_generator.platforms import KNOWN_PLATFORMS
lib = Path("library/modules")
manifests = list_modules(lib)
def hf(name):
    md = master_project_dir(Path("library/masters"), name)
    return [] if not md.is_dir() else [(p.relative_to(md).as_posix(), p.read_text(encoding="utf-8", errors="replace")) for p in iter_project_files(md, pattern="*.h")]
interfaces = {p: interface_names(manifests, lib, p, hf(p)) for p in sorted(KNOWN_PLATFORMS)}
recipes = load_recipes(lib, manifests, interfaces)
spec = {s for s, c in recipes.items() if c.usable}
for plat in ("stm32", "mspm0"):
    have = [m.slug for m in manifests if m.platforms.get(plat) and m.slug in spec and recipes[m.slug].for_platform(plat)]
    no = [m.slug for m in manifests if m.platforms.get(plat) and not (m.slug in spec and recipes[m.slug].for_platform(plat))]
    print(plat, "有配方:", sorted(have))
    print(plat, "无配方(前12):", sorted(no)[:12])
