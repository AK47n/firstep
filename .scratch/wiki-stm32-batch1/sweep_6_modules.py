# -*- coding: utf-8 -*-
"""wiki-stm32-batch1 六件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-modules-batch13/sweep_52_modules.py 的检查面（mspm0 侧
改 stm32 侧）：stm32 条目存在性 / verified / hardware_bound / wordlist
lib_modules 挂接 / kit+source_url（wiki 原页判据）/ 依赖正检（用 delay_*
必须依赖 delay、用 adc_get 必须依赖 adc）；mspm0 条目零改动（保持原状）。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from contest_generator.clex import strip_comments  # noqa: E402

MOD = Path("library/modules")
wl = json.load(open("src/contest_generator/wordlist.json", encoding="utf-8"))
libmods = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

batch_slugs = ["relay", "flame", "human_ir", "microwave_radar", "ttp224", "ws2812"]

print("批次件数:", len(batch_slugs))
bad = 0
for slug in batch_slugs:
    m = json.load(open(MOD / slug / "manifest.json", encoding="utf-8"))
    st = m["platforms"].get("stm32")
    flags = []
    if st is None:
        flags.append("缺stm32条目")
        print(f"{slug:18s} " + "; ".join(flags))
        bad += 1
        continue
    if st.get("verified") is not True:
        flags.append("stm32 verified非true")
    if st.get("hardware_bound") is not False:
        flags.append("stm32 hardware_bound异常")
    if not st.get("kit"):
        flags.append("stm32 缺kit")
    su = st.get("source_url", "")
    if not re.match(r"https://wiki\.lckfb\.com/zh-hans/dkx-stm32f103c8t6/", su):
        flags.append("source_url非地阔星wiki原页")
    deps = m.get("dependencies", [])
    joined = ""
    for f in st.get("files", []):
        p = MOD / slug / f
        if not p.is_file():
            flags.append(f"缺文件{f}")
            continue
        joined += p.read_text(encoding="utf-8", errors="replace")
    code = strip_comments(joined)
    if re.search(r"\bdelay_(us|ms|cycles)\s*\(", code) and "delay" not in deps:
        flags.append("stm32用delay未依赖")
    if re.search(r"\badc_get\s*\(", code) and "adc" not in deps:
        flags.append("stm32用adc_get未依赖")
    if slug not in libmods:
        flags.append("wordlist未挂接")
    if "地阔星移植手册" not in st.get("notes", ""):
        flags.append("notes缺手册路径")
    if "未上板" not in st.get("notes", ""):
        flags.append("notes未注明未上板")
    line = f"{slug:18s} " + ("OK" if not flags else "; ".join(flags))
    print(line)
    if flags:
        bad += 1
print("异常件数:", bad)
