"""「故意不进包」那 5.29 GiB 具体是被哪条规则挡掉的、每个大头文件是谁。

用法：python .scratch/materials-baseline-writeback/measure-excluded.py [--top N]
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.full_pack import (  # noqa: E402
    INSTALLER_GLOBS,
    SKIP_FILE_NAMES,
    SKIP_FILE_SUFFIXES,
    materials_excluded,
)

MIB = 1024**2


def human(n: float) -> str:
    return f"{n / 1024**3:.2f} GiB" if n >= 512 * MIB else f"{n / MIB:.1f} MiB"


def reason(rel: str) -> str:
    """复刻 full_pack.materials_excluded 的判定顺序，给出「被谁挡的」。"""
    name = rel.rsplit("/", 1)[-1]
    for part in rel.split("/"):
        if part in (".git", "__pycache__", ".materials-manifest.json"):
            return f"目录/自身：{part}"
    if name in SKIP_FILE_NAMES:
        return f"文件名：{name}"
    if name.lower().endswith(SKIP_FILE_SUFFIXES):
        return f"后缀：{name.rsplit('.', 1)[-1]}"
    lowered = name.lower()
    for pattern in INSTALLER_GLOBS:
        if fnmatch.fnmatch(lowered, pattern.lower()):
            return f"装机件特征：{pattern}"
    return "（未命中——不该出现）"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    tree = ROOT / "sources" / "materials"
    per_rule: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    rows: list[tuple[int, str, str]] = []

    for path in tree.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(tree).as_posix()
        if not materials_excluded(rel):
            continue
        size = path.stat().st_size
        rule = reason(rel)
        per_rule[rule][0] += size
        per_rule[rule][1] += 1
        rows.append((size, rel, rule))

    total = sum(r[0] for r in per_rule.values())
    print(f"不进包合计：{human(total)} / {sum(r[1] for r in per_rule.values())} 个文件\n")
    print(f"{'被哪条规则挡的':<34}{'体积':>12}{'文件数':>8}")
    for rule, (size, count) in sorted(per_rule.items(), key=lambda kv: -kv[1][0]):
        print(f"{rule:<34}{human(size):>12}{count:>8}")

    print(f"\n== 单个最大的 {args.top} 个（全都不进包）==")
    for size, rel, rule in sorted(rows, reverse=True)[: args.top]:
        label = rel if len(rel) <= 92 else rel[:45] + "…" + rel[-46:]
        print(f"{human(size):>12}  {label}\n{'':>12}  ← {rule}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
