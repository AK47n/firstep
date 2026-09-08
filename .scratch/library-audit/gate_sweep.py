"""逐模块跑生成门禁（单模块隔离形态）：93 模块 × 两平台，全部走
build_module_corpus + run_generation_gates，零 LLM、零写盘。

目的：把「模块条目 → 生成语料 → 门禁」这条接缝在**每个模块**上都验一遍，
而不是只验测试里出现过的组合。
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.generator import (  # noqa: E402
    build_module_corpus,
    run_generation_gates,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402

MODULES_DIR = ROOT / "library" / "modules"
MASTERS_DIR = ROOT / "library" / "masters"


def main() -> None:
    manifests = list_modules(MODULES_DIR)
    failures: list[str] = []
    skipped = 0
    for platform in KNOWN_PLATFORMS:
        master_dir = MASTERS_DIR / platform
        main_c = ""  # 隔离模块级门禁：母版 main.c 的调用不在本扫描范围
        for manifest in manifests:
            if platform not in manifest.platforms:
                skipped += 1
                continue
            try:
                corpus = build_module_corpus(
                    [manifest], platform, MODULES_DIR, master_dir, main_c
                )
                run_generation_gates(corpus, [manifest], platform)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"{platform}/{manifest.slug}: {type(exc).__name__}: {exc}"
                )
    print(f"跑通 {len(manifests) * len(KNOWN_PLATFORMS) - skipped} 个（模块×平台）组合，"
          f"跳过无该平台版本 {skipped} 个")
    print(f"门禁失败 {len(failures)} 个：")
    for item in failures:
        print("  ✗", item)


if __name__ == "__main__":
    main()
