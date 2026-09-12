"""跨包逐字节一致性真机验证（工单 full-download/08 验收项 ④）。

在**真实仓库**上分别跑两个打包路径，逐一比对共有文件的字节：

1. 完整包：`prepare_full_package(..., limit=8MB)`——限值只影响分卷数，不影响内容；
2. 小发版：`tools/pack-update.ps1`（真脚本、真四件套）→ 取 `firstep-update-<tag>.zip`。

判据：共有文件里字节不同的 **= 0**，且 `.bat` 仍为 CRLF、`.githooks/*` 仍为 LF。

用法（仓库根）：
    python .scratch/full-download/verify-08-cross-pack-bytes.py
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TAG = "v0.0.0-eolcheck"
OUT = REPO / ".scratch" / "full-download" / "_verify08"


def times() -> float:
    return time.perf_counter()


def main() -> int:
    sys.path.insert(0, str(REPO / "src"))
    from contest_generator.full_pack import prepare_full_package

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"仓库：{REPO}")
    print(f"产物：{OUT}")

    # ---- 1. 完整包（小分卷，只为拿内容） ----
    started = times()
    full_dir = OUT / "full"
    manifest, zips = prepare_full_package(
        REPO, version=TAG, out_dir=full_dir, published_at="", limit=8 * 1024 * 1024
    )
    print(
        f"[1/3] 完整包：{len(manifest['files'])} 个文件 / {len(zips)} 卷 / "
        f"{manifest['total_bytes'] / 1048576:.1f} MB 原始（{times() - started:.1f}s）"
    )

    # ---- 2. 小发版（真脚本） ----
    started = times()
    update_dir = OUT / "update"
    completed = subprocess.run(
        (
            "powershell",
            "-NoProfile",
            "-File",
            str(REPO / "tools" / "pack-update.ps1"),
            "-Tag",
            TAG,
            "-OutDir",
            str(update_dir),
        ),
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        print("[失败] pack-update.ps1 退出码", completed.returncode)
        print(completed.stdout[-3000:])
        print(completed.stderr[-3000:])
        return 1
    print(f"[2/3] 小发版：pack-update.ps1 退出码 0（{times() - started:.1f}s）")
    for line in completed.stdout.strip().splitlines()[-5:]:
        print("      " + line.strip())

    # ---- 3. 逐字节对拍 ----
    def content(zip_path: Path) -> dict[str, bytes]:
        with zipfile.ZipFile(zip_path) as archive:
            return {
                name: archive.read(name)
                for name in archive.namelist()
                if not name.endswith("/")
            }

    full_content: dict[str, bytes] = {}
    for zip_path in sorted(full_dir.glob("firstep-full-*.zip")):
        full_content.update(content(zip_path))
    update_zip = update_dir / f"firstep-update-{TAG}.zip"
    update_content = content(update_zip)

    shared = sorted(set(full_content) & set(update_content))
    diff = [name for name in shared if full_content[name] != update_content[name]]

    print(f"[3/3] 共有文件 {len(shared)} 个；完整包 {len(full_content)} 个 / 小发版 {len(update_content)} 个")
    print(f"      字节不同的共有文件：{len(diff)} 个")
    for name in diff[:20]:
        print(f"        · {name}: {len(full_content[name])}B vs {len(update_content[name])}B")

    def eol_of(payload: bytes) -> str:
        crlf = payload.count(b"\r\n")
        lf = payload.count(b"\n") - crlf
        return f"CRLF={crlf} LF={lf}"

    bats = [n for n in shared if n.lower().endswith(".bat")]
    hooks = [n for n in shared if n.startswith(".githooks/")]
    print(f"      批处理 {len(bats)} 个，例：{bats[0] if bats else '-'} → {eol_of(update_content[bats[0]]) if bats else '-'}")
    print(f"      钩子 {len(hooks)} 个，例：{hooks[0] if hooks else '-'} → {eol_of(update_content[hooks[0]]) if hooks else '-'}")

    bat_ok = all(update_content[n] == full_content[n] for n in bats)
    # 四件套自洽
    files_txt = update_dir / f"firstep-update-{TAG}.files.txt"
    listed = sorted(
        line.strip() for line in files_txt.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    entries = sorted(update_content)
    sha_txt = (update_dir / f"firstep-update-{TAG}.sha256.txt").read_text(encoding="utf-8")
    zip_sha = hashlib.sha256(update_zip.read_bytes()).hexdigest()
    removed_txt = update_dir / f"firstep-update-{TAG}.removed.txt"

    checks = [
        ("共有文件字节差异 = 0", diff == []),
        ("共有文件非空（有可比对样本）", len(shared) > 0),
        ("批处理 CRLF 且两边一致", bat_ok and bool(bats)),
        ("小发版 zip 条目 = files.txt", listed == entries),
        ("sha256.txt 与实测一致", zip_sha in sha_txt),
        ("空删除清单写注释行（非 0 字节）", removed_txt.stat().st_size > 0
         and removed_txt.read_text(encoding="utf-8").lstrip().startswith("#")),
    ]
    print()
    failed = 0
    for what, ok in checks:
        print(("  ✓ " if ok else "  ✗ ") + what)
        failed += 0 if ok else 1

    print()
    if failed:
        print(f"验证失败：{failed} 项")
        return 1
    print(f"验证通过：两个包对同一 commit 的 {len(shared)} 个共有文件逐字节一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
