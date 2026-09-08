import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from contest_generator.boards import load_boards, BOARDS_DIR

board = next(b for b in load_boards(BOARDS_DIR) if b.platform == "mspm0")
io = {p.name for p in board.pins if p.kind == "io"}
text = Path("library/masters/mspm0/mspm0.syscfg").read_text(encoding="utf-8")
used = set(re.findall(r'\.\$assign\s*=\s*"(P[A-H]\d{1,2})"', text))
print("io", len(io))
print("used", len(used))
print("free", sorted(io - used))
print("offboard used", sorted(used - io))
