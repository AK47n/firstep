# -*- coding: utf-8 -*-
"""wiki-stm32-batch11 收尾一致性快检（stm32 线 77 页映射全覆盖核对 + 全库
stm32 条目不变量；提交前只读扫描）。

口径（如实）：
- A 类 61 页中 58 页有同 slug stm32 条目；3 页（huidu/xunji/sr04）为
  **mspm0-only 例外**——stm32 侧能力由 pid（gray_track 巡线）/us016（超声
  测距）承接（非同 slug；补录范围外，收尾报告记录）。
- B 9/9 + C 7/7 全部有 stm32 条目（C 类 servo/motor kit/source_url 已补）。
- D 类（无地阔星页面）例外：k230/zigbee_link verified=false（设计——
  纯 Python 副产物/未上板）、coord_detect/k230 hardware_bound=true
  （母版内嵌/副控板——既有设计）。
- oled 词表方案级缺口（显示模块组无 OLED 单色屏方案——models 已含
  OLED；lib_modules 空——收尾报告记录）。
"""
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from contest_generator.clex import strip_comments  # noqa: E402

MOD = REPO / "library" / "modules"
PIN_CFG = (REPO / "library" / "masters" / "stm32" / "pin_config.h").read_text(
    encoding="utf-8", errors="replace"
)
wl = json.load(open(REPO / "src" / "contest_generator" / "wordlist.json", encoding="utf-8"))
libmods: set[str] = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

# A 类 mspm0-only 例外（无同 slug stm32 条目——设计如此）
A_EXCEPT_NO_STM32 = {
    "huidu": "巡线 mspm0-only——stm32 能力由 pid(gray_track) 承接",
    "xunji": "巡线 mspm0-only——stm32 能力由 pid(gray_track) 承接",
    "sr04": "超声波 mspm0-only——stm32 能力由 us016 承接",
}
# D 类（无地阔星页面）设计例外
D_VERIFIED_EXCEPT = {"k230", "zigbee_link"}
D_HW_EXCEPT = {"coord_detect", "k230"}
# kit/source_url 例外（既有内嵌条目——batch10 sweep kit_optional 先例）
KIT_EXCEPT = {
    "oled": "I2C 内嵌母版 ml_oled 既有条目（mspm0 同款既有状；C 类 4 页均归本 slug——键值留空，收尾报告记录）",
}

problems: list[str] = []
counts = {"A": 0, "B": 0, "C": 0}
exceptions: list[str] = []


def manifest(slug):
    path = MOD / slug / "manifest.json"
    if not path.is_file():
        return None
    return json.load(open(path, encoding="utf-8"))


_DKX_MAP = REPO / ".scratch" / "materials-wiki" / "dkx-map.tsv"
if not _DKX_MAP.is_file():
    raise SystemExit(
        f"缺 {_DKX_MAP}（映射轮次工作产物，未随仓库保存）——先重生成：\n"
        "  python .scratch/materials-wiki/dkx_extract.py\n"
        "  python .scratch/materials-wiki/dkx_build_map.py\n"
        "注意：重生成按当前 manifest 分类，A/C 与映射轮次快照不同。"
    )

with open(_DKX_MAP, encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))
assert len(rows) == 77, f"dkx-map.tsv 行数 {len(rows)} ≠ 77"

for row in rows:
    action = row["action"].strip()
    slug = row["lib_slug"].strip()
    if slug.startswith("（新）"):
        slug = slug[3:].strip()
        assert slug, row["page_file"]
    m = manifest(slug)
    if m is None:
        problems.append(f"{row['page_file']}: lib_slug {slug} 无 manifest")
        continue
    counts[action] = counts.get(action, 0) + 1
    st = m.get("platforms", {}).get("stm32")
    if st is None:
        if action == "A" and slug in A_EXCEPT_NO_STM32:
            exceptions.append(f"A/mspm0-only: {row['page_file']} → {slug}"
                              f"（{A_EXCEPT_NO_STM32[slug]}）")
            continue
        problems.append(f"{row['page_file']} → {slug}: 无 stm32 条目")
        continue
    if st.get("verified") is not True:
        problems.append(f"{row['page_file']} → {slug}: stm32 verified != True")
    for rel in st.get("files", []):
        if not (MOD / slug / rel).is_file():
            problems.append(f"{row['page_file']} → {slug}: 文件缺失 {rel}")
    if slug == "oled":
        continue  # 既有内嵌条目 kit/source_url 空（KIT_EXCEPT）
    if not st.get("kit") or not st.get("source_url"):
        problems.append(f"{row['page_file']} → {slug}: kit/source_url 缺失")

# 全库 stm32 条目宏观不变量
for d in sorted(MOD.iterdir()):
    if not d.is_dir():
        continue
    m = json.load(open(d / "manifest.json", encoding="utf-8"))
    st = m.get("platforms", {}).get("stm32")
    if st is None:
        continue
    if st.get("verified") is not True and d.name not in D_VERIFIED_EXCEPT:
        problems.append(f"{d.name}: stm32 verified != True（非 D 类例外）")
    if st.get("hardware_bound") is not False and d.name not in D_HW_EXCEPT:
        problems.append(f"{d.name}: hardware_bound 应 False")
    for rel in st.get("files", []):
        if not (MOD / d.name / rel).is_file():
            problems.append(f"{d.name}: 文件缺失 {rel}")
    for p in st.get("pins", []):
        for macro in p.get("macros", []):
            if not re.search(r"#define\s+" + re.escape(macro) + r"\s+", PIN_CFG):
                problems.append(f"{d.name}.{p['id']}: pin_config.h 未定义 {macro}")

# 头基名跨模块唯一
owners: dict[str, set[str]] = {}
for manifest_dir in MOD.iterdir():
    if not manifest_dir.is_dir():
        continue
    for path in manifest_dir.rglob("*.h"):
        if path.is_file():
            owners.setdefault(path.name.lower(), set()).add(manifest_dir.name)
for name, slugs in owners.items():
    if len(slugs) > 1:
        problems.append(f"头基名跨模块重复: {name} -> {sorted(slugs)}")

# 字体副本 static + 守卫
for slug in ("ili9341", "ili9488", "st7789_para"):
    font = MOD / slug / ("code/%s_font.h" % slug)
    if not font.is_file():
        problems.append(f"{slug}: 字体副本缺失")
        continue
    ft = font.read_text(encoding="utf-8", errors="replace")
    for arr in ("ascii_1206", "ascii_1608", "tfont16"):
        if not re.search(r"static const\s+(?:unsigned\s+char|typFNT_GB16)\s+%s" % arr, ft):
            problems.append(f"{slug}: 字体 {arr} 未 static 化")

for slug, pats in {
    "ili9341": (r"\bFSMC\b", r"\bPOINT_COLOR\b|\bLCD_ShowString\b", r"\bPBout\b|\bPAin\b"),
    "ili9488": (r"\bFSMC\b", r"\bPOINT_COLOR\b|\bLCD_ShowString\b", r"\bPBout\b|\bPAin\b"),
    "st7789_para": (r"\bFSMC\b", r"\bPOINT_COLOR\b|\bLCD_ShowString\b", r"\bPBout\b|\bPAin\b"),
}.items():
    for path in sorted((MOD / slug).glob("code/*_stm32.c")):
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"),
                              keep_preprocessor=True)
        for pat in pats:
            if re.search(pat, text):
                problems.append(f"{slug}/{path.name}: 守卫 {pat!r} 残留")

# 显示族 wordlist 挂接（oled 例外——方案级缺口记录）
for slug in ("lcd", "ili9341", "ili9488", "st7789_para", "max7219", "tp_xpt2046"):
    if slug not in libmods:
        problems.append(f"{slug}: wordlist lib_modules 未挂接")
if "oled" not in libmods:
    exceptions.append("词表缺口: oled（单色 OLED）无方案级 lib_modules 挂接"
                      "（显示模块组 models 已含 OLED；补录留后续）")

print("映射行数:", len(rows), "A/B/C =", {k: counts[k] for k in sorted(counts)})
print("A 类例外（mspm0-only，无同 slug stm32 条目）:", len(A_EXCEPT_NO_STM32))
for e in exceptions:
    print("例外/记录:", e)
if problems:
    print("FAIL (%d)" % len(problems))
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("SWEEP OK（77 页映射：A %d/61 + B 9/9 + C 7/7 = %d/77 同 slug 条目"
      " + %d A 类 mspm0-only 例外；全库 stm32 不变量通过）"
      % (61 - len(A_EXCEPT_NO_STM32), 77 - len(A_EXCEPT_NO_STM32),
         len(A_EXCEPT_NO_STM32)))
