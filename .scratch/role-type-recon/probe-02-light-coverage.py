# -*- coding: utf-8 -*-
"""recon 2：令牌的**亮色覆盖完整性**盘上实况（为「要不要立腿」提供读数）。

口径：:root（合并全部块）= 暗色基线；html[data-theme="light"] = 亮色覆盖。
一个令牌三种状态：两主题都有定义（成套）/ 只在 :root（靠继承）/ 只在亮色块（畸形）。
按前缀分组统计，列全部「部分覆盖」的族 —— 那就是"亮色覆盖完整性"这条腿**今天会判红的面**。
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTML = REPO / "src" / "contest_generator" / "static" / "index.html"

TOKEN_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")


def blocks(text: str):
    dark, light = {}, {}
    for m in re.finditer(r"\n {2}:root \{([\s\S]*?)\n {2}\}", text):
        for t in TOKEN_RE.finditer(m.group(1)):
            dark[t.group(1)] = t.group(2).strip()
    for m in re.finditer(r"\n {2}html\[data-theme=\"light\"\] \{([\s\S]*?)\n {2}\}", text):
        for t in TOKEN_RE.finditer(m.group(1)):
            light[t.group(1)] = t.group(2).strip()
    return dark, light


def family(name: str) -> str:
    """族 = 前缀（去掉最后一个 - 段）——`--pin-gpio-dim` → `--pin-*`，`--tok-com` → `--tok-*`。"""
    body = name[2:]
    parts = body.split("-")
    if len(parts) <= 1:
        return "--" + parts[0]
    # 数字结尾（--bracket-rainbow-0）归到前缀
    return "--" + parts[0] + "-*"


def main() -> int:
    text = HTML.read_text(encoding="utf-8")
    dark, light = blocks(text)
    out = []
    out.append("=" * 96)
    out.append("§1 令牌覆盖总览")
    out.append("=" * 96)
    out.append(f"  :root（暗色基线）令牌数：{len(dark)}")
    out.append(f"  亮色块里另有定义的令牌数：{len(light)}")
    only_light = sorted(set(light) - set(dark))
    out.append(f"  只在亮色块定义（畸形）：{len(only_light)} {only_light}")
    out.append("")

    fam = defaultdict(lambda: {"both": [], "dark_only": []})
    for name in sorted(dark):
        key = family(name)
        if name in light:
            fam[key]["both"].append(name)
        else:
            fam[key]["dark_only"].append(name)

    out.append("=" * 96)
    out.append("§2 按族看「亮色覆盖完整性」（both = 两主题都写值；dark_only = 靠继承）")
    out.append("=" * 96)
    full = [k for k, v in fam.items() if not v["dark_only"]]
    partial = [k for k, v in fam.items() if v["dark_only"] and v["both"]]
    none_ = [k for k, v in fam.items() if not v["both"]]
    out.append(f"  成套覆盖的族（{len(full)}）：{'、'.join(sorted(full))}")
    out.append("")
    out.append(f"  **部分覆盖**的族（{len(partial)}）—— 立「成套」腿后这些就是判红面：")
    for k in sorted(partial):
        v = fam[k]
        out.append(f"    {k:<22} 亮色有 {len(v['both']):>2} / 靠继承 {len(v['dark_only']):>2}"
                   f"   继承的：{'、'.join(v['dark_only'][:8])}{' …' if len(v['dark_only']) > 8 else ''}")
    out.append("")
    out.append(f"  完全不覆盖的族（{len(none_)}）：{'、'.join(sorted(none_))}")
    out.append("")
    out.append("=" * 96)
    out.append("§3 `--pin-*` 族逐条（本轮动的那个族）")
    out.append("=" * 96)
    for name in sorted(n for n in dark if n.startswith("--pin-")):
        state = "亮色覆盖" if name in light else "靠继承（暗色值）"
        out.append(f"  {name:<20} dark={dark[name]:<34} {state}"
                   + (f" light={light[name]}" if name in light else ""))

    body = "\n".join(out)
    print(body.encode("utf-8", "replace").decode("utf-8", "replace"))
    dest = Path(__file__).with_suffix(".txt")
    dest.write_text(body + "\n", encoding="utf-8")
    print(f"\n[落盘] {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
