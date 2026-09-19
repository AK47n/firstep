# -*- coding: utf-8 -*-
"""量具（只读）：把「更新后盘上多出来的文件」按**参照系**拆开算。

为什么先量再动（工单 `update-orphan-files/01`）：工单给的根因是「删除清单只覆盖
上一版 → 落后两版留下孤儿」，而演练里的判据（`not_in_official == 0`）用的是
**完整包清单**当参照系。两个参照系下的「孤儿」根本不是同一批文件，先算清楚是谁。

三个参照系（都在同一份沙箱盘面上取差集）：

- A 完整包清单（`firstep-full-v1.2.1.manifest.json` 的 `files`）——工单/演练用的那个；
- B 小发版包自己的文件清单（`firstep-update-v1.2.1.files.txt`）——「这次更新写了什么」；
- C 沙箱 `git ls-files`（沙箱自带 `.git`）——「这棵树按 git 口径该有什么」。

用法::

    python .scratch/update-orphan-files/measure-sets.py
"""

from __future__ import annotations

import collections
import json
import subprocess
from pathlib import Path

HOME = Path.home()
SIM = HOME / "Desktop" / "firstep-sim"
PACK = HOME / "Desktop" / "firstep-pack"

TOP_LEVELS = (
    "src", "library", "sources", "tests", "docs", "assets", "tools", ".githooks",
    ".gitattributes", ".gitignore", "CLAUDE.md", "README.md", "CONTEXT.md",
    "CHANGELOG.md", "VERSIONS.md", "pyproject.toml", "install.bat", "start-app.bat",
    "start-app.vbs", "stop-firstep.bat", "stop-firstep.vbs",
)
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache",
             ".pytest_cache", ".scratch"}


def on_disk() -> set[str]:
    out: set[str] = set()
    for path in SIM.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(SIM).as_posix()
        parts = rel.split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue
        if parts[0] not in TOP_LEVELS:
            continue
        if rel.startswith("sources/materials/"):
            continue
        out.add(rel)
    return out


def by_top(paths) -> dict[str, int]:
    return dict(collections.Counter("/".join(p.split("/")[:2]) for p in paths).most_common(20))


def main() -> int:
    manifest = json.loads(
        (PACK / "firstep-full-v1.2.1.manifest.json").read_text(encoding="utf-8-sig"))
    full = {str(item["path"]) for item in manifest["files"]}
    small = {line.strip() for line in
             (PACK / "firstep-update-v1.2.1.files.txt").read_text(
                 encoding="utf-8").splitlines() if line.strip()}
    git_index = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"], cwd=str(SIM),
        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    git_files = {line for line in git_index.splitlines() if line}

    disk = on_disk()
    print(f"沙箱盘面（顶层白名单 / 排除 sources/materials）：{len(disk)}")
    print(f"A 完整包清单 files：{len(full)}")
    print(f"B 小发版 files.txt：{len(small)}")
    print(f"C 沙箱 git ls-files：{len(git_files)}")
    print()

    for name, ref in (("A 完整包清单", full), ("B 小发版清单", small), ("C git 索引", git_files)):
        extra = disk - ref
        miss = ref - disk
        print(f"[{name}] 盘上多出 {len(extra)} / 盘上缺 {len(miss)}")
        print(f"    多出按二级目录：{by_top(extra)}")
        for sample in sorted(extra)[:8]:
            print(f"      + {sample}")
        if miss:
            print(f"    缺的按二级目录：{by_top(miss)}")
        print()

    # A ∩ B 的差：完整包清单排除、小发版包却发的（两条打包口径不一致的直接证据）
    print("[口径差] 在小发版清单里但不在完整包清单里：", len(small - full))
    print("  按二级目录：", by_top(small - full))
    print("[口径差] 在完整包清单里但不在小发版清单里：", len(full - small))
    print("  按二级目录：", by_top(full - small))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
