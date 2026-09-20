# -*- coding: utf-8 -*-
"""量具（工单 module-hwcheck/07 开工前）第四跑：「I2C 类」那一批的**可扫面**。

对每个声明了 i2c_scl / i2c_sda 的「模块 × 平台」格，列出：
- 声明里的引脚（default）与 macros（stm32 写侧宏名，mspm0 为空）；
- 该模块**自己头文件**里的公开函数名（能不能找到"探一下地址"的原语）；
- 板定义里这些脚的板载注记。
结论用来定"扫描器扫哪条总线、拿什么驱动它"。
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = Path(__file__).resolve().parent / "probe-07-i2c-surface.txt"

from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402
from contest_generator.skeleton import (  # noqa: E402
    extract_header_functions,
    format_interface_blocks,
)

LIBRARY = ROOT / "library" / "modules"


def own_names(manifest, platform: str) -> list[str]:
    entry = manifest.platforms[platform]
    blocks = []
    for rel in entry.files:
        if rel.lower().endswith(".h"):
            path = LIBRARY / manifest.slug / rel
            if path.is_file():
                blocks.append((manifest.slug, rel,
                               path.read_text(encoding="utf-8", errors="replace")))
    return sorted(extract_header_functions(format_interface_blocks(blocks)))


def main() -> None:
    manifests = list_modules(LIBRARY)
    for manifest in sorted(manifests, key=lambda m: m.slug):
        for platform in sorted(KNOWN_PLATFORMS):
            entry = manifest.platforms.get(platform)
            if entry is None:
                continue
            roles = {pin.type for pin in entry.pins}
            if not ({"i2c_scl", "i2c_sda"} & roles):
                continue
            board = board_for_platform(platform)
            print(f"=== {manifest.slug} × {platform} ===")
            for pin in entry.pins:
                note = ""
                bp = board.pin(pin.default) if hasattr(board, "pin") else None
                if bp is not None:
                    note = getattr(bp, "notes", "") or ""
                print(f"  pin {pin.type:<9} {pin.default:<6} macros={list(pin.macros)}"
                      f"  note={note[:40]!r}")
            names = own_names(manifest, platform)
            print(f"  自己的头文件函数名（{len(names)}）：{names[:24]}")


if __name__ == "__main__":
    # UTF-8 落盘（别用 PowerShell 的 `*>`：会按本机 GBK 写，评审当二进制看）
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
