"""精确定位「真冗余候选」：`sources/materials` 里改名重复中的**文档类**（排除原厂 SDK 树）。

TI SDK 树里的 `mspm0l1303.lds` / `mspm0l1343.lds` 这类「同名不同芯片、内容恰好相同」
是原厂打包方式，删了会破坏 SDK 结构 → 单独归类，不进候选。

用法：python .scratch/library-dedup-audit/probe-03-material-doc-dups.py [--apply]
      --apply 时把候选移入 `sources/.trash-dedup/<日期>/`（镜像路径，可手动恢复），
      而不是真删——`sources/materials` 未被 git 跟踪，删了不可回滚。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MATERIALS = REPO / "sources" / "materials"
TRASH = REPO / "sources" / ".trash-dedup"
ARCHIVE_SUFFIXES = {".zip", ".rar", ".7z", ".gz", ".xz", ".z01", ".z02", ".tar"}
SDK_MARKERS = ("/source/ti/devices/", "/网盘下载/", "/1-Demo/", "/Install libraries/")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect() -> tuple[list[list[Path]], list[list[Path]]]:
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(MATERIALS.rglob("*")):
        if path.is_file() and path.stat().st_size > 0:
            by_hash[sha256_of(path)].append(path)

    doc_groups: list[list[Path]] = []
    sdk_groups: list[list[Path]] = []
    for paths in by_hash.values():
        if len(paths) < 2:
            continue
        if len({p.name.lower() for p in paths}) == 1:
            continue  # 同名 → 应用自身判据已覆盖，不重复处理
        if any(p.suffix.lower() in ARCHIVE_SUFFIXES for p in paths):
            continue  # 原厂分包（改名重发的压缩包）
        posix = paths[0].as_posix()
        if any(marker in posix for marker in SDK_MARKERS):
            sdk_groups.append(paths)
        else:
            doc_groups.append(paths)
    return doc_groups, sdk_groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="移入回收目录（默认只报告）")
    args = parser.parse_args()

    doc_groups, sdk_groups = collect()
    print("=" * 78)
    print("sources/materials：改名重复的「文档类」候选（可删）")
    print("=" * 78)
    total = 0
    for paths in sorted(doc_groups, key=lambda ps: -ps[0].stat().st_size):
        size = paths[0].stat().st_size
        total += size * (len(paths) - 1)
        print(f"\n  {size:>12,} B × {len(paths)} 份")
        for path in paths:
            print(f"     {path.relative_to(REPO).as_posix()}")
    print(f"\n候选合计：{len(doc_groups)} 组 / 可省 {total / 1048576:.2f} MB")

    print("\n" + "=" * 78)
    print("结构性重复（原厂 SDK / demo 树内，**不动**）")
    print("=" * 78)
    sdk_total = sum(ps[0].stat().st_size * (len(ps) - 1) for ps in sdk_groups)
    print(f"  {len(sdk_groups)} 组 / {sdk_total / 1048576:.2f} MB —— 例：")
    for paths in sdk_groups[:3]:
        print(f"     {paths[0].name} × {len(paths)}（{paths[0].relative_to(REPO).as_posix()[:70]}…）")

    if not args.apply:
        print("\n（只报告模式；加 --apply 才移入回收目录）")
        return 0

    date = time.strftime("%Y-%m-%d")
    moved = 0
    for paths in doc_groups:
        for path in sorted(paths)[1:]:  # 保留第一个（按路径序），其余回收
            target = TRASH / date / path.relative_to(MATERIALS)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.stem}_1{target.suffix}")
            shutil.move(str(path), str(target))
            moved += 1
            print(f"  回收 {path.relative_to(REPO).as_posix()}")
    print(f"\n已移入 {TRASH.relative_to(REPO).as_posix()}/{date}/：{moved} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
