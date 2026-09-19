import sys
sys.path.insert(0, "src")
from pathlib import Path
from contest_generator.library import list_modules
from contest_generator.manifest import collect_exclusive_groups
ms = list_modules(Path("library/modules"))
print("modules declaring a group:")
for m in ms:
    if m.exclusive_group is not None:
        print("  ", m.slug, "->", m.exclusive_group.id, "|", m.exclusive_group.label,
              "| platforms:", sorted(m.platforms))
print()
for plat in (None, "stm32", "mspm0"):
    groups = collect_exclusive_groups(ms, platform=plat) if plat else collect_exclusive_groups(ms)
    print("collect_exclusive_groups", plat, "->", [(g.id, [x.slug for x in g.members]) for g in groups])
