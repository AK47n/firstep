# -*- coding: utf-8 -*-
"""立创 wiki 派生模块源码来源标注注入（工单 lckfb-attribution/01）。

遍历 library/modules/*/manifest.json，对平台条目 source_url 命中 wiki 判据
（manifest.is_wiki_source_url）的模块，在其 code/*.c / *.h 顶部注入标准来源
注释块（原页 URL + 页面标题 + 改写与版权要求说明）——立创版权要求第三条
（复制/传播/修改/公开展示/其他网站使用须标明来源与链接）的源码面履行。

- 幂等：文件已含该 source_url 则跳过（重跑零变化）；
- 标题 = 对应抓取 md 首行（sources/materials/lckfb-地猛星移植手册/<cat>--<slug>.md），
  md 缺失（轻量 clone 无资料库）降级为「地猛星 MSPM0G3507 模块移植手册」；
- 只注入 .c/.h；换行风格跟随原文件（\r\n 或 \n）；
- 不改动任何既有代码行/注释，仅文件顶部插入注释块。

运行：python .scratch/lckfb-attribution/inject_source_notes.py [--check]
--check 只报告将注入的文件清单不写盘。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contest_generator.manifest import (  # noqa: E402
    ModuleManifest,
    is_wiki_source_url,
)
from contest_generator.source_notes import inject_source_note  # noqa: E402

LIBRARY_MODULES = Path(__file__).resolve().parents[2] / "library" / "modules"
MATERIALS_MD_ROOT = (
    Path(__file__).resolve().parents[2]
    / "sources"
    / "materials"
    / "lckfb-地猛星移植手册"
)

FALLBACK_TITLE = "地猛星 MSPM0G3507 模块移植手册"


def wiki_title_of(cat: str, slug: str) -> str:
    """从抓取 md 首行取页面标题；md 缺失降级 FALLBACK_TITLE。"""
    md = MATERIALS_MD_ROOT / f"{cat}--{slug}.md"
    if not md.is_file():
        return FALLBACK_TITLE
    first = md.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    first_line = first.splitlines()[0] if first.splitlines() else ""
    if first_line.startswith("#"):
        title = first_line[1:].strip()
        if title:
            return title
    return FALLBACK_TITLE


def iter_plan() -> list[tuple[Path, str, str, str]]:
    """(文件路径, source_url, 标题, 原文本)——所有待注入文件（顺序确定）。"""
    plan: list[tuple[Path, str, str, str]] = []
    for manifest_path in sorted(LIBRARY_MODULES.glob("*/manifest.json")):
        manifest = ModuleManifest.load(manifest_path.parent)
        for platform, entry in manifest.platforms.items():
            if not is_wiki_source_url(entry.source_url):
                continue
            parts = entry.source_url.rstrip("/").split("/")
            cat, slug = parts[-2], parts[-1].replace(".html", "")
            title = wiki_title_of(cat, slug)
            for rel in entry.files:
                if not rel.endswith((".c", ".h")):
                    continue
                f = manifest_path.parent / rel
                if not f.is_file():
                    continue
                text = f.read_text(encoding="utf-8", errors="replace")
                plan.append((f, entry.source_url, title, text))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只报告不写盘")
    args = parser.parse_args()

    plan = iter_plan()
    changed = 0
    for f, url, title, text in plan:
        new = inject_source_note(text, url, title)
        if new == text:
            continue
        changed += 1
        print(f"[{'check' if args.check else 'inject'}] {f.relative_to(LIBRARY_MODULES)}")
        if not args.check:
            f.write_text(new, encoding="utf-8")
    print(f"待注入 {len(plan)} 文件 / 将变更 {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
