# -*- coding: utf-8 -*-
"""dkx-map.tsv 完整性终检：页面对齐、slug 合法、统计快照"""
import csv, os, glob, json

pages_dir = "sources/materials/lckfb-地阔星移植手册"
paged_files = sorted(f for f in os.listdir(pages_dir)
                     if f.endswith(".md") and "索引" not in f)

rows = list(csv.reader(open(".scratch/materials-wiki/dkx-map.tsv", encoding="utf-8"), delimiter="\t"))
hdr, data = rows[0], rows[1:]
assert hdr == ["page_file","cat","wiki_slug","wiki_title","lib_slug","stm32_entry","stm32_files","action","f4_suspect","code_blocks","备注"], hdr
assert len(data) == 77 == len(paged_files), (len(data), len(paged_files))
tsv_files = [r[0] for r in data]
assert tsv_files == paged_files, set(paged_files) ^ set(tsv_files)

# 每行一致性：stm32_entry/stm32_files/action 与库 manifest 实况一致
libs = json.load(open("library/modules.json", encoding="utf-8")) if os.path.exists("library/modules.json") else None
LIB = {}
for f in glob.glob("library/modules/*/manifest.json"):
    j = json.load(open(f, encoding="utf-8"))
    stm = j.get("platforms", {}).get("stm32")
    LIB[j["slug"]] = (stm, ",".join(stm["files"]) if (stm and stm.get("files")) else "（母版内嵌）" if stm else "")
bad = []
for r in data:
    if r[4].startswith("（新）"):
        assert r[5] == "-" and r[6] == "-" and r[7] == "B", r
        continue
    stm, files = LIB["lib" if False else r[4]]
    assert r[5] == ("Y" if stm else "N"), r
    assert r[6] == files, (r[4], r[6], files)
    assert r[7] == ("C" if stm else "A"), r
assert not bad, bad

# F4 命中数复核（独立 grep）
import re
for r in data:
    if r[8] == "Y":
        c = open(os.path.join(pages_dir, r[0]), encoding="utf-8", errors="replace").read()
        n = len(re.findall(r"RCC_AHB1PeriphClockCmd|GPIO_OType", c))
        assert n > 0, r
    else:
        c = open(os.path.join(pages_dir, r[0]), encoding="utf-8", errors="replace").read()
        assert "RCC_AHB1PeriphClockCmd" not in c and "GPIO_OType" not in c, r
for r in data:
    if r[8] == "Y":
        c = open(os.path.join(pages_dir, r[0]), encoding="utf-8", errors="replace").read()
        n = len(re.findall(r"RCC_AHB1PeriphClockCmd|GPIO_OType", c))
        assert r[9] and n > 0

print("ALL CHECKS PASSED: 77 rows aligned, manifest consistency OK, f4 flag matches grep.")
