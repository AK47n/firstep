import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from contest_generator.manifest import ModuleManifest
from contest_generator.boards import load_boards, BOARDS_DIR

roles = []
for module_dir in sorted(Path("library/modules").iterdir()):
    if not module_dir.is_dir():
        continue
    m = ModuleManifest.load(module_dir)
    entry = m.platforms.get("stm32")
    if entry:
        for p in entry.pins:
            roles.append((m.slug, p.id, p.default, p.type))
print("roles", len(roles))
print("distinct pins used", len(set(r[2] for r in roles)))
c = Counter(r[2] for r in roles)
print("shared:", [(p, n) for p, n in sorted(c.items()) if n > 1])
board = next(b for b in load_boards(BOARDS_DIR) if b.platform == "stm32")
io = {p.name for p in board.pins if p.kind == "io"}
print("io pins", len(io))
print("unused io", sorted(io - {r[2] for r in roles}))
