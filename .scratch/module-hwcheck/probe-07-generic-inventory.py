# -*- coding: utf-8 -*-
"""量具（工单 module-hwcheck/07 开工前）：通用降级能拿到哪些**库内已声明的事实**。

回答三个问题，全部只读、不改库：

1. 未专精的「模块 × 平台」格有多少？哪些声明了 I2C 类引脚角色（i2c_scl / i2c_sda）？
2. 每一格的**初始化调用**能不能机械地从该模块**自己的头文件**里认出来
   （约定 `<slug>_init` 是否唯一命中 / 有没有别的候选）？
3. 「I2C 类」两种判据的差集：按 manifest pins 判 vs 按板能力 token 判。
"""

from __future__ import annotations

import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = Path(__file__).resolve().parent / "probe-07-generic-inventory.txt"

from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.hwcheck_recipe import (  # noqa: E402
    load_recipes,
    recipe_library_path,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402
from contest_generator.skeleton import (  # noqa: E402
    extract_header_functions,
    format_interface_blocks,
)

LIBRARY = ROOT / "library" / "modules"
I2C_ROLES = ("i2c_scl", "i2c_sda")
_CALLISH = re.compile(r"^[A-Za-z_]\w*$")


def own_header_names(manifest, platform: str) -> tuple[str, ...]:
    """该模块**自己**头文件里的名字（不含母版头：母版头是全库共享的噪声）。"""
    entry = manifest.platforms.get(platform)
    if entry is None:
        return ()
    blocks = []
    for rel in entry.files:
        if not rel.lower().endswith(".h"):
            continue
        path = LIBRARY / manifest.slug / rel
        if path.is_file():
            blocks.append((manifest.slug, rel,
                           path.read_text(encoding="utf-8", errors="replace")))
    return tuple(sorted(extract_header_functions(format_interface_blocks(blocks))))


def main() -> None:
    manifests = list_modules(LIBRARY)
    recipes = load_recipes(LIBRARY, manifests)  # 只判形状：本探针不查引用
    print(f"配方文件：{recipe_library_path(LIBRARY)}  存在={recipe_library_path(LIBRARY).is_file()}")
    print(f"库内模块数：{len(manifests)}；有配方的 slug：{sorted(recipes)}\n")

    specialized = {
        (slug, platform)
        for slug, catalog in recipes.items()
        for platform in catalog.sections
    }

    rows = []
    for manifest in sorted(manifests, key=lambda m: m.slug):
        for platform in sorted(KNOWN_PLATFORMS):
            entry = manifest.platforms.get(platform)
            if entry is None:
                continue
            if (manifest.slug, platform) in specialized:
                continue
            roles = tuple(pin.type for pin in entry.pins)
            i2c_by_pins = any(role in I2C_ROLES for role in roles)
            board = board_for_platform(platform)
            caps = []
            for pin in entry.pins:
                hit = board.pin(pin.default) if hasattr(board, "pin") else None
                caps.append((pin.default, tuple(hit.capabilities) if hit else ()))
            names = own_header_names(manifest, platform)
            init_like = [
                name for name in names
                if _CALLISH.match(name) and name.lower().endswith("_init")
            ]
            exact = [name for name in init_like if name.lower() == f"{manifest.slug}_init"]
            rows.append({
                "slug": manifest.slug, "platform": platform,
                "files": len(entry.files), "roles": roles,
                "i2c_by_pins": i2c_by_pins, "caps": caps,
                "names": len(names), "init_like": init_like, "exact": exact,
            })

    print(f"未专精的「模块 × 平台」格：{len(rows)}\n")
    i2c_rows = [r for r in rows if r["i2c_by_pins"]]
    print(f"其中声明了 I2C 类引脚角色的：{len(i2c_rows)} 格")
    for r in i2c_rows:
        print(f"  {r['slug']:<16} {r['platform']:<6} roles={r['roles']}  "
              f"exact_init={r['exact']}")
    print()

    no_init = [r for r in rows if not r["exact"]]
    print(f"**没有**唯一 `<slug>_init` 命中的格：{len(no_init)}")
    for r in no_init:
        print(f"  {r['slug']:<16} {r['platform']:<6} files={r['files']} "
              f"init_like={r['init_like'][:6]} 头文件名字数={r['names']}")
    print()

    ambiguous = [r for r in rows if len(r["init_like"]) > 1 and r["exact"]]
    print(f"有 `<slug>_init` 但还有别的 *_init 候选的格：{len(ambiguous)}")
    for r in ambiguous:
        print(f"  {r['slug']:<16} {r['platform']:<6} init_like={r['init_like'][:8]}")
    print()

    empty = [r for r in rows if not r["names"]]
    print(f"模块自己的头文件里一个名字都没有的格：{len(empty)}")
    for r in empty:
        print(f"  {r['slug']:<16} {r['platform']:<6} files={r['files']}")


if __name__ == "__main__":
    # 证据一律写 UTF-8 文件（**不要**用 PowerShell 的 `*>` 重定向：那会按本机
    # ANSI/GBK 落盘，read 工具与评审都当二进制看，本单评审抓到过这一条）
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    OUT.write_text(text, encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    print(text)
