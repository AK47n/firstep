# -*- coding: utf-8 -*-
"""地阔星 wiki 页面元数据提取：cat / slug / title / code_blocks / f4_suspect"""
import os, re, json, glob

PAGES_DIR = "sources/materials/lckfb-地阔星移植手册"
OUT = ".scratch/materials-wiki/dkx-pages.json"

pages = []
for f in sorted(glob.glob(os.path.join(PAGES_DIR, "*.md"))):
    base = os.path.basename(f)
    if base in ("模块索引.md", "网盘索引.md"):
        continue
    m = re.match(r"^(control|rf|screen|sensor)--(.+)\.md$", base)
    if not m:
        print("SKIP(no cat--slug):", base)
        continue
    cat, slug = m.group(1), m.group(2)
    raw = open(f, encoding="utf-8", errors="replace").read()
    title = ""
    code_blocks = ""
    for line in raw.splitlines()[:12]:
        if line.startswith("- 标题："):
            title = line[len("- 标题："):].strip()
        elif line.startswith("- 代码块："):
            code_blocks = line[len("- 代码块："):].strip()
    cb_m = re.search(r"(\d+)\s*个", code_blocks)
    cb = int(cb_m.group(1)) if cb_m else 0
    f4 = "Y" if ("RCC_AHB1PeriphClockCmd" in raw or "GPIO_OType" in raw) else "N"
    pages.append({"file": base, "cat": cat, "slug": slug, "title": title,
                  "code_blocks": cb, "f4": f4})

json.dump(pages, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("pages:", len(pages))
for p in pages:
    print(f"{p['file']}\t{p['cat']}\t{p['slug']}\t{p['title']}\t{p['code_blocks']}\t{p['f4']}")
