"""资料库（sources/materials）体积构成盘点：大头在哪、进不进完整包。

回答的问题：本机 `sources/materials` 约 5.9 GiB，谁占的？其中多少是
「故意不进包的装机件」（`full_pack.INSTALLER_GLOBS` 等排除规则命中），
多少是真进包的资料。

用法：python .scratch/materials-baseline-writeback/measure-composition.py [--top N]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.full_pack import materials_excluded  # noqa: E402

MIB = 1024**2
GIB = 1024**3


def human(n: float) -> str:
    return f"{n / GIB:.2f} GiB" if n >= 0.5 * GIB else f"{n / MIB:.1f} MiB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    tree = ROOT / "sources" / "materials"
    if not tree.is_dir():
        print(f"资料库目录不在：{tree}")
        return 2

    total = 0
    included = 0
    per_batch: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [included, excluded]
    per_suffix: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    biggest: list[tuple[int, str, bool]] = []  # (size, relpath, included)

    for path in tree.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(tree).as_posix()
        size = path.stat().st_size
        excluded = materials_excluded(rel)
        # 顶级批次目录 = 组成（没有顶级目录的文件归到「(根)」）
        batch = rel.split("/", 1)[0] if "/" in rel else "(根)"
        total += size
        per_batch[batch][1 if excluded else 0] += size
        suffix = path.suffix.lower() or "(无扩展名)"
        per_suffix[suffix][1 if excluded else 0] += size
        if not excluded:
            included += size
            biggest.append((size, rel, True))

    print(f"资料库总计：{human(total)}（{sum(1 for _ in tree.rglob('*') if _.is_file())} 个文件）")
    print(f"  会进完整包：{human(included)}")
    print(f"  故意不进包：{human(total - included)}（第三方装机件 / 缓存 / 清单自身）")

    print(f"\n== 按批次（前 {args.top}）==")
    print(f"{'批次目录':<44}{'总计':>12}{'进包':>12}{'不进包':>12}")
    rows = sorted(per_batch.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
    for name, (inc, exc) in rows[: args.top]:
        label = name if len(name) <= 42 else name[:41] + "…"
        print(f"{label:<44}{human(inc + exc):>12}{human(inc):>12}{human(exc):>12}")

    print(f"\n== 按类型（前 {args.top}）==")
    print(f"{'扩展名':<16}{'总计':>12}{'进包':>12}{'不进包':>12}")
    srows = sorted(per_suffix.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
    for name, (inc, exc) in srows[: args.top]:
        print(f"{name:<16}{human(inc + exc):>12}{human(inc):>12}{human(exc):>12}")

    print(f"\n== 会进包的最大 {args.top} 个文件 ==")
    for size, rel, _ in sorted(biggest, reverse=True)[: args.top]:
        label = rel if len(rel) <= 96 else rel[:47] + "…" + rel[-46:]
        print(f"{human(size):>12}  {label}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
