# -*- coding: utf-8 -*-
"""抽查几个典型页面的图片/网盘/代码提取情况（全量抓取前验证）。"""
import re
import urllib.request
from pathlib import Path

BASE = "https://wiki.lckfb.com"

CASES = [
    ("screen", "0-96-color-screen"),
    ("control", "tb6612-motor-drive-module"),
    ("rf", "nrf24l01-2-4-g-control-module"),
    ("sensor", "grayscale-sensor"),
]

for cat, slug in CASES:
    url = f"{BASE}/zh-hans/dmx/module/{cat}/{slug}.html"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception as exc:
        print(f"{slug}: FETCH FAIL {exc}")
        continue
    main = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I)
    seg = main.group(1) if main else html
    imgs = re.findall(r'src="([^"]+\.(?:png|jpg|jpeg|webp|gif))"', seg, flags=re.I)
    data_src = re.findall(r'data-src="([^"]+\.(?:png|jpg|jpeg|webp|gif))"', seg, flags=re.I)
    codes = len(re.findall(r"<pre[^>]*><code", seg, flags=re.I))
    pans = re.findall(r"pan\.baidu\.com/s/[A-Za-z0-9_\-?=]+", seg)
    heads = re.findall(r"<h[12][^>]*>(.*?)</h[12]>", seg, re.S)
    heads = [re.sub(r"<[^>]+>", "", h).strip()[:20] for h in heads[:4]]
    print(f"{slug}: img={len(imgs)} data-src={len(data_src)} codes={codes} pans={len(pans)} heads={heads}")
    for i in imgs[:3]:
        print("   src:", i)
