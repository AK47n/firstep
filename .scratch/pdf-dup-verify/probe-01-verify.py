# -*- coding: utf-8 -*-
"""PDF 资料库重复复核（只读）：应用判据 vs 内容 SHA256。

请求：「PDF资料库里面看看是否真的重复，如果是真的重复就删掉」。

应用判据（static/js/fx/pdf.js:pdfDupGroups）= 同名（大小写不敏感）+ 同大小
+ 大小 > 0 + 组内 >= 2 成员，标「疑似」且**不读内容 hash**。本探针把每个
疑似组逐字节复算（SHA256），回答「疑似是否属实」；另做一次全库内容分组，
把应用判据抓不到的「改名重复」也列出来。

输出：分组明细 + 汇总（真重复冗余字节 / 假重复组数 / 改名重复组数）。
"""

from __future__ import annotations

import hashlib
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "sources" / "materials"


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def collect(root: Path) -> list[dict]:
    out: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        st = path.stat()
        out.append(
            {
                "rel": path.relative_to(root).as_posix(),
                "name": path.name,
                "size": st.st_size,
                "path": path,
            }
        )
    return out


def main() -> int:
    if not ROOT.is_dir():
        print(f"[错误] 素材根不存在：{ROOT}")
        return 1
    files = collect(ROOT)
    print(f"素材根：{ROOT}")
    print(f"PDF 总数：{len(files)}，合计 {sum(f['size'] for f in files) / 1e6:.2f} MB")

    for f in files:
        f["sha"] = sha256(f["path"])

    # —— 一、应用判据的疑似组 ——
    suspect: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for f in files:
        if f["size"] > 0:
            suspect[(f["name"].lower(), f["size"])].append(f)
    suspect = {k: v for k, v in suspect.items() if len(v) >= 2}

    print(f"\n=== 一、应用判据「疑似重复」组：{len(suspect)} 组 ===")
    true_groups = 0
    false_groups = 0
    true_bytes = 0
    for (name_low, size), members in sorted(suspect.items(), key=lambda kv: -kv[0][1]):
        hashes = {m["sha"] for m in members}
        ok = len(hashes) == 1
        true_groups += ok
        false_groups += (not ok)
        if ok:
            true_bytes += size * (len(members) - 1)
        tag = "真重复（内容逐字节相同）" if ok else f"**假重复**（内容不同，{len(hashes)} 种）"
        print(f"\n[{tag}] {members[0]['name']}  {size:,} B  ×{len(members)}")
        for m in members:
            print(f"    {m['sha'][:12]}  {m['rel']}")

    # —— 二、全库内容分组（含改名重复）——
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        if f["size"] > 0:
            by_hash[f["sha"]].append(f)
    content_dups = {h: v for h, v in by_hash.items() if len(v) >= 2}

    covered = {m["rel"] for members in suspect.values() for m in members}
    renamed = {h: v for h, v in content_dups.items()
               if not any(m["rel"] in covered for m in v)}

    print(f"\n=== 二、全库内容重复组：{len(content_dups)} 组"
          f"（其中应用判据抓不到的「改名重复」：{len(renamed)} 组）===")
    if renamed:
        for h, members in sorted(renamed.items(), key=lambda kv: -kv[1][0]["size"]):
            print(f"\n[改名重复] {members[0]['size']:,} B ×{len(members)}")
            for m in members:
                print(f"    {h[:12]}  {m['rel']}")
    else:
        print("（无——应用判据已覆盖全部内容重复组）")

    # —— 三、汇总 ——
    unique_contents = len(by_hash)
    print("\n=== 三、汇总 ===")
    print(f"PDF 文件数：{len(files)}，唯一内容数：{unique_contents}")
    print(f"疑似组：{len(suspect)}（真重复 {true_groups} 组 / 假重复 {false_groups} 组）")
    print(f"疑似组内可回收冗余：{true_bytes / 1e6:.2f} MB")
    all_dup_bytes = sum(v[0]["size"] * (len(v) - 1) for v in content_dups.values())
    print(f"全库内容重复可回收冗余：{all_dup_bytes / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
