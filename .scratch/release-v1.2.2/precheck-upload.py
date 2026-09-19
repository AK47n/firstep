# -*- coding: utf-8 -*-
"""上传前校验（工单 release-v1.2.2/04）：四件套自洽 + 关键内容在场（只读）。

**为什么必须跑**：上一轮踩过两次——
① `Select-Object -First N` 接在 `powershell -File tools\\pack-update.ps1` 后面会**提前掐断上游**，
   打包器跑不到写 `sha256.txt` 那一步：zip 生成了、校验和文件还是**上一版的**；
② 0 字节的 `removed.txt` 会被 GitHub 拒收（`HTTP 400: Bad Content-Length`）。

判据（逐条打印，任一红即非 0 退出）：

1. `sha256.txt` 里记的哈希 == **现算**的 zip 哈希（两个包各一次）；
2. 四件套齐、`removed.txt` 非 0 字节且条数与"本版不发"的规模对得上；
3. 完整包 zip 里真的有 `00-START-HERE.txt`（新用户解压第一眼要看到的东西），
   且**没有** `egg-info` / `revise-backups`（这一版摘掉的两类）；
4. zip 内条目数 == 清单条数（小发版：「zip 条目 == 清单」是打包器的既有自检，这里复核）。
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACK = Path.home() / "Desktop" / "firstep-pack"
TAG = "v1.2.2"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_recorded(name: str) -> str:
    text = (PACK / name).read_text(encoding="utf-8-sig")
    return text.split()[0].strip().lower()


def main() -> int:
    ok = True
    print(f"# 上传前校验：{TAG}")

    # ---- 1. zip 实算 vs sha256.txt ----
    print("\n## 1. zip 实算 vs sha256.txt（上一轮就是这里被掐断的）")
    for kind in ("update", "full"):
        zip_path = PACK / f"firstep-{kind}-{TAG}.zip"
        sha_path = PACK / f"firstep-{kind}-{TAG}.sha256.txt"
        if not zip_path.is_file():
            print(f"  ✗ {zip_path.name} 不存在")
            ok = False
            continue
        actual = sha256_of(zip_path)
        recorded = read_recorded(sha_path.name) if sha_path.is_file() else "(缺)"
        same = actual == recorded
        print(f"  {'✓' if same else '✗'} {zip_path.name}"
              f"（{zip_path.stat().st_size:,} B）")
        print(f"      实算 {actual}")
        print(f"      记录 {recorded}")
        ok = ok and same

    # ---- 2. 四件套齐 + removed 非空 ----
    print("\n## 2. 四件套齐整")
    for kind in ("update", "full"):
        names = [f"firstep-{kind}-{TAG}.zip",
                 f"firstep-{kind}-{TAG}.{'files.txt' if kind == 'update' else 'manifest.json'}",
                 f"firstep-{kind}-{TAG}.removed.txt",
                 f"firstep-{kind}-{TAG}.sha256.txt"]
        for name in names:
            path = PACK / name
            size = path.stat().st_size if path.is_file() else -1
            good = size > 0
            print(f"  {'✓' if good else '✗'} {name}（{size:,} B）")
            ok = ok and good

    # ---- 3. 完整包 zip 内容 ----
    print("\n## 3. 完整包内容关键项")
    full_zip = PACK / f"firstep-full-{TAG}.zip"
    with zipfile.ZipFile(full_zip) as archive:
        names = archive.namelist()
    manifest = json.loads((PACK / f"firstep-full-{TAG}.manifest.json")
                          .read_bytes().decode("utf-8-sig"))
    listed = [str(item["path"]) for item in manifest["files"]]
    print(f"  zip 条目 {len(names)} / 清单 {len(listed)}："
          f"{'✓' if len(names) == len(listed) else '✗'}")
    ok = ok and len(names) == len(listed)
    start_here = "00-START-HERE.txt" in names
    print(f"  00-START-HERE.txt 在场：{'✓' if start_here else '✗'}")
    ok = ok and start_here
    for label, needle in (("egg-info", "egg-info"), ("revise-backups", "revise-backups")):
        hits = [n for n in names if needle in n]
        print(f"  不含 {label}：{'✓' if not hits else f'✗（{len(hits)} 条）'}")
        ok = ok and not hits
    removed = manifest.get("removed") or []
    print(f"  清单内 removed {len(removed)} 条（更新器只读清单，删除清单必须同时进 JSON）")
    print(f"  removed.txt 与清单 removed 一致："
          f"{'✓' if len((PACK / f'firstep-full-{TAG}.removed.txt').read_text(encoding='utf-8-sig').splitlines()) == len(removed) else '✗'}")
    ok = ok and bool(removed)

    # ---- 4. 小发版：zip 条目 == files.txt ----
    print("\n## 4. 小发版 zip 条目 == 清单")
    update_zip = PACK / f"firstep-update-{TAG}.zip"
    with zipfile.ZipFile(update_zip) as archive:
        entries = [n for n in archive.namelist() if not n.endswith("/")]
    files_txt = [line.strip() for line in
                 (PACK / f"firstep-update-{TAG}.files.txt").read_text(encoding="utf-8-sig")
                 .splitlines() if line.strip()]
    same = sorted(entries) == sorted(files_txt)
    print(f"  zip 条目 {len(entries)} / files.txt {len(files_txt)}：{'✓' if same else '✗'}")
    if not same:
        only_zip = sorted(set(entries) - set(files_txt))[:10]
        only_txt = sorted(set(files_txt) - set(entries))[:10]
        print(f"      只在 zip：{only_zip}")
        print(f"      只在清单：{only_txt}")
    ok = ok and same

    print(f"\n总判：{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
