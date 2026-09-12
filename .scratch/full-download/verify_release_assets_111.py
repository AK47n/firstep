"""发布前自检（v1.1.1）：四件套自洽 + 修复是否真进了包。"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

PACK = Path.home() / "Desktop" / "firstep-pack"
VERSION = "v1.1.1"
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


for kind, prefix in (("完整包", "firstep-full"), ("小发版", "firstep-update")):
    print(f"== {kind} ==")
    zip_path = PACK / f"{prefix}-{VERSION}.zip"
    sha_path = PACK / f"{prefix}-{VERSION}.sha256.txt"
    check(zip_path.is_file(), f"{zip_path.name} 存在（{zip_path.stat().st_size / 1048576:.1f} MB）")
    expected = sha_path.read_text(encoding="utf-8").split()[0].lower()
    check(expected == sha256_of(zip_path), f"{zip_path.name} SHA256 可复算")

print("== 完整包清单 ==")
manifest_path = PACK / f"firstep-full-{VERSION}.manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
zip_path = PACK / f"firstep-full-{VERSION}.zip"
check(manifest["version"] == VERSION, f"清单版本 = {VERSION}")
check(manifest["parts"][0]["sha256"] == sha256_of(zip_path), "清单内分卷 SHA256 与文件一致")
check(manifest["removed"] == [], "首次完整包：删除清单为空")
check(len(manifest["materials_manifest"]["batches"]) == 12, "资料库基线 12 批次")
with zipfile.ZipFile(zip_path) as archive:
    names = set(archive.namelist())
    check(len(names) == len(manifest["files"]), "zip 条目数 = 清单文件数")
    listing = {n for n in names if not n.endswith("/")}
    check(
        set(f["path"] for f in manifest["files"]) == listing,
        "zip 条目与清单 files 逐条一致",
    )
    check(
        not any(n.lower().endswith((".exe", ".rar", ".img", ".img.gz", ".img.xz")) for n in listing),
        "不含装机用安装包 / 固件镜像",
    )

print("== 修复是否真进了包（关键：这次发布的意义）==")
with zipfile.ZipFile(zip_path) as archive:
    tool_root_src = archive.read("src/contest_generator/tool_root.py").decode("utf-8")
    check("def find_tool_root" in tool_root_src, "工具根单源模块进包")
    materials_src = archive.read("src/contest_generator/materials_update.py").decode("utf-8")
    check("find_tool_root" in materials_src, "资料库目录改用工具根单源")
    apply_src = archive.read("src/contest_generator/full_apply.py").decode("utf-8")
    check("resolve_launcher_port" in apply_src, "停服端口取自 FIRSTEP_LAUNCHER_PORT")
    check("_is_placeholder" not in apply_src and "更新器脚本不存在" in apply_src,
          "拉起前预检更新器脚本存在")
    with archive.open("src/contest_generator/__init__.py") as handle:
        version_src = handle.read().decode("utf-8-sig")
    check('__version__ = "1.1.1"' in version_src, "包内版本号 = 1.1.1")
    updater_src = archive.read("tools/update-app.py").decode("utf-8")
    check(
        'if location.startswith(("http://", "https://"))' in updater_src,
        "更新器按字符串判 URL（不再被 Path 折叠）",
    )

print("== 小发版清单 ==")
up_zip = PACK / f"firstep-update-{VERSION}.zip"
up_files = PACK / f"firstep-update-{VERSION}.files.txt"
with zipfile.ZipFile(up_zip) as archive:
    up_names = sorted(n for n in archive.namelist() if not n.endswith("/"))
listed = sorted(line.strip() for line in up_files.read_text(encoding="utf-8").splitlines() if line.strip())
check(up_names == listed, "更新包条目与 files.txt 一致")
check(any(n == "src/contest_generator/tool_root.py" for n in up_names), "更新包也含工具根修复")
with zipfile.ZipFile(up_zip) as archive:
    with archive.open("src/contest_generator/__init__.py") as handle:
        check('__version__ = "1.1.1"' in handle.read().decode("utf-8-sig"), "更新包内版本号 = 1.1.1")

print()
if failures:
    print(f"自检失败：{len(failures)} 项")
    for item in failures:
        print("  ✗", item)
    raise SystemExit(1)
print("自检通过：v1.1.1 四件套自洽，且三处修复确实进了两个包")
