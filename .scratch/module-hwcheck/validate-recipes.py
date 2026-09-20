# -*- coding: utf-8 -*-
"""配方校验器（工单 module-hwcheck/09 的**量具**）：配方文件 ↔ 真库一致性。

口径与 `webapp._hwcheck_recipes` 逐条相同（同一套 `interface_names` /
`platform_header_names` / `load_recipes` / `build_console_table`），差别只是
**不必起服务器**：直接在进程里跑一遍，给几件器件渲染一次，把结果打成一张表。

三件事：

1. **配方能解析**（形状 / 段名 / 引用校验）——坏配方当场抛 `HwCheckError`；
2. **逐格渲染**：对 `--cell slug:platform` 每一格单独渲染一次检测程序，
   要求该器件真的出了小节（专精），且 `main.c` 里有它的小节函数；
3. **命令字符空间**：把点名的器件**一起**放进一次渲染（同屏选择的最坏情况），
   `build_console_table` 会把抢字符 / 抢保留字当场判红。

用法：

    python .scratch/module-hwcheck/validate-recipes.py                     # 真库配方全量检查
    python .scratch/module-hwcheck/validate-recipes.py --recipe draft.json \\
        --cell key:mspm0 --cell key:stm32                                  # 校验候选配方
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.hwcheck import HwCheckConfig, hwcheck_modules, render_main_c  # noqa: E402
from contest_generator.hwcheck_board import hwcheck_board_view  # noqa: E402
from contest_generator.hwcheck_console import build_console_table  # noqa: E402
from contest_generator.hwcheck_recipe import (  # noqa: E402
    interface_names,
    load_recipes,
    platform_header_names,
    resolve_sections,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.master_store import master_project_dir  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402
from contest_generator.selection import resolve_dependencies  # noqa: E402
from contest_generator.treewalk import iter_project_files  # noqa: E402

# v1 专精清单**单源**：直接取地板断言那份 `PILOT`（tests/test_hwcheck_recipe.py）。
# 这份清单曾在三个地方各手抄一遍（测试 / 本脚本 / 编译矩阵探针），第三份当场
# 漂移（矩阵自称 17 格却漏了 adc×mspm0）——本单评审抓到，改为一处。
sys.path.insert(0, str(REPO))
from tests.test_hwcheck_recipe import PILOT  # noqa: E402

PILOT_CELLS: tuple[tuple[str, str], ...] = tuple(PILOT)


def _interfaces(library: Path, masters: Path, manifests) -> tuple[dict, dict]:
    interfaces: dict[str, dict[str, frozenset[str]]] = {}
    headers: dict[str, frozenset[str]] = {}
    for name in sorted(KNOWN_PLATFORMS):
        master_dir = master_project_dir(masters, name)
        if not master_dir.is_dir() or next(iter(master_dir.iterdir()), None) is None:
            continue
        master_headers = [
            (path.relative_to(master_dir).as_posix(),
             path.read_text(encoding="utf-8", errors="replace"))
            for path in iter_project_files(master_dir, pattern="*.h")
        ]
        interfaces[name] = interface_names(manifests, library, name, master_headers)
        headers[name] = platform_header_names(manifests, name, master_headers)
    return interfaces, headers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default=str(REPO / "library" / "modules"))
    parser.add_argument("--masters", default=str(REPO / "library" / "masters"))
    parser.add_argument("--recipe", default="", help="候选配方文件（缺省 = 库内那份）")
    parser.add_argument("--cell", action="append", default=[],
                        help="slug:platform（缺省 = PILOT_CELLS 全量）")
    args = parser.parse_args()

    library = Path(args.library)
    masters = Path(args.masters)
    recipe_path = Path(args.recipe) if args.recipe else None
    manifests = list(list_modules(library))
    by_slug = {m.slug: m for m in manifests}
    interfaces, headers = _interfaces(library, masters, manifests)
    print(f"平台接口清单：{ {k: len(v) for k, v in interfaces.items()} }")
    recipes = load_recipes(
        library, manifests, interfaces, recipe_path=recipe_path, headers=headers
    )
    print(f"配方件数：{len(recipes)}（{', '.join(sorted(recipes))}）")

    cells = (
        [tuple(c.split(":", 1)) for c in args.cell] if args.cell else list(PILOT_CELLS)
    )
    failures: list[str] = []
    for slug, platform in cells:
        catalog = recipes.get(slug)
        section = catalog.for_platform(platform) if catalog else None
        if section is None:
            failures.append(f"{slug}:{platform} 没有配方")
            continue
        if not section.usable:
            failures.append(f"{slug}:{platform} 是空壳（没有 prereq/init/probe/read）")
            continue
        manifests_for = resolve_dependencies([slug], by_slug)
        sections = resolve_sections(platform, [slug], recipes, manifests_for)
        if not any(s.slug == slug for s in sections):
            failures.append(f"{slug}:{platform} resolve_sections 没给出这一件")
            continue
        config = HwCheckConfig(
            platform=platform, debug_uart=True, oled=False, devices=(slug,)
        )
        board = hwcheck_board_view(platform, manifests_for, _board(platform))
        code = render_main_c(config, sections)
        if f"hwcheck_check_{slug}(" not in code:
            failures.append(f"{slug}:{platform} 渲染出的 main.c 里没有这一件的小节")
            continue
        console = build_console_table(sections)
        print(
            f"OK  {slug}:{platform}  命令={console.entries[0].command if console.entries else '-'}"
            f"  探头={'有' if section.probe else '无'}  读数={len(section.read)}"
        )

    # 命令字符空间：点名的器件一起选（同屏最坏情况）——抢字符当场红
    picked = sorted({slug for slug, _ in cells})
    if picked:
        manifests_all = resolve_dependencies(picked, by_slug)
        all_sections = resolve_sections(cells[0][1], picked, recipes, manifests_all)
        table = build_console_table(all_sections)
        print(f"命令表（{cells[0][1]} 上同时选 {len(picked)} 件）："
              + " ".join(f"{e.command}={e.slug}" for e in table.entries))

    if failures:
        print("\n判红：")
        for line in failures:
            print("  -", line)
        return 1
    print(f"\n全部 {len(cells)} 格通过")
    return 0


def _board(platform: str):
    from contest_generator.boards import board_for_platform

    return board_for_platform(platform)


if __name__ == "__main__":
    raise SystemExit(main())
