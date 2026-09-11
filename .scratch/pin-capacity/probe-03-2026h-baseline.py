"""工单 pin-capacity/01 的判定量钉死基线（只读、零额度、零网络）。

为什么留这份：门禁新文案里的每个数字都必须与「判定量复用现成两件」的口径对齐——
落点/占用脚 = pin_bindings._role_entries，可解性 = auto_assign_bindings(...,
resolve_default_conflicts=True) 的剩余 conflict 组，板上可用 IO = board.pins 里
capabilities 非空的脚数。本脚本把 2026H / mspm0 真机样本的这几个量现算并打印，
供测试用例与工单验收逐字对照（spec「本轮实测基线」表即出自本脚本）。

只读观测、不写任何文件；库或母版漂移后重跑即可看到数字变化（测试若钉死这些数字，
漂移即变红——那正是本基线存在的意义）。

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-capacity/probe-03-2026h-baseline.py
"""

import json, sys
from pathlib import Path
REPO = Path(".").resolve()
sys.path.insert(0, str(REPO / "src"))
from contest_generator.boards import load_board
from contest_generator.pin_bindings import _role_entries, _shared_groups, auto_assign_bindings
from contest_generator.selection import resolve_selection
board = load_board(REPO / "src/contest_generator/boards/mspm0-dimx.json")
io = [p.name for p in board.pins if p.capabilities]
print("板上可用 IO:", len(io), io)
p = REPO / ".scratch/real-run/cache/recommend_2026H.json"
data = json.loads(p.read_text(encoding="utf-8"))
platform = data.get("platform") or "mspm0"
slugs = [m["slug"] for m in (data.get("done") or {}).get("modules") or []]
print("样本:", p.name, platform, len(slugs), slugs)
res = resolve_selection(REPO / "library/modules", platform, slugs)
ms = list(res.manifests)
entries = _role_entries(ms, platform, {})
print("角色落点(含依赖展开后模块数 %d):" % len(ms), len(entries))
print("落点引脚集合:", sorted({e[3] for e in entries}))
print("板外落点(不在排针):", sorted({e[3] for e in entries if board.pin_index.get(e[3]) is None}))
g = _shared_groups(ms, platform, board, {})
conf = [x for x in g if x["kind"] == "conflict"]
print("默认布局 conflict 组:", len(conf), [ (x["pin"], x["roles"]) for x in conf ])
r = auto_assign_bindings(ms, platform, board, {}, resolve_default_conflicts=True)
print("solver 增量:", r.bindings)
print("solver fixed:", r.fixed)
rem = [x for x in r.shared if x["kind"] == "conflict"]
print("剩余 conflict 组:", len(rem), [(x["pin"], x["roles"]) for x in rem])
post = _role_entries(ms, platform, r.bindings)
print("解后落点引脚:", sorted({e[3] for e in post}))
print("解后占用脚数:", len({e[3] for e in post}))
