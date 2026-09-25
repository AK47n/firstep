# -*- coding: utf-8 -*-
"""专精面扩张的前置测量：**配方命令字符撞车会怎样**（决定要不要先做让位机制）。

背景：`build_console_table` 的判据之二是「两件不得占用同一个字符」——配方命令是
**写死的**（不像自建件那样从池子里分配）。专精件从 10 件扩到 30 件以后，"学生同时
勾两件传感器"这种常规操作就可能因为两个配方都挑了 `t` 而**生成前 400**。

本探针量三件事（只读，不改库）：
  1. 现状：现有 10 件 / 17 格的命令字符有没有撞（应当没有）；
  2. 反证：把两件配方的字符改成同一个，`build_console_table` 是不是真红（判据真实存在）；
  3. 容量：可用字符池还剩多少个（保留字 r/y/g/o/b/? 之后，字母数字里还能放几件）。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.hwcheck_console import (  # noqa: E402
    CUSTOM_COMMAND_FALLBACK, RESERVED_COMMANDS, build_console_table,
)
from contest_generator.hwcheck_errors import HwCheckError  # noqa: E402
from contest_generator.hwcheck_recipe import load_library_recipes, resolve_sections  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
LINES: list[str] = ["=== 专精面扩张前置测量：配方命令字符空间 ===", ""]

manifests = list_modules(MODULES)
catalog = load_library_recipes(MODULES, MASTERS, manifests)
lines_used: list[tuple[str, str]] = []
for slug, one_catalog in sorted(catalog.items()):
    for platform, section in sorted(one_catalog.sections.items()):
        if section.usable and section.console is not None:
            lines_used.append((slug, section.console.command))
LINES.append(f"1) 现状：{len(lines_used)} 格声明了命令字符 → "
             + "、".join(f"{slug}={cmd}" for slug, cmd in lines_used))
seen: dict[str, str] = {}
collide = [f"{slug}={cmd}" for slug, cmd in lines_used
           if (cmd in seen and seen[cmd] != slug) or seen.setdefault(cmd, slug) == slug and False]
dup = [f"{cmd}:{slug}" for slug, cmd in lines_used if list(c for s, c in lines_used).count(cmd) > 1]
LINES.append(f"   撞车：{dup or '无'}")
LINES.append("")

# 2) 反证：真撞一次，判据必须红
sections = resolve_sections(PLATFORM_MSPM0, ["ml_mpu6050", "jy61p"], catalog, manifests)
LINES.append("2) 反证：取 ml_mpu6050（命令 m）+ jy61p（命令 j）两节，把后者改成 m")
patched = []
for section in sections:
    if section.slug == "jy61p" and section.console is not None:
        from dataclasses import replace
        section = replace(section, console=replace(section.console, command="m"))
    patched.append(section)
try:
    build_console_table(patched)
    LINES.append("   ✗ 没红——判据不存在（与文档不符）")
except HwCheckError as exc:
    LINES.append("   ✓ 构建期红：" + str(exc).splitlines()[0][:150])
LINES.append("")

# 3) 容量
pool = [c for c in CUSTOM_COMMAND_FALLBACK if c not in RESERVED_COMMANDS]
LINES.append(f"3) 容量：可用字符池 {len(pool)} 个（{''.join(pool)}）；"
             f"保留字 {''.join(sorted(RESERVED_COMMANDS))}")
LINES.append(f"   现状已占用 {len({cmd for _, cmd in lines_used})} 个；"
             f"若扩到 30 件专精件、每件 1 个字符 → 剩 {len(pool) - 30} 个（够，但撞车概率极高）")

text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-console-space.txt").write_text(
    text, encoding="utf-8"
)
print(text)
