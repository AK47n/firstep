"""发布前自检：核对完整包四件套的自洽性（大小 / 哈希 / 清单与 zip 内容一致）。"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

PACK = Path.home() / "Desktop" / "firstep-pack"
VERSION = "v1.1.0"
failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + what)
    if not cond:
        failures.append(what)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---- 完整包 ----
print("== 完整包 four-piece ==")
manifest_path = PACK / f"firstep-full-{VERSION}.manifest.json"
zip_path = PACK / f"firstep-full-{VERSION}.zip"
removed_path = PACK / f"firstep-full-{VERSION}.removed.txt"
sha_path = PACK / f"firstep-full-{VERSION}.sha256.txt"

check(manifest_path.is_file(), f"清单存在（{manifest_path.name}）")
check(zip_path.is_file(), f"分卷存在（{zip_path.name} {zip_path.stat().st_size / 1048576:.1f} MB）")
check(removed_path.is_file(), "删除清单存在")
check(sha_path.is_file(), "SHA256 汇总存在")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
check(manifest["version"] == VERSION, f"清单版本 = {VERSION}")
check(len(manifest["parts"]) == 1, "分卷数 = 1")
part = manifest["parts"][0]
check(part["zip_name"] == zip_path.name, "分卷名与清单一致")
check(part["size"] == zip_path.stat().st_size, "分卷大小与清单一致")
check(part["sha256"] == sha256_of(zip_path), "分卷 SHA256 可复算一致")
check(
    part["sha256"] in sha_path.read_text(encoding="utf-8"),
    "SHA256 汇总文件含该分卷哈希",
)
check(manifest["removed"] == [], "首次完整包：删除清单为空（无基线）")
check(
    removed_path.read_text(encoding="utf-8").strip() == "",
    "removed.txt 与清单 removed 均为空",
)

with zipfile.ZipFile(zip_path) as archive:
    names = sorted(n for n in archive.namelist() if not n.endswith("/"))
listed = sorted(f["path"] for f in manifest["files"])
check(len(names) == len(listed), f"zip 内条目数 = 清单文件数（{len(names)}）")
check(names == listed, "zip 条目与清单 files 逐条一致")
check(
    not any(n.lower().endswith((".exe", ".rar", ".img", ".img.gz", ".img.xz")) for n in names),
    "包内不含装机用安装包 / 固件镜像",
)
check(
    any(n.endswith("install.bat") for n in names) and any(n.startswith("src/") for n in names),
    "包内含工具本体（src/ 与根级启动脚本）",
)

materials = manifest["materials_manifest"]
materials_files = sum(len(b["files"]) for b in materials["batches"])
check(len(materials["batches"]) == 12, f"资料库基线 {len(materials['batches'])} 个批次")
check(materials_files == 5087, f"资料库基线 {materials_files} 个文件")
check(materials["version"] == VERSION, "资料库基线版本 = 完整包版本")
missing_from_zip = [
    f"sources/materials/{item['path']}"
    for b in materials["batches"]
    for item in b["files"]
    if f"sources/materials/{item['path']}" not in set(listed)
]
check(not missing_from_zip, f"基线里每个文件都在包内（缺失 {len(missing_from_zip)} 个）")

# ---- 小发版 ----
print("== 小发版 four-piece ==")
up_zip = PACK / f"firstep-update-{VERSION}.zip"
up_files = PACK / f"firstep-update-{VERSION}.files.txt"
up_removed = PACK / f"firstep-update-{VERSION}.removed.txt"
up_sha = PACK / f"firstep-update-{VERSION}.sha256.txt"
check(up_zip.is_file(), f"更新包存在（{up_zip.stat().st_size / 1048576:.1f} MB）")
check(up_files.is_file() and up_removed.is_file() and up_sha.is_file(), "清单 / 删除清单 / 校验和齐全")
check(
    sha256_of(up_zip).lower() in up_sha.read_text(encoding="utf-8").lower(),
    "更新包 SHA256 与汇总一致",
)
up_sha_expected = (up_sha.read_text(encoding="utf-8").split()[0]).lower()
check(up_sha_expected == sha256_of(up_zip), "更新包 SHA256 可复算")
with zipfile.ZipFile(up_zip) as archive:
    up_names = sorted(n for n in archive.namelist() if not n.endswith("/"))
check(up_names == sorted(l.strip() for l in up_files.read_text(encoding="utf-8").splitlines() if l.strip()),
      "更新包条目与 files.txt 一致")

print()
if failures:
    print(f"自检失败：{len(failures)} 项")
    for item in failures:
        print("  ✗", item)
    raise SystemExit(1)
print("自检通过：完整包与小发版四件套均自洽")
