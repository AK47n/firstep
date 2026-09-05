# -*- coding: utf-8 -*-
"""对账：live 页面经真实转换管线（wiki_md）→ 与磁盘产物逐 fence 比对。"""
import re
import sys
import urllib.request

sys.path.insert(0, "src")

from contest_generator.wiki_md import parse_main  # noqa: E402

PAGE = "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/sht30-temp-humi-sensor.html"
SLUG = "sht30"

req = urllib.request.Request(PAGE, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
main = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I).group(1)
md_live, imgs = parse_main(main, SLUG)

fences_live = re.findall(r"^```c\n([\s\S]*?)\n^```", md_live, re.M)
from pathlib import Path
md_file = Path("sources/materials/lckfb-地猛星移植手册/sensor--sht30-temp-humi-sensor.md").read_text(encoding="utf-8")
fences_file = re.findall(r"^```c\n([\s\S]*?)\n^```", md_file, re.M)

print("live fences:", [len(f.splitlines()) for f in fences_live])
print("file fences:", [len(f.splitlines()) for f in fences_file])
for i, (a, b) in enumerate(zip(fences_live, fences_file)):
    same = a.splitlines() == b.splitlines()
    print(f"fence{i}: live={len(a.splitlines())} file={len(b.splitlines())} 一致={same}")
    if not same:
        la, lb = a.splitlines(), b.splitlines()
        for j in range(min(len(la), len(lb))):
            if la[j] != lb[j]:
                print("  首个差异行", j, repr(la[j][:50]), "<->", repr(lb[j][:50]))
                break
