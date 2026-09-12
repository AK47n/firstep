"""发布前自检：核对完整包四件套的自洽性（大小 / 哈希 / 清单与 zip 内容一致）。

**跨包判据（工单 full-download/08 补）**：小发版与完整包对同一源文件必须产出同一份
字节——两个包曾对 3474 个共有文件里 926 个字节不同（全是换行符，`git archive`
的 `core.autocrlf` 转换），单个包自洽的自检抓不到，只有对拍才看得见。

被测函数（`file_bytes` / `cross_pack_byte_diff` / `sha256_of`）供
`tests/test_pack_update.py` 直接导入；**导入不产生副作用**，校验主体在 `main()` 里
且只读已存在的产物：本地没有 `firstep-pack`（未发过版的机器 / CI）会明确跳过，
不再抛异常——原先的模块级写法连导入都会崩。

用法：`python .scratch/full-download/verify_release_assets.py`
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

PACK = Path.home() / "Desktop" / "firstep-pack"
VERSION = "v1.1.0"

__all__ = ["cross_pack_byte_diff", "file_bytes", "main", "sha256_of"]

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


def file_bytes(zip_path: Path) -> dict[str, bytes]:
    """zip → {条目路径: 原始字节}（跨包比对只认内容，不比 zip 容器元数据）。"""
    content: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            content[name] = archive.read(name)
    return content


def cross_pack_byte_diff(full: dict[str, bytes], update: dict[str, bytes]) -> list[str]:
    """两个包的共有文件里字节不同的那些（空 = 通过）。

    只比共有文件：完整包含资料库内容，小发版按定义只含 tracked 快照，
    文件集不同是设计如此；同一路径必须字节相同。
    """
    shared = sorted(set(full) & set(update))
    return [name for name in shared if full[name] != update[name]]


def main(argv: list[str] | None = None) -> int:
    del argv  # 目前无参数（版本用模块常量；需要时再开 CLI 面）
    failures.clear()

    if not PACK.is_dir():
        print(f"跳过：未找到发布产物目录 {PACK}（本机未发过版 / 未保留产物）")
        return 0

    # ---- 完整包 ----
    print("== 完整包 four-piece ==")
    manifest_path = PACK / f"firstep-full-{VERSION}.manifest.json"
    zip_path = PACK / f"firstep-full-{VERSION}.zip"
    removed_path = PACK / f"firstep-full-{VERSION}.removed.txt"
    sha_path = PACK / f"firstep-full-{VERSION}.sha256.txt"

    if not manifest_path.is_file():
        print(f"跳过：清单不存在 {manifest_path.name}（产物已清理 / 版本不同）")
        return 0

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
    check(
        up_names
        == sorted(l.strip() for l in up_files.read_text(encoding="utf-8").splitlines() if l.strip()),
        "更新包条目与 files.txt 一致",
    )

    # ---- 跨包一致性（工单 full-download/08） ----
    print("== 跨包共有文件字节一致性 ==")
    full_content = file_bytes(zip_path)
    update_content = file_bytes(up_zip)
    shared = sorted(set(full_content) & set(update_content))
    diff = cross_pack_byte_diff(full_content, update_content)
    check(len(shared) > 0, f"两个包存在共有文件可比对（{len(shared)} 个）")
    check(diff == [], f"共有文件字节全一致（差异 {len(diff)} 个）")
    for name in diff[:10]:
        print(
            f"      · {name}：完整包 {len(full_content[name])}B / "
            f"更新包 {len(update_content[name])}B"
        )

    print()
    if failures:
        print(f"自检失败：{len(failures)} 项")
        for item in failures:
            print("  ✗", item)
        return 1
    print("自检通过：完整包与小发版四件套均自洽，跨包字节一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
