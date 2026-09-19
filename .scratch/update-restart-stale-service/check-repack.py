# -*- coding: utf-8 -*-
"""一次性检查：重打的 v1.2.1 两套资产 vs 线上原版（只打印短行，不 dump 清单）。

回答三件事：
1. 完整包清单的 `files` 里到底有没有 `sources/materials/` 条目、有没有 `00-START-HERE.txt`
   （新旧各一份，判「我的重打有没有漏东西」）；
2. `removed.txt` 里列的文件，有没有**同时**也在包里（那会在换装后把刚落位的文件删掉——必须为空）；
3. 更新包的同一项检查 + 文件数对照。
"""

from __future__ import annotations

import json
import pathlib
import zipfile

PACK = pathlib.Path(r"C:\Users\luoji\Desktop\firstep-pack")
BAK = PACK / "prerepublish-v1.2.1"


def describe_manifest(label: str, path: pathlib.Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    files = data.get("files") or []
    paths = [str(item["path"]) for item in files]
    materials = [p for p in paths if p.startswith("sources/materials/")]
    print(f"[{label}] {path.name}")
    print(f"    files 条数 = {len(paths)}（其中 sources/materials = {len(materials)}）")
    print(f"    00-START-HERE.txt 在 files 里: {'00-START-HERE.txt' in paths}")
    print(f"    removed 条数 = {len(data.get('removed') or [])}")
    print(f"    materials_manifest.batches = {len((data.get('materials_manifest') or {}).get('batches') or [])}")
    return {"paths": set(paths), "removed": list(data.get("removed") or [])}


def check_removed_intersection(label: str, removed_path: pathlib.Path,
                               zip_path: pathlib.Path) -> None:
    removed = {line.strip() for line in removed_path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")}
    with zipfile.ZipFile(zip_path) as archive:
        names = {n.replace("/", "\\") for n in archive.namelist()}
        names |= {n for n in archive.namelist()}
    overlap = sorted(removed & names)
    print(f"[{label}] removed {len(removed)} 条 ∩ 包内条目 {len(names)} 条 = {len(overlap)} 条")
    for item in overlap[:5]:
        print(f"    ** 危险：{item}")


print("=" * 70)
new_full = describe_manifest("新完整包", PACK / "firstep-full-v1.2.1.manifest.json")
old_full = describe_manifest("线上原版完整包", BAK / "firstep-full-v1.2.1.manifest.json")
print(f"[差集] 新有旧无 = {len(new_full['paths'] - old_full['paths'])} 条；"
      f"旧有新无 = {len(old_full['paths'] - new_full['paths'])} 条")
for item in sorted(old_full["paths"] - new_full["paths"])[:10]:
    print(f"    - 旧有新无：{item}")
for item in sorted(new_full["paths"] - old_full["paths"])[:10]:
    print(f"    + 新有旧无：{item}")

print("=" * 70)
check_removed_intersection("新完整包", PACK / "firstep-full-v1.2.1.removed.txt",
                           PACK / "firstep-full-v1.2.1.zip")
check_removed_intersection("新更新包", PACK / "firstep-update-v1.2.1.removed.txt",
                           PACK / "firstep-update-v1.2.1.zip")

print("=" * 70)
for label, removed_path in (("新完整包 vs 线上原版",
                             (PACK / "firstep-full-v1.2.1.removed.txt",
                              BAK / "firstep-full-v1.2.1.removed.txt")),):
    new = {line.strip() for line in removed_path[0].read_text(encoding="utf-8").splitlines() if line.strip()}
    old = {line.strip() for line in removed_path[1].read_text(encoding="utf-8").splitlines() if line.strip()}
    print(f"[{label}] 新 {len(new)} / 旧 {len(old)}；旧有新无 {len(old - new)}；新有旧无 {len(new - old)}")
    by_top: dict[str, int] = {}
    for item in sorted(new - old):
        top = item.split("/")[0]
        by_top[top] = by_top.get(top, 0) + 1
    print(f"    多出来的按顶层分布：{by_top}")
