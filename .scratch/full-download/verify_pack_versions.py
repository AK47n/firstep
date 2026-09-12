"""核对已打包产物的版本号与关键文件（防「包内版本 ≠ tag」）。"""

from __future__ import annotations

import difflib
import io
import zipfile
from pathlib import Path

PACK = Path.home() / "Desktop" / "firstep-pack"


def show(zip_name: str, member: str) -> None:
    path = PACK / zip_name
    if not path.is_file():
        print(f"（缺 {zip_name}）")
        return
    with zipfile.ZipFile(path) as archive:
        try:
            text = archive.read(member).decode("utf-8-sig")
        except KeyError:
            print(f"{zip_name} 内没有 {member}")
            return
    print(f"--- {zip_name} :: {member} ---")
    print(text.strip()[:300])


show("firstep-update-v1.1.0.zip", "src/contest_generator/__init__.py")
show("firstep-update-v1.1.0.zip", "VERSIONS.md")
show("firstep-full-v1.1.0.zip", "src/contest_generator/__init__.py")
show("firstep-full-v1.1.0.zip", "tools/pack-full.ps1")

# 更新包 vs 完整包：共有文件的差异数量（判断两个包是否同一版本快照）
up_zip = PACK / "firstep-update-v1.1.0.zip"
full_zip = PACK / "firstep-full-v1.1.0.zip"
if up_zip.is_file() and full_zip.is_file():
    with zipfile.ZipFile(up_zip) as a, zipfile.ZipFile(full_zip) as b:
        up_names = {n for n in a.namelist() if not n.endswith("/")}
        full_names = {n for n in b.namelist() if not n.endswith("/")}
        common = sorted(up_names & full_names)
        differ: list[str] = []
        for name in common:
            if a.read(name) != b.read(name):
                differ.append(name)
        print(f"\n共有文件 {len(common)} 个，内容不同的 {len(differ)} 个：")
        for name in differ[:10]:
            print("  -", name)
        print(f"仅在小发版：{len(up_names - full_names)} 个；仅在完整包：{len(full_names - up_names)} 个")
        print("仅在小发版示例：", sorted(up_names - full_names)[:5])
        print("仅在完整包示例：", sorted(full_names - up_names)[:5])
        if differ:
            name = differ[0]
            left = a.read(name).decode("utf-8", "replace").splitlines()
            right = b.read(name).decode("utf-8", "replace").splitlines()
            print(f"\n首个差异文件的 diff（{name}）：")
            for line in list(difflib.unified_diff(left, right, "更新包", "完整包", lineterm=""))[:20]:
                print("   ", line)
