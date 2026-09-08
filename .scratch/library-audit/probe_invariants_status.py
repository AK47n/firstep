"""临时探针：候选「全库不变量」在当前库上的成立情况（工单 02 的先红后绿依据）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import ModuleManifest  # noqa: E402

MODULES = ROOT / "library" / "modules"
manifests = list_modules(MODULES)
by_slug = {m.slug: m for m in manifests}
print(f"模块 {len(manifests)} 个\n")


def report(name: str, problems: list[str]) -> None:
    flag = "OK  " if not problems else f"FAIL({len(problems)})"
    print(f"[{flag}] {name}")
    for p in problems[:5]:
        print(f"        - {p}")
    if len(problems) > 5:
        print(f"        … 另 {len(problems) - 5} 条")


# 1. slug 与目录名一致
report(
    "slug == 目录名",
    [
        f"{m.slug} != {m.slug!r} 目录"
        for m in manifests
        if not (MODULES / m.slug / "manifest.json").is_file()
    ],
)

# 2. 平台条目声明的文件真实存在（空 files = 内嵌母版，跳过）
missing_files = []
for m in manifests:
    for platform, entry in m.platforms.items():
        for rel in entry.files:
            if not (MODULES / m.slug / rel).is_file():
                missing_files.append(f"{m.slug}/{platform}: {rel}")
report("平台条目声明的文件存在", missing_files)

# 3. verified 条目必须有文件（内嵌母版形态：files 空但 verified）
verified_empty = [
    f"{m.slug}/{p}"
    for m in manifests
    for p, e in m.platforms.items()
    if e.verified and not e.files
]
report("verified 条目有文件", verified_empty)

# 4. 依赖都在库内
dangling = [
    f"{m.slug} → {dep}"
    for m in manifests
    for dep in m.dependencies
    if dep not in by_slug
]
report("依赖不悬空", dangling)

# 5. 依赖无环
cycles: list[str] = []
seen: set[str] = set()
stack: list[str] = []


def walk(slug: str) -> None:
    if slug in stack:
        cycles.append(" → ".join([*stack, slug]))
        return
    if slug in seen:
        return
    stack.append(slug)
    for dep in by_slug[slug].dependencies:
        if dep in by_slug:
            walk(dep)
    stack.pop()
    seen.add(slug)


for slug in sorted(by_slug):
    walk(slug)
report("依赖无环", cycles)

# 6. 词表 lib_modules 引用都在库内
wl = json.loads(
    (ROOT / "src" / "contest_generator" / "wordlist.json").read_text(encoding="utf-8")
)
bad_refs = [
    f"{g['category']}/{s['name']} → {slug}"
    for g in wl
    for s in g.get("solutions", [])
    for slug in s.get("lib_modules", [])
    if slug not in by_slug
]
report("词表 lib_modules 引用存在", bad_refs)

# 7. 平台声明文件不重复 / slug 唯一
dupes = []
for m in manifests:
    for platform, entry in m.platforms.items():
        if len(set(entry.files)) != len(entry.files):
            dupes.append(f"{m.slug}/{platform} 文件重复")
report("平台条目文件无重复", dupes)

# 8. 多实例模块必须有 max/variant
bad_multi = [
    m.slug
    for m in manifests
    if m.multi_instance is not None and not (m.multi_instance.max and m.multi_instance.variant)
]
report("多实例声明完整", bad_multi)

# 9. 模块有 description
no_desc = [m.slug for m in manifests if not m.description.strip()]
report("模块有简介", no_desc)
