"""定向分析：内容完全相同、但**文件名不同**的重复（应用自身判据抓不到的那类）。

应用侧判据（`static/js/fx/pdf.js:47-56` pdfDupGroups）= **同名 + 同大小**，标注「疑似」；
本脚本用 SHA256 复算，专门挑「字节相同但名字不同」——那才是同一份文件被存了两遍。

输出按「是否属于第三方资料包结构」（压缩包 / SDK 头文件 / demo 树）分类，
因为那类重复是原厂打包方式使然，删了会破坏包内结构。

用法：python .scratch/library-dedup-audit/probe-02-renamed-dups.py
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIBS = {
    "library/references": REPO / "library" / "references",
    "library/topics": REPO / "library" / "topics",
    "sources/materials": REPO / "sources" / "materials",
    "sources/contest": REPO / "sources" / "contest",
    "sources/car": REPO / "sources" / "car",
}
ARCHIVE_SUFFIXES = {".zip", ".rar", ".7z", ".gz", ".xz", ".z01", ".z02", ".tar"}
SDK_HEADER = "stm32f10x.h"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(paths: list[Path]) -> str:
    """判断这组重复是不是「第三方资料包/原厂 demo 树」的结构性重复。"""
    names = {p.name.lower() for p in paths}
    if len(names) == 1:
        return "同名（应用判据能抓到的形态）"
    if any(p.suffix.lower() in ARCHIVE_SUFFIXES for p in paths):
        return "压缩包（原厂分包重复）"
    if SDK_HEADER in names:
        return "SDK 头文件（原厂 demo 树 × 多工程）"
    # 同一 vendor 大目录下的多份拷贝（路径首段到第 3 段相同）
    prefixes = {"/".join(p.parts[:5]) for p in paths}
    if len(prefixes) < len(paths) and len(paths) > 2:
        return "同一资料目录内多份拷贝"
    return "改名重复（真实冗余候选）"


def main() -> int:
    print("=" * 78)
    print("改名重复分析（字节相同、文件名不同）")
    print("=" * 78)

    for lib, root in LIBS.items():
        if not root.is_dir():
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.stat().st_size == 0:
                continue
            by_hash[sha256_of(path)].append(path)

        groups = [ps for ps in by_hash.values() if len(ps) > 1]
        buckets: dict[str, list[list[Path]]] = defaultdict(list)
        for paths in groups:
            buckets[classify(paths)].append(paths)

        total_waste = sum(ps[0].stat().st_size * (len(ps) - 1) for paths in groups for ps in [paths])
        print(f"\n[{lib}] 重复组 {len(groups)} 个 / 冗余 {sum(len(p) - 1 for p in groups)} 个文件 / {total_waste / 1048576:.2f} MB")
        for bucket, items in sorted(buckets.items(), key=lambda kv: -sum(x[0].stat().st_size * (len(x) - 1) for x in kv[1])):
            waste = sum(x[0].stat().st_size * (len(x) - 1) for x in items)
            print(f"   ▸ {bucket}：{len(items)} 组 / {waste / 1048576:.2f} MB")
            if bucket == "改名重复（真实冗余候选）":
                for paths in sorted(items, key=lambda ps: -ps[0].stat().st_size):
                    size = paths[0].stat().st_size
                    print(f"       · {size:>10,} B × {len(paths)}：")
                    for p in paths:
                        print(f"           {p.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
