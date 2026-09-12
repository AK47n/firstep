"""拿新判据照**历史发版包**：证明跨包判据真能抓到工单里那 926 个（工单 full-download/08）。

v1.1.0 / v1.1.1 的四件套还在本机 `%USERPROFILE%\\Desktop\\firstep-pack`，
直接用 `verify_release_assets.cross_pack_byte_diff` 对拍——若判据有效，
它必须点名那批只有换行符不同的文件（v1.1.0 现场记录：3474 个共有文件里 926 个）。

同时给出「归一化换行后还剩几个真差异」，用于区分「全是换行符」与「真有内容差异」。

用法：python .scratch/full-download/probe-08-historical-cross-pack.py [v1.1.0 v1.1.1]
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_release_assets import cross_pack_byte_diff  # noqa: E402

PACK = Path.home() / "Desktop" / "firstep-pack"


def content(zip_path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(zip_path) as archive:
        return {
            name: archive.read(name) for name in archive.namelist() if not name.endswith("/")
        }


def normalize_eol(payload: bytes) -> bytes:
    return payload.replace(b"\r\n", b"\n")


def main(argv: list[str]) -> int:
    versions = argv or ["v1.1.0", "v1.1.1"]
    if not PACK.is_dir():
        print(f"跳过：未找到 {PACK}")
        return 0

    failed = 0
    for version in versions:
        full_zip = PACK / f"firstep-full-{version}.zip"
        update_zip = PACK / f"firstep-update-{version}.zip"
        if not (full_zip.is_file() and update_zip.is_file()):
            print(f"[{version}] 跳过：缺少 {full_zip.name} 或 {update_zip.name}")
            continue

        full = content(full_zip)
        update = content(update_zip)
        shared = sorted(set(full) & set(update))
        diff = cross_pack_byte_diff(full, update)
        eol_only = [n for n in diff if normalize_eol(full[n]) == normalize_eol(update[n])]
        real = [n for n in diff if n not in set(eol_only)]

        print(f"== {version} ==")
        print(f"  共有文件：{len(shared)} 个（完整包 {len(full)} / 更新包 {len(update)}）")
        print(f"  新判据报出的字节差异：{len(diff)} 个")
        print(f"    其中仅换行符不同：{len(eol_only)} 个")
        print(f"    真实内容差异：{len(real)} 个")
        for name in diff[:5]:
            print(
                f"      · {name}: 完整包 {len(full[name])}B / 更新包 {len(update[name])}B"
            )
        print(f"  → 判据{'有效（抓到了这批差异）' if diff else '未报差异'}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
