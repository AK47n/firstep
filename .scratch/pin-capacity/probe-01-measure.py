"""只读核算（候选单「选中集引脚容量」取证）：历史推荐集在这块板上够不够脚。

为什么先量：生成门禁（pin-conflict-gate/01）已经把「撞脚的工程」堵在生成前，但**物理不可
实现**的选中集（撞脚数 > 空闲脚数）用户无论怎么点「自动配置」都编不过——要不要为它加一道
「容量预警」防线，取决于真机推荐集里这种集子到底占多少比例。零额度、零网络、纯只读。

样本 = 盘上现成的真机推荐产物：
- `.scratch/*/done-*.json`（探针跑真实推荐落盘的 done 载荷，platform 从文件名读）；
- `.scratch/real-run/cache/recommend_*.json`（生产推荐缓存，带 platform 字段）。

口径（对**当前库**核算 = 「今天照这个选中集生成会怎样」，旧样本的库已漂移属正常）：
- 角色落点需求 slots = Σ 每个选中模块的引脚角色数（含依赖展开）；
- 占用的不同脚 distinct；板上可用 IO（能力集非空）= pins；
- 空闲脚 free = pins - distinct（生成时 prune 之后的真空脚，可搬家当）；
- 撞脚组 conflicts = `_shared_groups` 里 kind=conflict 的组；
- 可解性 = 跑产品自己的 `auto_assign_bindings(..., resolve_default_conflicts=True)`，
  剩余 conflict 组 > 0 = **不可解**（不是算法没解，是脚不够）；
- 鸽笼硬界：slots_max = 每个占用脚最多 1 个非共享落点 → 硬上界用「不同脚 distinct + free」
  与「角色落点 slots − 合法共享节省」对照，故只作参考打印。

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-capacity/probe-01-measure.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.boards import load_board  # noqa: E402
from contest_generator.pin_bindings import (  # noqa: E402
    _role_entries,
    _shared_groups,
    auto_assign_bindings,
)
from contest_generator.selection import resolve_selection  # noqa: E402

BOARDS = {
    "mspm0": REPO / "src" / "contest_generator" / "boards" / "mspm0-dimx.json",
    "stm32": REPO / "src" / "contest_generator" / "boards" / "stm32-min-system.json",
}


def samples() -> list[tuple[str, str, str, list[str]]]:
    """(来源标签, topic, platform, slugs)——盘上现成真机推荐产物。"""
    found: list[tuple[str, str, str, list[str]]] = []
    for path in sorted(REPO.glob(".scratch/*/done-*.json")):
        name = path.name
        platform = "mspm0" if "-mspm0" in name else "stm32"
        topic = name.split("-")[2] if len(name.split("-")) > 2 else name
        data = json.loads(path.read_text(encoding="utf-8"))
        mods = data.get("modules") or []
        found.append((str(path.relative_to(REPO)), topic, platform,
                      [m["slug"] for m in mods]))
    for path in sorted(REPO.glob(".scratch/real-run/cache/recommend_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        platform = data.get("platform") or "stm32"
        topic = data.get("topic_key") or path.stem
        mods = (data.get("done") or {}).get("modules") or []
        found.append((str(path.relative_to(REPO)), topic, platform,
                      [m["slug"] for m in mods]))
    return [s for s in found if s[3]]


def measure(topic: str, platform: str, slugs: list[str]) -> dict[str, object]:
    board = load_board(BOARDS[platform])
    io_pins = [pin.name for pin in board.pins if pin.capabilities]
    resolved = resolve_selection(REPO / "library" / "modules", platform, slugs)
    manifests = list(resolved.manifests)
    entries = _role_entries(manifests, platform, {})
    slots = len(entries)
    distinct = len({pin for _, _, _, pin in entries})
    conflicts = [
        group for group in _shared_groups(manifests, platform, board, {})
        if group["kind"] == "conflict"
    ]
    solved = auto_assign_bindings(
        manifests, platform, board, {}, resolve_default_conflicts=True
    )
    remaining = [g for g in solved.shared if g["kind"] == "conflict"]
    return {
        "topic": topic,
        "platform": platform,
        "slugs": len(slugs),
        "modules": len(manifests),
        "slots": slots,
        "distinct": distinct,
        "io": len(io_pins),
        "free": max(0, len(io_pins) - distinct),
        "conflicts": len(conflicts),
        "resolved": len(solved.bindings),
        "remaining": len(remaining),
        "over_pigeonhole": slots > len(io_pins),
    }


def main() -> int:
    rows = [
        measure(topic, platform, slugs)
        for _label, topic, platform, slugs in samples()
    ]
    print(f"[容量核算] 样本 {len(rows)} 个真机推荐集（对当前库核算）\n")
    head = (f"{'样本':<26}{'平台':<7}{'模块':>4}{'落点':>6}{'占用脚':>7}"
            f"{'可用IO':>7}{'空闲':>5}{'撞脚':>5}{'可解':>5}{'未解':>5}")
    print(head)
    print("-" * len(head))
    for label, row in zip([s[0] for s in samples()], rows):
        short = label.split("/")[-1].replace(".json", "")[:25]
        print(f"{short:<26}{row['platform']:<7}{row['modules']:>4}{row['slots']:>6}"
              f"{row['distinct']:>7}{row['io']:>7}{row['free']:>5}"
              f"{row['conflicts']:>5}{row['resolved']:>5}{row['remaining']:>5}")

    print("\n[分离性] 落点需求 > 板上可用 IO 作为预警线的预测力：")
    tight = [r for r in rows if r["slots"] <= r["io"]]
    over = [r for r in rows if r["slots"] > r["io"]]
    print(f"  落点 ≤ 可用 IO（{len(tight)} 样本）：未解组合计 "
          f"{sum(r['remaining'] for r in tight)}")
    print(f"  落点 > 可用 IO（{len(over)} 样本）：有未解组的 "
          f"{sum(1 for r in over if r['remaining'])} 个，未解组合计 "
          f"{sum(r['remaining'] for r in over)}")


    print()
    for platform in ("mspm0", "stm32"):
        subset = [r for r in rows if r["platform"] == platform]
        if not subset:
            continue
        unsolvable = [r for r in subset if r["remaining"]]
        tight = [r for r in subset if not r["remaining"] and r["free"] <= 4]
        c = Counter(r["remaining"] for r in subset)
        print(f"[{platform}] 样本 {len(subset)}：不可解（未解组 > 0）**{len(unsolvable)}** "
              f"；临界（解完但空闲 ≤ 4 脚）{len(tight)}；未解组分布 {dict(sorted(c.items()))}")
        for r in unsolvable:
            print(f"    · {r['topic']}：{r['modules']} 模块 / 落点 {r['slots']} / "
                  f"占用 {r['distinct']} 脚 / 空闲 {r['free']} / 撞脚 {r['conflicts']} → "
                  f"剩 {r['remaining']} 组无解")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
