# -*- coding: utf-8 -*-
"""抽查：跨分类产物 + 索引一致性 + 素材清单计数。"""
import re
from pathlib import Path

from contest_generator.md_library import list_markdowns

base = Path("sources/materials/lckfb-地猛星移植手册")

print("== 清单计数 ==")
mds = list_markdowns(Path("sources/materials"))
batch_md = [m for m in mds if m["batch"] == "lckfb-地猛星移植手册"]
print("  批次内 md 文件数:", len(batch_md), "（应为 72 = 70 页 + 2 索引）")

print("== 索引一致性 ==")
idx = (base / "模块索引.md").read_text(encoding="utf-8")
pages = [l for l in idx.splitlines() if l.startswith("- ") and "：[原页]" in l]
print("  索引行数:", len(pages))

print("== 跨分类抽查 ==")
names = set()
for c in ("sensor--", "screen--", "rf--", "control--"):
    hits = sorted(m["name"] for m in batch_md if m["name"].startswith(c))
    if hits:
        names.add(hits[0])
for name in sorted(names):
    s = (base / name).read_text(encoding="utf-8")
    fences = re.findall(r"^```c\n([\s\S]*?)\n^```", s, re.M)
    headings = [l for l in s.splitlines() if re.match(r"^#{2,3} ", l)][:5]
    print(f"- {name}：围栏 {len(fences)} 个（行数 {[len(f.splitlines()) for f in fences]}）")
    print(f"   章节: {headings}")
