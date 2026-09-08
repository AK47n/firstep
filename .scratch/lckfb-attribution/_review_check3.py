from pathlib import Path
import json
import re

LIB = Path("library/modules")
MAT = Path("sources/materials/lckfb-地猛星移植手册")
bad = []
for p in sorted(LIB.glob("*/manifest.json")):
    m = json.loads(p.read_text(encoding="utf-8"))
    for platform, entry in m.get("platforms", {}).items():
        url = entry.get("source_url", "") or ""
        if not url.startswith("https://wiki.lckfb.com/"):
            continue
        parts = url.rstrip("/").split("/")
        cat, slug = parts[-2], parts[-1].replace(".html", "")
        md = MAT / f"{cat}--{slug}.md"
        # 找注入后的头注释（取该平台第一个 .c/.h）
        head = None
        for rel in entry.get("files", []):
            if rel.endswith((".c", ".h")):
                f = p.parent / rel
                if f.is_file():
                    head = f.read_text(encoding="utf-8", errors="replace")[:500]
                    break
        if not md.is_file():
            bad.append(f"{m['slug']}[{platform}]: md 缺失 -> 降级标题")
            continue
        first = md.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff").splitlines()
        title = first[0][1:].strip() if first and first[0].startswith("#") else ""
        if head and title and title not in head:
            bad.append(f"{m['slug']}[{platform}]: 头注释标题 {title!r} 不在注入块/diff")
print("titles not verified:", len(bad))
for b in bad:
    print(b)

# 源目录文件分类
files = sorted(MAT.glob("*.md"))
conform = [f for f in files if re.match(r"^[a-z0-9_]+--[a-z0-9-]+\.md$", f.name)]
upper = [f for f in files if "--" in f.name and f.name[0].isupper()]
other = [f for f in files if "--" not in f.name]
print("total md:", len(files), "| lowercase-conforming:", len(conform), "| uppercase:", len(upper), "| no--:", len(other))
for f in upper + other:
    print("  name:", repr(f.name))
