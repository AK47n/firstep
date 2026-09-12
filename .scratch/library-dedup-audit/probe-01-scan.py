"""各库重复项盘点（只读，不改任何文件）。

口径：
- 扫描六个内容库 + 三类非内容目录（备份 / 回收站），分开统计；
- 重复 = **同一库内**内容完全相同（SHA256 同）的多个文件；
  跨库同内容另列，因为「wiki 手册页」与「references 条目」这类跨库同内容是设计如此。
- 输出：按重复组列出（组内文件数、字节数、可省字节），并汇总每个库的浪费。

用法：python .scratch/library-dedup-audit/probe-01-scan.py [--min-size N]
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 内容库（用户可见的知识资产）
CONTENT_LIBS = {
    "library/modules": REPO / "library" / "modules",
    "library/masters": REPO / "library" / "masters",
    "library/references": REPO / "library" / "references",
    "library/topics": REPO / "library" / "topics",
    "sources/materials": REPO / "sources" / "materials",
    "sources/contest": REPO / "sources" / "contest",
    "sources/car": REPO / "sources" / "car",
}

# 非内容目录（备份 / 回收站 / 生成缓存）——单独看，是否清理是另一个决定
NON_CONTENT_DIRS = {
    "library/fix-backups": REPO / "library" / "fix-backups",
    "library/revise-backups": REPO / "library" / "revise-backups",
    "sources/.trash-pdf": REPO / "sources" / ".trash-pdf",
}

SKIP_DIR_NAMES = {"__pycache__", ".pytest_cache", "node_modules", ".git"}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        found.append(path)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-size", type=int, default=0, help="只看 ≥ N 字节的文件")
    args = parser.parse_args()

    print("=" * 78)
    print("内容库重复盘点（同一库内，内容完全相同）")
    print("=" * 78)

    global_by_hash: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    total_files = total_bytes = waste_bytes = 0

    for name, root in CONTENT_LIBS.items():
        files = [f for f in collect(root) if f.stat().st_size >= args.min_size]
        if not files:
            print(f"\n[{name}] 不存在或为空")
            continue
        size = sum(f.stat().st_size for f in files)
        total_files += len(files)
        total_bytes += size

        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in files:
            digest = sha256_of(path)
            by_hash[digest].append(path)
            global_by_hash[digest].append((name, path))

        groups = {h: ps for h, ps in by_hash.items() if len(ps) > 1}
        lib_waste = sum(ps[0].stat().st_size * (len(ps) - 1) for ps in groups.values())
        waste_bytes += lib_waste
        print(
            f"\n[{name}] 文件 {len(files)} 个 / {size / 1048576:.1f} MB —— "
            f"重复组 {len(groups)} 个，冗余 {sum(len(p) - 1 for p in groups.values())} 个文件 / {lib_waste / 1048576:.2f} MB"
        )
        ranked = sorted(groups.values(), key=lambda ps: ps[0].stat().st_size * (len(ps) - 1), reverse=True)
        for paths in ranked[:12]:
            rel = [p.relative_to(REPO).as_posix() for p in paths]
            print(f"   · {paths[0].stat().st_size:>9,} B × {len(paths)} 份")
            for item in rel[:6]:
                print(f"       {item}")
            if len(rel) > 6:
                print(f"       … 另 {len(rel) - 6} 个")

    print("\n" + "=" * 78)
    print("跨库同内容（可能是设计如此，仅列前 15 组）")
    print("=" * 78)
    cross = 0
    for digest, items in sorted(global_by_hash.items(), key=lambda kv: -len(kv[1])):
        libs = {lib for lib, _ in items}
        if len(libs) < 2 or len(items) < 2:
            continue
        cross += 1
        if cross > 15:
            continue
        sample = items[0][1]
        print(f"   · {sample.stat().st_size:>9,} B × {len(items)} 份，跨 {len(libs)} 个库：{sorted(libs)}")
        for lib, path in items[:4]:
            print(f"       [{lib}] {path.relative_to(REPO).as_posix()}")
    print(f"\n跨库同内容组合计：{cross} 组")

    print("\n" + "=" * 78)
    print("非内容目录（备份 / 回收站）")
    print("=" * 78)
    for name, root in NON_CONTENT_DIRS.items():
        files = collect(root)
        if not files:
            print(f"[{name}] 空")
            continue
        size = sum(f.stat().st_size for f in files)
        print(f"[{name}] {len(files)} 个文件 / {size / 1048576:.1f} MB")

    print(
        f"\n内容库合计：{total_files} 个文件 / {total_bytes / 1048576:.1f} MB；"
        f"同库冗余 {waste_bytes / 1048576:.2f} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
