# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/05 的落地脚本：给每条配方的 `console.candidates` **纯追加**没人用过的池位。

为什么：命令空间 31 个字符里只有 25 个被声明过（`4 5 6 7 8 9` 无人用），于是"把专精件全勾上"
必然 400（stm32 第 23 件 / mspm0 第 26 件），而报错文案还印着"可用字符一共 31 个"。
纯追加 = 已有候选一个不删、顺序不动（沿用批次 E/F 的共享后备池先例），只是把池子补齐。

纪律：逐字节读写（LF 保持），不重新序列化整个 JSON；插完复核 JSON 合法 + 声明面并集 == 命令池。
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECIPE = ROOT / "library" / "hwcheck_recipes.json"
ADD = ("4", "5", "6", "7", "8", "9")
BLOCK = re.compile(r'("candidates": \[)(?P<body>[^\]]*?)(?P<closing>\n(?P<indent>[ \t]*)\])')


def main() -> int:
    original = RECIPE.read_bytes()
    text = original.decode("utf-8")

    def extend(match: re.Match[str]) -> str:
        body = match.group("body")
        indent = match.group("indent")
        lines = body.split("\n")
        # 最后一条元素（当前没有尾逗号）→ 补逗号，再追加新池位
        last = len(lines) - 1
        while last >= 0 and not lines[last].strip():
            last -= 1
        if last < 0:
            return match.group(0)
        elem_indent = lines[last][: len(lines[last]) - len(lines[last].lstrip())]
        existing = {
            json.loads(entry.strip().rstrip(","))
            for entry in lines
            if entry.strip()
        }
        fresh = [char for char in ADD if char not in existing]
        if not fresh:
            return match.group(0)
        lines[last] = lines[last].rstrip() + ","
        lines.extend(f'{elem_indent}"{char}",' for char in fresh)
        # 最后一行不留尾逗号（保持 JSON 数组的排版习惯）
        lines[-1] = lines[-1].rstrip(",")
        return match.group(1) + "\n".join(lines) + match.group("closing")

    text, count = BLOCK.subn(extend, text)
    RECIPE.write_bytes(text.encode("utf-8"))

    raw = RECIPE.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    declared: set[str] = set()
    pool = [c for c in "abcdefghijklmnopqrstuvwxyz0123456789" if c not in set("rygob")]
    cells = 0
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        for cell in entry.values():
            if not isinstance(cell, dict):
                continue
            console = cell.get("console")
            if isinstance(console, dict) and console.get("command"):
                cells += 1
                declared.add(str(console["command"]).lower())
                declared.update(str(c).lower() for c in (console.get("candidates") or []))
    missing = sorted(set(pool) - declared)
    print(f"改了 {count} 个 candidates 数组")
    print(f"复核：console 格 {cells}；声明面 {len(declared)} 个字符；池外声明 = {sorted(declared - set(pool))}")
    print(f"      池里仍没人声明的：{missing or '（无——文案里的 N 已是真实可分配数）'}")
    print(f"      JSON 合法；换行 = {'CRLF' if bytes([13, 10]) in raw else 'LF'}；字节 {len(original)} → {len(raw)}")
    return 0 if not missing and cells else 1


if __name__ == "__main__":
    raise SystemExit(main())
