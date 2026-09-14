# -*- coding: utf-8 -*-
"""重算资料库基线清单（`.materials-manifest.json`），版本号显式标注非发布态。

为什么需要它：`.scratch/materials-baseline-writeback/init-baseline.py` 的判据是
「本地扫描 == 线上 v1.2.0 完整包清单里那份」——用途是**证明本机与线上包一致**。
路径减肥之后这条**必然不等**（改名本来就要让路径变），那个脚本会正确地报一堆差异，
但它不是用来「就地重算」的。

本脚本做的是另一件事：把**当前本地资料库**扫成基线并落盘，version 写成
`<发布版本>+<变化标记>`——读数的人一眼能看出「这份基线与线上包不同源，别拿它比对
线上包」，同时「资料库检查」拿到基线后不再报 `baseline-missing`。

用法：
    python .scratch/path-budget/rebuild-materials-baseline.py                   # dry-run
    python .scratch/path-budget/rebuild-materials-baseline.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.full_pack import materials_excluded  # noqa: E402
from contest_generator.materials_pack import (  # noqa: E402
    MANIFEST_FILENAME,
    scan_as_manifest,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="重算资料库基线清单")
    ap.add_argument("--write", action="store_true", help="落盘（缺省 dry-run）")
    ap.add_argument("--version", default="v1.2.0+pathbudget",
                    help="写入清单的 version（非发布态必须带 + 标记）")
    args = ap.parse_args()

    root = ROOT / "sources" / "materials"
    if not root.is_dir():
        print(f"资料库目录不在：{root}")
        return 2

    # 与完整包打包同一份排除规则（materials_excluded）：否则会把「故意不进包」的
    # 第三方安装包当成资料库内容写进基线。
    manifest = scan_as_manifest(root, args.version, exclude=materials_excluded)
    files = sum(len(b["files"]) for b in manifest["batches"])
    longest = max(
        (len(f["path"]) for b in manifest["batches"] for f in b["files"]), default=0
    )
    print(f"版本：{manifest['version']}")
    print(f"批次：{len(manifest['batches'])} / 文件：{files}")
    print(f"最长包内路径（基线口径）：{longest} 字符")
    print(f"目标文件：{root / MANIFEST_FILENAME}")

    if not args.write:
        print("\n[dry-run] 未写盘；确认无误后加 --write。")
        return 0

    (root / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("已写入。")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
