# -*- coding: utf-8 -*-
"""工单 01 的反证读数：**配方命令字符让位**（首选被占 → 候选）真的发生了吗。

三问（只读，不改库；`library/hwcheck_recipes.json` 一个字节不写）：

1. **现状**：真库全部专精件在**每个平台**各分到什么字符（对照配方里声明的首选）——
   顺带回答"这一趟把库内所有专精件都勾上，字符池够不够"（扩张批次最关心的容量）。
2. **反证 A（撤掉让位）**：拿真库里两节配方，把第二件的字符改成与第一件相同、
   且**都不声明候选** → `build_console_table` 必须构建期红（老判据还在，不是被新机制
   悄悄放过去了）。
3. **反证 B（带上让位）**：同一次改动再给第二件加候选 → 让位成功，且**页面载荷**
   （`console_payload`）与**板上分派**（`render_console_runtime` 的 `case`）读到的是
   **同一个、分配后**的字符。

用法：`py -3 .scratch/hwcheck-specialize/probe-console-fallback.py`
读数先落盘 `probe-console-fallback.txt` 再打印。
"""
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.hwcheck_console import (  # noqa: E402
    COMMAND_POOL, RESERVED_COMMANDS, _normalize, build_console_table,
    console_payload, render_console_runtime,
)
from contest_generator.hwcheck_errors import HwCheckError  # noqa: E402
from contest_generator.hwcheck_recipe import (  # noqa: E402
    load_library_recipes, resolve_sections,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
LINES: list[str] = ["=== 工单 01 反证：配方命令字符让位（首选 → 候选） ===", ""]

manifests = list_modules(MODULES)
catalog = load_library_recipes(MODULES, MASTERS, manifests)

# ---------------------------------------------------------------- 1) 现状 + 容量
for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
    slugs = [
        slug for slug, one in sorted(catalog.items())
        if one.for_platform(platform) is not None and one.for_platform(platform).usable
    ]
    if not slugs:
        continue
    sections = resolve_sections(platform, slugs, catalog, manifests)
    table = build_console_table(sections)
    used = {entry.slug: entry.command for entry in table.entries}
    LINES.append(f"1) {platform}：库内专精件 {len(slugs)} 件，全部勾上 → 命令表 {len(used)} 条")
    for section in sections:
        declared = section.console
        if declared is None:
            LINES.append(f"   {section.slug:14s} 没有 console 段（不进表）")
            continue
        got = used.get(section.slug, "—")
        moved = "  ← 让位" if got != _normalize(declared.command) else ""
        LINES.append(
            f"   {section.slug:14s} 首选 {declared.command!r} / 候选 "
            f"{list(declared.candidates)!r} → 分配 {got!r}{moved}"
        )
    free = [c for c in COMMAND_POOL if c not in used.values()]
    LINES.append(f"   池子 {len(COMMAND_POOL)} 个、已占 {len(used)} 个、空闲 {len(free)} 个："
                 f"{''.join(free) or '（无）'}")
    LINES.append("")

# ------------------------------------------------- 2/3) 反证：真库两节，硬改成撞车
pair = resolve_sections(PLATFORM_STM32, ["led", "oled"], catalog, manifests)
assert len(pair) == 2 and all(s.console is not None for s in pair), "真库 led/oled 应当都有配方"
first, second = pair
clash = first.console.command            # 第二件硬改成与第一件同字符
LINES.append(f"2/3) 取真库两节：{first.slug}（{clash!r}）与 {second.slug}"
             f"（{second.console.command!r}）——把后者也改成 {clash!r} 再跑：")

no_fallback = (first, replace(second, console=replace(
    second.console, command=clash, candidates=())))
LINES.append("   A) 不声明候选（撤掉让位的形态）→")
try:
    build_console_table(no_fallback)
    LINES.append("      ✗ 没红——老判据丢了（与文档不符）")
except HwCheckError as exc:
    LINES.append("      ✓ 构建期红：" + str(exc).splitlines()[0][:230])

with_fallback = (first, replace(second, console=replace(
    second.console, command=clash, candidates=("w", "z"))))
LINES.append("   B) 声明候选 ['w', 'z']（让位一档）→")
try:
    table = build_console_table(with_fallback)
    page = console_payload(True, table)
    shown = {item["slug"]: item["command"] for item in page["commands"]}
    code = "\n".join(render_console_runtime(table))
    cases = [line.strip() for line in code.splitlines()
             if line.strip().startswith("case '")]
    LINES.append("      ✓ 让位成功 —— " + "、".join(
        f"{entry.slug}={entry.command!r}" for entry in table.entries))
    LINES.append("      页面载荷 commands：" + "、".join(
        f"{item['slug']}={item['command']!r}" for item in page["commands"]))
    LINES.append("      板上分派 case：" + " ".join(cases[:8])
                 + (" …" if len(cases) > 8 else ""))
    for entry in table.entries:
        same = "页面与板上同一个字符" if shown.get(entry.slug) == entry.command else "✗ 页面 ≠ 板上"
        how = "首选" if entry.command == clash else "让位后"
        LINES.append(f"      {entry.slug} → {entry.command!r}（{how}）；{same}")
except HwCheckError as exc:  # pragma: no cover - 让位机制坏了才会走到
    LINES.append("      ✗ 让位没成功：" + str(exc).splitlines()[0][:200])

LINES.append("")
LINES.append(f"（保留字 {''.join(sorted(RESERVED_COMMANDS))} 一个不碰；"
             f"池子 = 字母数字去掉保留字 = {len(COMMAND_POOL)} 个）")

text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-console-fallback.txt").write_text(
    text, encoding="utf-8")
print(text)
