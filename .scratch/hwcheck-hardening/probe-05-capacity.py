# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/05 的前置测量（**只读、纯内存**）：

「把库里该平台的专精件全勾上」现在能不能建出命令表？给每条 `console.candidates` **纯追加**
池位 `4 5 6 7 8 9`（既不是保留字、也不是任何一件首选）之后呢？

做法：直接读真库配方文件 → 用 `parse_recipes` 解析成 `RecipeSection` → 每个平台取"有 console 段的
全部小节"喂给 `build_console_table`。**不碰盘上任何文件**；读数落 `probe-05-capacity.txt`。
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.hwcheck import HwCheckError  # noqa: E402
from contest_generator.hwcheck_console import COMMAND_POOL, build_console_table  # noqa: E402
from contest_generator.hwcheck_recipe import parse_recipes  # noqa: E402

RECIPE = ROOT / "library" / "hwcheck_recipes.json"
OUT = pathlib.Path(__file__).with_name("probe-05-capacity.txt")
FALLBACK_ADD = ["4", "5", "6", "7", "8", "9"]


def with_fallback(raw: dict) -> dict:
    """纯追加：已有候选一个不删、顺序不动，只在末尾补上没人声明过的池位。"""
    data = copy.deepcopy(raw)
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        for cell in entry.values():
            if not isinstance(cell, dict):
                continue
            console = cell.get("console")
            if isinstance(console, dict) and console.get("command"):
                cands = list(console.get("candidates") or [])
                for char in FALLBACK_ADD:
                    if char not in cands:
                        cands.append(char)
                console["candidates"] = cands
    return data


def full_selection(sections: dict, platform: str) -> list:
    return [
        section
        for catalog in sections.values()
        for plat, section in catalog.items()
        if plat == platform and section.console is not None
    ]


def attempt(sections: dict, platform: str) -> str:
    selected = full_selection(sections, platform)
    try:
        table = build_console_table(selected)
    except HwCheckError as exc:
        return f"[红] {platform}：把 {len(selected)} 件全勾上 → 400：{exc}"
    return f"[绿] {platform}：把 {len(selected)} 件全勾上也能建出表（{len(table.entries)} 条命令）"


def main() -> int:
    raw = json.loads(RECIPE.read_text(encoding="utf-8"))
    lines = [
        "=== 工单 hwcheck-hardening/05：命令字符容量前置测量（只读、纯内存）===",
        f"COMMAND_POOL = {len(COMMAND_POOL)} 个：{''.join(COMMAND_POOL)}",
        "",
    ]
    for label, data in (("现状", raw), ("纯追加池位 4~9 之后", with_fallback(raw))):
        sections = parse_recipes(data, source="probe-05（内存副本，非盘上文件）")
        lines.append(f"—— {label} ——")
        for platform in ("stm32", "mspm0"):
            lines.append("    " + attempt(sections, platform))
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
